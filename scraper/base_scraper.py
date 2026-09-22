from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
import re
import unicodedata
from urllib.parse import urlparse

class BaseStoreScraper(ABC):
    """
    Abstract Base Class for all E-Commerce Store Scrapers.
    
    To add support for a new store (e.g. Makro, Wootware, Bob Shop),
    subclass this class, implement `search()`, `fetch_product()`, and `extract_identifier()`,
    and register your class in `scraper.stores`.
    """
    store_id: str = "base"
    store_name: str = "Base Store"
    domains: List[str] = []

    @abstractmethod
    def search(
        self,
        query: str,
        limit: int = 25,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        seen_ids: Optional[set] = None
    ) -> List[str]:
        """
        Search the store for query and return clean product URLs or identifiers.
        
        Args:
            query: Search keywords
            limit: Maximum candidate URLs to retrieve
            max_price: Optional maximum price filter
            min_price: Optional minimum price filter
            seen_ids: Set of previously collected identifiers to skip
            
        Returns:
            List of unique, clean product URLs
        """
        pass

    @abstractmethod
    def fetch_product(self, url_or_id: str, **kwargs) -> Dict[str, Any]:
        """
        Fetch full 360-degree product metadata from a product URL or ID.
        
        Returns:
            Standardized product dictionary containing:
            - id / asin / plid: Unique product identifier
            - title: Product title
            - brand: Brand name
            - price: Formatted price string (e.g., 'R 1,299.00')
            - original_price: Original list price / RRP
            - rating: Customer star rating
            - review_count: Number of customer reviews
            - availability: In Stock / Out of Stock
            - image_url: High-resolution product image
            - description: Product description
            - bullet_points: List of key features
            - specs: Dictionary of technical specifications
            - url: Canonical product URL
            - source: Store name (e.g. 'Amazon', 'Takealot')
        """
        pass

    @abstractmethod
    def extract_identifier(self, url_or_input: str) -> Optional[str]:
        """
        Extract unique SKU/ASIN/PLID/ID from URL or input string.
        """
        pass

    def matches_url(self, url: str) -> bool:
        """Check if a URL belongs to this store based on its configured domains."""
        if not url:
            return False
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        return any(domain.lower() in netloc for domain in self.domains)

    @staticmethod
    def parse_price_number(price_str: str) -> Optional[float]:
        """Normalize and extract float numerical price from any currency string (e.g. 'R 1 299,00' -> 1299.0)."""
        if not price_str or "unavailable" in price_str.lower():
            return None
        cleaned = "".join(c for c in price_str if unicodedata.category(c) != 'Cf')
        cleaned = re.sub(r'[\s\xa0\u202f\u2009\u200b]+', ' ', cleaned).strip()
        cleaned = re.sub(r'(\d+)\s+(\d+)', r'\1\2', cleaned)
        cleaned = re.sub(r'(\d+),(\d{3})', r'\1\2', cleaned)
        cleaned = re.sub(r'(\d+),(\d{2})\b', r'\1.\2', cleaned)
        
        matches = re.findall(r'\d+(?:\.\d+)?', cleaned)
        if matches:
            try:
                numbers = [float(m) for m in matches]
                return max(numbers)
            except ValueError:
                pass
        return None

    @staticmethod
    def clean_price_display(price_str: str) -> str:
        """Clean invisible formatting characters and normalize whitespace in price displays."""
        if not price_str:
            return ""
        cleaned = "".join(c for c in price_str if unicodedata.category(c) != 'Cf')
        cleaned = re.sub(r'[\s\xa0\u202f\u2009\u200b]+', ' ', cleaned).strip()
        return cleaned
