document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('urlInput');
    const contextInput = document.getElementById('contextInput');
    const btnScan = document.getElementById('btnScan');
    const btnCompare = document.getElementById('btnCompare');
    const btnDownloadJson = document.getElementById('btnDownloadJson');
    const btnDownloadMd = document.getElementById('btnDownloadMd');
    const btnCopyPrompt = document.getElementById('btnCopyPrompt');
    const loader = document.getElementById('loader');
    const loaderText = document.getElementById('loaderText');

    const aiResultSection = document.getElementById('aiResultSection');
    const specMatrixSection = document.getElementById('specMatrixSection');
    const productCardsSection = document.getElementById('productCardsSection');

    let currentProducts = [];

    // Category presets
    const PRESETS = {
        protein: [
            "Optimum Nutrition Gold Standard 100% Whey Protein Powder Double Rich Chocolate 5 lbs",
            "Dymatize ISO100 Hydrolyzed 100% Whey Isolate Powder Gourmet Chocolate 5 lbs",
            "Body Fortress Super Advanced Whey Protein Powder Milk Chocolate 4 lbs"
        ],
        laptops: [
            "Apple MacBook Air M3 15-inch 16GB RAM 512GB SSD",
            "Dell XPS 15 OLED Intel Core i7 32GB RAM RTX 4060",
            "Lenovo ThinkPad X1 Carbon Gen 11 Intel i7 16GB RAM"
        ],
        headphones: [
            "Sony WH-1000XM5 Wireless Industry Leading Noise Canceling Headphones",
            "Bose QuietComfort Ultra Wireless Noise Canceling Headphones",
            "Apple AirPods Max Wireless Over-Ear Headphones"
        ],
        watches: [
            "Apple Watch Ultra 2 GPS + Cellular 49mm Titanium",
            "Garmin Epix Gen 2 Sapphire Premium Multisport GPS Watch",
            "Samsung Galaxy Watch 6 Classic 47mm Bluetooth"
        ]
    };

    // Preset button handlers
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const key = btn.dataset.preset;
            if (PRESETS[key]) {
                urlInput.value = PRESETS[key].join('\n');
                if (key === 'protein') {
                    contextInput.value = "Which whey protein powder has the absolute best bang for buck (highest grams of protein per dollar and lowest cost per serving)?";
                } else if (key === 'laptops') {
                    contextInput.value = "Need a laptop for 4K video editing, coding, and long travel. Powerful GPU and high-res screen preferred under $1,400.";
                } else if (key === 'headphones') {
                    contextInput.value = "Best wireless headphones for long flights, high audio clarity, and Zoom calls under $350.";
                } else if (key === 'watches') {
                    contextInput.value = "Multisport GPS smartwatch for outdoor hiking, running, heart rate, and 7+ days battery life.";
                }
            }
        });
    });

    // Scan Products
    btnScan.addEventListener('click', async () => {
        const rawText = urlInput.value.trim();
        if (!rawText) {
            alert('Please enter at least one Amazon URL, ASIN, or product name.');
            return;
        }

        const lines = rawText.split('\n').filter(l => l.trim().length > 0);
        showLoader('Scanning Amazon products and parsing technical specifications...');

        try {
            const response = await fetch('/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ inputs: lines })
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Scan failed.');

            currentProducts = data.products || [];
            renderProductCards(currentProducts);
            renderSpecMatrix(currentProducts);

            btnCompare.disabled = currentProducts.length === 0;
            hideLoader();

            // Smooth scroll to results
            specMatrixSection.scrollIntoView({ behavior: 'smooth' });

        } catch (err) {
            hideLoader();
            alert('Error scanning products: ' + err.message);
        }
    });

    // AI Compare Products
    btnCompare.addEventListener('click', async () => {
        if (currentProducts.length === 0) return;

        showLoader('AI Engine is evaluating product specs, prices, and your criteria...');

        try {
            const response = await fetch('/api/compare', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    products: currentProducts,
                    context: contextInput.value.trim()
                })
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Comparison failed.');

            renderAIResult(data.analysis);
            hideLoader();

            aiResultSection.scrollIntoView({ behavior: 'smooth' });

        } catch (err) {
            hideLoader();
            alert('Error running AI comparison: ' + err.message);
        }
    });

    // Render Product Cards
    function renderProductCards(products) {
        const grid = document.getElementById('productGrid');
        grid.innerHTML = '';

        products.forEach(p => {
            const card = document.createElement('div');
            card.className = 'prod-card';

            const imgUrl = p.image_url || 'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=400&q=80';
            const bullets = (p.bullet_points || []).slice(0, 3).map(b => `<li>${escapeHtml(b)}</li>`).join('');

            card.innerHTML = `
                <img src="${escapeHtml(imgUrl)}" alt="Product Image" class="prod-image" onerror="this.src='https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=400&q=80'">
                <div class="prod-title">${escapeHtml(p.title || 'Amazon Product')}</div>
                <div class="prod-price-row">
                    <span class="prod-price">${escapeHtml(p.price || 'N/A')}</span>
                    ${p.original_price ? `<span class="prod-orig-price">${escapeHtml(p.original_price)}</span>` : ''}
                </div>
                <div style="font-size:12px; color:#9ca3af; margin-bottom:10px;">
                    <i class="fa-solid fa-star" style="color:#f59e0b;"></i> ${escapeHtml(p.rating || '4.5')} (${escapeHtml(p.review_count || 'Reviews')})
                </div>
                <ul class="prod-bullets">${bullets}</ul>
            `;
            grid.appendChild(card);
        });

        productCardsSection.classList.remove('hidden');
    }

    // Render Spec Table
    function renderSpecMatrix(products) {
        const headerRow = document.getElementById('specTableHeader');
        const tbody = document.getElementById('specTableBody');
        document.getElementById('productCountTag').textContent = `${products.length} Products`;

        headerRow.innerHTML = '<th>Specification Attribute</th>';
        tbody.innerHTML = '';

        products.forEach(p => {
            const th = document.createElement('th');
            th.textContent = (p.title || '').substring(0, 35) + '...';
            headerRow.appendChild(th);
        });

        // Collect unique keys
        const allKeys = new Set();
        products.forEach(p => {
            Object.keys(p.specs || {}).forEach(k => allKeys.add(k));
        });

        allKeys.forEach(key => {
            const tr = document.createElement('tr');
            const tdKey = document.createElement('td');
            tdKey.style.fontWeight = '600';
            tdKey.textContent = key;
            tr.appendChild(tdKey);

            products.forEach(p => {
                const tdVal = document.createElement('td');
                tdVal.textContent = p.specs ? (p.specs[key] || '-') : '-';
                tr.appendChild(tdVal);
            });

            tbody.appendChild(tr);
        });

        specMatrixSection.classList.remove('hidden');
    }

    // Render AI Analysis
    function renderAIResult(analysis) {
        document.getElementById('winnerTitle').textContent = analysis.winner_title || 'Winner Selected';
        
        let reasonFormatted = (analysis.recommendation_reason || '').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        document.getElementById('reasoningText').innerHTML = reasonFormatted.replace(/\n/g, '<br>');
        
        document.getElementById('verdictText').innerHTML = (analysis.verdict_summary || '').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        document.getElementById('bestValueTitle').textContent = analysis.best_value_title ? `${analysis.best_value_title}` : 'See scores';

        const scoreGrid = document.getElementById('scoreCardsGrid');
        scoreGrid.innerHTML = '';

        (analysis.scores || []).forEach(item => {
            const card = document.createElement('div');
            card.className = 'score-card';

            card.innerHTML = `
                <div class="score-card-header">
                    <div class="score-card-title">${escapeHtml(item.title)}</div>
                    <div class="overall-score-badge">${item.overall_score}/10</div>
                </div>
                ${renderScoreBar('Performance', item.performance_score)}
                ${renderScoreBar('Value Ratio', item.value_score)}
                ${renderScoreBar('Specs Completeness', item.specs_score)}
                <div style="margin-top:10px; font-size:11px; color:#9ca3af;">
                    <strong style="color:#10b981;">Pros:</strong> ${(item.pros || []).join(', ')}
                </div>
            `;
            scoreGrid.appendChild(card);
        });

        aiResultSection.classList.remove('hidden');
    }

    function renderScoreBar(label, val) {
        const pct = Math.min(100, Math.max(0, val * 10));
        return `
            <div class="score-bar-group">
                <div class="score-bar-label">
                    <span>${label}</span>
                    <span>${val}/10</span>
                </div>
                <div class="score-bar-bg">
                    <div class="score-bar-fill" style="width:${pct}%"></div>
                </div>
            </div>
        `;
    }

    // Downloads
    btnDownloadJson.addEventListener('click', () => {
        window.location.href = '/api/download/json';
    });

    btnDownloadMd.addEventListener('click', () => {
        window.location.href = '/api/download/markdown';
    });

    btnCopyPrompt.addEventListener('click', async () => {
        try {
            const resp = await fetch('/api/download/markdown');
            const text = await resp.text();
            await navigator.clipboard.writeText(text);
            alert('Copied Markdown spec dataset to clipboard! You can now paste this directly into ChatGPT, Claude, or Gemini.');
        } catch (e) {
            alert('Failed to copy to clipboard: ' + e);
        }
    });

    function showLoader(msg) {
        loaderText.textContent = msg;
        loader.classList.remove('hidden');
    }

    function hideLoader() {
        loader.classList.add('hidden');
    }

    function escapeHtml(str) {
        return (str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
});
