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

    # 2. Price & Original Price
    price = "Price unavailable"
    original_price = ""
    
    price_el = soup.select_one('span.currency, .buybox-module_price_1wP-n, div[class*="price-module"], span[class*="price"]')
    if price_el:
        price = price_el.get_text(strip=True)
    if not price or "unavailable" in price.lower():
        p_match = re.search(r'R\s*[\d\s,.]+', html_content)
        if p_match:
            price = p_match.group(0).strip()

    # Original / List Price (if on sale / discounted)
    orig_price_el = soup.select_one('.buybox-module_list-price_2uD8a, span[class*="list-price"], .crossed-out-price, s, del')
    if orig_price_el:
        original_price = orig_price_el.get_text(strip=True)

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

    # 5. Product Specs & Details (Comprehensive extraction of all key-value pairs)
    specs = {}
    brand = ""
    ingredients = ""
    
    # Extract from Product Information section & any definition tables
    info_sections = soup.find_all(['div', 'section', 'table'])
    for sec in info_sections:
        # Check standard table rows first
        for row in sec.select('tr'):
            cols = row.select('th, td')
            if len(cols) == 2:
                k = cols[0].get_text(strip=True).rstrip(':')
                v = cols[1].get_text(strip=True)
                if k and v and len(k) < 50:
                    specs[k] = v

        # Parse Takealot Product Information structured text
        sec_text = sec.get_text(strip=True, separator='\n')
        if "Product Information" in sec_text and len(sec_text) < 4000:
            raw_lines = [l.strip() for l in sec_text.split('\n') if l.strip()]
            # Known / common Takealot attribute keys
            known_takealot_keys = {
                "Brand", "Format", "Ingredients", "Volume", "Barcode", "What's in the box", "Warranty",
                "Gender", "is vegan", "Flavour", "Flavor", "Serving Size", "Servings per Container",
                "Skin Type", "Scent", "Colour", "Color", "Material", "Model", "Model Number",
                "Packed Quantity", "Unit Count", "Assembled Dimensions", "Weight", "Item Weight",
                "Medicine or Substance Schedule", "Zero Rated VAT", "Allergens", "Dietary Needs",
                "Country of Origin", "Age Group", "Pack Count", "Storage Instructions"
            }
            
            i = 0
            while i < len(raw_lines):
                line = raw_lines[i]
                if line in known_takealot_keys and i + 1 < len(raw_lines):
                    val = raw_lines[i + 1]
                    if val not in known_takealot_keys and len(val) < 400:
                        specs[line] = val
                        if line.lower() in ["brand", "brand name"] and not brand:
                            brand = val
                        if line.lower() in ["ingredients", "active ingredients", "key ingredients"] and not ingredients:
                            ingredients = val
                        i += 2
                        continue
                # Also capture any "Key: Value" lines
                elif ":" in line and len(line) < 150:
                    parts = line.split(":", 1)
                    k_clean, v_clean = parts[0].strip(), parts[1].strip()
                    if k_clean and v_clean and len(k_clean) < 40:
                        specs[k_clean] = v_clean
                i += 1

    if not brand:
        brand_el = soup.select_one('a[href*="/brand/"], .brand-link')
        if brand_el:
            brand = brand_el.get_text(strip=True)

    # 6. Description, Directions, Safety Warnings & Bullet Points
    description = ""
    bullet_points = []
    directions = ""
    safety_warning = ""

    desc_elem = soup.select_one('div[class*="description"], div[class*="product-description"]')
    if desc_elem:
        description = desc_elem.get_text(strip=True, separator=' ')
        description = re.sub(r'^(Description\s*)+', '', description, flags=re.IGNORECASE).strip()
        
        # Extract bullet points from lists in description
        for li in desc_elem.select('li'):
            li_text = li.get_text(strip=True)
            if li_text and len(li_text) > 3 and li_text not in bullet_points:
                bullet_points.append(li_text)

    # If no explicit <li> tags, parse bullet points from "Key Benefits:" / "Features:" lines
    if not bullet_points and description:
        benefit_matches = re.findall(r'(?:[-•*]|\b(?:Benefits?|Features?):\s*)([^\n•*-]+)', description)
        for bm in benefit_matches[:8]:
            clean_b = bm.strip()
            if len(clean_b) > 5 and len(clean_b) < 200:
                bullet_points.append(clean_b)

    # Directions / Suggested Use extraction
    if "Suggested Use" in description or "Directions" in description or "Suggested Directions" in description:
        d_match = re.search(r'(?:Suggested Use|Directions|How to use):?\s*([^.\n]+(?:\.[^.\n]+){0,2})', description, re.IGNORECASE)
        if d_match:
            directions = d_match.group(1).strip()

    # Safety Warning / Disclaimer extraction
    if "Disclaimer" in description or "Warning" in description or "Caution" in description:
        w_match = re.search(r'(?:Disclaimer|Safety Warning|Warnings?|Caution):?\s*([^.\n]+(?:\.[^.\n]+){0,3})', description, re.IGNORECASE)
        if w_match:
            safety_warning = w_match.group(1).strip()

    if not ingredients:
        ingredients = extract_ingredients(soup, description, bullet_points, specs)

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
        "original_price": original_price,
        "rating": rating,
        "review_count": review_count,
        "availability": "In stock",
        "image_url": image_url,
        "ingredients": ingredients or "Not specified on main detail page",
        "description": description,
        "directions": directions,
        "safety_warning": safety_warning,
        "important_information": "",
        "bullet_points": bullet_points,
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

