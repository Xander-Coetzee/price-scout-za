import re
from typing import Dict, Any, List, Optional

def classify_package_integrity(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Universal E-Commerce Package & Listing Integrity Classifier.
    Works across ALL Amazon & Takealot categories (Tools, Tech, Pest Control, Health,
    Cameras, Smart Home, Appliances, Accessories, Consumables).
    
    Classifies:
    1. Package Type:
       - 'Starter Kit / Complete Bundle'
       - 'Refill / Replacement Consumable'
       - 'Bare Tool / Body Only (No Battery/Lens)'
       - 'Accessory / Case / Mount (Device Not Included)'
       - 'Standalone Device / Appliance'
       - 'Standard Product'
    2. Physical Device Inclusion (device_included: True/False/None)
    3. Listing Integrity Alerts (detects vendor copy-paste mismatches across any category)
    """
    title = product.get("title", "").strip()
    description = product.get("description", "").strip()
    bullet_points = product.get("bullet_points", []) or []
    specs = product.get("specs", {}) or {}
    aplus_text = product.get("aplus_content", "") or ""
    breadcrumbs = product.get("breadcrumbs", []) or []
    
    title_lower = title.lower()
    combined_desc = " ".join([description, " ".join(bullet_points), aplus_text]).lower()
    combined_all = f"{title_lower} {combined_desc}"
    
    alerts = []
    
    # -------------------------------------------------------------
    # 1. UNIVERSAL STARTER KIT / COMPLETE BUNDLE DETECTION
    # -------------------------------------------------------------
    starter_kit_patterns = [
        r'\bstarter kit\b', r'\bstarter pack\b', r'\bstarter set\b',
        r'\bcomplete kit\b', r'\bfull kit\b', r'\bcombo kit\b',
        r'\bprimary unit with\b', r'\bunit \+ refill\b', r'\bdevice with refill\b',
        r'\bmachine \+ \b', r'\bwith charger and battery\b', r'\bwith 2 batteries\b',
        r'\blens kit\b', r'\bwith [0-9\-]+mm lens\b', r'\bbundle with\b'
    ]
    is_starter_kit = any(re.search(pat, title_lower) for pat in starter_kit_patterns)
    
    # -------------------------------------------------------------
    # 2. UNIVERSAL BARE TOOL / BODY ONLY DETECTION (Tools, Cameras)
    # -------------------------------------------------------------
    bare_unit_patterns = [
        r'\bbare tool\b', r'\btool only\b', r'\btool-only\b',
        r'\bbody only\b', r'\bbody-only\b',
        r'\bwithout battery\b', r'\bno battery\b', r'\bbattery not included\b',
        r'\bno charger\b', r'\bcharger not included\b',
        r'\bwithout lens\b', r'\bno lens\b', r'\blens not included\b'
    ]
    is_bare_unit = any(re.search(pat, title_lower) for pat in bare_unit_patterns)
    
    # -------------------------------------------------------------
    # 3. UNIVERSAL ACCESSORY / CASE / MOUNT DETECTION
    # -------------------------------------------------------------
    accessory_patterns = [
        r'\b(?:case|cover|sleeve|housing|pouch|skin)\s+(?:for|compatible with)\b',
        r'\b(?:stand|mount|bracket|dock|holder|tripod|strap|band)\s+(?:for|compatible with)\b',
        r'\bscreen protector\b', r'\bprotective (?:case|cover|glass)\b'
    ]
    is_accessory = any(re.search(pat, title_lower) for pat in accessory_patterns)
    
    # -------------------------------------------------------------
    # 4. UNIVERSAL REFILL / REPLACEMENT / CONSUMABLE DETECTION
    # -------------------------------------------------------------
    refill_keywords = [
        r'\brefills?\b', r'\breplacement\b', r'\bcartridges?\b',
        r'\btoner\b', r'\bink cartridge\b', r'\bbrush heads?\b',
        r'\brazor blades?\b', r'\bmats?\b', r'\bpads?\b',
        r'\bfilter pack\b', r'\bwater filters?\b', r'\bcoffee pods?\b',
        r'\bcapsules?\b', r'\btablets?\b', r'\bpods?\b', r'\btape roll\b'
    ]
    is_refill = any(re.search(kw, title_lower) for kw in refill_keywords)
    
    # Check for multi-pack of liquids/consumables (e.g. "Twin Pack, 2 x 33 ml", "Pack of 3")
    if not is_refill and re.search(r'\b(?:twin|2|3|4|5|6|12)\s*pack\b', title_lower):
        has_volume = bool(re.search(r'\b(?:\d+\s*ml|\d+\s*g|liquid|oil|bottles?|capsules?|tablets?)\b', title_lower))
        is_liquid_form = "oil" in str(specs.get("Item form", "")).lower() or "liquid" in str(specs.get("Item form", "")).lower()
        if (has_volume or is_liquid_form) and not is_starter_kit:
            is_refill = True
            
    # Check manufacturer text: "for your existing unit", "requires existing machine"
    requires_existing = False
    if re.search(r'existing\s+(?:unit|device|machine|appliance|heater|plug|diffuser|printer|shaver|toothbrush|dispenser)', combined_desc):
        requires_existing = True
        if not is_starter_kit:
            is_refill = True

    # -------------------------------------------------------------
    # 5. DETERMINE PACKAGE TYPE & DEVICE STATUS
    # -------------------------------------------------------------
    if is_starter_kit:
        package_type = "Starter Kit / Complete Bundle"
        device_included = True
        is_refill_only = False
        requires_base_device = False
    elif is_bare_unit:
        package_type = "Bare Tool / Body Only (No Battery/Lens)"
        device_included = True  # Tool itself is present, but missing power/lens
        is_refill_only = False
        requires_base_device = False
        alerts.append(
            "BARE_UNIT_WARNING: This product is sold as 'Bare Tool / Body Only'. Batteries, charger, or lenses are NOT included and must be purchased separately."
        )
    elif is_accessory:
        package_type = "Accessory / Case / Mount"
        device_included = False
        is_refill_only = False
        requires_base_device = True
        # Check if description confuses the accessory with the host electronic device
        if re.search(r'\b(?:oled|display|processor|ram|storage|battery life|mah|camera)\b', combined_desc):
            alerts.append(
                "ACCESSORY_ONLY_WARNING: This product is a protective case, mount, or accessory. The actual electronic device is NOT included."
            )
    elif is_refill:
        package_type = "Refill / Replacement Consumable"
        device_included = False
        is_refill_only = True
        requires_base_device = True
    else:
        # Check if it is a standalone electrical device/appliance
        is_appliance = any(w in title_lower for w in [
            "laptop", "tv", "monitor", "speaker", "phone", "tablet", "console", "printer",
            "blender", "kettle", "toaster", "vacuum", "drill", "saw", "grinder",
            "lamp", "zapper", "trap", "swatter", "inverter", "power station", "generator",
            "camera", "diffuser unit", "primary unit"
        ])
        if is_appliance:
            package_type = "Standalone Device / Appliance"
            device_included = True
            is_refill_only = False
            requires_base_device = False
        else:
            package_type = "Standard Product"
            device_included = None
            is_refill_only = False
            requires_base_device = False

    # -------------------------------------------------------------
    # 6. UNIVERSAL CONTRADICTION & VENDOR MISMATCH DETECTOR
    # -------------------------------------------------------------
    if package_type == "Refill / Replacement Consumable":
        # Check if seller's copy-pasted text claims whole-machine features
        misleading_claims = []
        if re.search(r'\bplugs into (?:standard )?outlet\b', combined_desc):
            misleading_claims.append("plugs into outlet")
        if re.search(r'\bautomatic shut-off\b', combined_desc):
            misleading_claims.append("automatic shut-off")
        if re.search(r'\b(?:led indicator|digital display|lcd screen)\b', combined_desc):
            misleading_claims.append("electronic display/LED")
        if re.search(r'\b(?:rechargeable battery|built-in battery|usb-c charging)\b', combined_desc):
            misleading_claims.append("battery/charging")
        if re.search(r'\b(?:variable speed|motor speed|watts? power)\b', combined_desc):
            misleading_claims.append("motor/wattage")
            
        # Extract pack quantity
        unit_count = specs.get("Unit count") or specs.get("Unit Count") or specs.get("Number of items") or specs.get("Number of Items") or ""
        item_volume = specs.get("Item volume") or specs.get("Item Volume") or specs.get("Units") or ""
        qty_match = re.search(r'(\d+)\s*(?:x\s*(\d+(?:\.\d+)?\s*(?:ml|g|count|liters?)))', title, re.IGNORECASE)
        pack_quantity = f"{qty_match.group(1)} x {qty_match.group(2)}" if qty_match else (str(unit_count) if unit_count else "1")

        if misleading_claims:
            claims_str = ", ".join([f"'{c}'" for c in misleading_claims])
            alerts.append(
                f"VENDOR_DESCRIPTION_MISMATCH: The seller description contains machine/electrical features ({claims_str}), "
                f"but this listing is a REFILL / REPLACEMENT ONLY ({pack_quantity}). The base device/machine is NOT included."
            )
        elif requires_existing:
            alerts.append(
                "REFILL_ONLY_NOTICE: Requires an existing host machine or unit. No base appliance is included."
            )

    unit_count = specs.get("Unit count") or specs.get("Unit Count") or specs.get("Number of items") or specs.get("Number of Items") or ""
    item_volume = specs.get("Item volume") or specs.get("Item Volume") or specs.get("Units") or ""
    qty_match = re.search(r'(\d+)\s*(?:x\s*(\d+(?:\.\d+)?\s*(?:ml|g|count|liters?)))', title, re.IGNORECASE)
    pack_quantity = f"{qty_match.group(1)} x {qty_match.group(2)}" if qty_match else (str(unit_count) if unit_count else "1")

    return {
        "package_type": package_type,
        "is_refill_only": is_refill_only,
        "device_included": device_included,
        "requires_base_device": requires_base_device,
        "pack_quantity": pack_quantity,
        "net_volume_or_weight": item_volume,
        "listing_integrity_alerts": alerts
    }
