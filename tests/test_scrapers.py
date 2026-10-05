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

class TestPackageClassification(unittest.TestCase):
    def test_refill_twin_pack_detection_and_mismatch_alert(self):
        from scraper.package_classifier import classify_package_integrity
        product = {
            "title": "Raid, Electric Unit, Odourless, Mosquito Killer, Liquid Refill, Twin Pack, 2 x 33 ml",
            "description": "The unit plugs into a standard outlet and heats up the liquid repellent... Unit automatically shuts off after 12 hours.",
            "bullet_points": ["Plugs into standard outlet", "Automatic shut-off after 12 hours"],
            "specs": {"Item Volume": "66 Milliliters", "Unit Count": "2 count", "Item Form": "Oil"}
        }
        res = classify_package_integrity(product)
        self.assertEqual(res["package_type"], "Refill / Replacement Consumable")
        self.assertTrue(res["is_refill_only"])
        self.assertFalse(res["device_included"])
        self.assertTrue(res["requires_base_device"])
        self.assertEqual(res["pack_quantity"], "2 x 33 ml")
        self.assertEqual(len(res["listing_integrity_alerts"]), 1)
        self.assertIn("VENDOR_DESCRIPTION_MISMATCH", res["listing_integrity_alerts"][0])
        self.assertIn("REFILL / REPLACEMENT", res["listing_integrity_alerts"][0])

    def test_starter_kit_detection(self):
        from scraper.package_classifier import classify_package_integrity
        product = {
            "title": "Raid Essentials Liquid Electric Mosquito Killer Primary Unit with Refill",
            "description": "Plugs into any standard outlet and comes with a refill.",
            "specs": {"Unit Count": "1 count"}
        }
        res = classify_package_integrity(product)
        self.assertEqual(res["package_type"], "Starter Kit / Complete Bundle")
        self.assertFalse(res["is_refill_only"])
        self.assertTrue(res["device_included"])
        self.assertFalse(res["requires_base_device"])
        self.assertEqual(len(res["listing_integrity_alerts"]), 0)

    def test_standalone_device_detection(self):
        from scraper.package_classifier import classify_package_integrity
        product = {
            "title": "Electric Mosquito Killer USBLamp",
            "description": "USB-powered mosquito lamp trap",
            "specs": {"Material": "Plastic"}
        }
        res = classify_package_integrity(product)
        self.assertEqual(res["package_type"], "Standalone Device / Appliance")
        self.assertTrue(res["device_included"])
        self.assertFalse(res["is_refill_only"])

    def test_bare_tool_detection(self):
        from scraper.package_classifier import classify_package_integrity
        product = {
            "title": "DeWalt 20V MAX Cordless Circular Saw, Bare Tool (DCS391B)",
            "description": "5150 RPM motor. Battery and charger sold separately."
        }
        res = classify_package_integrity(product)
        self.assertEqual(res["package_type"], "Bare Tool / Body Only (No Battery/Lens)")
        self.assertTrue(res["device_included"])
        self.assertEqual(len(res["listing_integrity_alerts"]), 1)
        self.assertIn("BARE_UNIT_WARNING", res["listing_integrity_alerts"][0])

    def test_phone_case_accessory_detection(self):
        from scraper.package_classifier import classify_package_integrity
        product = {
            "title": "Spigen Ultra Hybrid Protective Case for iPhone 15 Pro Max",
            "description": "Designed for iPhone 15 Pro with Super Retina XDR OLED display."
        }
        res = classify_package_integrity(product)
        self.assertEqual(res["package_type"], "Accessory / Case / Mount")
        self.assertFalse(res["device_included"])
        self.assertEqual(len(res["listing_integrity_alerts"]), 1)
        self.assertIn("ACCESSORY_ONLY_WARNING", res["listing_integrity_alerts"][0])

if __name__ == "__main__":
    unittest.main()
