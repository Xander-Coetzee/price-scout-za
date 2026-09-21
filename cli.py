import argparse
import os
import sys
import time
import re
import json
from typing import List, Dict, Any, Union
from scraper.amazon_scraper import (
    batch_fetch_amazon_products,
    extract_all_amazon_urls,
    unwrap_amazon_url,
    fetch_amazon_product,
    parse_price_number,
    extract_asin,
    get_amazon_session,
    is_valid_amazon_product
)
from scraper.takealot_scraper import fetch_takealot_product, search_takealot_product_urls, extract_plid
from exporter.data_exporter import export_all_metadata

def generate_default_filename(queries: Union[List[str], str], ext: str = "json") -> str:
    """Generate clean output filename from one or more search query strings (e.g. ['whey', 'casein'] -> 'whey_casein.json')."""
    if isinstance(queries, str):
        queries = [queries]
    cleaned_parts = []
    for q in queries:
        c = re.sub(r'[^a-zA-Z0-9]+', '_', q.strip().lower()).strip('_')
        if c:
            cleaned_parts.append(c)
    if not cleaned_parts:
        return f"scraped_products.{ext}"
    combined = "_".join(cleaned_parts)
    if len(combined) > 40:
        combined = combined[:40].rstrip('_')
    return f"{combined}.{ext}"

def collect_amazon_urls(query: str, domain: str = "amazon.co.za", max_price: float = None, min_price: float = None, target_count: int = 25, seen_ids: set = None) -> List[str]:
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

def run_multi_store_search(queries: Union[List[str], str], limit: int = 10, source: str = "both", max_price: float = None, min_price: float = None, api_key: str = "", output_file: str = "") -> List[Dict[str, Any]]:
    """Automates multi-store search (Amazon + Takealot) with multi-query support and automatic deduplication."""
    if isinstance(queries, str):
        queries = [queries]
        
    # Clean & normalize query list
    clean_queries = []
    for q in queries:
        for part in q.split(','):
            cleaned = part.strip()
            if cleaned and cleaned not in clean_queries:
                clean_queries.append(cleaned)

    if not output_file:
        output_file = generate_default_filename(clean_queries)

    filter_desc = f" (Max Price: <= {max_price})" if max_price is not None else ""
    query_display = ", ".join(f"'{q}'" for q in clean_queries)
    print(f"[*] Starting multi-store search for {query_display}{filter_desc}...")
    print(f"    Source Mode: {source.upper()} | Target Goal: Save exactly {limit} UNIQUE products into '{output_file}'.\n")

    valid_products = []
    seen_identifiers = set()
    amazon_target = limit
    takealot_target = limit

    if source.lower() == "both":
        amazon_target = limit // 2
        takealot_target = limit - amazon_target
        print(f"    -> 50/50 Split Allocation: {amazon_target} Amazon products + {takealot_target} Takealot products = {limit} Total\n")

    amazon_session = get_amazon_session()

    # 1. Fetch Amazon Listings across queries with balanced per-query allocation
    if source.lower() in ["amazon", "both"] and amazon_target > 0:
        print(f"--- [ FETCHING AMAZON LISTINGS (Target: {amazon_target} Unique Items) ] ---")
        amazon_valid = []
        amazon_candidates_by_query = {}

        # First Pass: Balanced quota per query
        for q_idx, q in enumerate(clean_queries):
            if len(amazon_valid) >= amazon_target:
                break
            
            remaining_queries = len(clean_queries) - q_idx
            remaining_needed = amazon_target - len(amazon_valid)
            query_quota = (remaining_needed + remaining_queries - 1) // remaining_queries
            query_goal = len(amazon_valid) + query_quota

            if len(clean_queries) > 1:
                print(f"\n[Amazon Query {q_idx + 1}/{len(clean_queries)}]: Searching for '{q}' (Allocated Quota: up to {query_quota} items)...")

            needed = max(query_quota * 4, 30)
            amazon_urls = collect_amazon_urls(q, target_count=needed, max_price=max_price, min_price=min_price, seen_ids=seen_identifiers)
            amazon_candidates_by_query[q] = amazon_urls

            for idx, url in enumerate(amazon_urls, 1):
                if len(amazon_valid) >= query_goal or len(amazon_valid) >= amazon_target:
                    break

                asin = extract_asin(url)
                if asin and asin in seen_identifiers:
                    print(f"  [{idx}/{len(amazon_urls)}] [DUPLICATE SKIPPED]: ASIN [{asin}] already in dataset.")
                    sys.stdout.flush()
                    continue

                try:
                    prod = fetch_amazon_product(url, api_key=api_key, session=amazon_session)
                    if not is_valid_amazon_product(prod):
                        print(f"  [{idx}/{len(amazon_urls)}] [SKIPPED]: [{asin}] Invalid / placeholder details.")
                        sys.stdout.flush()
                        continue

                    prod["source"] = "Amazon"
                    prod_asin = prod.get('asin') or asin

                    # Secondary deduplication check on parsed ASIN
                    if prod_asin and prod_asin in seen_identifiers:
                        print(f"  [{idx}/{len(amazon_urls)}] [DUPLICATE SKIPPED]: [{prod_asin}] {prod.get('title')[:36]}... (Already in dataset)")
                        sys.stdout.flush()
                        continue

                    raw_price = prod.get('price', '')
                    num_price = parse_price_number(raw_price)

                    if max_price is not None:
                        if num_price is None or num_price > max_price:
                            print(f"  [{idx}/{len(amazon_urls)}] [SKIPPED]: [{prod_asin}] {prod.get('title')[:36]}... (Price '{raw_price}' > max {max_price})")
                            sys.stdout.flush()
                            continue

                    if min_price is not None:
                        if num_price is None or num_price < min_price:
                            print(f"  [{idx}/{len(amazon_urls)}] [SKIPPED]: [{prod_asin}] {prod.get('title')[:36]}... (Price '{raw_price}' < min {min_price})")
                            sys.stdout.flush()
                            continue

                    if prod_asin:
                        seen_identifiers.add(prod_asin)
                    seen_identifiers.add(url)

                    amazon_valid.append(prod)
                    valid_products.append(prod)
                    count = len(amazon_valid)
                    title_abbr = prod.get('title', 'Product')[:38] + "..." if len(prod.get('title', '')) > 40 else prod.get('title', 'Product')
                    specs_count = len(prod.get('specs', {}))
                    print(f"  [{idx}/{len(amazon_urls)}] [AMAZON {count}/{amazon_target}] Saved: [{prod_asin}] {title_abbr} | Price: {raw_price} | Specs: {specs_count}")
                    sys.stdout.flush()

                    export_all_metadata(valid_products, filepath=output_file)
                except Exception as e:
                    print(f"  [!] Amazon error on {url}: {e}")
                time.sleep(0.2)

        # Second Pass: Deficit Rollover across remaining candidates if goal not reached
        if len(amazon_valid) < amazon_target:
            print(f"\n[*] Rollover pass: Filling remaining Amazon deficit ({amazon_target - len(amazon_valid)} items needed)...")
            for q, urls in amazon_candidates_by_query.items():
                if len(amazon_valid) >= amazon_target:
                    break
                for idx, url in enumerate(urls, 1):
                    if len(amazon_valid) >= amazon_target:
                        break
                    asin = extract_asin(url)
                    if (asin and asin in seen_identifiers) or url in seen_identifiers:
                        continue
                    try:
                        prod = fetch_amazon_product(url, api_key=api_key, session=amazon_session)
                        if not is_valid_amazon_product(prod):
                            continue
                        prod["source"] = "Amazon"
                        prod_asin = prod.get('asin') or asin
                        if prod_asin and prod_asin in seen_identifiers:
                            continue

                        raw_price = prod.get('price', '')
                        num_price = parse_price_number(raw_price)

                        if max_price is not None and (num_price is None or num_price > max_price):
                            continue
                        if min_price is not None and (num_price is None or num_price < min_price):
                            continue

                        if prod_asin:
                            seen_identifiers.add(prod_asin)
                        seen_identifiers.add(url)

                        amazon_valid.append(prod)
                        valid_products.append(prod)
                        count = len(amazon_valid)
                        title_abbr = prod.get('title', 'Product')[:38] + "..." if len(prod.get('title', '')) > 40 else prod.get('title', 'Product')
                        specs_count = len(prod.get('specs', {}))
                        print(f"  [ROLLOVER] [AMAZON {count}/{amazon_target}] Saved: [{prod_asin}] {title_abbr} | Price: {raw_price} | Specs: {specs_count}")
                        sys.stdout.flush()

                        export_all_metadata(valid_products, filepath=output_file)
                    except Exception:
                        pass
                    time.sleep(0.2)

    # 2. Fetch Takealot Listings across queries with balanced per-query allocation
    if source.lower() in ["takealot", "both"] and takealot_target > 0:
        print(f"\n--- [ FETCHING TAKEALOT LISTINGS (Target: {takealot_target} Unique Items) ] ---")
        takealot_valid = []
        takealot_candidates_by_query = {}

        for q_idx, q in enumerate(clean_queries):
            if len(takealot_valid) >= takealot_target:
                break

            remaining_queries = len(clean_queries) - q_idx
            remaining_needed = takealot_target - len(takealot_valid)
            query_quota = (remaining_needed + remaining_queries - 1) // remaining_queries
            query_goal = len(takealot_valid) + query_quota

            if len(clean_queries) > 1:
                print(f"\n[Takealot Query {q_idx + 1}/{len(clean_queries)}]: Searching for '{q}' (Allocated Quota: up to {query_quota} items)...")

            needed = max(query_quota * 4, 30)
            takealot_urls = search_takealot_product_urls(q, target_count=needed)
            takealot_candidates_by_query[q] = takealot_urls

            for idx, url in enumerate(takealot_urls, 1):
                if len(takealot_valid) >= query_goal or len(takealot_valid) >= takealot_target:
                    break

                plid = extract_plid(url)
                if plid and plid in seen_identifiers:
                    print(f"  [{idx}/{len(takealot_urls)}] [DUPLICATE SKIPPED]: PLID [{plid}] already in dataset.")
                    sys.stdout.flush()
                    continue

                try:
                    prod = fetch_takealot_product(url)
                    prod["source"] = "Takealot"
                    prod_plid = prod.get('plid') or plid

                    # Secondary deduplication check on parsed PLID
                    if prod_plid and prod_plid in seen_identifiers:
                        print(f"  [{idx}/{len(takealot_urls)}] [DUPLICATE SKIPPED]: [{prod_plid}] {prod.get('title')[:36]}... (Already in dataset)")
                        sys.stdout.flush()
                        continue

                    raw_price = prod.get('price', '')
                    num_price = parse_price_number(raw_price)

                    if max_price is not None:
                        if num_price is None or num_price > max_price:
                            print(f"  [{idx}/{len(takealot_urls)}] [SKIPPED]: [{prod_plid}] {prod.get('title')[:36]}... (Price '{raw_price}' > max {max_price})")
                            sys.stdout.flush()
                            continue

                    if min_price is not None:
                        if num_price is None or num_price < min_price:
                            print(f"  [{idx}/{len(takealot_urls)}] [SKIPPED]: [{prod_plid}] {prod.get('title')[:36]}... (Price '{raw_price}' < min {min_price})")
                            sys.stdout.flush()
                            continue

                    if prod_plid:
                        seen_identifiers.add(prod_plid)
                    seen_identifiers.add(url)

                    takealot_valid.append(prod)
                    valid_products.append(prod)
                    count = len(takealot_valid)
                    title_abbr = prod.get('title', 'Product')[:38] + "..." if len(prod.get('title', '')) > 40 else prod.get('title', 'Product')
                    specs_count = len(prod.get('specs', {}))
                    print(f"  [{idx}/{len(takealot_urls)}] [TAKEALOT {count}/{takealot_target}] Saved: [{prod_plid}] {title_abbr} | Price: {raw_price} | Specs: {specs_count}")
                    sys.stdout.flush()

                    export_all_metadata(valid_products, filepath=output_file)
                except Exception as e:
                    print(f"  [!] Takealot error on {url}: {e}")
                time.sleep(0.2)

        # Second Pass for Takealot if deficit remains
        if len(takealot_valid) < takealot_target:
            print(f"\n[*] Rollover pass: Filling remaining Takealot deficit ({takealot_target - len(takealot_valid)} items needed)...")
            for q, urls in takealot_candidates_by_query.items():
                if len(takealot_valid) >= takealot_target:
                    break
                for idx, url in enumerate(urls, 1):
                    if len(takealot_valid) >= takealot_target:
                        break
                    plid = extract_plid(url)
                    if (plid and plid in seen_identifiers) or url in seen_identifiers:
                        continue
                    try:
                        prod = fetch_takealot_product(url)
                        prod["source"] = "Takealot"
                        prod_plid = prod.get('plid') or plid
                        if prod_plid and prod_plid in seen_identifiers:
                            continue

                        raw_price = prod.get('price', '')
                        num_price = parse_price_number(raw_price)

                        if max_price is not None and (num_price is None or num_price > max_price):
                            continue
                        if min_price is not None and (num_price is None or num_price < min_price):
                            continue

                        if prod_plid:
                            seen_identifiers.add(prod_plid)
                        seen_identifiers.add(url)

                        takealot_valid.append(prod)
                        valid_products.append(prod)
                        count = len(takealot_valid)
                        title_abbr = prod.get('title', 'Product')[:38] + "..." if len(prod.get('title', '')) > 40 else prod.get('title', 'Product')
                        specs_count = len(prod.get('specs', {}))
                        print(f"  [ROLLOVER] [TAKEALOT {count}/{takealot_target}] Saved: [{prod_plid}] {title_abbr} | Price: {raw_price} | Specs: {specs_count}")
                        sys.stdout.flush()

                        export_all_metadata(valid_products, filepath=output_file)
                    except Exception:
                        pass
                    time.sleep(0.2)

    return valid_products

def main():
    parser = argparse.ArgumentParser(description="Multi-Store Product Metadata Scraper & Auto URL Collector (Amazon & Takealot)")
    parser.add_argument("-u", "--urls", nargs="+", help="Product URLs to scrape (Amazon or Takealot)")
    parser.add_argument("-f", "--file-input", type=str, help="Text file containing list of product URLs (one per line)")
    parser.add_argument("-s", "--search", nargs="+", help="One or more search prompts (e.g. --search 'whey' 'creatine' or --search 'whey, creatine')")
    parser.add_argument("--source", type=str, choices=["amazon", "takealot", "both"], default="both", help="Store provider selection: 'amazon', 'takealot', or 'both' for 50/50 split (default 'both')")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Target number of VALID UNIQUE products to save in output file (default 10)")
    parser.add_argument("-p", "--max-price", type=float, help="Maximum price limit (e.g. --max-price 400 for products under R400 / $400)")
    parser.add_argument("--min-price", type=float, help="Minimum price limit (e.g. --min-price 10)")
    parser.add_argument("-w", "--watch", action="store_true", help="Watch mode: Automatically scrape when urls.txt is updated or downloaded")
    parser.add_argument("-o", "--output", type=str, help="Output file path (defaults to search query name, e.g. whey_creatine.json)")
    parser.add_argument("--api-key", type=str, default="", help="Optional Rainforest API / Scraper API key")

    args = parser.parse_args()

    # Parse search queries if provided
    search_queries = []
    if args.search:
        for item in args.search:
            for part in item.split(','):
                cleaned = part.strip()
                if cleaned and cleaned not in search_queries:
                    search_queries.append(cleaned)

    output_filename = args.output
    if not output_filename:
        if search_queries:
            output_filename = generate_default_filename(search_queries)
        else:
            output_filename = "scraped_products.json"

    # Watch Mode Loop
    if args.watch:
        print("[*] WATCH MODE ACTIVE. Listening for updates to 'urls.txt' or Downloads/urls.txt...")
        last_mtime = 0
        target_file = args.file_input or "urls.txt"
        session = get_amazon_session()
        
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
                    seen_watch_ids = set()
                    for u in lines:
                        asin = extract_asin(u)
                        plid = extract_plid(u)
                        unique_key = asin or plid or u
                        if unique_key in seen_watch_ids:
                            continue
                        seen_watch_ids.add(unique_key)
                        
                        if "takealot.com" in u:
                            products.append(fetch_takealot_product(u))
                        else:
                            products.append(fetch_amazon_product(u, api_key=args.api_key, session=session))
                            
                    out_path = export_all_metadata(products, filepath=output_filename)
                    print(f"[+] Done! Saved {len(products)} unique products to: {os.path.abspath(out_path)}")
            time.sleep(2)

    if search_queries:
        if os.path.exists("urls.txt"):
            os.remove("urls.txt")
            
        products = run_multi_store_search(
            queries=search_queries,
            limit=args.limit,
            source=args.source,
            max_price=args.max_price,
            min_price=args.min_price,
            api_key=args.api_key,
            output_file=output_filename
        )
        
        output_path = export_all_metadata(products, filepath=output_filename)
        print(f"\n[+] SUCCESS! Scraped dataset ({len(products)} unique products) saved to output file:")
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
        print("[!] No search prompt or product URLs provided. Quick Examples:")
        print("    1. Multiple Search Prompts:       python cli.py --search \"whey\" \"creatine\" --limit 20 --max-price 400")
        print("    2. Comma-separated Prompts:       python cli.py --search \"whey, casein, creatine\" --limit 30")
        print("    3. Store-Specific Multi-Search:   python cli.py --search \"hand soap\" \"body wash\" --source takealot --limit 10")
        sys.exit(1)

    # Deduplicate direct input list
    products = []
    seen_direct_ids = set()
    session = get_amazon_session()
    for item in inputs:
        asin = extract_asin(item)
        plid = extract_plid(item)
        unique_key = asin or plid or item
        if unique_key in seen_direct_ids:
            continue
        seen_direct_ids.add(unique_key)
        
        if "takealot.com" in item:
            products.append(fetch_takealot_product(item))
        else:
            products.append(fetch_amazon_product(item, api_key=args.api_key, session=session))

    output_path = export_all_metadata(products, filepath=output_filename)

    print(f"\n[+] SUCCESS! All {len(products)} unique product metadata consolidated into single file:")
    print(f"    -> {os.path.abspath(output_path)}\n")

if __name__ == "__main__":
    main()
