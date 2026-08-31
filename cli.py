import argparse
import os
import sys
import time
import re
import json
from typing import List, Dict, Any
from scraper.amazon_scraper import batch_fetch_amazon_products, extract_all_amazon_urls, unwrap_amazon_url, fetch_amazon_product, parse_price_number
from scraper.takealot_scraper import fetch_takealot_product, search_takealot_product_urls
from exporter.data_exporter import export_all_metadata

def generate_default_filename(query: str, ext: str = "json") -> str:
    """Generate clean output filename from search query string (e.g. 'whey protein' -> 'whey_protein.json')."""
    clean = re.sub(r'[^a-zA-Z0-9]+', '_', query.strip().lower()).strip('_')
    return f"{clean}.{ext}" if clean else f"scraped_products.{ext}"

def collect_amazon_urls(query: str, domain: str = "amazon.co.za", max_price: float = None, min_price: float = None, target_count: int = 25) -> List[str]:
    """Navigates Amazon search pages and collects unique candidate product links."""
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
    seen = set()
    page_num = 1

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

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
                            if clean and clean not in seen:
                                seen.add(clean)
                                urls.append(clean)
                                new_count += 1

                    if new_count == 0:
                        break
                    page_num += 1
                except Exception:
                    break

            browser.close()
    except Exception as e:
        print(f"[!] Search error: {e}")

    return urls

def run_multi_store_search(query: str, limit: int = 10, source: str = "both", max_price: float = None, min_price: float = None, api_key: str = "", output_file: str = "") -> List[Dict[str, Any]]:
    """Automates multi-store search (Amazon + Takealot) with configurable 50/50 split."""
    if not output_file:
        output_file = generate_default_filename(query)

    filter_desc = f" (Max Price: <= {max_price})" if max_price is not None else ""
    print(f"[*] Starting multi-store search for '{query}'{filter_desc}...")
    print(f"    Source Mode: {source.upper()} | Target Goal: Save exactly {limit} valid products into '{output_file}'.\n")

    valid_products = []
    amazon_target = limit
    takealot_target = limit

    if source.lower() == "both":
        amazon_target = limit // 2
        takealot_target = limit - amazon_target
        print(f"    -> 50/50 Split Allocation: {amazon_target} Amazon products + {takealot_target} Takealot products = {limit} Total\n")

    # 1. Fetch Amazon Listings
    if source.lower() in ["amazon", "both"] and amazon_target > 0:
        print(f"--- [ FETCHING AMAZON LISTINGS (Target: {amazon_target}) ] ---")
        amazon_urls = collect_amazon_urls(query, target_count=max(amazon_target * 3, 30), max_price=max_price, min_price=min_price)
        amazon_valid = []

        for idx, url in enumerate(amazon_urls, 1):
            if len(amazon_valid) >= amazon_target:
                break
            try:
                prod = fetch_amazon_product(url, api_key=api_key)
                prod["source"] = "Amazon"
                raw_price = prod.get('price', '')
                num_price = parse_price_number(raw_price)

                if max_price is not None and num_price is not None and num_price > max_price:
                    print(f"  [{idx}/{len(amazon_urls)}] [SKIPPED]: [{prod.get('asin')}] {prod.get('title')[:36]}... (Price {raw_price} > max {max_price})")
                    sys.stdout.flush()
                    continue

                if min_price is not None and num_price is not None and num_price < min_price:
                    print(f"  [{idx}/{len(amazon_urls)}] [SKIPPED]: [{prod.get('asin')}] {prod.get('title')[:36]}... (Price {raw_price} < min {min_price})")
                    sys.stdout.flush()
                    continue

                amazon_valid.append(prod)
                valid_products.append(prod)
                count = len(amazon_valid)
                title_abbr = prod.get('title', 'Product')[:38] + "..." if len(prod.get('title', '')) > 40 else prod.get('title', 'Product')
                print(f"  [{idx}/{len(amazon_urls)}] [AMAZON {count}/{amazon_target}] Saved: [{prod.get('asin')}] {title_abbr} | Price: {raw_price}")
                sys.stdout.flush()

                export_all_metadata(valid_products, filepath=output_file)
            except Exception as e:
                print(f"  [!] Amazon error on {url}: {e}")
            time.sleep(0.3)

    # 2. Fetch Takealot Listings
    if source.lower() in ["takealot", "both"] and takealot_target > 0:
        print(f"\n--- [ FETCHING TAKEALOT LISTINGS (Target: {takealot_target}) ] ---")
        takealot_urls = search_takealot_product_urls(query, target_count=max(takealot_target * 3, 30))
        takealot_valid = []

        for idx, url in enumerate(takealot_urls, 1):
            if len(takealot_valid) >= takealot_target:
                break
            try:
                prod = fetch_takealot_product(url)
                prod["source"] = "Takealot"
                raw_price = prod.get('price', '')
                num_price = parse_price_number(raw_price)

                if max_price is not None and num_price is not None and num_price > max_price:
                    print(f"  [{idx}/{len(takealot_urls)}] [SKIPPED]: [{prod.get('plid')}] {prod.get('title')[:36]}... (Price {raw_price} > max {max_price})")
                    sys.stdout.flush()
                    continue

                if min_price is not None and num_price is not None and num_price < min_price:
                    print(f"  [{idx}/{len(takealot_urls)}] [SKIPPED]: [{prod.get('plid')}] {prod.get('title')[:36]}... (Price {raw_price} < min {min_price})")
                    sys.stdout.flush()
                    continue

                takealot_valid.append(prod)
                valid_products.append(prod)
                count = len(takealot_valid)
                title_abbr = prod.get('title', 'Product')[:38] + "..." if len(prod.get('title', '')) > 40 else prod.get('title', 'Product')
                print(f"  [{idx}/{len(takealot_urls)}] [TAKEALOT {count}/{takealot_target}] Saved: [{prod.get('plid')}] {title_abbr} | Price: {raw_price}")
                sys.stdout.flush()

                export_all_metadata(valid_products, filepath=output_file)
            except Exception as e:
                print(f"  [!] Takealot error on {url}: {e}")
            time.sleep(0.3)

    return valid_products

def main():
    parser = argparse.ArgumentParser(description="Multi-Store Product Metadata Scraper & Auto URL Collector (Amazon & Takealot)")
    parser.add_argument("-u", "--urls", nargs="+", help="Product URLs to scrape (Amazon or Takealot)")
    parser.add_argument("-f", "--file-input", type=str, help="Text file containing list of product URLs (one per line)")
    parser.add_argument("-s", "--search", type=str, help="Automate search & collect valid product listings (e.g. --search 'whey protein')")
    parser.add_argument("--source", type=str, choices=["amazon", "takealot", "both"], default="both", help="Store provider selection: 'amazon', 'takealot', or 'both' for 50/50 split (default 'both')")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Target number of VALID products to save in output file (default 10)")
    parser.add_argument("-p", "--max-price", type=float, help="Maximum price limit (e.g. --max-price 400 for products under R400 / $400)")
    parser.add_argument("--min-price", type=float, help="Minimum price limit (e.g. --min-price 10)")
    parser.add_argument("-w", "--watch", action="store_true", help="Watch mode: Automatically scrape when urls.txt is updated or downloaded")
    parser.add_argument("-o", "--output", type=str, help="Output file path (defaults to search query name, e.g. whey_protein.json)")
    parser.add_argument("--api-key", type=str, default="", help="Optional Rainforest API / Scraper API key")

    args = parser.parse_args()

    output_filename = args.output
    if not output_filename:
        if args.search:
            output_filename = generate_default_filename(args.search)
        else:
            output_filename = "scraped_products.json"

    # Watch Mode Loop
    if args.watch:
        print("[*] WATCH MODE ACTIVE. Listening for updates to 'urls.txt' or Downloads/urls.txt...")
        last_mtime = 0
        target_file = args.file_input or "urls.txt"
        
        while True:
            check_paths = [target_file, os.path.expanduser("~/Downloads/urls.txt")]
            found_path = None
            for p in check_paths:
                if os.path.exists(p):
                    found_path = p
                    break
                    
            if found_path:
                mtime = os.path.getmtime(found_path)
                if mtime > last_mtime:
                    last_mtime = mtime
                    print(f"\n[!] New URL file detected at '{found_path}'! Starting scraper...")
                    with open(found_path, 'r', encoding='utf-8') as f:
                        lines = [l.strip() for l in f.readlines() if l.strip()]
                    
                    products = []
                    for u in lines:
                        if "takealot.com" in u:
                            products.append(fetch_takealot_product(u))
                        else:
                            products.append(fetch_amazon_product(u, api_key=args.api_key))
                            
                    out_path = export_all_metadata(products, filepath=output_filename)
                    print(f"[+] Done! Saved to: {os.path.abspath(out_path)}")
            time.sleep(2)

    if args.search:
        if os.path.exists("urls.txt"):
            os.remove("urls.txt")
            
        products = run_multi_store_search(
            query=args.search,
            limit=args.limit,
            source=args.source,
            max_price=args.max_price,
            min_price=args.min_price,
            api_key=args.api_key,
            output_file=output_filename
        )
        
        output_path = export_all_metadata(products, filepath=output_filename)
        print(f"\n[+] SUCCESS! Scraped dataset ({len(products)} products) saved to output file:")
        print(f"    -> {os.path.abspath(output_path)}\n")
        sys.exit(0)

    inputs = []

    if args.file_input and os.path.exists(args.file_input):
        with open(args.file_input, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            for l in lines:
                inputs.append(l)

    if args.urls:
        for item in args.urls:
            inputs.append(item)

    if not inputs:
        print("[!] No product URLs provided. Quick Examples:")
        print("    1. 50/50 Amazon + Takealot Search: python cli.py --search \"whey protein\" --limit 20 --max-price 400")
        print("    2. Takealot Only Search:          python cli.py --search \"hand soap\" --source takealot --limit 10")
        print("    3. Amazon Only Search:            python cli.py --search \"hand soap\" --source amazon --limit 10")
        sys.exit(1)

    products = []
    for item in inputs:
        if "takealot.com" in item:
            products.append(fetch_takealot_product(item))
        else:
            products.append(fetch_amazon_product(item, api_key=args.api_key))

    output_path = export_all_metadata(products, filepath=output_filename)

    print(f"\n[+] SUCCESS! All {len(products)} product metadata consolidated into single file:")
    print(f"    -> {os.path.abspath(output_path)}\n")

if __name__ == "__main__":
    main()
