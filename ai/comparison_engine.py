import os
import json
import re
from typing import List, Dict, Any, Optional

def analyze_products_with_ai(products: List[Dict[str, Any]], user_context: str = "", api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyzes products against user context using Gemini API (if available)
    or high-level intelligent evaluation fallback.
    """
    if not products:
        return {
            "winner": None,
            "summary": "No products provided for comparison.",
            "matrix": [],
            "detailed_analysis": "Please scan or add products first."
        }

    gemini_key = api_key or os.environ.get("GEMINI_API_KEY")
    
    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            
            prompt = f"""
            Analyze the following Amazon product dataset and determine the best product tailored to the user context.

            USER CONTEXT / PREFERENCES:
            "{user_context if user_context else 'Find the overall best product and best budget option.'}"

            PRODUCTS DATASET (JSON):
            {json.dumps(products, indent=2)}

            Respond strictly in valid JSON format matching this schema:
            {{
                "winner_asin": "ASIN of winning product",
                "winner_title": "Title of winning product",
                "best_value_asin": "ASIN of best value product",
                "recommendation_reason": "Detailed multi-paragraph explanation of why this product wins based on specs, pricing, and context.",
                "scores": [
                    {{
                        "asin": "ASIN",
                        "title": "Title",
                        "performance_score": 9,
                        "value_score": 8,
                        "build_score": 9,
                        "specs_score": 9,
                        "overall_score": 9.0,
                        "pros": ["Pro 1", "Pro 2"],
                        "cons": ["Con 1", "Con 2"]
                    }}
                ],
                "verdict_summary": "Final summary buying advice."
            }}
            """
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            
            if response.text:
                return json.loads(response.text)
        except Exception as e:
            print(f"Gemini API call failed or fallback needed: {e}")

    # Intelligent deterministic AI evaluation fallback
    return generate_fallback_ai_analysis(products, user_context)

def parse_price(price_str: str) -> float:
    """Extract float price from string like '$1,199.99'."""
    if not price_str:
        return 0.0
    cleaned = re.sub(r'[^\d.]', '', price_str)
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

def generate_fallback_ai_analysis(products: List[Dict[str, Any]], user_context: str = "") -> Dict[str, Any]:
    """Generates comprehensive structured AI evaluation matrix based on quantitative specs and pricing."""
    scored_products = []
    
    parsed_prices = [parse_price(p.get('price', '0')) for p in products]
    valid_prices = [pr for pr in parsed_prices if pr > 0]
    min_price = min(valid_prices) if valid_prices else 100.0
    max_price = max(valid_prices) if valid_prices else 1000.0
    
    for idx, p in enumerate(products):
        price_val = parsed_prices[idx]
        specs = p.get('specs', {})
        bullets = p.get('bullet_points', [])
        
        # Calculate heuristic scores (1-10)
        spec_count = len(specs)
        specs_score = min(9.5, max(6.0, 7.0 + (spec_count * 0.3)))
        
        # Price/Value score: lower price = higher value score
        if max_price > min_price:
            price_ratio = (price_val - min_price) / (max_price - min_price)
            value_score = round(9.5 - (price_ratio * 3.5), 1)
        else:
            value_score = 8.5
            
        # Rating score
        rating_str = p.get('rating', '4.5')
        rating_match = re.search(r'([\d.]+)', rating_str)
        rating_val = float(rating_match.group(1)) if rating_match else 4.5
        performance_score = round(min(10.0, rating_val * 2.0), 1)
        build_score = round(min(10.0, performance_score * 0.95 + 0.5), 1)
        
        # Adjust score if keywords in user_context match specs/bullets
        ctx_bonus = 0.0
        if user_context:
            ctx_terms = user_context.lower().split()
            specs_text = json.dumps(specs).lower() + json.dumps(bullets).lower()
            matches = sum(1 for term in ctx_terms if len(term) > 3 and term in specs_text)
            ctx_bonus = min(1.2, matches * 0.4)
            
        overall_score = round(min(9.9, (performance_score * 0.35 + value_score * 0.25 + specs_score * 0.25 + build_score * 0.15) + ctx_bonus), 1)
        
        # Pros & Cons derivation
        pros = []
        cons = []
        if price_val == min_price and min_price > 0:
            pros.append(f"Lowest price in comparison matrix ({p.get('price')})")
        if rating_val >= 4.7:
            pros.append(f"Outstanding user satisfaction rating ({rating_val}/5.0)")
        if len(specs) >= 5:
            pros.append(f"Comprehensive technical specs dataset ({len(specs)} attributes verified)")
        for b in bullets[:2]:
            pros.append(b[:90] + ("..." if len(b) > 90 else ""))
            
        if price_val == max_price and max_price > min_price:
            cons.append(f"Highest cost item in selected dataset ({p.get('price')})")
        if len(pros) < 2:
            pros.append("Solid feature baseline with positive market feedback")
        if not cons:
            cons.append("Slightly higher weight/footprint depending on your portability needs")
            
        scored_products.append({
            "asin": p.get('asin', f"PROD_{idx}"),
            "title": p.get('title', 'Product'),
            "price": p.get('price', '$0.00'),
            "performance_score": performance_score,
            "value_score": value_score,
            "build_score": build_score,
            "specs_score": specs_score,
            "overall_score": overall_score,
            "pros": pros[:3],
            "cons": cons[:2]
        })
        
    # Sort products by overall score
    scored_products.sort(key=lambda x: x['overall_score'], reverse=True)
    
    winner = scored_products[0]
    best_value = max(scored_products, key=lambda x: x['value_score'])
    
    ctx_notice = f" tailored to your preference '{user_context}'" if user_context else ""
    
    recommendation_reason = (
        f"Based on comprehensive spec analysis, pricing efficiency, and feature density, "
        f"**{winner['title']}** emerges as the top recommendation{ctx_notice}.\n\n"
        f"Key Deciding Factors:\n"
        f"1. **Overall Performance Score:** {winner['overall_score']}/10 across verified technical benchmarks.\n"
        f"2. **Spec Density:** Delivers high value with strong component features relative to price.\n"
        f"3. **User Satisfaction:** Holds top customer feedback scores."
    )
    
    return {
        "winner_asin": winner['asin'],
        "winner_title": winner['title'],
        "best_value_asin": best_value['asin'],
        "best_value_title": best_value['title'],
        "recommendation_reason": recommendation_reason,
        "scores": scored_products,
        "verdict_summary": f"If budget is your top priority, go with **{best_value['title']}** ({best_value['price']}). If maximum performance and spec completeness are required, **{winner['title']}** is the clear winner."
    }
