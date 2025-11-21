"""
Bol.com Product Scraper - Gets Product URL
Uses undetected-chromedriver to avoid bot detection
"""

import time
import random
import undetected_chromedriver as uc


def get_product_url(url):
    """Get product URL from bol.com (with anti-bot detection)."""
    
    # Initialize browser with undetected-chromedriver (anti-bot detection)
    options = uc.ChromeOptions()
    options.add_argument('--lang=nl-NL')
    options.add_argument('--start-maximized')
    driver = uc.Chrome(options=options, version_main=None)
    
    try:
#    noticed below code is unnecessary and removed
        # # Anti-bot: Human-like behavior - visit homepage first
        # driver.get("https://www.bol.com")
        # time.sleep(random.uniform(3, 5))
        # driver.execute_script("window.scrollTo(0, 300);")
        # time.sleep(random.uniform(1, 2))
        
        # Navigate to product page
        driver.get(url)
        time.sleep(random.uniform(5, 7))
        
        # Anti-bot: Human-like scrolling
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        time.sleep(random.uniform(1, 2))
        
        return url
        
    except Exception:
        return url
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == '__main__':
    url = "https://www.bol.com/nl/nl/p/wispeed-c10-55-max-elektrische-step-blauw-met-krachtige-350w-motor-snelheid-tot-25km-h-bereik-tot-55km/9300000183681124/?cid=1763649766605-3789494265949&bltgh=01bf5f6b-ed3f-4be7-b2b6-d37d931294ca.ProductList_Middle.0.ProductImage"
    
    product_url = get_product_url(url)
    
    print("=" * 60)
    print("PRODUCT URL:")
    print("=" * 60)
    print(product_url)
    print("=" * 60)
