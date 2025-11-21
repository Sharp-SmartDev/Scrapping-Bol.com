"""
Bol.com Product Scraper
Extracts product information from bol.com category pages.
"""

import os
import logging
import time
import random
import re
from urllib.parse import urljoin, urlparse, parse_qs
from typing import List, Dict, Set
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


class BolScraper:
    """Scraper for extracting product data from bol.com category pages."""
    
    def __init__(self):
        """Initialize the scraper with configuration from environment variables."""
        self.start_page = int(os.getenv('START_PAGE', '1'))
        self.max_pages = int(os.getenv('MAX_PAGES', '3'))
        self.output_path = os.getenv('OUTPUT_PATH', '/app/output/products.xlsx')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.category_urls = self._parse_category_urls()
        
        # Setup logging
        self._setup_logging()
        
        # Track seen products to avoid duplicates
        self.seen_urls: Set[str] = set()
        
        self.logger.info("Scraper initialized with configuration:")
        self.logger.info(f"  START_PAGE: {self.start_page}")
        self.logger.info(f"  MAX_PAGES: {self.max_pages}")
        self.logger.info(f"  OUTPUT_PATH: {self.output_path}")
        self.logger.info(f"  LOG_LEVEL: {self.log_level}")
        self.logger.info(f"  CATEGORY_URLS: {len(self.category_urls)} categories")
    
    def _parse_category_urls(self) -> List[str]:
        """Parse category URLs from environment variable."""
        urls_str = os.getenv('CATEGORY_URLS', '')
        if not urls_str:
            # Default test URL
            return [
                'https://www.bol.com/nl/nl/l/analoge-instantcamera-s/20974/'
            ]
        return [url.strip() for url in urls_str.split(',') if url.strip()]
    
    def _setup_logging(self):
        """Configure logging based on LOG_LEVEL."""
        level = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
    
    def _handle_cookie_consent(self, driver):
        """Handle the cookie consent banner if it appears."""
        try:
            # Wait a bit for the banner to appear
            time.sleep(3)
            
            # Try to find and click the accept button
            accept_selectors = [
                (By.CSS_SELECTOR, 'button[id*="accept"]'),
                (By.CSS_SELECTOR, 'button[class*="accept"]'),
                (By.XPATH, '//button[contains(text(), "Accepteren")]'),
                (By.XPATH, '//button[contains(text(), "Alles accepteren")]'),
                (By.CSS_SELECTOR, '[data-test="consent-modal-accept-all"]')
            ]
            
            for by, selector in accept_selectors:
                try:
                    wait = WebDriverWait(driver, 2)
                    button = wait.until(EC.element_to_be_clickable((by, selector)))
                    if button:
                        button.click()
                        self.logger.info("Cookie consent accepted")
                        time.sleep(1)
                        return
                except (TimeoutException, NoSuchElementException):
                    continue
                    
            self.logger.debug("No cookie consent banner found or already accepted")
        except Exception as e:
            self.logger.debug(f"Cookie consent handling: {e}")
    
    def extract_product_urls_from_page(self, driver, url: str) -> List[str]:
        """Extract all product URLs from a single category page."""
        product_urls = []
        
        try:
            self.logger.info(f"Navigating to: {url}")
            driver.get(url)
            time.sleep(3)
            
            # Handle cookie consent on first page
            if len(self.seen_urls) == 0:
                self._handle_cookie_consent(driver)
            
            # Wait for product listings to load
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/nl/nl/p/"]')))
            
            # Extract product links
            links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/nl/nl/p/"]')
            
            for link in links:
                try:
                    href = link.get_attribute('href')
                    if href:
                        # Construct full URL
                        full_url = urljoin('https://www.bol.com', href)
                        # Clean URL (remove query parameters)
                        clean_url = full_url.split('?')[0]
                        
                        # Only add if not seen before
                        if clean_url not in self.seen_urls:
                            product_urls.append(clean_url)
                            self.seen_urls.add(clean_url)
                except Exception as e:
                    self.logger.debug(f"Error extracting link: {e}")
            
            self.logger.info(f"Found {len(product_urls)} new products on this page")
            
        except TimeoutException:
            self.logger.error(f"Timeout loading page: {url}")
        except Exception as e:
            self.logger.error(f"Error extracting products from {url}: {e}")
        
        return product_urls
    
    def extract_all_product_urls(self, driver, base_category_url: str) -> List[str]:
        """Extract product URLs from all pages in a category."""
        all_product_urls = []
        
        self.logger.info(f"Extracting products from category: {base_category_url}")
        
        for page_num in range(self.start_page, self.start_page + self.max_pages):
            # Construct paginated URL
            separator = '&' if '?' in base_category_url else '?'
            paginated_url = f"{base_category_url}{separator}page={page_num}"
            
            product_urls = self.extract_product_urls_from_page(driver, paginated_url)
            
            if not product_urls:
                self.logger.info(f"No products found on page {page_num}, stopping pagination")
                break
            
            all_product_urls.extend(product_urls)
            
            # Be respectful with rate limiting (random human-like delays)
            time.sleep(random.uniform(2, 4))
        
        self.logger.info(f"Total products extracted from category: {len(all_product_urls)}")
        return all_product_urls
    
    def extract_product_details(self, driver, product_url: str) -> Dict:
        """Extract EAN and price from a product page."""
        details = {
            'product_url': product_url,
            'ean': None,
            'price': None
        }
        
        try:
            self.logger.debug(f"Extracting details from: {product_url}")
            driver.get(product_url)
            time.sleep(2)
            
            # Extract EAN
            try:
                # Look for EAN in various possible locations
                ean_selectors = [
                    (By.XPATH, '//dt[contains(text(), "EAN")]/following-sibling::dd[1]'),
                    (By.XPATH, '//*[@data-test="specifications-table"]//dt[contains(text(), "EAN")]/following-sibling::dd[1]'),
                    (By.XPATH, '//span[contains(text(), "EAN")]/following-sibling::span[1]'),
                    (By.XPATH, '//*[contains(@class, "specs__item")]//dt[contains(text(), "EAN")]/following-sibling::dd[1]')
                ]
                
                for by, selector in ean_selectors:
                    try:
                        wait = WebDriverWait(driver, 2)
                        ean_element = wait.until(EC.presence_of_element_located((by, selector)))
                        if ean_element:
                            ean = ean_element.text.strip()
                            if ean:
                                details['ean'] = ean
                                self.logger.debug(f"Found EAN: {ean}")
                                break
                    except (TimeoutException, NoSuchElementException):
                        continue
                
                # If not found in specifications, try meta tags
                if not details['ean']:
                    try:
                        meta_ean = driver.find_element(By.CSS_SELECTOR, 'meta[property="product:ean"]')
                        if meta_ean:
                            ean = meta_ean.get_attribute('content')
                            if ean:
                                details['ean'] = ean
                                self.logger.debug(f"Found EAN in meta: {ean}")
                    except NoSuchElementException:
                        pass
                
            except Exception as e:
                self.logger.warning(f"Could not extract EAN from {product_url}: {e}")
            
            # Extract price
            try:
                price_selectors = [
                    (By.CSS_SELECTOR, '[data-test="price"]'),
                    (By.CSS_SELECTOR, '.promo-price'),
                    (By.CSS_SELECTOR, '.product-price'),
                    (By.CSS_SELECTOR, 'meta[property="product:price:amount"]')
                ]
                
                for by, selector in price_selectors:
                    try:
                        if selector.startswith('meta'):
                            price_element = driver.find_element(by, selector)
                            if price_element:
                                price = price_element.get_attribute('content')
                        else:
                            wait = WebDriverWait(driver, 2)
                            price_element = wait.until(EC.presence_of_element_located((by, selector)))
                            if price_element:
                                price = price_element.text.strip()
                        
                        if price:
                            # Clean price (remove currency symbols, normalize)
                            price = price.replace('€', '').replace(',', '.').strip()
                            # Extract just the number
                            match = re.search(r'(\d+\.?\d*)', price)
                            if match:
                                details['price'] = float(match.group(1))
                                self.logger.debug(f"Found price: {details['price']}")
                                break
                    except (TimeoutException, NoSuchElementException):
                        continue
                        
            except Exception as e:
                self.logger.warning(f"Could not extract price from {product_url}: {e}")
            
            # Log if any data is missing
            if not details['ean']:
                self.logger.warning(f"Missing EAN for {product_url}")
            if not details['price']:
                self.logger.warning(f"Missing price for {product_url}")
                
        except TimeoutException:
            self.logger.error(f"Timeout loading product page: {product_url}")
        except Exception as e:
            self.logger.error(f"Error extracting details from {product_url}: {e}")
        
        return details
    
    def scrape(self):
        """Main scraping workflow."""
        self.logger.info("Starting scraping process")
        
        all_products = []
        
        # Configure Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
        chrome_options.add_argument('--lang=nl-NL')
        chrome_options.add_argument('--accept-lang=nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7')
        
        # Set headless mode (set to False to see the browser)
        headless_mode = os.getenv('HEADLESS', 'False').lower() == 'true'
        if headless_mode:
            chrome_options.add_argument('--headless')
        
        # Initialize Chrome driver
        # Try to use webdriver-manager if available, otherwise use system ChromeDriver
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            self.logger.info("Using webdriver-manager for ChromeDriver")
        except ImportError:
            # Fallback to system ChromeDriver (must be in PATH)
            driver = webdriver.Chrome(options=chrome_options)
            self.logger.info("Using system ChromeDriver")
        
        try:
            # Hide automation indicators
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Override the plugins and mimeTypes to look like a real browser
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    // Override chrome object
                    window.chrome = {
                        runtime: {}
                    };
                    
                    // Override permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                '''
            })
            
            # Step 1: Extract all product URLs from all categories
            all_product_urls = []
            for category_url in self.category_urls:
                product_urls = self.extract_all_product_urls(driver, category_url)
                all_product_urls.extend(product_urls)
                time.sleep(random.uniform(3, 6))  # Rate limiting between categories
            
            self.logger.info(f"Total unique products to scrape: {len(all_product_urls)}")
            
            # Step 2: Extract details from each product
            for idx, product_url in enumerate(all_product_urls, 1):
                self.logger.info(f"Processing product {idx}/{len(all_product_urls)}")
                details = self.extract_product_details(driver, product_url)
                all_products.append(details)
                
                # Rate limiting (random human-like delays)
                time.sleep(random.uniform(2, 4))
            
            # Step 3: Save to Excel
            self.save_to_excel(all_products)
            
        finally:
            driver.quit()
        
        self.logger.info("Scraping completed successfully")
    
    def save_to_excel(self, products: List[Dict]):
        """Save product data to Excel file."""
        if not products:
            self.logger.warning("No products to save")
            return
        
        try:
            # Create DataFrame
            df = pd.DataFrame(products)
            
            # Reorder columns
            df = df[['product_url', 'ean', 'price']]
            
            # Ensure output directory exists
            output_dir = os.path.dirname(self.output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Save to Excel
            df.to_excel(self.output_path, index=False, engine='openpyxl')
            
            self.logger.info(f"Saved {len(products)} products to {self.output_path}")
            
            # Log statistics
            complete_records = df.dropna().shape[0]
            missing_ean = df['ean'].isna().sum()
            missing_price = df['price'].isna().sum()
            
            self.logger.info(f"Statistics:")
            self.logger.info(f"  Total records: {len(products)}")
            self.logger.info(f"  Complete records: {complete_records}")
            self.logger.info(f"  Missing EAN: {missing_ean}")
            self.logger.info(f"  Missing price: {missing_price}")
            
        except Exception as e:
            self.logger.error(f"Error saving to Excel: {e}")
            raise


def main():
    """Entry point for the scraper."""
    scraper = BolScraper()
    scraper.scrape()


if __name__ == '__main__':
    main()

