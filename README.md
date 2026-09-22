# PriceScout-ZA: E-Commerce Product Metadata Scraper & Price Comparison Engine

[![CI Test Suite](https://github.com/Xander-Coetzee/price-scout-za/actions/workflows/ci.yml/badge.svg)](https://github.com/Xander-Coetzee/price-scout-za/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

An open-source, modular multi-store product scraper, ingredient analyzer, and price aggregator designed for South African e-commerce. Currently powering unified 360-degree metadata extraction across Amazon South Africa (`amazon.co.za`) and Takealot (`takealot.com`), with an extensible store plugin architecture.

Built with Python, Playwright, BeautifulSoup4, and optional Google Gemini AI.

---

## Supported Stores & Plugin Ecosystem

| Store | Domain | Status | Extracted Data |
| :--- | :--- | :---: | :--- |
| **Amazon South Africa** | `amazon.co.za` | Supported | Title, Price, Original RRP, Star Ratings, Specs, Bullets, Ingredients, High-res Images |
| **Takealot** | `takealot.com` | Supported | Title, Price, Star Ratings, PLID, Reviews, Specs, High-res Images |
| **Makro** | `makro.co.za` | PR Wanted | [Help us build this plugin!](#contributing--adding-new-stores) |
| **Wootware** | `wootware.co.za` | PR Wanted | [Help us build this plugin!](#contributing--adding-new-stores) |
| **Bob Shop** | `bobshop.co.za` | PR Wanted | [Help us build this plugin!](#contributing--adding-new-stores) |
| **Incredible Connection** | `incredible.co.za` | PR Wanted | [Help us build this plugin!](#contributing--adding-new-stores) |

> Want to add another South African or international retailer? Check out the [`BaseStoreScraper`](scraper/base_scraper.py) guide below to add any store in under 15 minutes.

---

## Key Capabilities

- **50/50 Multi-Store Split Allocation**: Automatically divides target product count across stores (e.g. `--limit 50` yields 25 Amazon + 25 Takealot items).
- **Cross-Prompt Deduplication & Deficit Rollover**: Search across 5+ search prompts in one run without duplicate listings; automatically fills query deficits from secondary search candidates.
- **360-Degree Technical Specifications & Ingredients**: Extracts 10-40+ technical specification key-value pairs per item, plus dedicated formulation and ingredient parsing for health/fitness items.
- **ZAR Currency & Precision Price Filtering**: Restrict searches with `--max-price` (e.g. `--max-price 5000`) or `--min-price`. Accurately handles South African price spacing (`R2 799.00`, `R 1,299.99`).
- **Persistent Stealth Session**: Uses high-efficiency desktop HTTP sessions with automated Playwright stealth fallbacks (`--disable-blink-features=AutomationControlled`), achieving 100% CAPTCHA-free results in ~0.2s per product.
- **Gemini AI Analysis**: Optional evaluation with Gemini Flash models, falling back to deterministic price-performance spec matrix scoring.

---

## Quick Start

### 1. Installation
```bash
git clone https://github.com/Xander-Coetzee/price-scout-za.git
cd price-scout-za

python -m venv venv
# Windows:
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### 2. Run Tests
```bash
python -m unittest discover tests
```

---

## CLI Usage Examples

### 1. Multi-Store Search with Price Limit (Amazon + Takealot 50/50 Split)
```bash
python cli.py --search "portable power station" "ups inverter" --source both --limit 10 --max-price 5000
```
> Searches both stores across both prompts, saves 5 Amazon + 5 Takealot items under R5,000, and outputs `portable_power_station_ups_inverter.json`.

### 2. Single-Store Deep Extraction
```bash
# Amazon South Africa only under R400
python cli.py --search "whey protein" --source amazon --limit 20 --max-price 400

# Takealot only under R1000
python cli.py --search "mechanical keyboard" --source takealot --limit 10 --max-price 1000
```

### 3. Direct Product URLs (Auto-Routed to Store Plugin)
```bash
python cli.py -u \
  "https://www.amazon.co.za/dp/B0DLT1WSHY" \
  "https://www.takealot.com/product/PLID96145568" \
  -o comparison.json
```

### 4. Browser Watch Mode (`--watch`)
Install `amazon_url_collector.user.js` in Tampermonkey. Middle-click products as you browse, click **Export urls.txt**, and let the watcher scrape automatically:
```bash
python cli.py --watch -o collected_products.json
```

---

## Python API Usage

You can import and use the store scrapers directly in your Python applications:

```python
from scraper.stores import get_store_scraper, resolve_scraper_for_url

# 1. Fetch by URL (auto-resolves Amazon, Takealot, or any registered plugin)
url = "https://www.amazon.co.za/dp/B0DLT1WSHY"
scraper = resolve_scraper_for_url(url)
product = scraper.fetch_product(url)

print(f"Title: {product['title']}")
print(f"Price: {product['price']}")
print(f"Specs Count: {len(product['specs'])}")

# 2. Search a store directly
takealot = get_store_scraper("takealot")
urls = takealot.search(query="solar generator", limit=10)
```

---

## Contributing & Adding New Stores

Adding a new store takes 3 steps:
1. Copy [`scraper/stores/template.py`](scraper/stores/template.py) to `scraper/stores/<store_id>.py`.
2. Implement `search()`, `fetch_product()`, and `extract_identifier()`.
3. Register your class in `scraper/stores/__init__.py`.

See the [`CONTRIBUTING.md`](CONTRIBUTING.md) guide for complete details and pull request guidelines.

---

## Project Roadmap

- [x] Dual-store support for **Amazon South Africa** (`amazon.co.za`) and **Takealot** (`takealot.com`)
- [x] Balanced 50/50 store allocation with deficit rollover
- [x] Multi-query search with cross-prompt deduplication
- [x] 360-degree technical specifications and ingredients extraction
- [x] Modular `BaseStoreScraper` plugin architecture
- [x] GitHub Actions CI testing matrix (Python 3.10-3.12)
- [ ] Community Store Plugins: Makro, Wootware, Bob Shop, Evetech, Checkers Sixty60
- [ ] Telegram & Discord Webhook Price Alert Bot
- [ ] SQLite / DuckDB Historical Price Tracker

---

## Legal & Ethical Scraping Disclaimer

This tool is designed for educational, research, and personal price-comparison purposes.
- **Public Data Only**: The scraper accesses only publicly available pricing and catalog data accessible to unauthenticated web visitors without bypassing passwords, firewalls, or paywalls.
- **Rate-Limiting**: The scraper implements built-in request intervals to avoid overwhelming retailer servers.
- **Compliance**: Users are responsible for complying with the Terms of Service of individual websites and applicable local regulations. Do not use this tool for high-frequency or disruptive traffic.

---

## License

This project is open source and available under the [MIT License](LICENSE).
