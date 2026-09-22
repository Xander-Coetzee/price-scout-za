# Contributing to PriceScout-ZA 🇿🇦
 
Thank you for your interest in contributing! This project is the premier open-source South African e-commerce scraping, price comparison, and metadata extraction toolkit.
 
We welcome all contributions—from adding new store scrapers (Makro, Wootware, Bob Shop, etc.) to improving DOM extractors, optimizing anti-bot resilience, and building new export formats.
 
---
 
## Quick Start: Development Setup
 
### 1. Fork & Clone
```bash
git clone https://github.com/<your-username>/price-scout-za.git
cd price-scout-za
```

### 2. Create Virtual Environment
```bash
python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
pip install pytest flake8
playwright install chromium
```

### 4. Verify Tests Pass
```bash
python -m unittest discover tests
```

---

## 🚀 How to Add a New Store Plugin (in 3 Simple Steps)

Adding support for another South African or international store (e.g. Makro, Wootware, Evetech, Checkers Sixty60, Bob Shop) is designed to be straightforward and modular:

### Step 1: Copy the Template
Copy [`scraper/stores/template.py`](scraper/stores/template.py) to a new file named after the store:
```bash
cp scraper/stores/template.py scraper/stores/makro.py
```

### Step 2: Implement the Scraper Class
Inherit from `BaseStoreScraper` and implement the 3 core methods:
- `search(query, limit, max_price, min_price, seen_ids)`: Query the store and return a list of clean product URLs.
- `fetch_product(url_or_id)`: Extract product title, price, brand, specs, images, and description into the standardized schema.
- `extract_identifier(url_or_input)`: Extract the unique SKU or Product ID from the URL.

```python
from scraper.base_scraper import BaseStoreScraper

class MakroStoreScraper(BaseStoreScraper):
    store_id = "makro"
    store_name = "Makro"
    domains = ["makro.co.za"]

    def search(self, query: str, limit: int = 25, **kwargs):
        # Your search logic here
        ...

    def fetch_product(self, url_or_id: str, **kwargs):
        # Your extraction logic here
        ...

    def extract_identifier(self, url_or_input: str):
        # Your ID extraction logic here
        ...
```

### Step 3: Register in `scraper/stores/__init__.py`
Import your new scraper and add it to `_STORE_REGISTRY`:
```python
from scraper.stores.makro import MakroStoreScraper

_STORE_REGISTRY = {
    AmazonStoreScraper.store_id: AmazonStoreScraper,
    TakealotStoreScraper.store_id: TakealotStoreScraper,
    MakroStoreScraper.store_id: MakroStoreScraper,  # <--- Your new store!
}
```

Add a unit test in `tests/test_scrapers.py` confirming URL resolution and submit your PR!

---

## 🧪 Running Tests

Before submitting a Pull Request, make sure all tests pass:
```bash
python -m unittest discover tests
```

To run lint checks:
```bash
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

---

## 📦 Pull Request Guidelines

1. **Descriptive Branch Names**: Use `feat/add-makro-scraper` or `fix/amazon-price-regex`.
2. **Atomic Commits**: Follow [Conventional Commits](https://www.conventionalcommits.org/) (e.g. `feat(store): add Wootware hardware scraper`, `fix(takealot): update title selector`).
3. **Keep it Free**: Do not introduce mandatory paid API keys or commercial proxies. Fallbacks to free tools (Playwright / requests) must always be preserved.
4. **Clean Code**: Remove unnecessary debug print statements and temporary dump files before committing.

Thank you for helping make South African e-commerce open and accessible! 🚀
