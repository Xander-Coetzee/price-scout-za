from typing import List, Dict, Any, Optional
from scraper.base_scraper import BaseStoreScraper
from scraper.takealot_scraper import (
    fetch_takealot_product,
    search_takealot_product_urls,
    extract_plid
)

class TakealotStoreScraper(BaseStoreScraper):
    """Store scraper plugin for Takealot (takealot.com - South Africa's largest e-commerce platform)."""
    store_id = "takealot"
    store_name = "Takealot"
    domains = ["takealot.com"]

    def search(
        self,
        query: str,
        limit: int = 25,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        seen_ids: Optional[set] = None
    ) -> List[str]:
        return search_takealot_product_urls(query=query, target_count=limit)

    def fetch_product(self, url_or_id: str, **kwargs) -> Dict[str, Any]:
        prod = fetch_takealot_product(url_or_id)
        prod["source"] = self.store_name
        return prod

    def extract_identifier(self, url_or_input: str) -> Optional[str]:
        return extract_plid(url_or_input)

    def is_valid(self, prod: Dict[str, Any]) -> bool:
        title = prod.get("title", "").strip()
        price = prod.get("price", "").strip()
        return bool(title and price and price != "Price unavailable")
