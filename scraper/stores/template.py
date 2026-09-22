"""
COMMUNITY STORE SCRAPER TEMPLATE
--------------------------------
Want to add support for another South African or international store?
(e.g., Makro, Wootware, Bob Shop, Evetech, Woolworths, Checkers)

Follow these 3 easy steps:
1. Copy this template to `scraper/stores/<store_id>.py` (e.g. `scraper/stores/makro.py`)
2. Implement the 3 required methods below (`search`, `fetch_product`, and `extract_identifier`)
3. Register your class in `scraper/stores/__init__.py` and open a Pull Request!
"""

from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from scraper.base_scraper import BaseStoreScraper

class ExampleStoreScraper(BaseStoreScraper):
    """
    Store scraper plugin for [Store Name].
    """
    store_id = "example"                 # Unique CLI identifier (e.g. 'makro', 'wootware')
    store_name = "Example Store"         # User-facing store name (e.g. 'Makro South Africa')
    domains = ["example.co.za"]          # Domains used to match direct product URLs

    def search(
        self,
        query: str,
        limit: int = 25,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        seen_ids: Optional[set] = None
    ) -> List[str]:
        """
        Search the store's catalogue and return up to `limit` clean product URLs.
        """
        candidate_urls: List[str] = []
        # TODO: Implement search request or Playwright navigation
        # search_url = f"https://www.example.co.za/search?q={query}"
        # Parse search results and collect product URLs
        return candidate_urls

    def fetch_product(self, url_or_id: str, **kwargs) -> Dict[str, Any]:
        """
        Scrape complete product metadata and return standardized product dictionary.
        """
        # TODO: Implement detail page fetching (via requests or Playwright)
        # response = requests.get(url_or_id, headers={"User-Agent": "..."})
        # soup = BeautifulSoup(response.text, "html.parser")
        
        return {
            "id": self.extract_identifier(url_or_id) or "N/A",
            "title": "Example Product Title",
            "brand": "Example Brand",
            "price": "R 499.00",
            "original_price": "R 599.00",
            "rating": "4.5 out of 5",
            "review_count": "12 reviews",
            "availability": "In Stock",
            "image_url": "https://example.co.za/images/sample.jpg",
            "description": "Product description text...",
            "bullet_points": [
                "Feature highlight 1",
                "Feature highlight 2"
            ],
            "specs": {
                "Color": "Black",
                "Warranty": "1 Year"
            },
            "url": url_or_id,
            "source": self.store_name
        }

    def extract_identifier(self, url_or_input: str) -> Optional[str]:
        """
        Extract unique SKU/Product ID from a URL or raw input string.
        """
        # TODO: Extract store product SKU or unique ID
        return None
