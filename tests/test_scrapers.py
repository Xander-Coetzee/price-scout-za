import unittest
from scraper.base_scraper import BaseStoreScraper
from scraper.stores import (
    get_store_scraper,
    list_supported_stores,
    resolve_scraper_for_url
)
from scraper.amazon_scraper import parse_price_number, clean_price_display, extract_asin
from scraper.takealot_scraper import extract_plid

class TestPriceParsing(unittest.TestCase):
    def test_zar_price_variations(self):
        self.assertEqual(parse_price_number("R2 799.00"), 2799.0)
        self.assertEqual(parse_price_number("R2\xa0799.00"), 2799.0)
        self.assertEqual(parse_price_number("R2\u202f799.00"), 2799.0)
        self.assertEqual(parse_price_number("R 1,249.99"), 1249.99)
        self.assertEqual(parse_price_number("R350"), 350.0)
        self.assertEqual(parse_price_number("R13 997.00"), 13997.0)
        self.assertIsNone(parse_price_number("Price unavailable"))
        self.assertIsNone(parse_price_number(""))

    def test_clean_price_display(self):
        cleaned = clean_price_display("R2\xa0799.00")
        self.assertEqual(cleaned, "R2 799.00")

    def test_asin_extraction(self):
        self.assertEqual(extract_asin("https://www.amazon.co.za/dp/B0DLT1WSHY"), "B0DLT1WSHY")
        self.assertEqual(extract_asin("https://www.amazon.com/gp/product/B0B8MXPRDB?ref=xyz"), "B0B8MXPRDB")
        self.assertEqual(extract_asin("B0DLT1WSHY"), "B0DLT1WSHY")

    def test_plid_extraction(self):
        self.assertEqual(extract_plid("https://www.takealot.com/product/PLID96145568"), "PLID96145568")
        self.assertEqual(extract_plid("PLID102454007"), "PLID102454007")

class TestStoreRegistry(unittest.TestCase):
    def test_supported_stores(self):
        stores = list_supported_stores()
        self.assertIn("amazon", stores)
        self.assertIn("takealot", stores)

    def test_get_store_scraper(self):
        amz = get_store_scraper("amazon")
        self.assertEqual(amz.store_name, "Amazon")
        tak = get_store_scraper("takealot")
        self.assertEqual(tak.store_name, "Takealot")

    def test_resolve_scraper_for_url(self):
        amz_scraper = resolve_scraper_for_url("https://www.amazon.co.za/dp/B0DLT1WSHY")
        self.assertIsNotNone(amz_scraper)
        self.assertEqual(amz_scraper.store_id, "amazon")

        tak_scraper = resolve_scraper_for_url("https://www.takealot.com/product/PLID96145568")
        self.assertIsNotNone(tak_scraper)
        self.assertEqual(tak_scraper.store_id, "takealot")

        unknown = resolve_scraper_for_url("https://www.unknown-domain.com/item/123")
        self.assertIsNone(unknown)

if __name__ == "__main__":
    unittest.main()
