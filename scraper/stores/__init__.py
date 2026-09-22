from typing import Dict, Type, List, Optional
from scraper.base_scraper import BaseStoreScraper
from scraper.stores.amazon import AmazonStoreScraper
from scraper.stores.takealot import TakealotStoreScraper

# Store Registry mapping store_id -> Store Scraper Class
_STORE_REGISTRY: Dict[str, Type[BaseStoreScraper]] = {
    AmazonStoreScraper.store_id: AmazonStoreScraper,
    TakealotStoreScraper.store_id: TakealotStoreScraper,
}

# Singletons cache
_STORE_INSTANCES: Dict[str, BaseStoreScraper] = {}

def register_store(scraper_cls: Type[BaseStoreScraper]) -> None:
    """Register a new store scraper plugin."""
    _STORE_REGISTRY[scraper_cls.store_id] = scraper_cls

def get_store_scraper(store_id: str) -> BaseStoreScraper:
    """Retrieve an initialized store scraper instance by store_id."""
    normalized_id = store_id.lower().strip()
    if normalized_id not in _STORE_REGISTRY:
        raise ValueError(f"Unknown store '{store_id}'. Supported stores: {list_supported_stores()}")
    if normalized_id not in _STORE_INSTANCES:
        _STORE_INSTANCES[normalized_id] = _STORE_REGISTRY[normalized_id]()
    return _STORE_INSTANCES[normalized_id]

def list_supported_stores() -> List[str]:
    """List all registered store IDs."""
    return list(_STORE_REGISTRY.keys())

def resolve_scraper_for_url(url: str) -> Optional[BaseStoreScraper]:
    """Automatically find and return the appropriate store scraper for a given product URL."""
    for store_id in list_supported_stores():
        scraper = get_store_scraper(store_id)
        if scraper.matches_url(url):
            return scraper
    return None

__all__ = [
    "BaseStoreScraper",
    "AmazonStoreScraper",
    "TakealotStoreScraper",
    "register_store",
    "get_store_scraper",
    "list_supported_stores",
    "resolve_scraper_for_url"
]
