// ==UserScript==
// @name         Amazon Auto Product URL Collector
// @namespace    https://github.com/amazon-comparison
// @version      1.0
// @description  Automatically collects Amazon product URLs when middle-clicking search results & provides 1-click export to urls.txt.
// @author       Antigravity
// @match        https://www.amazon.com/*
// @match        https://www.amazon.co.za/*
// @match        https://www.amazon.co.uk/*
// @match        https://www.amazon.de/*
// @match        https://www.amazon.ca/*
// @grant        none
// ==UserScript==

(function() {
    'use strict';

    const STORAGE_KEY = 'amazon_collected_urls';

    function getCollectedUrls() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        } catch(e) {
            return [];
        }
    }

    function saveCollectedUrls(urls) {
        const unique = Array.from(new Set(urls.filter(Boolean)));
        localStorage.setItem(STORAGE_KEY, JSON.stringify(unique));
        updateFloatingUI();
    }

    function extractCleanAmazonUrl(url) {
        if (!url || !url.includes('amazon')) return null;
        const match = url.match(/(https?:\/\/[^\/]+(?:\/[^\/]+)?\/dp\/[A-Z0-9]{10})/i) ||
                      url.match(/(https?:\/\/[^\/]+\/gp\/product\/[A-Z0-9]{10})/i) ||
                      url.match(/(https?:\/\/[^\/]+\/dp\/[A-Z0-9]{10})/i);
        if (match) {
            return match[1];
        }
        // Fallback: clean query parameters
        if (url.includes('/dp/') || url.includes('/gp/product/')) {
            return url.split('?')[0];
        }
        return null;
    }

    // Intercept middle-click (button === 1) or click on product links
    document.addEventListener('auxclick', function(e) {
        if (e.button === 1) { // Middle click
            const anchor = e.target.closest('a');
            if (anchor && anchor.href) {
                const cleanUrl = extractCleanAmazonUrl(anchor.href);
                if (cleanUrl) {
                    const current = getCollectedUrls();
                    if (!current.includes(cleanUrl)) {
                        current.push(cleanUrl);
                        saveCollectedUrls(current);
                        showToast(`✓ Added: ${cleanUrl.split('/dp/')[0].split('/').pop().replace(/-/g, ' ')}`);
                    }
                }
            }
        }
    }, true);

    // Add "+" toggle buttons on search result product cards
    function injectCardBadges() {
        const productCards = document.querySelectorAll('div[data-component-type="s-search-result"]');
        const collected = getCollectedUrls();

        productCards.forEach(card => {
            if (card.querySelector('.amz-collector-btn')) return;
            const linkElem = card.querySelector('h2 a, a.a-link-normal.s-no-outline');
            if (!linkElem) return;

            const cleanUrl = extractCleanAmazonUrl(linkElem.href);
            if (!cleanUrl) return;

            const btn = document.createElement('button');
            btn.className = 'amz-collector-btn';
            const isAdded = collected.includes(cleanUrl);
            btn.innerHTML = isAdded ? '✓ Added' : '+ Collect';
            btn.style.cssText = `
                margin-top: 6px;
                padding: 4px 10px;
                background: ${isAdded ? '#10b981' : '#2563eb'};
                color: #fff;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                cursor: pointer;
                z-index: 99;
            `;

            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const curr = getCollectedUrls();
                const idx = curr.indexOf(cleanUrl);
                if (idx > -1) {
                    curr.splice(idx, 1);
                    btn.innerHTML = '+ Collect';
                    btn.style.background = '#2563eb';
                } else {
                    curr.push(cleanUrl);
                    btn.innerHTML = '✓ Added';
                    btn.style.background = '#10b981';
                }
                saveCollectedUrls(curr);
            });

            const titleHeader = card.querySelector('h2') || card;
            titleHeader.appendChild(btn);
        });
    }

    // Floating UI Bar
    function createFloatingUI() {
        if (document.getElementById('amz-collector-bar')) return;

        const bar = document.createElement('div');
        bar.id = 'amz-collector-bar';
        bar.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #0f172a;
            color: #fff;
            padding: 12px 18px;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            font-family: sans-serif;
            font-size: 13px;
            z-index: 999999;
            display: flex;
            align-items: center;
            gap: 12px;
            border: 1px solid #334155;
        `;

        bar.innerHTML = `
            <span id="amz-counter" style="font-weight:bold; color:#38bdf8;">🛒 0 URLs Collected</span>
            <button id="amz-btn-download" style="background:#10b981; color:#fff; border:none; padding:6px 12px; border-radius:6px; font-weight:bold; cursor:pointer;">📥 Export urls.txt</button>
            <button id="amz-btn-copy" style="background:#6366f1; color:#fff; border:none; padding:6px 12px; border-radius:6px; font-weight:bold; cursor:pointer;">📋 Copy</button>
            <button id="amz-btn-clear" style="background:#ef4444; color:#fff; border:none; padding:6px 10px; border-radius:6px; font-weight:bold; cursor:pointer;">🗑️ Clear</button>
        `;

        document.body.appendChild(bar);

        document.getElementById('amz-btn-download').addEventListener('click', downloadUrlsFile);
        document.getElementById('amz-btn-copy').addEventListener('click', copyUrlsToClipboard);
        document.getElementById('amz-btn-clear').addEventListener('click', () => {
            saveCollectedUrls([]);
            showToast('Cleared collected URLs');
        });

        updateFloatingUI();
    }

    function updateFloatingUI() {
        const urls = getCollectedUrls();
        const counter = document.getElementById('amz-counter');
        if (counter) {
            counter.textContent = `🛒 ${urls.length} URL${urls.length === 1 ? '' : 's'} Collected`;
        }
        injectCardBadges();
    }

    function downloadUrlsFile() {
        const urls = getCollectedUrls();
        if (urls.length === 0) {
            alert('No URLs collected yet! Middle-click product links or click "+ Collect" on search results.');
            return;
        }
        const textContent = urls.join('\n');
        const blob = new Blob([textContent], { type: 'text/plain' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'urls.txt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast('Downloaded urls.txt! Now run: python cli.py -f urls.txt');
    }

    function copyUrlsToClipboard() {
        const urls = getCollectedUrls();
        if (urls.length === 0) return;
        navigator.clipboard.writeText(urls.join('\n')).then(() => {
            showToast('Copied URLs to clipboard!');
        });
    }

    function showToast(msg) {
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            bottom: 75px;
            right: 20px;
            background: #1e293b;
            color: #38bdf8;
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 12px;
            z-index: 999999;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            border: 1px solid #0284c7;
        `;
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 2500);
    }

    // Initialize after DOM load & scroll
    window.addEventListener('load', () => {
        createFloatingUI();
        setInterval(injectCardBadges, 1500);
    });

})();
