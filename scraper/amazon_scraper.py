import re
import random
import json
import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, unquote
from scraper.package_classifier import classify_package_integrity

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0"
]

def parse_price_number(price_str: str) -> Optional[float]:
    """Extract float price number from string like 'R35.00', 'R2 380,00', 'R1 199.90', or '$1,299.99'."""
    if not price_str or "unavailable" in price_str.lower():
        return None
    import unicodedata
    # 1. Strip formatting characters (directional marks, zero-width spaces, soft hyphens)
    cleaned = "".join(c for c in price_str if unicodedata.category(c) != 'Cf')
    # 2. Normalize all whitespace variants (non-breaking space \xa0, thin space \u202f, etc) to ascii space
    cleaned = re.sub(r'[\s\xa0\u202f\u2009\u200b]+', ' ', cleaned).strip()
    # 3. Join thousand separator spaces e.g. "1 249.00" -> "1249.00"
    cleaned = re.sub(r'(\d+)\s+(\d+)', r'\1\2', cleaned)
    # 4. Join thousand separator commas e.g. "1,249.00" -> "1249.00"
    cleaned = re.sub(r'(\d+),(\d{3})', r'\1\2', cleaned)
    # 5. Normalize decimal comma e.g. "35,99" -> "35.99"
    cleaned = re.sub(r'(\d+),(\d{2})\b', r'\1.\2', cleaned)
    
    matches = re.findall(r'\d+(?:\.\d+)?', cleaned)
    if matches:
        try:
            numbers = [float(m) for m in matches]
            return max(numbers)
        except ValueError:
            pass
    return None

def clean_price_display(price_str: str) -> str:
    """Clean unprintable unicode spaces and normalization glitches from raw scraped price."""
    if not price_str:
        return ""
    import unicodedata
    cleaned = "".join(c for c in price_str if unicodedata.category(c) != 'Cf')
    cleaned = re.sub(r'[\s\xa0\u202f\u2009\u200b]+', ' ', cleaned).strip()
    return cleaned

def unwrap_amazon_url(url: str) -> str:
    """Clean Amazon ad tracking redirects (aax-eu...) to extract the clean direct product URL."""
    if not url:
        return ""
    if "/x/c/" in url and "https://" in url.split("/x/c/")[1]:
        parts = url.split("https://")
        if len(parts) >= 2:
            url = "https://" + parts[-1]
            
    asin = extract_asin(url)
    if asin and ("amazon." in url or "amzn." in url):
        parsed = urlparse(url)
        domain = parsed.netloc or "www.amazon.com"
        return f"https://{domain}/dp/{asin}"
        
    return url.split('?')[0] if '?' in url else url

def extract_all_amazon_urls(text_block: str) -> List[str]:
    """Extract all Amazon URLs or ASINs from a raw block of text or copied browser tabs."""
    if not text_block:
        return []
    
    url_pattern = r'https?://[^\s]*amazon[^\s]+'
    found_urls = re.findall(url_pattern, text_block, re.IGNORECASE)
    cleaned_urls = []
    
    if found_urls:
        for u in found_urls:
            clean = unwrap_amazon_url(u)
            if clean:
                cleaned_urls.append(clean)
        return list(dict.fromkeys(cleaned_urls))

    lines = [line.strip() for line in re.split(r'[\r\n,]+', text_block) if line.strip()]
    for l in lines:
        clean = unwrap_amazon_url(l)
        if clean:
            cleaned_urls.append(clean)
    return list(dict.fromkeys(cleaned_urls))

def extract_asin(url_or_input: str) -> Optional[str]:
    """Extract 10-character Amazon Standard Identification Number (ASIN) from URL or string."""
    if not url_or_input:
        return None
    url_or_input = url_or_input.strip()
    
    if re.match(r'^[A-Z0-9]{10}$', url_or_input, re.IGNORECASE):
        return url_or_input.upper()
        
    patterns = [
        r'/dp/([A-Z0-9]{10})',
        r'/gp/product/([A-Z0-9]{10})',
        r'/ASIN/([A-Z0-9]{10})',
        r'/product/([A-Z0-9]{10})',
        r'asin=([A-Z0-9]{10})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_input, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None

def extract_title_from_url(url: str) -> str:
    """Extract readable product title from Amazon URL slug if HTML parsing fails."""
    try:
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        parts = path.split('/')
        if parts and parts[0] and parts[0] != 'dp' and parts[0] != 'gp':
            slug = unquote(parts[0])
            clean = slug.replace('-', ' ').replace('_', ' ').title()
            if len(clean) > 3:
                return clean
    except Exception:
        pass
    return ""

def detect_currency(url: str, html_text: str = "") -> str:
    """Detect regional currency symbol (R for .za, £ for .uk, € for .de, $ for .com)."""
    if ".co.za" in url or "R " in html_text or "ZAR" in html_text:
        return "R"
    elif ".co.uk" in url:
        return "£"
    elif ".de" in url or ".fr" in url or ".es" in url or ".it" in url:
        return "€"
    elif ".ca" in url:
        return "CA$"
    elif ".com.au" in url:
        return "A$"
    return "$"

def get_random_headers() -> Dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }

_shared_amazon_session: Optional[requests.Session] = None

def get_amazon_session() -> requests.Session:
    """Returns a singleton requests Session configured with realistic desktop headers."""
    global _shared_amazon_session
    if _shared_amazon_session is None:
        _shared_amazon_session = requests.Session()
        _shared_amazon_session.headers.update(get_random_headers())
    return _shared_amazon_session

def extract_ingredients(soup: BeautifulSoup, description: str, bullet_points: List[str], specs: Dict[str, str]) -> str:
    """Aggressively extracts and consolidates ingredients from all DOM nodes, tables, and text sections."""
    found_ingredients = []

    # 1. From Product Specs / Overview Table
    for key in ["Active Ingredients", "Ingredients", "Special Ingredients", "Key Ingredients", "Inactive Ingredients", "Formula", "Composition"]:
        val = specs.get(key)
        if val and len(val) > 2:
            found_ingredients.append(f"{key}: {val}")

    # 2. From Important Information Container (#important-information)
    imp_elem = soup.select_one("#important-information, #importantInformation, div[data-feature-name='importantInformation']")
    if imp_elem:
        imp_text = imp_elem.get_text(strip=True, separator='\n')
        patterns = [
            r'(?:Active\s+)?Ingredients\s*\n+([^\n]+(?:\n+[^\n]+)*?)(?=\n+[A-Z][a-z]+|$)',
            r'Ingredients:?\s*([^\n]+)',
            r'Composition:?\s*([^\n]+)'
        ]
        for p in patterns:
            match = re.search(p, imp_text, re.IGNORECASE)
            if match:
                ing_str = match.group(1).strip()
                if ing_str and ing_str not in found_ingredients and len(ing_str) > 3:
                    found_ingredients.append(ing_str)

    # 3. From A+ Content / Product Description / Bullets
    text_to_search = description + " " + " ".join(bullet_points)
    desc_matches = re.findall(r'(?:Active\s+)?Ingredients:?\s*([^.\n]+(?:\.[^.\n]+){0,2})', text_to_search, re.IGNORECASE)
    for m in desc_matches:
        cleaned = m.strip()
        if cleaned and len(cleaned) > 5 and not any(cleaned in existing for existing in found_ingredients):
            found_ingredients.append(cleaned)

    # Deduplicate while preserving order
    unique = list(dict.fromkeys([i.strip() for i in found_ingredients if i.strip()]))
    return " | ".join(unique) if unique else "Not specified on main detail page"

def is_valid_amazon_product(prod: Dict[str, Any]) -> bool:
    """Checks whether an extracted product is a legitimate detailed scrape rather than an empty fallback placeholder."""
    if not prod:
        return False
    title = prod.get("title", "").strip()
    if not title:
        return False
    if title.startswith("Amazon Product (") and title.endswith(")"):
        return False
    # If title is valid and we have price or specs or bullet points or image
    has_price = prod.get("price") and prod.get("price") != "Price unavailable"
    has_specs = bool(prod.get("specs"))
    has_bullets = bool(prod.get("bullet_points"))
    has_image = bool(prod.get("image_url"))
    
    return bool(has_price or has_specs or has_bullets or has_image)

def parse_amazon_html(html_content: str, source_url: str = "") -> Dict[str, Any]:
    """Extract all product metadata and technical specs from Amazon product HTML."""
    if not html_content:
        asin = extract_asin(source_url) or ""
        return {
            "asin": asin,
            "title": f"Amazon Product ({asin})" if asin else "Amazon Product",
            "brand": "",
            "price": "Price unavailable",
            "original_price": "",
            "rating": "N/A",
            "review_count": "0 reviews",
            "availability": "Unknown",
            "image_url": "",
            "ingredients": "Not specified on main detail page",
            "description": "",
            "directions": "",
            "safety_warning": "",
            "important_information": "",
            "bullet_points": [],
            "specs": {},
            "url": source_url
        }

    soup = BeautifulSoup(html_content, 'lxml') if 'lxml' in html_content else BeautifulSoup(html_content, 'html.parser')
    currency_symbol = detect_currency(source_url, html_content)
    
    # 0. Breadcrumbs / Category hierarchy
    breadcrumbs = []
    crumb_elems = soup.select("#wayfinding-breadcrumbs_feature_div a, .a-breadcrumb a")
    for cr in crumb_elems:
        c_text = cr.get_text(strip=True)
        if c_text and c_text not in breadcrumbs:
            breadcrumbs.append(c_text)

    # 1. Title
    title = ""
    title_elem = soup.select_one("#productTitle, #title span, h1#title, span#productTitle, #productTitle_feature_div span")
    if title_elem:
        title = title_elem.get_text(strip=True)
    if not title:
        h1_elem = soup.select_one("h1")
        if h1_elem and "about this item" not in h1_elem.get_text(strip=True).lower():
            title = h1_elem.get_text(strip=True)
    if not title and soup.title:
        raw_page_title = soup.title.get_text(strip=True)
        # Clean Amazon page title suffixes (e.g. "DaranEner 600W ... : Amazon.co.za: Garden")
        cleaned_page_title = re.split(r'\s*[:|]\s*Amazon\.', raw_page_title, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        if cleaned_page_title and "robot check" not in cleaned_page_title.lower() and "page not found" not in cleaned_page_title.lower():
            title = cleaned_page_title
    if not title:
        title = extract_title_from_url(source_url)
        
    # 2. Price & Original Price
    price = ""
    original_price = ""
    
    price_elem = soup.select_one(".a-price .a-offscreen, #corePriceDisplay_desktop_feature_div .a-offscreen, #corePrice_feature_div .a-offscreen, #priceblock_ourprice, #priceblock_dealprice, .apexPriceToPay .a-offscreen, #price_inside_buybox")
    if price_elem and price_elem.get_text(strip=True):
        price = clean_price_display(price_elem.get_text(strip=True))
    else:
        whole = soup.select_one(".a-price-whole")
        fraction = soup.select_one(".a-price-fraction")
        if whole:
            w_text = clean_price_display(whole.get_text(strip=True)).rstrip('.')
            price = f"{currency_symbol}{w_text}"
            if fraction:
                price += f".{clean_price_display(fraction.get_text(strip=True))}"

    orig_price_elem = soup.select_one(".a-text-price .a-offscreen, span.basisPrice .a-offscreen, #listPrice, .priceBlockStrikePriceString")
    if orig_price_elem:
        original_price = clean_price_display(orig_price_elem.get_text(strip=True))

    # 3. Rating & Review Count
    rating = "N/A"
    rating_elem = soup.select_one("i.a-icon-star span.a-icon-alt, #acrPopover .a-size-base, span[data-hook='rating-out-of-text']")
    if rating_elem:
        rating = rating_elem.get_text(strip=True)
        
    review_count = "0 reviews"
    reviews_elem = soup.select_one("#acrCustomerReviewText, #customer-reviews_feature_div span.a-size-base")
    if reviews_elem:
        review_count = reviews_elem.get_text(strip=True)

    # 4. Product Image
    image_url = ""
    img_elem = soup.select_one("#landingImage, #imgBlkFront, #main-image, #main-image-container img")
    if img_elem:
        image_url = img_elem.get('data-old-hires') or img_elem.get('data-dynamic-image') or img_elem.get('src', '')
        if image_url.startswith('{'):
            try:
                img_dict = json.loads(image_url)
                image_url = list(img_dict.keys())[0]
            except Exception:
                image_url = img_elem.get('src', '')

    # 5. Bullet points / Key features
    bullet_points = []
    bullet_elems = soup.select("#feature-bullets ul li span.a-list-item, #featurebullets_feature_div ul li span, #feature-bullets li")
    for b in bullet_elems:
        text = b.get_text(strip=True)
        if text and not text.startswith("Make sure this fits") and len(text) > 3 and text not in bullet_points:
            bullet_points.append(text)

    # 6. Technical Specifications & Details Table
    specs = {}

    # Variant A: Top Product Overview Table (#productOverview_feature_div)
    overview_rows = soup.select("#productOverview_feature_div tr, div[data-feature-name='productOverview'] tr, #productOverview_feature_div .po-row")
    for row in overview_rows:
        tds = row.find_all(['td', 'th'])
        if len(tds) >= 2:
            k = tds[0].get_text(strip=True).rstrip(":")
            v = tds[1].get_text(strip=True).replace('\u200e', '').replace('\u200f', '')
            if k and v and len(k) < 60 and k not in specs:
                specs[k] = v
        else:
            spans = row.select('.po-break-word')
            if len(spans) >= 2:
                k = spans[0].get_text(strip=True).rstrip(":")
                v = spans[1].get_text(strip=True).replace('\u200e', '').replace('\u200f', '')
                if k and v and len(k) < 60 and k not in specs:
                    specs[k] = v

    # Variant B: Technical Specs & Product Details Tables
    spec_rows = soup.select("#productDetails_db_sections tr, #productDetails_techSpec_section_1 tr, #productDetails_techSpec_section_2 tr, #technicalSpecifications_section_1 tr, .prodDetTable tr, #productDetails_feature_div tr, table.a-keyvalue tr")
    for row in spec_rows:
        th = row.select_one("th, td.prodDetSectionEntry, td.a-color-secondary")
        td = row.select_one("td.prodDetAttrValue, td.a-size-base, td:not(.prodDetSectionEntry):not(.a-color-secondary)")
        if not td:
            all_tds = row.select("td")
            if len(all_tds) >= 2:
                th, td = all_tds[0], all_tds[1]
        if th and td:
            k = th.get_text(strip=True).rstrip(":")
            v = td.get_text(strip=True).replace('\u200e', '').replace('\u200f', '')
            if k and v and k not in specs and len(k) < 60:
                specs[k] = v

    # Variant C: Bullet specs list (#detailBullets_feature_div & #detailBulletsWrapper_feature_div)
    bullet_specs = soup.select("#detailBullets_feature_div li, #detailBulletsWrapper_feature_div li")
    for li in bullet_specs:
        spans = li.select("span.a-list-item > span")
        if len(spans) >= 2:
            k = spans[0].get_text(strip=True).replace(":", "").strip()
            v = spans[1].get_text(strip=True).replace('\u200e', '').replace('\u200f', '')
            if k and v and k not in specs and len(k) < 60:
                specs[k] = v

    # Variant D: A+ Enhanced Brand Content Tables (.aplus-v2, #aplus)
    aplus_tables = soup.select(".aplus-v2 table tr, #aplus table tr, #dpx-aplus-product-description_feature_div table tr")
    for row in aplus_tables:
        cols = row.select("th, td")
        if len(cols) == 2:
            k = cols[0].get_text(strip=True).rstrip(":")
            v = cols[1].get_text(strip=True).replace('\u200e', '').replace('\u200f', '')
            if k and v and len(k) < 50 and len(v) < 200 and k not in specs:
                specs[k] = v

    # 7. Product Description, Directions, Safety Warnings & Important Information
    description = ""
    desc_elem = soup.select_one("#productDescription p, #productDescription span, #productDescription")
    if desc_elem:
        description = desc_elem.get_text(strip=True, separator=' ')
        description = re.sub(r'^(Product description\s*)+', '', description, flags=re.IGNORECASE).strip()

    directions = ""
    safety_warning = ""
    important_information = ""

    imp_elem = soup.select_one("#important-information, #importantInformation, div[data-feature-name='importantInformation']")
    if imp_elem:
        imp_text = imp_elem.get_text(strip=True, separator='\n')
        important_information = imp_text
        
        if "Directions" in imp_text:
            match = re.search(r'Directions\s*\n+([^\n]+(?:\n+[^\n]+)*?)(?=\n+[A-Z][a-z]+|$)', imp_text)
            if match:
                directions = match.group(1).strip()
        if "Safety Warning" in imp_text or "Safety Information" in imp_text:
            match = re.search(r'Safety (?:Warning|Information)\s*\n+([^\n]+(?:\n+[^\n]+)*?)(?=\n+[A-Z][a-z]+|$)', imp_text)
            if match:
                safety_warning = match.group(1).strip()

    if not directions and "Directions" in description:
        d_match = re.search(r'Directions:?\s*([^.]+(?:\.[^.]+){0,2})', description, re.IGNORECASE)
        if d_match:
            directions = d_match.group(1).strip()
            
    if not safety_warning and "Safety" in description:
        s_match = re.search(r'Safety (?:Warning|Information):?\s*([^.]+(?:\.[^.]+){0,2})', description, re.IGNORECASE)
        if s_match:
            safety_warning = s_match.group(1).strip()

    # Comprehensive Ingredients Extraction
    ingredients = extract_ingredients(soup, description, bullet_points, specs)

    # 8. Brand / Manufacturer
    brand = specs.get("Brand") or specs.get("Brand Name") or specs.get("Manufacturer") or ""
    if not brand:
        brand_elem = soup.select_one("#bylineInfo, a#bylineInfo")
        if brand_elem:
            brand = brand_elem.get_text(strip=True).replace("Brand: ", "").replace("Visit the ", "").replace(" Store", "")

    # 9. Availability
    availability = "In Stock"
    avail_elem = soup.select_one("#availability span")
    if avail_elem:
        availability = avail_elem.get_text(strip=True)
        
    asin = extract_asin(source_url) or ""

    # 10. A+ Enhanced Brand / Manufacturer Content
    aplus_content = ""
    aplus_elem = soup.select_one("#aplus_feature_div, .aplus-v2, #dpx-aplus-product-description_feature_div")
    if aplus_elem:
        raw_aplus = aplus_elem.get_text(separator=' ', strip=True)
        raw_aplus = re.sub(r'\s+', ' ', raw_aplus).strip()
        if len(raw_aplus) > 15:
            aplus_content = raw_aplus

    # 11. What's in the Box / Included Components
    whats_in_the_box = []
    box_elems = soup.select("#whatIsInTheBox_feature_div li, #includedComponents_feature_div li, .whats-in-the-box li")
    for be in box_elems:
        btxt = be.get_text(strip=True)
        if btxt and btxt not in whats_in_the_box:
            whats_in_the_box.append(btxt)
    if not whats_in_the_box:
        inc_spec = specs.get("Included Components") or specs.get("Package Contents")
        if inc_spec:
            whats_in_the_box = [s.strip() for s in inc_spec.split(",") if s.strip()]

    product_data = {
        "asin": asin,
        "title": title or (f"Amazon Product ({asin})" if asin else "Amazon Product"),
        "brand": brand,
        "price": price or "Price unavailable",
        "original_price": original_price,
        "rating": rating,
        "review_count": review_count,
        "availability": availability,
        "breadcrumbs": breadcrumbs,
        "image_url": image_url,
        "ingredients": ingredients,
        "description": description,
        "aplus_content": aplus_content,
        "whats_in_the_box": whats_in_the_box,
        "directions": directions,
        "safety_warning": safety_warning,
        "important_information": important_information,
        "bullet_points": bullet_points,
        "specs": specs,
        "url": source_url
    }

    # 12. Package Details & Listing Integrity Analysis
    pkg_analysis = classify_package_integrity(product_data)
    product_data["package_details"] = {
        "package_type": pkg_analysis["package_type"],
        "is_refill_only": pkg_analysis["is_refill_only"],
        "device_included": pkg_analysis["device_included"],
        "requires_base_device": pkg_analysis["requires_base_device"],
        "pack_quantity": pkg_analysis["pack_quantity"],
        "net_volume_or_weight": pkg_analysis["net_volume_or_weight"]
    }
    product_data["listing_integrity_alerts"] = pkg_analysis["listing_integrity_alerts"]

    return product_data

def fetch_amazon_product(url_or_asin: str, api_key: Optional[str] = None, session: Optional[requests.Session] = None) -> Dict[str, Any]:
    """Scrapes Amazon product page metadata using high-speed desktop HTTP session with Playwright stealth fallback."""
    asin = extract_asin(url_or_asin)
    if not asin and not url_or_asin.startswith("http"):
        target_url = f"https://www.amazon.co.za/s?k={requests.utils.quote(url_or_asin)}"
    elif asin and not url_or_asin.startswith("http"):
        target_url = f"https://www.amazon.co.za/dp/{asin}"
    else:
        target_url = url_or_asin

    # Option 1: Rainforest API if user provided an API key
    if api_key:
        try:
            domain = 'amazon.co.za' if '.co.za' in target_url else 'amazon.com'
            params = {
                'api_key': api_key,
                'type': 'product',
                'amazon_domain': domain,
                'asin': asin
            }
            resp = requests.get('https://api.rainforestapi.com/request', params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                prod = data.get('product', {})
                specs_dict = {s.get('name'): s.get('value') for s in prod.get('specifications', []) if s.get('name')}
                
                for attr in prod.get('attributes', []):
                    if attr.get('name') and attr.get('value'):
                        specs_dict[attr.get('name')] = attr.get('value')

                currency_sym = detect_currency(target_url)
                raw_price = prod.get('buybox_winner', {}).get('price', {}).get('raw', '')
                if not raw_price:
                    raw_price = f"{currency_sym}{prod.get('buybox_winner', {}).get('price', {}).get('value', '0.00')}"

                return {
                    "asin": prod.get('asin', asin),
                    "title": prod.get('title', ''),
                    "brand": prod.get('brand', ''),
                    "price": clean_price_display(raw_price),
                    "original_price": clean_price_display(prod.get('buybox_winner', {}).get('rrp', {}).get('raw', '')),
                    "rating": str(prod.get('rating', 'N/A')),
                    "review_count": f"{prod.get('ratings_total', 0)} ratings",
                    "image_url": prod.get('main_image', {}).get('link', ''),
                    "availability": "In Stock" if prod.get('buybox_winner', {}).get('availability', {}).get('raw') else "Unknown",
                    "description": prod.get('description', ''),
                    "directions": str(prod.get('directions', '')),
                    "safety_warning": str(prod.get('safety_warning', '')),
                    "important_information": str(prod.get('important_information', '')),
                    "bullet_points": prod.get('feature_bullets', []),
                    "specs": specs_dict,
                    "url": target_url
                }
        except Exception as e:
            print(f"Rainforest API request failed: {e}")

    # Option 2: High-Speed Persistent HTTP Session (Ultra-Fast & Full Metadata)
    req_session = session or get_amazon_session()
    try:
        resp = req_session.get(target_url, timeout=12)
        if resp.status_code == 200:
            is_blocked = "Robot Check" in resp.text or "api-services-support@amazon.com" in resp.text or "Type the characters you see in this image" in resp.text
            if not is_blocked:
                parsed = parse_amazon_html(resp.text, target_url)
                if is_valid_amazon_product(parsed):
                    return parsed
    except Exception as e:
        pass

    # Option 3: Playwright Stealth Browser with Anti-Bot Automation Flags (Fallback)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US"
            )
            page = context.new_page()
            page.goto(target_url, wait_until="load", timeout=20000)
            
            # Wait for key product container if needed
            try:
                page.wait_for_selector("#productTitle, #title, #dp-container, #centerCol", timeout=5000)
            except Exception:
                pass
                
            html_content = page.content()
            browser.close()

            if html_content and "api-services-support@amazon.com" not in html_content:
                parsed = parse_amazon_html(html_content, target_url)
                if is_valid_amazon_product(parsed):
                    return parsed
    except Exception as pw_err:
        pass

    # Option 4: Parse with fallback metadata if available
    fallback_title = extract_title_from_url(target_url) or (f"Amazon Product ({asin})" if asin else "Amazon Product")
    currency = detect_currency(target_url)
    
    return {
        "asin": asin or "N/A",
        "title": fallback_title,
        "brand": fallback_title.split()[0] if fallback_title else "Generic",
        "price": "Price unavailable",
        "original_price": "",
        "rating": "N/A",
        "review_count": "0 reviews",
        "availability": "Unknown",
        "image_url": "",
        "description": "",
        "directions": "",
        "safety_warning": "",
        "important_information": "",
        "bullet_points": [],
        "specs": {},
        "url": target_url
    }

def batch_fetch_amazon_products(inputs: List[str], api_key: Optional[str] = None, max_price: Optional[float] = None, min_price: Optional[float] = None) -> List[Dict[str, Any]]:
    """Scan multiple Amazon product URLs/ASINs and extract complete metadata with live price filtering."""
    results = []
    
    cleaned_inputs = []
    seen_keys = set()
    for item in inputs:
        if not item or not item.strip():
            continue
        clean_url = unwrap_amazon_url(item.strip())
        asin = extract_asin(clean_url)
        key = asin or clean_url
        if key not in seen_keys:
            seen_keys.add(key)
            cleaned_inputs.append(clean_url)
            
    total = len(cleaned_inputs)
    filter_info = ""
    if max_price is not None and min_price is not None:
        filter_info = f" [Price Filter: {min_price} to {max_price}]"
    elif max_price is not None:
        filter_info = f" [Max Price Filter: <= {max_price}]"
    elif min_price is not None:
        filter_info = f" [Min Price Filter: >= {min_price}]"

    print(f"[*] Extracting metadata for {total} unique Amazon product(s){filter_info}...\n")
    import sys
    session = get_amazon_session()

    for idx, item in enumerate(cleaned_inputs, 1):
        try:
            prod = fetch_amazon_product(item, api_key=api_key, session=session)
            if not is_valid_amazon_product(prod):
                print(f"  [{idx}/{total}] [SKIPPED]: [{prod.get('asin')}] Placeholder / unreadable product details.")
                sys.stdout.flush()
                continue

            raw_price = prod.get('price', '')
            num_price = parse_price_number(raw_price)

            # Price Filter Enforcement
            if max_price is not None:
                if num_price is None or num_price > max_price:
                    print(f"  [{idx}/{total}] [SKIPPED]: [{prod.get('asin')}] {prod.get('title')[:40]}... (Price '{raw_price}' > max {max_price})")
                    sys.stdout.flush()
                    continue

            if min_price is not None:
                if num_price is None or num_price < min_price:
                    print(f"  [{idx}/{total}] [SKIPPED]: [{prod.get('asin')}] {prod.get('title')[:40]}... (Price '{raw_price}' < min {min_price})")
                    sys.stdout.flush()
                    continue

            results.append(prod)
            
            title_abbr = prod.get('title', 'Product')
            if len(title_abbr) > 50:
                title_abbr = title_abbr[:47] + "..."
                
            specs_count = len(prod.get('specs', {}))
            asin = prod.get('asin', 'N/A')
            
            print(f"  [{idx}/{total}] Extracting: [{asin}] {title_abbr} | Price: {raw_price} | Specs: {specs_count} items")
            sys.stdout.flush()
        except Exception as e:
            print(f"  [{idx}/{total}] Failed for {item}: {e}")
            sys.stdout.flush()
            
        time.sleep(0.2)
        
    return results

def collect_amazon_urls(query: str, domain: str = "amazon.co.za", max_price: Optional[float] = None, min_price: Optional[float] = None, target_count: int = 25, seen_ids: Optional[set] = None) -> List[str]:
    """Navigates Amazon search pages and collects unique candidate product links."""
    if seen_ids is None:
        seen_ids = set()

    refinement_param = ""
    if max_price is not None and min_price is not None:
        min_cents = int(min_price * 100)
        max_cents = int(max_price * 100)
        refinement_param = f"&refinements=p_36%3A{min_cents}-{max_cents}"
    elif max_price is not None:
        max_cents = int(max_price * 100)
        refinement_param = f"&refinements=p_36%3A-{max_cents}"
    elif min_price is not None:
        min_cents = int(min_price * 100)
        refinement_param = f"&refinements=p_36%3A{min_cents}-"

    urls = []
    page_num = 1

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )

            while len(urls) < target_count and page_num <= 20:
                search_url = f"https://www.{domain}/s?k={query.replace(' ', '+')}&page={page_num}{refinement_param}"
                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_selector('a[href*="/dp/"]', timeout=8000)

                    link_elems = page.query_selector_all('a[href*="/dp/"], a[href*="/gp/product/"]')
                    new_count = 0
                    for l in link_elems:
                        href = l.get_attribute('href')
                        if href:
                            if href.startswith('/'):
                                href = f"https://www.{domain}{href}"
                            clean = unwrap_amazon_url(href)
                            asin = extract_asin(clean) or clean
                            if clean and asin not in seen_ids and clean not in urls:
                                urls.append(clean)
                                new_count += 1
                                if len(urls) >= target_count:
                                    break

                    if new_count == 0:
                        break
                    page_num += 1
                except Exception:
                    break

            browser.close()
    except Exception as e:
        print(f"[!] Amazon search error: {e}")

    return urls

