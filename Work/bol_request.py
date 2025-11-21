"""
Python script to scrape bol.com product data
Extracts product URLs, EAN, and price from category pages
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import pandas as pd
from urllib.parse import urljoin
from typing import List, Dict, Set


def get_headers():
    """Get headers for bol.com requests."""
    return {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'max-age=0',
        'priority': 'u=0, i',
        'referer': 'https://www.bol.com/nl/nl/l/analoge-instantcamera-s/20974',
        'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
    }


def get_cookies():
    """Get cookies for bol.com requests."""
    return {
        'BUI': 'bba424c0-0ac6-4867-ab80-52935a1c4a79',
        'XSC': 'wN5JWf9XyzGz2lLkT8oD7ESuKym3GLra',
        'rl_anonymous_id': 'RS_ENC_v3_IjBkZDViZjAzLWI5ZGQtNDQyZC1iYWI5LTNmNGY1OWEwMjE3MyI%3D',
        'rl_page_init_referrer': 'RS_ENC_v3_IiRkaXJlY3Qi',
        'rl_trait': 'RS_ENC_v3_eyJjbGllbnRJZCI6ImJiYTQyNGMwLTBhYzYtNDg2Ny1hYjgwLTUyOTM1YTFjNGE3OSIsInJlY29nbml0aW9uVHlwZSI6ImFub255bW91cyIsInNob3BDb3VudHJ5IjoibmwiLCJzaG9wTGFuZ3VhZ2UiOiJubCJ9',
        'locale': 'NL',
        '_gcl_au': '1.1.626006917.1763587408',
        '_fbp': 'fb.1.1763587410256.483314663823860757',
        '_ga': 'GA1.1.232749993.1763587572',
        'ga_client_id': '232749993.1763587572',
        'sbsd_o': 'CDF4CB04EF4C28C1410D798560536AE8823C45C270A285597AEB66641582DC9D~sQxsIflR6F2yaeGEKCmvNbqhrt+C5fRqxlDnZCrn8sWZEadTZup5uhzNuSRg4PaBU8U7J0jIElFpQ8AZms9Lf64IUitsLOq649MBr911YLYwVT6+shZXY50PXO0uGJ3vn9+0zJDCZw33Sw0ju/ZoX/0jfgEv4T1hlHDDOYV1AF9ahL9QsbAX8+LR/c201l4BNtGhfL0TISKsA9QHHp1uG1FDNCRNuDVPCLd57Ghja+z8=',
        '_abck': 'EAF9313405BA34C33A6C309357A86FF8~-1~YAAQJzsvF26LPpmaAQAA3sZ1nw5uY4s7rZlbHwaO/ByLzWGUjAcKPqzOWg3EAtu2COMp/qjtwzSjndoRCZYkI4GieMmmH+xA3CZd2G6HdAamdAfYxEMqnZom/EUYXk1aP8I3iu1QnrzgZdaIDo3K/WXntYPL+oEIe1qfxrqSXoGPWdXFiHSnW2n9iKDHn1mJYpfS6zfE8f1nGx66aYWm5F1YxjsLmYrRPpL0NV5ykMJuKZp0v8oR/xW2exFQQqplWTik9MonuOcintAQ2kn1D0ei0tsbrgsShd3hXU2HFQQostBoJEuvPaaRbxlYcwbE/RSTnLFk3v0rwBnFz3IggarJJhDWFTGWpNqYG+zepXzLg2S68QcuPMLCBtHIobOIcFfqjxyh5oLJuoK8zHPxkwz+XzjjCijWoWVkrtjV61dXtLYD0XlejL9bRRYhCjb8OjPzA4BN0ZHbcD9PRPJNYQzn7/VtdqseslJC5drb5wEh6fYx9ZLlJS5jjks=~-1~-1~-1~-1~-1',
        'ak_bmsc': '3EF266FB74206BD7B8FFFBD01781CBF3~000000000000000000000000000000~YAAQJzsvF2+LPpmaAQAA3sZ1nx1q9P9iBmDIMw35tuGbjs1SzCxpRvDVDyvR3j868zng6x4/7snkvB7qo9/NAVErh1IfjX7P9AQwUwjCTV+fGntFW1A4OE59Dq+mMWxWhYquCGBd+FvwMuF4/ivWNvWKyUAJFMHuhvt8ld2SV4m9/sfuX5bvclYDVVgtUWDZriFyYgTXAfzlmNl0nLzm1EajKGe9KZQMBlEYqcttQ90Hz1QDVGGE11CXdkwpcF3ebc8hliEyvPsBNmflZ4b7yms1zRnzMBgrbO2Xd543TOgCPT4v2T9d7yBrncwYkJ98GOj6RaajnototGit/M7YB0lgft4DjWtnlzNyVu4amjTbY5/U/3cUSGxPfcAevGvB',
        'bm_lso': 'CDF4CB04EF4C28C1410D798560536AE8823C45C270A285597AEB66641582DC9D~sQxsIflR6F2yaeGEKCmvNbqhrt+C5fRqxlDnZCrn8sWZEadTZup5uhzNuSRg4PaBU8U7J0jIElFpQ8AZms9Lf64IUitsLOq649MBr911YLYwVT6+shZXY50PXO0uGJ3vn9+0zJDCZw33Sw0ju/ZoX/0jfgEv4T1hlHDDOYV1AF9ahL9QsbAX8+LR/c201l4BNtGhfL0TISKsA9QHHp1uG1FDNCRNuDVPCLd57Ghja+z8=^1763611887724',
        'shopping_session_id': '21311d7039cf620c08edff6ece1c4da5890418e8f7acf345048e6d6923cefc53',
        'bltgSessionId': '1749d14e-ba6a-4c9e-a0da-9ada1b49d918',
        'sbsd_c': '4~1~129994650~plyK7/codUGBqAey37b2kyMcjuqSKe7JG+cfNjhWMGtDEpYAshV1cfyCmvIuSjxhNuX0zcZTr6dEghjkh5MEfj00Kj0rGj7iPOMEg+T0v4WfkvBaqyU0PTHzX1smRmnI0JtwZZaZ6tLZv3TEzZjc3TquNDiq/cMS2ASUjzSGSP6qjbNmYa5jNc940GeSRaeulk9SVmNNXm6XBQaOXTk+EOiCllqUj3p1dXveYxHXva7HKRLBfIRNvAxSfe+soWOQcO',
        'XSRF-TOKEN': '98859086-3df9-46ba-aeb8-0e5f950dca7b',
        'bolConsentChoices': 'source#OFC|version#6|int-tran#true|ext-tran#true|int-beh#true|ext-beh#true',
        'sbsd': 'so70xW91dpUY1Yzrg17I06//kVCPNjseHbIhhM9KZlHdqJ6x1Ahi/1LBNaaED20aOr9WQGZCtUVSGbph+JzFFo5q936ceyZP4XGi5GXYqE5WVP8/U+H7hMOcwWkygxXRdHsE5GolcEZ9gpIpSrYi1t19Hui4kqyL8f8M4UsZI8o93+tKkqzD+IrRuz+O8e3YYl6a+B1fl7FK4PdzuP/bShZ2zsA/zxOpKGRin+PFuK7JSGE0uncJhk7yLAHCajivEEoTAAKPGdfIDaV1EBR6KqOEsUu3wrPr6Pv+oOz5JnhRSHLvev5qDbTCaQ1VzEFh638H/9GoPvruO8axI5lFJ6OkxR9AUb6C36vaK61TO/t7TaS+B+xTlu4x/I9Kz6X0klEP1bgEMgLyvVb5+ctF7du/wqmucUMbh85Xjjus1DFI=',
        'bm_sz': 'B6E07AE346982F14AD052E7B307382B5~YAAQJzsvFw+PPpmaAQAATNZ1nx3saKP4ofhxNTkcxAfifJWseThHmrzx0LZ3eErXKltmbZgWMokoh0D2ZXeKTF4wNClzISbJs2GOxX+rJ0WUeAtEIJFRjoQ4Xnojmilif4r0hbuBLgpOKx5lzQUiHKi4v1LcJhD5fjI20KpHYnSm3XMyqIQ59uyyrquS5qiutHrDI3nj0E9m+qjSfjQ4vkAGm9Y8CFF0DvG9CQPQGyLzjnP/WMQax5J2Ic6Pc3G+oz2tKIQVtoH965fU901o++g5vfxhU0jJzSoNrIANqJznkTtwLKEfd87w7SenfD4MYm+VYwOmSx6mUuUFsXL9h+P2AFcwCgBgtWlk3D2zetLMf0thXBHG0/UnDXSpCgnvf4Gbm+zobMmYfAn0h+TGTaIt7O0C~4405559~3160368',
        'language': 'nl-NL',
        'P': '.wspc-deployment-65954ddcf5-2rpd7',
        '__eoi': 'ID=7fe28e95c40e598b:T=1763587409:RT=1763611894:S=AA-AfjYna8RRMt6EHAdbXikwfHjw',
        '_ga_MY1G523SMZ': 'GS2.1.s1763611897$o3$g0$t1763611897$j60$l0$h0',
        '_uetsid': 'fdf91820c58d11f09299296f94a48d57',
        '_uetvid': 'fdf94090c58d11f0912f27f6a9d021ce',
        'ga_session_id': '1763611897',
        'rl_session': 'RS_ENC_v3_eyJpZCI6MTc2MzYxMTg5MDk0OCwiZXhwaXJlc0F0IjoxNzYzNjEzODI3MDY5LCJ0aW1lb3V0IjoxODAwMDAwLCJhdXRvVHJhY2siOnRydWUsInNlc3Npb25TdGFydCI6ZmFsc2V9',
        'bm_sv': 'B811D9807C9F91BE7A9D8E895FDA05B9~YAAQJ05DF75VfXuaAQAAP9Z4nx2FMy0IwRVqoGxRH0I+M4aMJgkHV69KEs3ROLq/2g+LctZwb4w2GjyUd3TI2TZXAjwpvYMTFs6Rt424zSm05sYtDvs3OGn/i/RocIzC4sMkgMlZiYpwk7LBPIu3TMMDW5tGaRGfrwFqh0MU8T/TdJ5vzVWxPC7JpR2nOToCJ0mvAvOmjUbqRnTgET0GB8Nuk3SvZ1BZprdn9x5MPGnVGe9+UXAdpT6Cqtd8/A==~1'
    }


def extract_product_urls(html_content: str, base_url: str = 'https://www.bol.com') -> List[str]:
    """
    Extract product URLs from category page HTML.
    
    Args:
        html_content: HTML content of the category page
        base_url: Base URL for constructing full URLs
        
    Returns:
        List of unique product URLs
    """
    soup = BeautifulSoup(html_content, 'lxml')
    product_urls: Set[str] = set()
    
    # Find all links that contain product paths
    links = soup.find_all('a', href=re.compile(r'/nl/nl/p/'))
    
    for link in links:
        href = link.get('href')
        if href:
            # Construct full URL
            if href.startswith('http'):
                full_url = href
            else:
                full_url = urljoin(base_url, href)
            
            # Clean URL (remove query parameters)
            clean_url = full_url.split('?')[0]
            
            # Only add product URLs (not other links)
            if '/nl/nl/p/' in clean_url:
                product_urls.add(clean_url)
    
    return list(product_urls)


def extract_product_details(html_content: str, product_url: str) -> Dict:
    """
    Extract EAN and price from product page HTML.
    
    Args:
        html_content: HTML content of the product page
        product_url: URL of the product page
        
    Returns:
        Dictionary with product_url, ean, and price
    """
    details = {
        'product_url': product_url,
        'ean': None,
        'price': None
    }
    
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Extract EAN
    # Try multiple selectors
    ean_selectors = [
        ('dt', {'text': re.compile(r'^EAN', re.I)}),  # dt element with EAN text
        ('meta', {'property': 'product:ean'}),
        ('meta', {'name': 'product:ean'}),
    ]
    
    for tag_name, attrs in ean_selectors:
        try:
            if tag_name == 'dt':
                # Find dt with EAN, then get the next dd
                dt = soup.find('dt', string=re.compile(r'^EAN', re.I))
                if dt:
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        ean = dd.get_text(strip=True)
                        if ean:
                            details['ean'] = ean
                            break
            else:
                # Meta tag
                meta = soup.find(tag_name, attrs)
                if meta:
                    ean = meta.get('content')
                    if ean:
                        details['ean'] = ean
                        break
        except Exception:
            continue
    
    # Extract price
    price_selectors = [
        ('meta', {'property': 'product:price:amount'}),
        ('meta', {'property': 'product:price:currency'}),
        ('span', {'class': re.compile(r'price', re.I)}),
        ('div', {'class': re.compile(r'price', re.I)}),
        ('span', {'data-test': 'price'}),
    ]
    
    for tag_name, attrs in price_selectors:
        try:
            if tag_name == 'meta':
                meta = soup.find('meta', {'property': 'product:price:amount'})
                if meta:
                    price_str = meta.get('content')
                    if price_str:
                        try:
                            details['price'] = float(price_str)
                            break
                        except ValueError:
                            pass
            else:
                # Try to find price in text
                elements = soup.find_all(tag_name, attrs)
                for elem in elements:
                    price_text = elem.get_text(strip=True)
                    if price_text:
                        # Extract number from price text (e.g., "€ 29,99" -> 29.99)
                        price_match = re.search(r'(\d+[.,]\d+)', price_text.replace(',', '.'))
                        if price_match:
                            try:
                                details['price'] = float(price_match.group(1))
                                break
                            except ValueError:
                                continue
                if details['price']:
                    break
        except Exception:
            continue
    
    return details


def scrape_category(category_url: str, max_products: int = None) -> List[Dict]:
    """
    Scrape products from a category page.
    
    Args:
        category_url: URL of the category page
        max_products: Maximum number of products to scrape (None for all)
        
    Returns:
        List of product dictionaries with url, ean, and price
    """
    print(f"Fetching category page: {category_url}")
    
    headers = get_headers()
    cookies = get_cookies()
    
    # Update referer to match the category URL
    headers['referer'] = category_url
    
    # Use a session to maintain cookies
    session = requests.Session()
    session.headers.update(headers)
    session.cookies.update(cookies)
    
    # Get category page
    response = session.get(category_url)
    
    print(f"Status Code: {response.status_code}")
    
    # Check if we got blocked
    if response.status_code == 403:
        print("\n⚠️  403 Forbidden - The cookies may have expired or the site is blocking the request.")
        print("Possible solutions:")
        print("1. Get fresh cookies from your browser (use browser dev tools)")
        print("2. The site might be detecting automated requests")
        print("\nResponse preview:")
        print(response.text[:500])
        response.raise_for_status()
    
    if response.status_code != 200:
        print(f"\n⚠️  Unexpected status code: {response.status_code}")
        print("Response preview:")
        print(response.text[:500])
        response.raise_for_status()
    
    print(f"Extracting product URLs...")
    
    # Extract product URLs
    product_urls = extract_product_urls(response.text)
    
    if max_products:
        product_urls = product_urls[:max_products]
    
    print(f"Found {len(product_urls)} products")
    
    # Extract details from each product
    all_products = []
    
    for idx, product_url in enumerate(product_urls, 1):
        print(f"Processing product {idx}/{len(product_urls)}: {product_url}")
        
        try:
            # Update referer for product page
            session.headers['referer'] = category_url
            
            # Get product page
            product_response = session.get(product_url)
            
            if product_response.status_code != 200:
                print(f"  ⚠️  Status {product_response.status_code} for {product_url}")
                if product_response.status_code == 403:
                    print("  Cookies may have expired. Skipping remaining products.")
                    break
            
            product_response.raise_for_status()
            
            # Extract product details
            details = extract_product_details(product_response.text, product_url)
            all_products.append(details)
            
            print(f"  EAN: {details['ean']}, Price: {details['price']}")
            
            # Rate limiting - be respectful
            time.sleep(1)
            
        except Exception as e:
            print(f"  Error processing {product_url}: {e}")
            # Still add the product with None values
            all_products.append({
                'product_url': product_url,
                'ean': None,
                'price': None
            })
    
    return all_products


def save_to_excel(products: List[Dict], output_path: str = 'products.xlsx'):
    """Save product data to Excel file."""
    if not products:
        print("No products to save")
        return
    
    df = pd.DataFrame(products)
    df = df[['product_url', 'ean', 'price']]
    df.to_excel(output_path, index=False, engine='openpyxl')
    
    print(f"\nSaved {len(products)} products to {output_path}")
    
    # Statistics
    complete_records = df.dropna().shape[0]
    missing_ean = df['ean'].isna().sum()
    missing_price = df['price'].isna().sum()
    
    print(f"Statistics:")
    print(f"  Total records: {len(products)}")
    print(f"  Complete records: {complete_records}")
    print(f"  Missing EAN: {missing_ean}")
    print(f"  Missing price: {missing_price}")


def test_connection(category_url: str):
    """Test if we can connect to the category page."""
    print("Testing connection...")
    
    headers = get_headers()
    cookies = get_cookies()
    
    # Try with cookies first
    print("Attempting request with cookies...")
    response = requests.get(category_url, headers=headers, cookies=cookies)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Length: {len(response.text)} bytes")
    
    if response.status_code == 403:
        print("\n❌ 403 Forbidden - Cookies are likely expired!")
        print("\nTo get fresh cookies:")
        print("1. Open your browser and go to: https://www.bol.com/nl/nl/l/analoge-instantcamera-s/20974/")
        print("2. Open Developer Tools (F12)")
        print("3. Go to Network tab")
        print("4. Refresh the page")
        print("5. Click on the first request to the page")
        print("6. Go to 'Headers' section")
        print("7. Scroll down to 'Request Headers' and copy the 'Cookie' header")
        print("8. Update the get_cookies() function with fresh cookie values")
        
        # Try without cookies to see if that's the issue
        print("\nTrying without cookies...")
        response_no_cookies = requests.get(category_url, headers=headers)
        print(f"Status Code (no cookies): {response_no_cookies.status_code}")
        
    elif response.status_code == 200:
        print("✅ Connection successful!")
        print(f"Found {len(extract_product_urls(response.text))} product URLs")
    
    return response


if __name__ == '__main__':
    # Category URL
    category_url = 'https://www.bol.com/nl/nl/l/analoge-instantcamera-s/20974/'
    
    # Test connection first
    test_response = test_connection(category_url)
    
    if test_response.status_code == 200:
        print("\n" + "="*50)
        print("Starting scraping...")
        print("="*50 + "\n")
        
        # Scrape products (limit to 10 for testing, remove max_products parameter for all)
        products = scrape_category(category_url, max_products=10)
        
        # Save to Excel
        save_to_excel(products, 'products.xlsx')
        
        print("\nScraping completed!")
    else:
        print("\n⚠️  Cannot proceed with scraping. Please update cookies first.")
