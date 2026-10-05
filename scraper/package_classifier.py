import re
from typing import Dict, Any, List

def classify_package_integrity(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes product metadata (title, specs, description, A+ content, bullet points)
    to classify the package type, verify if an electric/base device is actually included,
    and detect deceptive or copy-pasted vendor listing descriptions.
    """
    title = product.get("title", "").strip()
    description = product.get("description", "").strip()
    bullet_points = product.get("bullet_points", []) or []
    specs = product.get("specs", {}) or {}
    aplus_text = product.get("aplus_content", "") or ""
    
    combined_text = " ".join([title, description, " ".join(bullet_points), aplus_text]).lower()
    title_lower = title.lower()
    
    # 1. Detect Refills, Consumables, and Accessories
    is_refill = False
    refill_keywords = [
        r'\brefills?\b', r'\breplacement\b', r'\bcartridges?\b',
        r'\bmats?\b', r'\bpads?\b', r'\btablets?\b', r'\bpods?\b'
    ]
    for kw in refill_keywords:
        if re.search(kw, title_lower):
            is_refill = True
            break
            
    # Check for pack of liquids / consumables without device (e.g. "Twin Pack, 2 x 33 ml")
    if not is_refill and re.search(r'\b(?:twin|2|3|4|5|6)\s*pack\b', title_lower):
        has_volume = bool(re.search(r'\b(?:\d+\s*ml|\d+\s*g|liquid|oil|bottles?)\b', title_lower))
        is_oil_form = "oil" in str(specs.get("Item form", "")).lower() or "liquid" in str(specs.get("Item form", "")).lower()
        if (has_volume or is_oil_form) and not any(w in title_lower for w in ["lamp", "zapper", "trap", "bulb", "diffuser unit"]):
            is_refill = True
            
    # Check A+ content or description for "existing unit" / "existing device"
    requires_existing = False
    if re.search(r'existing\s+(?:electric|mosquito|heater|plug|diffuser|device|unit|machine|applicator)', combined_text):
        requires_existing = True
        is_refill = True
        
    # 2. Detect Starter Kits / Base Units Included
    starter_kit_patterns = [
        r'\bprimary unit with refill\b',
        r'\bprimary unit\s*,?\s*with\b',
        r'\bstarter kit\b',
        r'\bdevice with refill\b',
        r'\bcomplete kit\b',
        r'\bunit \+ refill\b',
        r'\bdiffuser \+ refill\b',
        r'\bheater \+ refill\b',
        r'\bmachine \+ refill\b'
    ]
    is_starter_kit = False
    for pat in starter_kit_patterns:
        if re.search(pat, title_lower):
            is_starter_kit = True
            break
            
    # Determine Package Type & Device Status
    if is_refill and not is_starter_kit:
        device_included = False
        requires_base_device = True
        package_type = "Refill Pack"
    elif is_starter_kit:
        device_included = True
        requires_base_device = False
        package_type = "Starter Kit (Device + Refill)"
    else:
        # Check if it is a standalone electrical device (Lamp, Zapper, etc.)
        if any(w in title_lower for w in ["lamp", "zapper", "trap", "globe", "swatter", "bat", "inverter", "power station"]):
            device_included = True
            requires_base_device = False
            package_type = "Standalone Device"
        else:
            device_included = None
            requires_base_device = False
            package_type = "Standard Product"

    # 3. Detect Unit Count & Volume
    unit_count = specs.get("Unit count") or specs.get("Unit Count") or specs.get("Number of items") or specs.get("Number of Items") or ""
    item_volume = specs.get("Item volume") or specs.get("Item Volume") or specs.get("Units") or ""
    
    qty_match = re.search(r'(\d+)\s*(?:x\s*(\d+(?:\.\d+)?\s*(?:ml|g|count|liters?)))', title, re.IGNORECASE)
    if qty_match:
        pack_quantity = f"{qty_match.group(1)} x {qty_match.group(2)}"
    elif "twin pack" in title_lower or "2 pack" in title_lower:
        pack_quantity = "2 Pack"
    else:
        pack_quantity = str(unit_count) if unit_count else "1"

    # 4. Detect Vendor Listing Copy-Paste Mismatches / Deceptions
    alerts = []
    if package_type == "Refill Pack":
        misleading_claims = []
        if re.search(r'\bplugs into (?:standard )?outlet\b', description.lower()) or any("plugs into" in str(b).lower() for b in bullet_points):
            misleading_claims.append("plugs into outlet")
        if re.search(r'\bautomatic shut-off\b', description.lower()) or any("shut-off" in str(b).lower() for b in bullet_points):
            misleading_claims.append("automatic shut-off")
        if re.search(r'\bheats up liquid\b', description.lower()):
            misleading_claims.append("heats up liquid repellent")
            
        if misleading_claims:
            claims_str = ", ".join([f"'{c}'" for c in misleading_claims])
            alerts.append(
                f"VENDOR_DESCRIPTION_MISMATCH: The seller description claims electrical device features ({claims_str}), "
                f"but this listing is a REFILL-ONLY pack ({pack_quantity}). A wall plug heater/diffuser unit is NOT included in the box."
            )
        elif requires_existing:
            alerts.append(
                "REFILL_ONLY_NOTICE: Requires an existing heating/diffuser unit. No wall plug device is included."
            )

    return {
        "package_type": package_type,
        "is_refill_only": is_refill and not is_starter_kit,
        "device_included": device_included,
        "requires_base_device": requires_base_device,
        "pack_quantity": pack_quantity,
        "net_volume_or_weight": item_volume,
        "listing_integrity_alerts": alerts
    }
