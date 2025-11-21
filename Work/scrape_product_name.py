"""
Bol.com Product Scraper
Extracts product URLs from category pages and extracts EAN code and price for each product.
Saves results to Excel file.
"""

import undetected_chromedriver as uc
import re
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin

# Constants
PAGE_LOAD_TIMEOUT = 30  # seconds
WEBDRIVER_WAIT_TIMEOUT = 15  # seconds
RETRY_ATTEMPTS = 2
PAGE_LOAD_DELAY = 1  # seconds
RETRY_DELAY = 2  # seconds
SHOW_MORE_WAIT = 3.0  # seconds
SCROLL_WAIT = 0.5  # seconds (wait after scrolling)
PAGE_ERROR_WAIT = 2  # seconds (wait when page load has errors)

# URL Constants
BOL_BASE_URL = 'https://www.bol.com'
PRODUCT_URL_PATH = '/nl/nl/p/'
CATEGORY_URL_PATH = '/nl/nl/l/'

# Regex Patterns
EAN_PATTERN = r'EAN[:\s\-]*(\d{8,14})'  # Pattern to match EAN codes (8-14 digits)


def extract_all_page_urls_from_pagination(driver):
    """Extract all page URLs from pagination by finding max page number from last li element.
    
    Since pagination uses ellipsis (...) to hide some pages, we find the maximum
    page number from the last <li> element that contains an <a> tag and generate all page URLs manually.
    """
    page_urls = []
    try:
        # Get current page URL to extract base URL
        current_url = driver.current_url
        base_url = current_url.split('?')[0]  # Remove query parameters
        
        # Find pagination div
        pagination_div = driver.find_element(By.CSS_SELECTOR, 'div[data-testid="pagination"]')
        # Find ul element inside pagination
        ul_element = pagination_div.find_element(By.TAG_NAME, 'ul')
        # Find all li elements
        li_elements = ul_element.find_elements(By.TAG_NAME, 'li')
        
        max_page = 1  # Default to page 1
        
        # Find the last li element that contains an <a> tag with href containing ?page=
        # Iterate in reverse to find the maximum page number quickly
        for li in reversed(li_elements):
            try:
                link = li.find_element(By.TAG_NAME, 'a')
                href = link.get_attribute('href')
                if href and '?page=' in href:
                    # Extract page number from URL like "?page=8"
                    page_num_str = href.split('?page=')[1].split('&')[0]
                    max_page = int(page_num_str)
                    break  # Found the last page link, exit loop
            except Exception:
                continue
        
        # Generate URLs for all pages from 1 to max_page
        page_urls.append(base_url)  # Page 1 is the base URL without ?page= parameter
        for page_num in range(2, max_page + 1):
            page_urls.append(f"{base_url}?page={page_num}")
        
    except Exception as e:
        print(f"Error extracting pagination: {e}")
        # Fallback: return at least the current page
        try:
            current_url = driver.current_url
            base_url = current_url.split('?')[0]
            if base_url and base_url not in page_urls:
                page_urls.append(base_url)
        except Exception:
            pass
    
    return page_urls


def get_product_price(driver, wait):
    """Extract price from product page.
    
    Returns:
        float: Price value, or None if extraction fails
    """
    try:
        # Wait for price element with timeout
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'span[data-test="price"]')))
        price_element = driver.find_element(By.CSS_SELECTOR, 'span[data-test="price"]')
        
        # Get main price from first text node
        price_main_raw = driver.execute_script("return arguments[0].childNodes[0].textContent.trim();", price_element)
        price_main = re.sub(r'[^\d]', '', price_main_raw)
        
        if not price_main:
            return None
        
        # Try to get fraction element
        try:
            price_fraction_element = driver.find_element(By.CSS_SELECTOR, 'sup[data-test="price-fraction"]')
            price_fraction = price_fraction_element.text.strip()
            if price_fraction:
                return float(f"{price_main}.{price_fraction}")
        except Exception:
            # No fraction element - add .00
            pass
        
        # Return price with .00 if no fraction found
        return float(f"{price_main}.00")
        
    except Exception:
        # Silently return None - error handling is done at higher level
        return None


def get_product_ean(driver, wait):
    """Extract EAN code from product specifications section.
    
    Args:
        driver: Selenium WebDriver instance
        wait: WebDriverWait instance
    
    Returns:
        EAN code as string, or None if not found
    """
    try:
        # Wait for specifications section to be present
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'section[data-group-name="ProductSpecification"]')))
        
        # Find the specifications section
        spec_section = driver.find_element(By.CSS_SELECTOR, 'section[data-group-name="ProductSpecification"]')
        
        # Scroll to the specifications section to ensure it's visible
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", spec_section)
        time.sleep(SCROLL_WAIT)
        
        # Try to find EAN without clicking show more (in case it's already visible)
        ean = _extract_ean_from_specs(driver, spec_section)
        if ean:
            return ean
        
        # If EAN not found, click "show more" button to reveal hidden content
        try:
            show_more_button = spec_section.find_element(By.CSS_SELECTOR, 'a[data-test="show-more"]')
            # Scroll to button and click using JavaScript to avoid interception
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", show_more_button)
            time.sleep(SCROLL_WAIT)
            driver.execute_script("arguments[0].click();", show_more_button)
            
            # Wait for additional content to load (increased wait time for dynamic content)
            time.sleep(SHOW_MORE_WAIT)
            
            # Refresh the spec_section reference after content loads
            spec_section = driver.find_element(By.CSS_SELECTOR, 'section[data-group-name="ProductSpecification"]')
            
            # Try to find EAN again after clicking show more
            ean = _extract_ean_from_specs(driver, spec_section)
            if ean:
                return ean
        except Exception:
            # Button might not exist, already clicked, or page structure is different
            pass
        
        return None
    except Exception as e:
        print(f"Error in get_product_ean: {e}")
        return None


def _extract_ean_from_specs(driver, spec_section):
    """Helper function to extract EAN from specifications section.
    
    Tries methods in order:
    1. Structured extraction using regular text (fastest, works for most cases)
    2. JavaScript text extraction (for dynamic content when .text fails)
    3. Regex pattern matching in full text (most robust fallback)
    """
    # Method 1: Structured extraction using regular text (fastest)
    try:
        spec_rows = spec_section.find_elements(By.CSS_SELECTOR, 'div.specs__row')
        for row in spec_rows:
            try:
                dt = row.find_element(By.CSS_SELECTOR, 'dt.specs__title')
                dd = row.find_element(By.CSS_SELECTOR, 'dd.specs__value')
                dt_text = dt.text.strip()
                if dt_text and 'EAN' in dt_text.upper():
                    ean = dd.text.strip()
                    if ean:
                        return ean
            except Exception:
                continue
    except Exception:
        pass
    
    # Method 2: JavaScript text extraction (for dynamic content)
    try:
        spec_rows = spec_section.find_elements(By.CSS_SELECTOR, 'div.specs__row')
        for row in spec_rows:
            try:
                dt = row.find_element(By.CSS_SELECTOR, 'dt.specs__title')
                dd = row.find_element(By.CSS_SELECTOR, 'dd.specs__value')
                dt_text = driver.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", dt)
                if dt_text and 'EAN' in dt_text.upper().strip():
                    ean = driver.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", dd)
                    if ean and ean.strip():
                        return ean.strip()
            except Exception:
                continue
    except Exception:
        pass
    
    # Method 3: Regex pattern matching in full text content (robust fallback)
    try:
        spec_section_text = driver.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", spec_section)
        # Pattern to find EAN: followed by numbers (8-14 digits, standard EAN length)
        # Handles variations like "EAN:", "EAN ", "EAN-", etc.
        match = re.search(EAN_PATTERN, spec_section_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    
    return None


def _retry_extraction(extraction_func, driver, wait, max_attempts=RETRY_ATTEMPTS):
    """Helper function to retry extraction with delays.
    
    Args:
        extraction_func: Function to call for extraction (takes driver, wait as args)
        driver: Selenium WebDriver instance
        wait: WebDriverWait instance
        max_attempts: Maximum number of attempts
    
    Returns:
        Result from extraction_func or None if all attempts fail
    """
    for attempt in range(max_attempts):
        result = extraction_func(driver, wait)
        if result:
            return result
        if attempt < max_attempts - 1:
            time.sleep(PAGE_LOAD_DELAY)
    return None


def _navigate_to_page(driver, page_url, delay=PAGE_LOAD_DELAY):
    """Helper function to navigate to a page with error handling.
    
    Args:
        driver: Selenium WebDriver instance (should have page_load_timeout already set)
        page_url: URL to navigate to
        delay: Delay after navigation in seconds
    
    Returns:
        bool: True if navigation succeeded, False otherwise
    """
    try:
        driver.get(page_url)
        time.sleep(delay)
        return True
    except Exception as e:
        print(f"  [WARNING] Page load issue: {e}")
        time.sleep(PAGE_ERROR_WAIT)
        return False


def extract_product_urls(driver, wait, page_url):
    """Extract product URLs from a single page/link.
    
    Args:
        driver: Selenium WebDriver instance
        wait: WebDriverWait instance
        page_url: URL of the page to extract product URLs from
    
    Returns:
        List of product URLs found on the page
    """
    product_urls = []
    
    try:
        driver.get(page_url)
        product_link_selector = f'a[href*="{PRODUCT_URL_PATH}"]'
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, product_link_selector)))
        
        # Extract product URLs
        product_links = driver.find_elements(By.CSS_SELECTOR, product_link_selector)
        
        for link in product_links:
            try:
                href = link.get_attribute('href')
                if href:
                    full_url = urljoin(BOL_BASE_URL, href)
                    clean_url = full_url.split('?')[0]
                    
                    # Only count actual product URLs (not category or other pages)
                    if PRODUCT_URL_PATH in clean_url and CATEGORY_URL_PATH not in clean_url:
                        product_urls.append(clean_url)
            except Exception:
                continue
        
        # Remove duplicates while preserving order (Python 3.7+ dict maintains insertion order)
        return list(dict.fromkeys(product_urls))
        
    except Exception as e:
        print(f"Error extracting product URLs from {page_url}: {e}")
        return []


def extract_product_urls_from_category(category_url, driver, wait, start_page=1, max_pages=2):
    """Extract all product URLs from a category page, handling pagination.
    
    Args:
        category_url: URL of the category page
        driver: Selenium WebDriver instance
        wait: WebDriverWait instance
        start_page: Starting page number (1-indexed, default: 1)
        max_pages: Number of pages to scrape starting from start_page (default: 2 for development, None for all pages)
    
    Returns:
        List of all unique product URLs from specified page range
    """
    all_product_urls = set()
    
    try:
        # Load first page to get all page URLs from pagination
        print(f"Loading category page: {category_url}")
        driver.get(category_url)
        product_link_selector = f'a[href*="{PRODUCT_URL_PATH}"]'
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, product_link_selector)))
        
        # Get all page URLs from pagination
        page_urls = extract_all_page_urls_from_pagination(driver)
        total_pages = len(page_urls)
        print(f"Found {total_pages} page(s) in pagination")
        
        # Validate start_page
        if start_page < 1:
            start_page = 1
        if start_page > total_pages:
            print(f"Warning: start_page ({start_page}) exceeds total pages ({total_pages}). No pages to process.")
            return []
        
        # Calculate end_page based on start_page + max_pages
        if max_pages is None:
            # Scrape all pages from start_page to end
            end_page = total_pages
        else:
            end_page = start_page + max_pages - 1
            end_page = min(end_page, total_pages)  # Cap at total available pages
        
        # Slice page_urls based on start_page and end_page (1-indexed to 0-indexed)
        page_urls_to_process = page_urls[start_page - 1:end_page]
        print(f"Processing pages {start_page} to {end_page} ({len(page_urls_to_process)} page(s))")
        
        # Extract product URLs from each page
        for idx, page_url in enumerate(page_urls_to_process, start=start_page):
            print(f"Page {idx}: {page_url}")
            
            # Extract product URLs from this page (function handles navigation)
            page_product_urls = extract_product_urls(driver, wait, page_url)
            page_products = len(page_product_urls)
            
            # Add to set to avoid duplicates
            for url in page_product_urls:
                all_product_urls.add(url)
            
            print(f"  Found {page_products} products (Total: {len(all_product_urls)})")
        
        return list(all_product_urls)
        
    except Exception as e:
        print(f"Error extracting product URLs: {e}")
        return list(all_product_urls)


def scrape_category_products(category_url, output_file='bol_products.xlsx', start_page=1, max_pages=2):
    """
    Complete scraper: Extract all product URLs from category and get EAN + price for each.
    
    Args:
        category_url: URL of the category page
        output_file: Name of the Excel file to save results
        start_page: Starting page number (1-indexed, default: 1)
        max_pages: Number of pages to scrape starting from start_page (default: 2 for development, None for all pages)
    """
    options = uc.ChromeOptions()
    options.add_argument('--lang=nl-NL')
    options.add_argument('--start-maximized')
    driver = uc.Chrome(options=options, version_main=None)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)  # Set once for all navigations
    wait = WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT)
    
    products_data = []
    
    try:
        print("=" * 60)
        print("PART 1: Extracting Product URLs from Category")
        print(f"Category URL: {category_url}")
        print(f"Start Page: {start_page}, Max Pages: {max_pages}")
        print("=" * 60)
        
        # Part 1: Extract all product URLs from specified page range
        product_urls = extract_product_urls_from_category(category_url, driver, wait, start_page=start_page, max_pages=max_pages)
        print(f"\nTotal product URLs found: {len(product_urls)}\n")
        
        if not product_urls:
            print("No products found. Exiting.")
            return
        
        print("=" * 60)
        print("PART 2: Extracting Product Details (EAN and Price)")
        print("=" * 60)
        
        # Part 2: Extract details for each product
        failed_products = []  # Track failed products for retry
        missing_ean_count = 0
        missing_price_count = 0
        error_count = 0
        # Use dict for O(1) lookup during retry phase
        products_dict = {}
        
        for idx, product_url in enumerate(product_urls, 1):
            print(f"\n[{idx}/{len(product_urls)}] Processing: {product_url}")
            
            try:
                # Load page with timeout handling
                _navigate_to_page(driver, product_url)
                
                # Extract price with retry
                price = _retry_extraction(get_product_price, driver, wait)
                if not price:
                    missing_price_count += 1
                    print(f"  Price: [MISSING]")
                
                # Extract EAN with retry
                ean = _retry_extraction(get_product_ean, driver, wait)
                if not ean:
                    missing_ean_count += 1
                    print(f"  EAN: [MISSING]")
                
                # Mark for retry if any field is missing
                if not price or not ean:
                    failed_products.append(product_url)
                    if not price and not ean:
                        error_count += 1
                
                product_data = {
                    'Product URL': product_url,
                    'EAN': ean if ean else '',
                    'Price': price if price else ''
                }
                products_data.append(product_data)
                products_dict[product_url] = product_data
                
                if price:
                    print(f"  Price: {price}")
                if ean:
                    print(f"  EAN: {ean}")
                
            except Exception as e:
                error_count += 1
                print(f"  [ERROR] Processing product: {e}")
                failed_products.append(product_url)
                product_data = {
                    'Product URL': product_url,
                    'EAN': '',
                    'Price': ''
                }
                products_data.append(product_data)
                products_dict[product_url] = product_data
        
        # Retry failed products once more
        if failed_products:
            print(f"\n{'=' * 60}")
            print(f"Retrying {len(failed_products)} failed products...")
            print(f"{'=' * 60}")
            
            for idx, product_url in enumerate(failed_products, 1):
                print(f"\n[RETRY {idx}/{len(failed_products)}] Processing: {product_url}")
                
                try:
                    # Load page with timeout handling (longer delay for retry)
                    _navigate_to_page(driver, product_url, delay=RETRY_DELAY)
                    
                    # Get product data from dict (O(1) lookup)
                    product = products_dict.get(product_url)
                    if not product:
                        continue
                    
                    # Retry price extraction
                    if not product['Price']:
                        price = _retry_extraction(get_product_price, driver, wait)
                        if price:
                            product['Price'] = price
                            missing_price_count -= 1
                            print(f"  Price: {price} [RETRIEVED]")
                    
                    # Retry EAN extraction
                    if not product['EAN']:
                        ean = _retry_extraction(get_product_ean, driver, wait)
                        if ean:
                            product['EAN'] = ean
                            missing_ean_count -= 1
                            print(f"  EAN: {ean} [RETRIEVED]")
                            
                except Exception as e:
                    print(f"  [ERROR] Retry failed: {e}")
        
        # Print summary statistics
        print(f"\n{'=' * 60}")
        print("EXTRACTION SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total products processed: {len(products_data)}")
        print(f"Products with missing EAN: {missing_ean_count}")
        print(f"Products with missing Price: {missing_price_count}")
        print(f"Products with errors: {error_count}")
        if len(products_data) > 0:
            success_rate = ((len(products_data) - error_count) / len(products_data) * 100)
            print(f"Success rate: {success_rate:.1f}%")
        else:
            print("Success rate: N/A (no products processed)")
        print(f"{'=' * 60}")
        
        # Save to Excel
        print("\n" + "=" * 60)
        print("Saving results to Excel...")
        print("=" * 60)
        
        save_result_to_excel(products_data, output_file)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def save_result_to_excel(products_data, output_file='bol_products.xlsx'):
    """Save products data to Excel file.
    
    Args:
        products_data: List of dictionaries with keys 'Product URL', 'EAN', 'Price'
        output_file: Name of the Excel file to save results
    """
    df = pd.DataFrame(products_data)
    df.to_excel(output_file, index=False)
    print(f"Results saved to: {output_file}")
    print(f"Total products: {len(products_data)}")


def update_missing_ean_codes(excel_file='bol_products.xlsx'):
    """Read Excel file, find URLs with missing EAN codes, test them, and update the file.
    
    Args:
        excel_file: Path to the Excel file to update
    """
    try:
        # Read existing Excel file
        df = pd.read_excel(excel_file)
        print(f"Loaded {len(df)} products from {excel_file}")
        
        # Ensure EAN column is string type to avoid dtype warnings
        df['EAN'] = df['EAN'].astype(str).replace('nan', '').replace('None', '')
        
        # Find rows with missing EAN codes (empty string or NaN)
        missing_ean_mask = (df['EAN'].isna()) | (df['EAN'] == '') | (df['EAN'].astype(str).str.strip() == '')
        missing_ean_df = df[missing_ean_mask].copy()
        
        if len(missing_ean_df) == 0:
            print("No missing EAN codes found. All products have EAN codes.")
            return
        
        print(f"\nFound {len(missing_ean_df)} products with missing EAN codes")
        print("=" * 60)
        
        # Initialize browser
        options = uc.ChromeOptions()
        options.add_argument('--lang=nl-NL')
        options.add_argument('--start-maximized')
        driver = uc.Chrome(options=options, version_main=None)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)  # Set once for all navigations
        wait = WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT)
        
        updated_count = 0
        
        try:
            for idx, row in missing_ean_df.iterrows():
                product_url = row['Product URL']
                print(f"\n[{updated_count + 1}/{len(missing_ean_df)}] Testing: {product_url}")
                
                try:
                    _navigate_to_page(driver, product_url)
                    
                    # Extract EAN with retry
                    ean = _retry_extraction(get_product_ean, driver, wait)
                    
                    if ean:
                        # Update the DataFrame
                        df.at[idx, 'EAN'] = ean
                        updated_count += 1
                        print(f"  [SUCCESS] EAN: {ean}")
                    else:
                        print(f"  [FAILED] Could not extract EAN")
                    
                except Exception as e:
                    print(f"  [ERROR] {e}")
        
        finally:
            try:
                driver.quit()
            except Exception:
                pass
        
        # Save updated DataFrame back to Excel
        if updated_count > 0:
            df.to_excel(excel_file, index=False)
            print(f"\n{'=' * 60}")
            print(f"Updated {updated_count} EAN codes in {excel_file}")
            print(f"{'=' * 60}")
        else:
            print("\nNo EAN codes were updated.")
            
    except FileNotFoundError:
        print(f"Error: Excel file '{excel_file}' not found.")
    except Exception as e:
        print(f"Error updating EAN codes: {e}")


if __name__ == '__main__':
    # Option 1: Update missing EAN codes in existing Excel file
    # update_missing_ean_codes('bol_products.xlsx')
    
    # Option 2: Run full scraper
    category_url = "https://www.bol.com/nl/nl/l/vlekkenreinigers-waterniveau-indicator/68305/"
    scrape_category_products(category_url, output_file='bol_products.xlsx', start_page=1, max_pages=2)
    
