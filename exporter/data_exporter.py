import json
import os
from datetime import datetime
from typing import List, Dict, Any

def export_all_metadata(products: List[Dict[str, Any]], filepath: str = "scraped_products.json") -> str:
    """
    Consolidates ALL scraped Amazon product metadata into ONE output file.
    Supports .json or .md based on file extension.
    """
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.md':
        return export_to_markdown_file(products, filepath)
    else:
        return export_to_json_file(products, filepath)

def export_to_json_file(products: List[Dict[str, Any]], filepath: str = "scraped_products.json") -> str:
    """Save all scraped product metadata into a single JSON dataset file."""
    data = {
        "metadata": {
            "scanned_at": datetime.now().isoformat(),
            "total_products": len(products),
            "tool": "PriceScout-ZA v1.0.0 (Unified South African E-Commerce Scraper)"
        },
        "products": products
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    return filepath

def export_to_markdown_file(products: List[Dict[str, Any]], filepath: str = "scraped_products.md") -> str:
    """Consolidates all scraped product metadata into a single clean Markdown spec document."""
    md = []
    md.append("# Scraped Product Metadata Spec Document\n")
    md.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append(f"**Total Products:** {len(products)}\n")
    md.append("---\n")
    
    # 1. Summary Table
    md.append("## 📊 Products Metadata Summary Table\n")
    md.append("| # | Store | Product Name | Brand | Price | Rating | ID / ASIN | Link |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for idx, p in enumerate(products, 1):
        store = p.get('source', 'Amazon')
        title = p.get('title', 'Unknown').replace('|', '-')
        brand = p.get('brand', 'N/A').replace('|', '-')
        price = p.get('price', 'N/A')
        rating = p.get('rating', 'N/A')
        pid = p.get('asin') or p.get('plid') or 'N/A'
        url = p.get('url', '#')
        md.append(f"| {idx} | **{store}** | **{title}** | {brand} | `{price}` | {rating} | `{pid}` | [Link]({url}) |")
        
    md.append("\n---\n")
    md.append("## 🔍 Detailed Product Metadata & Technical Specifications\n")
    
    for idx, p in enumerate(products, 1):
        store = p.get('source', 'Amazon')
        md.append(f"### Product {idx}: [{store}] {p.get('title')}")
        md.append(f"- **Brand:** {p.get('brand', 'N/A')}")
        md.append(f"- **ASIN:** `{p.get('asin')}`")
        md.append(f"- **Price:** **{p.get('price')}**" + (f" *(Original Price: {p.get('original_price')})*" if p.get('original_price') else ""))
        md.append(f"- **Rating:** {p.get('rating')} ({p.get('review_count')})")
        md.append(f"- **Availability:** {p.get('availability')}")
        md.append(f"- **URL:** {p.get('url')}\n")
        
        if p.get('description'):
            md.append("#### Product Description:")
            md.append(f"{p.get('description')}\n")
            
        if p.get('ingredients') and p.get('ingredients') != "Not specified on main detail page":
            md.append("#### 🌿 Ingredients:")
            md.append(f"**{p.get('ingredients')}**\n")

        if p.get('directions'):
            md.append("#### Directions:")
            md.append(f"{p.get('directions')}\n")
            
        if p.get('safety_warning'):
            md.append("#### Safety Warning:")
            md.append(f"{p.get('safety_warning')}\n")

        if p.get('bullet_points'):
            md.append("#### Key Features / Highlights:")
            for b in p.get('bullet_points', []):
                md.append(f"- {b}")
            md.append("")
            
        if p.get('specs'):
            md.append("#### Product Information, Features & Technical Specs:")
            md.append("| Attribute | Value |")
            md.append("| :--- | :--- |")
            for k, v in p.get('specs', {}).items():
                k_clean = str(k).replace('|', '-')
                v_clean = str(v).replace('|', '-')
                md.append(f"| **{k_clean}** | {v_clean} |")
            md.append("")
            
        md.append("---\n")

    markdown_content = "\n".join(md)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
        
    return filepath

# Backward-compatible function aliases for web app API
def export_to_json(products: List[Dict[str, Any]], filepath: str = "amazon_products_dataset.json") -> str:
    return export_to_json_file(products, filepath)

def export_to_markdown(products: List[Dict[str, Any]], user_context: str = "", filepath: str = "amazon_product_specs_for_ai.md") -> str:
    return export_to_markdown_file(products, filepath)

