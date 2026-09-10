import re
import time
import json
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from scraper.amazon_scraper import parse_price_number, extract_ingredients

def fetch_takealot_product(target_url: str) -> Dict[str, Any]:
    """Scrapes complete product metadata and technical specs from Takealot.com product page."""
    from playwright.sync_api import sync_playwright
    
    html_content = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            page = context.new_page()
            page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
            try:
                page.wait_for_selector('h1', timeout=12000)
            except Exception:
                pass
            page.wait_for_timeout(1000)
            html_content = page.content()
            browser.close()
    except Exception as e:
        print(f"  [!] Takealot page fetch error: {e}")

    if not html_content:
        return {
            "source": "Takealot",
            "title": "Takealot Product",
            "price": "Price unavailable",
            "url": target_url
        }

    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. Title
    title = ""
    title_el = soup.select_one('h1, h1.product-title, .product-title')
    if title_el:
        title = title_el.get_text(strip=True)

    # 2. Price
    price = "Price unavailable"
    price_el = soup.select_one('span.currency, .buybox-module_price_1wP-n, div[class*="price-module"], span[class*="price"]')
    if price_el:
        price = price_el.get_text(strip=True)
    if not price or "unavailable" in price.lower():
        p_match = re.search(r'R\s*[\d\s,.]+', html_content)
        if p_match:
            price = p_match.group(0).strip()

    # Normalize price format to R XX.XX
    if price and not price.startswith('R'):
        price = f"R {price}"

    # 3. Rating & Reviews
    rating = "N/A"
    rating_el = soup.select_one('.rating-module_rating_1vVl_, div[class*="star-rating"]')
    if rating_el:
        rating = rating_el.get_text(strip=True)

    review_count = "0 reviews"
    reviews_el = soup.select_one('a[href*="#reviews"], span[class*="review-count"]')
    if reviews_el:
        review_count = reviews_el.get_text(strip=True)

    # 4. Product Image
    image_url = ""
    img_el = soup.select_one('img[src*="takealot.com/covers_images/"], img[src*="takealot.com/media/"], img.gallery-image')
    if img_el:
        image_url = img_el.get('src', '')

    # 5. Product Specs & Details Table (parsed from Product Information container)
    specs = {}
    brand = ""
    ingredients = ""
    
    # Takealot key-value pair parsing from Product Information sections
    info_sections = soup.find_all(['div', 'section'])
    for sec in info_sections:
        sec_text = sec.get_text(strip=True, separator='\n')
        if "Product Information" in sec_text and len(sec_text) < 2000:
            lines = [l.strip() for l in sec_text.split('\n') if l.strip()]
            for idx in range(len(lines) - 1):
                k = lines[idx]
                v = lines[idx + 1]
                if k in ["Brand", "Format", "Ingredients", "Volume", "Barcode", "What's in the box", "Warranty", "Gender", "is vegan", "Flavour"]:
                    specs[k] = v
                    if k == "Brand" and not brand:
                        brand = v
                    if k == "Ingredients" and not ingredients:
                        ingredients = v

    if not brand:
        brand_el = soup.select_one('a[href*="/brand/"], .brand-link')
        if brand_el:
            brand = brand_el.get_text(strip=True)

    # 6. Description
    description = ""
    desc_container = soup.find(lambda tag: tag.name in ['div', 'section'] and "Description" in tag.get_text(strip=False))
    for sec in soup.find_all(['div', 'section']):
        text = sec.get_text(strip=True, separator=' ')
        if "Description" in text and len(text) > 30 and len(text) < 3000:
            description = text.replace("Description", "").strip()
            break

    if not ingredients:
        ingredients = extract_ingredients(soup, description, [], specs)

    # Extract PLID / Product ID
    plid = ""
    plid_match = re.search(r'PLID\d+', target_url)
    if plid_match:
        plid = plid_match.group(0)

    return {
        "source": "Takealot",
        "plid": plid,
        "title": title or f"Takealot Product ({plid})",
        "brand": brand or "Takealot",
        "price": price,
        "original_price": "",
        "rating": rating,
        "review_count": review_count,
        "availability": "In stock",
        "image_url": image_url,
        "ingredients": ingredients or "Not specified on main detail page",
        "description": description,
        "directions": "",
        "safety_warning": "",
        "important_information": "",
        "bullet_points": [],
        "specs": specs,
        "url": target_url
    }

def extract_plid(url_or_input: str) -> Optional[str]:
    """Extract PLID identifier from Takealot URL or string (e.g. PLID73601470)."""
    if not url_or_input:
        return None
    match = re.search(r'PLID\d+', url_or_input, re.IGNORECASE)
    return match.group(0).upper() if match else None

def search_takealot_product_urls(query: str, target_count: int = 25, max_price: Optional[float] = None, min_price: Optional[float] = None) -> List[str]:
    """Collects product URLs from Takealot search results across pagination pages."""
    urls = []
    seen = set()
    page_num = 1
    
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            page = context.new_page()

            while len(urls) < target_count and page_num <= 10:
                search_url = f"https://www.takealot.com/all?qsearch={query.replace(' ', '+')}&page={page_num}"
                if page_num == 1:
                    print(f"[*] Navigating Takealot search: {search_url}")
                page.goto(search_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(1500)

                link_elems = page.query_selector_all('a[href*="/PLID"]')
                new_links_count = 0
                for l in link_elems:
                    href = l.get_attribute('href')
                    if href:
                        if href.startswith('/'):
                            href = f"https://www.takealot.com{href}"
                        clean = href.split('?')[0]
                        plid = extract_plid(clean) or clean
                        if plid not in seen:
                            seen.add(plid)
                            urls.append(clean)
                            new_links_count += 1
                            if len(urls) >= target_count:
                                break

                if new_links_count == 0:
                    break
                page_num += 1
                            
            browser.close()
    except Exception as e:
        print(f"[!] Takealot search error: {e}")
        
    return urls

