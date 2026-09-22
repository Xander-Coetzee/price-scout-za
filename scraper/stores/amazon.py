from typing import List, Dict, Any, Optional
from scraper.base_scraper import BaseStoreScraper
from scraper.amazon_scraper import (
    fetch_amazon_product,
    collect_amazon_urls,
    extract_asin,
    get_amazon_session,
    is_valid_amazon_product
)

class AmazonStoreScraper(BaseStoreScraper):
    """Store scraper plugin for Amazon (primarily Amazon South Africa - amazon.co.za and global)."""
    store_id = "amazon"
    store_name = "Amazon"
    domains = ["amazon.co.za", "amazon.com", "amazon.co.uk", "amzn.to"]

    def __init__(self):
        self._session = None

    @property
    def session(self):
        if self._session is None:
            self._session = get_amazon_session()
        return self._session

    def search(
        self,
        query: str,
        limit: int = 25,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        seen_ids: Optional[set] = None
    ) -> List[str]:
        return collect_amazon_urls(
            query=query,
            domain="amazon.co.za",
            max_price=max_price,
            min_price=min_price,
            target_count=limit,
            seen_ids=seen_ids
        )

    def fetch_product(self, url_or_id: str, **kwargs) -> Dict[str, Any]:
        api_key = kwargs.get("api_key", "")
        prod = fetch_amazon_product(url_or_id, api_key=api_key, session=self.session)
        prod["source"] = self.store_name
        return prod

    def extract_identifier(self, url_or_input: str) -> Optional[str]:
        return extract_asin(url_or_input)

    def is_valid(self, prod: Dict[str, Any]) -> bool:
        return is_valid_amazon_product(prod)
