# 🛍️ E-Commerce Product Metadata Scraper & AI Comparison Tool

An automated, multi-store product metadata scraper, ingredient analyzer, and intelligent comparison engine for **Amazon** (`amazon.co.za`) and **Takealot** (`takealot.com`).

Built with **Python**, **Playwright**, **FastAPI**, and **Google Gemini AI**, this tool automates product link collection, price filtering, comprehensive ingredient parsing, and multi-store product comparisons into clean JSON & Markdown formats.

---

## ✨ Features

- 🛒 **Multi-Store Support**: Simultaneously search & scrape **Amazon** and **Takealot**.
- ⚖️ **50/50 Store Allocation**: Search both stores concurrently with a 50/50 item allocation (e.g. `--limit 50` $\rightarrow$ 25 Amazon + 25 Takealot).
- 🌿 **Comprehensive Ingredients Extraction**: Parses ingredients from overview tables, technical spec grids, `#important-information` tags, bullet points, and A+ descriptions into a dedicated `"ingredients"` field.
- 🏷️ **Price Range Filtering**: Restrict searches with `--max-price` (e.g. `--max-price 400` for items under R400) or `--min-price` filters. Handles complex thousand-separator spaces (`R1 249.00`).
- 🎯 **Target Product Goal Limit**: `--limit N` guarantees N valid matching products in your final output file (automatically auto-paginating across search pages until the goal is met).
- 📁 **Dynamic Query Output Naming**: `--search "whey protein"` automatically names your dataset `whey_protein.json` (or `whey_protein.md`).
- ⚡ **Tampermonkey Browser Integration**: 1-click URL collection via `amazon_url_collector.user.js` with middle-click auto-collection and auto-watch directory scraping (`--watch`).
- 📊 **Web Comparison Dashboard**: Interactive FastAPI web app featuring side-by-side spec grids, price per unit/gram, ingredient lists, and AI recommendations.
- 🤖 **AI Comparison Engine**: Built-in Gemini API integration (`gemini-2.5-flash`) with intelligent spec scoring fallback.

---

## 📁 Repository Architecture

```
Amazon Comparison/
│
├── cli.py                        # Command Line Interface (Multi-store search, filtering, watch mode)
├── app.py                        # FastAPI Web Dashboard Application
├── amazon_url_collector.user.js  # Tampermonkey Userscript for browser middle-click collection
├── requirements.txt              # Project dependencies
├── README.md                     # Project documentation
│
├── scraper/                      # Scraper Engine Modules
│   ├── amazon_scraper.py         # Amazon stealth scraper, ingredient parser & price evaluator
│   └── takealot_scraper.py       # Takealot React DOM scraper, specs & info extractor
│
├── exporter/                     # Dataset Exporting Modules
│   └── data_exporter.py          # Formatter for JSON datasets & Markdown spec documents
│
├── ai/                           # AI Analysis Engine
│   └── comparison_engine.py      # Gemini AI prompt engine & spec scoring matrix fallback
│
└── static/                       # Frontend Web Dashboard Assets
    ├── index.html                # Web app single-page UI
    ├── main.js                   # Client-side UI logic & API handler
    └── styles.css                # Custom styling & responsive layouts
```

---

## ⚙️ Installation

### 1. Prerequisites
- **Python 3.9+** installed on your system.
- **Git** installed.

### 2. Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/amazon-takealot-product-scraper.git
cd amazon-takealot-product-scraper
```

### 3. Install Dependencies & Playwright Browsers
```bash
pip install -r requirements.txt
playwright install chromium
```

---

## 🚀 CLI Usage Guide

### 1. Multi-Store Search with 50/50 Split (Amazon + Takealot)
Search both stores for items under a price threshold and save valid matching listings:
```bash
python cli.py --search "whey protein" --limit 20 --max-price 400
```
> *Outputs:* `whey_protein.json` containing 10 Amazon listings + 10 Takealot listings under R400.

### 2. Store-Specific Searching (`--source`)
Search only **Takealot** or only **Amazon**:
```bash
# Takealot only search under R50
python cli.py --search "hand soap" --source takealot --limit 15 --max-price 50

# Amazon only search under R100
python cli.py --search "hand soap" --source amazon --limit 15 --max-price 100
```

### 3. Scrape Product URLs directly
Pass specific product URLs via CLI:
```bash
python cli.py -u https://www.amazon.co.za/dp/B0FZTYJ7F6 https://www.takealot.com/usn-hydrotech-whey-900g-vanilla-cookie-dough/PLID73601470 -o my_scraped_items.json
```

### 4. Watch Mode with Tampermonkey Browser Userscript (`--watch`)
Install `amazon_url_collector.user.js` in Tampermonkey (Chrome/Firefox/Edge). Middle-click products as you browse, click **Export urls.txt**, and run:
```bash
python cli.py --watch -o my_collected_products.json
```
> The script automatically detects new `urls.txt` downloads and instantly extracts all product metadata.

---

## 🌐 Web Dashboard UI

Launch the interactive FastAPI Web Dashboard:
```bash
python app.py
```
Or with Uvicorn:
```bash
uvicorn app:app --reload --port 8000
```
Open **`http://localhost:8000`** in your browser to paste URLs, compare products side-by-side, inspect ingredients, and generate AI recommendations.

---

## 🤖 Gemini AI Setup (Optional)

To enable live Gemini AI product recommendations:
```bash
export GEMINI_API_KEY="your-gemini-api-key"   # Linux/macOS
$env:GEMINI_API_KEY="your-gemini-api-key"     # PowerShell
```
*Note: If no API key is provided, the tool automatically uses a built-in deterministic specification and price-performance scoring engine.*

---

## 📄 License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.
