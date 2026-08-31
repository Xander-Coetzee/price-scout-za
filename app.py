import os
import json
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from scraper.amazon_scraper import batch_fetch_amazon_products, extract_all_amazon_urls
from exporter.data_exporter import export_to_json, export_to_markdown
from ai.comparison_engine import analyze_products_with_ai

app = FastAPI(title="Amazon Product Data Scanner & AI Comparison Tool")

# Mount static frontend directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

class ScanRequest(BaseModel):
    inputs: List[str]
    raw_text: Optional[str] = None
    api_key: Optional[str] = None
    category_preset: Optional[str] = None

class CompareRequest(BaseModel):
    products: List[dict]
    context: Optional[str] = ""
    api_key: Optional[str] = None

class ExportRequest(BaseModel):
    products: List[dict]
    context: Optional[str] = ""

@app.post("/api/scan")
def scan_products(req: ScanRequest):
    """Scan Amazon URLs, ASINs, or model keywords to extract specs & pricing."""
    items = []
    if req.raw_text:
        items.extend(extract_all_amazon_urls(req.raw_text))
    if req.inputs:
        for i in req.inputs:
            items.extend(extract_all_amazon_urls(i))
            
    # Deduplicate
    items = list(dict.fromkeys([i.strip() for i in items if i.strip()]))
    
    if not items:
        raise HTTPException(status_code=400, detail="No valid URLs or ASINs provided.")
    
    products = batch_fetch_amazon_products(items, api_key=req.api_key)
    
    # Save default export files
    export_to_json(products, filepath="amazon_products_dataset.json")
    export_to_markdown(products, user_context="", filepath="amazon_product_specs_for_ai.md")
    
    return {
        "status": "success",
        "total_scanned": len(products),
        "products": products
    }

@app.post("/api/compare")
def compare_products(req: CompareRequest):
    """Run AI evaluation on scanned product specs against user context."""
    if not req.products:
        raise HTTPException(status_code=400, detail="Product list cannot be empty.")
        
    analysis = analyze_products_with_ai(req.products, user_context=req.context or "", api_key=req.api_key)
    
    # Update markdown dataset with current context
    export_to_markdown(req.products, user_context=req.context or "", filepath="amazon_product_specs_for_ai.md")
    
    return {
        "status": "success",
        "analysis": analysis
    }

@app.post("/api/export")
def export_files(req: ExportRequest):
    """Generates JSON and Markdown files on the server."""
    json_path = export_to_json(req.products, filepath="amazon_products_dataset.json")
    md_path = export_to_markdown(req.products, user_context=req.context or "", filepath="amazon_product_specs_for_ai.md")
    return {
        "status": "success",
        "json_file": os.path.abspath(json_path),
        "markdown_file": os.path.abspath(md_path)
    }

@app.get("/api/download/json")
def download_json():
    filepath = "amazon_products_dataset.json"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="JSON dataset not generated yet.")
    return FileResponse(filepath, media_type="application/json", filename="amazon_products_dataset.json")

@app.get("/api/download/markdown")
def download_markdown():
    filepath = "amazon_product_specs_for_ai.md"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Markdown dataset not generated yet.")
    return FileResponse(filepath, media_type="text/markdown", filename="amazon_product_specs_for_ai.md")

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
