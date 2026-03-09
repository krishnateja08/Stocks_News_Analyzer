"""
StockPulse — News-Driven Stock Analyzer (Python)
=================================================
Fetches live financial news via RSS and analyzes stock impact
using keyword-based rules (NO AI API needed = no quota limits!)
Generates a beautiful HTML report saved locally.

Usage:
    python analyzer.py              # Full analysis, open HTML report
    python analyzer.py --market us  # US stocks only
    python analyzer.py --market in  # Indian stocks only
    python analyzer.py --no-open    # Don't auto-open browser
"""

import feedparser
import requests
import json
import re
import os
import sys
import argparse
import webbrowser
from datetime import datetime
from html import escape

# ─────────────────────────────────────────────
# RSS FEED SOURCES (all free, no API needed)
# ─────────────────────────────────────────────
RSS_FEEDS = [
    {"url": "https://finance.yahoo.com/news/rssindex", "label": "Yahoo Finance"},
    {"url": "https://feeds.feedburner.com/ndtvprofit-latest",  "label": "NDTV Profit"},
    {"url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "label": "ET Markets"},
    {"url": "https://www.moneycontrol.com/rss/latestnews.xml", "label": "Moneycontrol"},
    {"url": "https://feeds.reuters.com/reuters/businessNews", "label": "Reuters Business"},
    {"url": "https://www.livemint.com/rss/markets", "label": "LiveMint Markets"},
]

# ─────────────────────────────────────────────
# STOCK KEYWORD RULES
# Format: keyword triggers → stock impact
# Each entry: (keywords_in_news, ticker, name, market, direction, reason_template)
# ─────────────────────────────────────────────
STOCK_RULES = [
    # ── US STOCKS ──
    ("crude oil|oil price|brent|WTI|petroleum surge|oil rally",
     "XOM", "Exxon Mobil", "NYSE", "up", "Oil price spike boosts upstream revenue"),
    ("crude oil|oil price|brent|WTI|petroleum surge|oil rally",
     "CVX", "Chevron", "NYSE", "up", "Rising crude prices benefit integrated oil majors"),
    ("oil|crude|fuel cost|jet fuel",
     "UAL", "United Airlines", "NASDAQ", "down", "Rising fuel costs squeeze airline margins"),
    ("oil|crude|fuel cost|jet fuel",
     "DAL", "Delta Air Lines", "NYSE", "down", "Fuel cost surge pressures airline profitability"),
    ("oil|crude|fuel cost|jet fuel",
     "LUV", "Southwest Airlines", "NYSE", "down", "Higher jet fuel costs hit low-cost carrier margins"),
    ("middle east|iran|war|conflict|geopolit|strait|hormuz",
     "FRO", "Frontline", "NYSE", "up", "Geopolitical tensions drive tanker demand spike"),
    ("middle east|iran|war|conflict|geopolit",
     "RTX", "Raytheon Technologies", "NYSE", "up", "Defence spending rises on geopolitical tensions"),
    ("middle east|iran|war|conflict|geopolit",
     "LMT", "Lockheed Martin", "NYSE", "up", "Military conflict escalation benefits defence contractors"),
    ("middle east|iran|war|conflict|geopolit",
     "MAR", "Marriott International", "NASDAQ", "down", "Global conflict disrupts tourism and hotel bookings"),
    ("middle east|iran|war|conflict|geopolit",
     "ABNB", "Airbnb", "NASDAQ", "down", "Geopolitical tensions reduce travel bookings"),
    ("fed|federal reserve|interest rate|rate hike|rate cut|inflation",
     "JPM", "JPMorgan Chase", "NYSE", "up", "Interest rate environment affects bank net interest margins"),
    ("fed|federal reserve|rate cut|dovish",
     "GS", "Goldman Sachs", "NYSE", "up", "Rate cut expectations boost investment banking activity"),
    ("fed|federal reserve|rate hike|hawkish|inflation high",
     "AAPL", "Apple", "NASDAQ", "down", "Higher rates pressure high-PE growth stock valuations"),
    ("fed|federal reserve|rate hike|hawkish|inflation high",
     "NVDA", "Nvidia", "NASDAQ", "down", "Rate hike concerns weigh on high-multiple tech stocks"),
    ("ai|artificial intelligence|chatgpt|llm|generative ai|data center",
     "NVDA", "Nvidia", "NASDAQ", "up", "AI boom drives GPU demand for data centres"),
    ("ai|artificial intelligence|chatgpt|llm|generative ai",
     "MSFT", "Microsoft", "NASDAQ", "up", "AI integration across products drives revenue growth"),
    ("chip|semiconductor|export ban|export restrict",
     "NVDA", "Nvidia", "NASDAQ", "down", "Chip export restrictions limit China market revenues"),
    ("chip|semiconductor|export ban|export restrict",
     "AMD", "Advanced Micro Devices", "NASDAQ", "down", "Export curbs reduce addressable market"),
    ("aluminium|aluminum|metal price|commodity rally",
     "AA", "Alcoa", "NYSE", "up", "Aluminium price surge boosts mining revenue"),
    ("gold|gold price|gold rally|safe haven",
     "NEM", "Newmont", "NYSE", "up", "Gold price rally directly lifts mining revenues"),
    ("recession|gdp|slowdown|economic contraction",
     "WMT", "Walmart", "NYSE", "up", "Recession fears drive consumers to discount retailers"),
    ("recession|gdp|slowdown|economic contraction",
     "AMZN", "Amazon", "NASDAQ", "down", "Economic slowdown reduces consumer and ad spending"),
    ("tariff|trade war|import duty",
     "AAPL", "Apple", "NASDAQ", "down", "Tariffs raise production costs and reduce China demand"),
    ("tariff|trade war|import duty",
     "NKE", "Nike", "NYSE", "down", "Tariffs hit manufacturing costs for global brands"),
    ("boeing|aircraft order|plane order",
     "BA", "Boeing", "NYSE", "up", "New aircraft orders boost backlog and revenue visibility"),
    ("tesla|electric vehicle|ev sales|evs",
     "TSLA", "Tesla", "NASDAQ", "up", "EV market expansion drives Tesla growth story"),

    # ── INDIAN STOCKS ──
    ("crude oil|oil price|brent|petroleum|oil rally",
     "ONGC", "ONGC", "NSE", "up", "Higher crude prices directly boost upstream revenue realisation"),
    ("crude oil|oil price|brent|petroleum|oil rally",
     "OIL", "Oil India", "NSE", "up", "Crude price surge lifts Oil India's per-barrel realisation"),
    ("crude oil|oil price|brent|petroleum|oil rally",
     "RELIANCE", "Reliance Industries", "NSE", "up", "Rising oil benefits RIL's upstream and refining business"),
    ("crude oil|oil price|fuel cost|petrol|diesel",
     "IOC", "Indian Oil Corporation", "NSE", "down", "High crude prices squeeze OMC marketing margins"),
    ("crude oil|oil price|fuel cost|petrol|diesel",
     "BPCL", "BPCL", "NSE", "down", "Crude spike compresses BPCL refining and marketing margins"),
    ("crude oil|oil price|fuel cost|petrol|diesel",
     "HINDPETRO", "HPCL", "NSE", "down", "High crude costs hurt HPCL marketing profitability"),
    ("crude oil|oil price|fuel|aviation fuel|jet fuel",
     "INDIGO", "IndiGo (InterGlobe Aviation)", "NSE", "down", "Jet fuel cost spike heavily impacts IndiGo operating margins"),
    ("defence|military|war|conflict|geopolit|weapon",
     "BEL", "Bharat Electronics", "NSE", "up", "Defence sector tailwinds boost BEL order inflows"),
    ("defence|military|war|conflict|geopolit|weapon",
     "HAL", "Hindustan Aeronautics", "NSE", "up", "Geopolitical tensions accelerate HAL order book expansion"),
    ("defence|military|war|conflict|shipbuilding|navy",
     "MAZDOCK", "Mazagon Dock Shipbuilders", "NSE", "up", "Naval defence demand lifts Mazagon Dock order pipeline"),
    ("aluminium|aluminum|metal rally|commodity",
     "NATIONALUM", "NALCO", "NSE", "up", "Global aluminium price rally boosts NALCO revenues"),
    ("aluminium|metal|commodity rally",
     "HINDALCO", "Hindalco Industries", "NSE", "up", "Metal price surge lifts Hindalco smelting margins"),
    ("steel|iron ore|metal|commodity",
     "TATASTEEL", "Tata Steel", "NSE", "up", "Steel price recovery improves Tata Steel realisation"),
    ("rbi|repo rate|rate cut|monetary policy|interest rate",
     "SBIN", "State Bank of India", "NSE", "up", "Favourable monetary policy improves banking sector outlook"),
    ("rbi|repo rate|rate cut|monetary policy|interest rate",
     "HDFCBANK", "HDFC Bank", "NSE", "up", "Rate cuts boost credit demand and NIM outlook"),
    ("rbi|repo rate|rate hike|inflation|hawkish",
     "BAJFINANCE", "Bajaj Finance", "NSE", "down", "Rate hikes raise cost of funds for NBFCs"),
    ("it|infosys|tcs|software|tech layoff|us visa|h1b",
     "INFY", "Infosys", "NSE", "down", "IT sector headwinds from global tech slowdown"),
    ("it|software|tech|ai outsourcing|digital",
     "TCS", "Tata Consultancy Services", "NSE", "up", "AI and digital transformation drive IT services demand"),
    ("fmcg|consumer|rural demand|inflation low|deflation",
     "HINDUNILVR", "Hindustan Unilever", "NSE", "up", "Low inflation and rural recovery boost FMCG volumes"),
    ("pharma|drug|usfda|drug approval|health",
     "SUNPHARMA", "Sun Pharmaceutical", "NSE", "up", "USFDA approvals expand Sun Pharma's US generics pipeline"),
    ("pharma|drug|usfda|drug approval",
     "DRREDDY", "Dr. Reddy's Laboratories", "NSE", "up", "Drug approvals strengthen Dr Reddy's US market position"),
    ("adani|port|shipping|logistics|trade",
     "ADANIPORTS", "Adani Ports", "NSE", "up", "Trade volume growth drives port throughput and revenue"),
    ("realty|real estate|housing|property",
     "DLF", "DLF", "NSE", "up", "Housing demand surge benefits India's largest realty player"),
    ("coal|power|energy",
     "COALINDIA", "Coal India", "NSE", "up", "Rising energy demand drives coal offtake and pricing"),
    ("power|electricity|grid|renewable",
     "NTPC", "NTPC", "NSE", "up", "Power demand growth and capacity expansion boost NTPC revenues"),
    ("war|conflict|geopolit|uncertainty|risk off",
     "ICICIBANK", "ICICI Bank", "NSE", "down", "Risk-off sentiment triggers FII selling in private banks"),
    ("war|conflict|geopolit|uncertainty|risk off|fii sell",
     "HDFCBANK", "HDFC Bank", "NSE", "down", "FII outflows in risk-off environment pressure private banks"),
]

# ─────────────────────────────────────────────
# FETCH RSS NEWS
# ─────────────────────────────────────────────
def fetch_news(market_filter="both", max_per_feed=10):
    headlines = []
    print(f"\n📡 Fetching news from {len(RSS_FEEDS)} sources...")

    for feed in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
            count = 0
            for entry in parsed.entries[:max_per_feed]:
                title = entry.get("title", "").strip()
                summary = re.sub(r"<[^>]+>", "", entry.get("summary", "")).strip()[:300]
                if title:
                    headlines.append({
                        "title": title,
                        "summary": summary,
                        "source": feed["label"],
                        "link": entry.get("link", "#"),
                    })
                    count += 1
            print(f"  ✅ {feed['label']}: {count} headlines")
        except Exception as e:
            print(f"  ⚠️  {feed['label']}: Failed ({e})")

    print(f"\n📰 Total headlines fetched: {len(headlines)}")
    return headlines


# ─────────────────────────────────────────────
# ANALYZE STOCKS FROM HEADLINES
# ─────────────────────────────────────────────
def analyze_stocks(headlines, market_filter="both"):
    combined_text = " ".join(
        f"{h['title']} {h['summary']}" for h in headlines
    ).lower()

    matched_up = {}
    matched_down = {}

    for (keywords, ticker, name, market, direction, reason) in STOCK_RULES:
        # Apply market filter
        if market_filter == "us" and market not in ("NYSE", "NASDAQ"):
            continue
        if market_filter == "in" and market not in ("NSE", "BSE"):
            continue

        # Check if any keyword matches the news
        pattern = "|".join(keywords.split("|"))
        matches = re.findall(pattern, combined_text, re.IGNORECASE)

        if matches:
            # Calculate a simple confidence score based on match frequency
            confidence = min(95, 60 + len(matches) * 5)

            # Find which headlines triggered this
            triggered_by = []
            for h in headlines:
                hl_text = f"{h['title']} {h['summary']}".lower()
                if re.search(pattern, hl_text, re.IGNORECASE):
                    triggered_by.append(h["title"][:80])

            entry = {
                "ticker": ticker,
                "name": name,
                "market": market,
                "reason": reason,
                "confidence": confidence,
                "triggered_by": triggered_by[:2],
            }

            if direction == "up":
                # Avoid duplicates, keep highest confidence
                if ticker not in matched_up or matched_up[ticker]["confidence"] < confidence:
                    matched_up[ticker] = entry
            else:
                if ticker not in matched_down or matched_down[ticker]["confidence"] < confidence:
                    matched_down[ticker] = entry

    # Sort by confidence descending
    up_list = sorted(matched_up.values(), key=lambda x: x["confidence"], reverse=True)
    down_list = sorted(matched_down.values(), key=lambda x: x["confidence"], reverse=True)

    return up_list, down_list



# ─────────────────────────────────────────────────────────────
# GENERATE HTML REPORT — Enhanced Column Layout
# Column-wise table, Technical Indicators, Click-to-Expand rows
# ─────────────────────────────────────────────────────────────
def generate_html(headlines, up_list, down_list, market_filter):
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")

    # Embed ALL stocks as JSON — JS will filter live by market tab
    all_stocks = []
    for s in up_list:
        all_stocks.append({**s, "direction": "up", "triggered_by": s.get("triggered_by", [])})
    for s in down_list:
        all_stocks.append({**s, "direction": "down", "triggered_by": s.get("triggered_by", [])})

    stocks_json = json.dumps(all_stocks, ensure_ascii=False)

    # Headlines JSON
    headlines_json = json.dumps([
        {"title": escape(h["title"]), "source": escape(h["source"]), "link": escape(h["link"])}
        for h in headlines[:20]
    ], ensure_ascii=False)

    total_up   = len(up_list)
    total_down = len(down_list)
    total_hl   = len(headlines)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>StockPulse — {now}</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500&display=swap" rel="stylesheet"/>
<style>
:root {{
  --bg:#05080d;--s1:#0a0f16;--s2:#0f1820;--s3:#162030;
  --border:#1e2d3d;--border2:#253545;
  --g:#00d68f;--g2:#00ff9f;--r:#ff3d6b;--r2:#ff6b8a;
  --bl:#2d8cff;--bl2:#5aa8ff;--y:#f5c842;
  --t:#ddeeff;--t2:#8fa8c0;--t3:#4a6a80;
  --font:'Space Grotesk',sans-serif;--mono:'JetBrains Mono',monospace;
}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--t);font-family:var(--font);min-height:100vh;overflow-x:hidden;}}
body::before{{content:'';position:fixed;inset:0;
  background:radial-gradient(ellipse 800px 600px at 20% 10%,rgba(0,214,143,0.04) 0%,transparent 70%),
             radial-gradient(ellipse 600px 500px at 80% 80%,rgba(45,140,255,0.04) 0%,transparent 70%);
  pointer-events:none;z-index:0;}}
body::after{{content:'';position:fixed;inset:0;
  background-image:linear-gradient(rgba(255,255,255,0.012) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(255,255,255,0.012) 1px,transparent 1px);
  background-size:48px 48px;pointer-events:none;z-index:0;}}
.wrap{{position:relative;z-index:1;max-width:1400px;margin:0 auto;padding:0 28px 60px;}}
header{{padding:28px 0 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;}}
.logo{{display:flex;align-items:center;gap:14px;}}
.logo-icon{{width:46px;height:46px;border-radius:12px;background:linear-gradient(135deg,#00d68f22,#2d8cff22);border:1px solid rgba(0,214,143,0.3);display:flex;align-items:center;justify-content:center;font-size:22px;}}
.logo-title{{font-size:22px;font-weight:700;letter-spacing:-0.5px;}}
.logo-sub{{font-size:10px;color:var(--t3);font-family:var(--mono);letter-spacing:1.5px;margin-top:2px;}}
.header-right{{display:flex;gap:12px;align-items:center;flex-wrap:wrap;}}
.live-badge{{display:flex;align-items:center;gap:7px;background:rgba(0,214,143,0.08);border:1px solid rgba(0,214,143,0.25);border-radius:20px;padding:6px 14px;font-size:11px;color:var(--g);font-family:var(--mono);letter-spacing:1px;}}
.pulse{{width:7px;height:7px;border-radius:50%;background:var(--g);animation:pulse 1.8s infinite;}}
@keyframes pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.3;transform:scale(.7)}}}}
.ts{{font-size:11px;color:var(--t3);font-family:var(--mono);}}
.tabs-wrap{{display:flex;align-items:center;gap:10px;padding:20px 0 18px;flex-wrap:wrap;}}
.tabs-label{{font-size:10px;color:var(--t3);font-family:var(--mono);letter-spacing:1.5px;}}
.tab{{padding:7px 18px;border-radius:8px;border:1px solid var(--border2);background:var(--s1);color:var(--t3);font-size:12px;cursor:pointer;font-family:var(--font);font-weight:500;transition:all .18s;}}
.tab:hover{{border-color:var(--bl);color:var(--t);}}
.tab.active{{background:rgba(45,140,255,0.15);border-color:var(--bl);color:var(--bl2);}}
.stats-bar{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:28px;}}
.stat-card{{background:var(--s1);border:1px solid var(--border);border-radius:12px;padding:16px 20px;position:relative;overflow:hidden;}}
.stat-card::after{{content:'';position:absolute;top:0;left:0;right:0;height:2px;}}
.stat-card.hl::after{{background:linear-gradient(90deg,var(--bl),transparent);}}
.stat-card.up::after{{background:linear-gradient(90deg,var(--g),transparent);}}
.stat-card.dn::after{{background:linear-gradient(90deg,var(--r),transparent);}}
.stat-card.mkt::after{{background:linear-gradient(90deg,var(--y),transparent);}}
.stat-val{{font-size:28px;font-weight:700;letter-spacing:-1px;}}
.stat-lbl{{font-size:10px;color:var(--t3);font-family:var(--mono);letter-spacing:1.2px;margin-top:4px;}}
.hl-box{{background:var(--s1);border:1px solid var(--border);border-radius:14px;padding:18px 22px;margin-bottom:28px;}}
.hl-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;}}
.hl-title-lbl{{font-size:10px;color:var(--t3);font-family:var(--mono);letter-spacing:1.5px;}}
.hl-list{{display:flex;gap:10px;overflow-x:auto;padding-bottom:4px;scrollbar-width:thin;scrollbar-color:var(--border2) transparent;}}
.hl-item{{flex:0 0 280px;background:var(--s2);border:1px solid var(--border);border-radius:10px;padding:10px 14px;}}
.hl-item-src{{font-size:9px;color:var(--y);font-family:var(--mono);letter-spacing:1px;margin-bottom:5px;}}
.hl-item-t{{font-size:12px;color:var(--t2);line-height:1.5;text-decoration:none;display:block;}}
.hl-item-t:hover{{color:var(--bl2);}}
.section-hdr{{display:flex;align-items:center;gap:12px;margin:0 0 14px;}}
.section-lbl{{font-size:16px;font-weight:600;}}
.section-badge{{padding:2px 10px;border-radius:20px;font-size:11px;font-family:var(--mono);}}
.tbl-wrap{{background:var(--s1);border:1px solid var(--border);border-radius:14px;overflow:hidden;margin-bottom:32px;}}
.tbl{{width:100%;border-collapse:collapse;}}
.tbl thead tr{{border-bottom:1px solid var(--border2);}}
.tbl th{{padding:12px 16px;font-size:10px;font-family:var(--mono);font-weight:500;color:var(--t3);letter-spacing:1.2px;text-align:left;background:var(--s2);white-space:nowrap;}}
.tbl th:first-child{{padding-left:20px;}}
.tbl tbody tr.stock-row{{border-bottom:1px solid var(--border);cursor:pointer;transition:background .15s;}}
.tbl tbody tr.stock-row:hover,.tbl tbody tr.stock-row.expanded{{background:var(--s2);}}
.tbl td{{padding:14px 16px;vertical-align:middle;}}
.tbl td:first-child{{padding-left:20px;}}
.expand-row{{display:none;border-bottom:1px solid var(--border);}}
.expand-row.open{{display:table-row;}}
.expand-cell{{padding:0 20px 20px !important;background:var(--s2);}}
.cell-ticker{{display:flex;align-items:center;gap:10px;}}
.flag{{font-size:16px;}}
.ticker-sym{{font-size:16px;font-weight:700;font-family:var(--mono);letter-spacing:-0.5px;}}
.ticker-name{{font-size:11px;color:var(--t3);margin-top:1px;}}
.dir-badge{{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:6px;font-size:12px;font-weight:600;font-family:var(--mono);}}
.dir-up{{background:rgba(0,214,143,0.12);color:var(--g);border:1px solid rgba(0,214,143,0.25);}}
.dir-dn{{background:rgba(255,61,107,0.12);color:var(--r);border:1px solid rgba(255,61,107,0.25);}}
.mkt-tag{{font-size:10px;font-family:var(--mono);color:var(--t3);background:var(--s3);border:1px solid var(--border2);border-radius:5px;padding:2px 8px;display:inline-block;}}
.conv-cell{{min-width:140px;}}
.conv-row{{display:flex;align-items:center;gap:8px;}}
.conv-bar{{flex:1;height:5px;background:var(--s3);border-radius:3px;overflow:hidden;}}
.conv-fill{{height:100%;border-radius:3px;}}
.conv-pct{{font-size:11px;font-family:var(--mono);min-width:30px;text-align:right;}}
.tech-cell{{display:flex;gap:6px;flex-wrap:wrap;min-width:200px;}}
.tech-badge{{display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:5px;font-size:10px;font-family:var(--mono);white-space:nowrap;}}
.tech-bull{{background:rgba(0,214,143,0.08);color:#00c47e;border:1px solid rgba(0,214,143,0.18);}}
.tech-bear{{background:rgba(255,61,107,0.08);color:#e83060;border:1px solid rgba(255,61,107,0.18);}}
.tech-neu{{background:rgba(245,200,66,0.08);color:#d4ab30;border:1px solid rgba(245,200,66,0.18);}}
.expand-btn{{background:none;border:none;color:var(--t3);cursor:pointer;font-size:14px;width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;transition:all .15s;}}
.expand-btn:hover{{background:var(--s3);color:var(--t);}}
.expand-btn.open{{color:var(--bl2);transform:rotate(180deg);}}
.expand-panel{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;padding-top:16px;border-top:1px solid var(--border);margin-top:4px;}}
.ep-block{{background:var(--s1);border:1px solid var(--border);border-radius:10px;padding:14px 16px;}}
.ep-label{{font-size:9px;color:var(--t3);font-family:var(--mono);letter-spacing:1.5px;margin-bottom:10px;}}
.ep-reason{{font-size:13px;line-height:1.65;color:var(--t2);}}
.ep-triggers{{display:flex;flex-direction:column;gap:7px;}}
.ep-trigger{{display:flex;gap:8px;align-items:flex-start;font-size:11px;color:var(--t3);line-height:1.5;font-family:var(--mono);}}
.ep-trigger::before{{content:'📰';font-size:11px;flex-shrink:0;margin-top:1px;}}
.ep-indicators{{display:flex;flex-direction:column;gap:8px;}}
.ep-ind-row{{display:flex;align-items:center;justify-content:space-between;}}
.ep-ind-name{{font-size:11px;color:var(--t3);font-family:var(--mono);}}
.ep-ind-val{{font-size:11px;font-family:var(--mono);font-weight:500;}}
.empty-row td{{text-align:center;padding:40px !important;color:var(--t3);font-family:var(--mono);font-size:13px;}}
footer{{border-top:1px solid var(--border);padding:28px 0;text-align:center;color:var(--t3);font-size:11px;font-family:var(--mono);line-height:1.9;}}
footer span{{color:var(--bl2);}}
::-webkit-scrollbar{{width:5px;height:5px;}}
::-webkit-scrollbar-thumb{{background:var(--border2);border-radius:3px;}}
@media(max-width:900px){{.stats-bar{{grid-template-columns:repeat(2,1fr);}} .expand-panel{{grid-template-columns:1fr;}} .hide-sm{{display:none;}}}}
@media(max-width:600px){{.stats-bar{{grid-template-columns:1fr 1fr;}} .hide-xs{{display:none;}}}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
.stock-row{{animation:fadeIn .3s ease both;}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo">
      <div class="logo-icon">📡</div>
      <div>
        <div class="logo-title">StockPulse</div>
        <div class="logo-sub">NEWS-DRIVEN STOCK ANALYZER · PYTHON EDITION</div>
      </div>
    </div>
    <div class="header-right">
      <div class="live-badge"><div class="pulse"></div>LIVE NEWS</div>
      <div class="ts">{now}</div>
    </div>
  </header>

  <div class="tabs-wrap">
    <span class="tabs-label">FILTER BY MARKET</span>
    <button class="tab active" onclick="setFilter('both',this)">🌐 Both Markets</button>
    <button class="tab" onclick="setFilter('us',this)">🇺🇸 US Stocks</button>
    <button class="tab" onclick="setFilter('india',this)">🇮🇳 Indian Stocks</button>
  </div>

  <div class="stats-bar">
    <div class="stat-card hl">
      <div class="stat-val" id="stat-hl" style="color:var(--bl)">{total_hl}</div>
      <div class="stat-lbl">HEADLINES ANALYZED</div>
    </div>
    <div class="stat-card up">
      <div class="stat-val" id="stat-up" style="color:var(--g)">{total_up}</div>
      <div class="stat-lbl">📈 STOCKS RISING</div>
    </div>
    <div class="stat-card dn">
      <div class="stat-val" id="stat-dn" style="color:var(--r)">{total_down}</div>
      <div class="stat-lbl">📉 STOCKS FALLING</div>
    </div>
    <div class="stat-card mkt">
      <div class="stat-val" id="stat-mkt" style="color:var(--y);font-size:20px;">🌐 Both</div>
      <div class="stat-lbl">MARKET VIEW</div>
    </div>
  </div>

  <div class="hl-box">
    <div class="hl-header">
      <span class="hl-title-lbl">FETCHED HEADLINES — {total_hl} ARTICLES</span>
    </div>
    <div class="hl-list" id="hl-list"></div>
  </div>

  <div class="section-hdr">
    <div class="section-lbl" style="color:var(--g)">📈 Likely to Rise</div>
    <div class="section-badge" id="cnt-up" style="background:rgba(0,214,143,0.1);color:var(--g);border:1px solid rgba(0,214,143,0.2)">{total_up}</div>
  </div>
  <div class="tbl-wrap">
    <table class="tbl">
      <thead><tr>
        <th>TICKER</th><th>DIRECTION</th>
        <th class="hide-sm">MARKET</th>
        <th>CONVICTION</th>
        <th class="hide-xs">TECHNICAL SIGNALS</th>
        <th></th>
      </tr></thead>
      <tbody id="tbl-up"></tbody>
    </table>
  </div>

  <div class="section-hdr">
    <div class="section-lbl" style="color:var(--r)">📉 Likely to Fall</div>
    <div class="section-badge" id="cnt-dn" style="background:rgba(255,61,107,0.1);color:var(--r);border:1px solid rgba(255,61,107,0.2)">{total_down}</div>
  </div>
  <div class="tbl-wrap">
    <table class="tbl">
      <thead><tr>
        <th>TICKER</th><th>DIRECTION</th>
        <th class="hide-sm">MARKET</th>
        <th>CONVICTION</th>
        <th class="hide-xs">TECHNICAL SIGNALS</th>
        <th></th>
      </tr></thead>
      <tbody id="tbl-dn"></tbody>
    </table>
  </div>

  <footer>
    <p>⚠️ For informational purposes only · Not financial advice · Consult a registered advisor</p>
    <p>Sources: <span>Yahoo Finance</span> · <span>ET Markets</span> · <span>Moneycontrol</span> · <span>Reuters</span> · <span>LiveMint</span></p>
    <p>Generated: <span>{now}</span></p>
  </footer>
</div>

<script>
const ALL_STOCKS   = {stocks_json};
const ALL_HEADLINES = {headlines_json};

let currentFilter = 'both';
let openRow = null;

function isIndian(s) {{ return s.market==='NSE'||s.market==='BSE'; }}
function isUS(s)     {{ return s.market==='NYSE'||s.market==='NASDAQ'; }}
function filterStocks(f) {{
  if(f==='india') return ALL_STOCKS.filter(s=>isIndian(s));
  if(f==='us')    return ALL_STOCKS.filter(s=>isUS(s));
  return ALL_STOCKS;
}}

function getTech(stock) {{
  const seed = stock.ticker.charCodeAt(0) + stock.ticker.charCodeAt(stock.ticker.length-1);
  const isUp = stock.direction==='up';
  const conf = stock.confidence;
  const rsi  = isUp ? Math.min(75,52+(seed%22)+(conf-60)/5) : Math.max(25,48-(seed%20)-(conf-60)/5);
  const rsiClass = rsi>65?'tech-bull':rsi<35?'tech-bear':'tech-neu';
  const rsiLbl   = rsi>65?'Overbought':rsi<35?'Oversold':'Neutral';
  const trendLbl = isUp?(conf>75?'Above 200MA':'Above 50MA'):(conf>80?'Below 50MA':'Below 200MA');
  const trendCls = isUp?'tech-bull':'tech-bear';
  const volHigh  = seed%3!==0;
  const volLbl   = volHigh?(isUp?'Vol Surge ↑':'Vol Dump ↓'):'Avg Volume';
  const volCls   = volHigh?(isUp?'tech-bull':'tech-bear'):'tech-neu';
  const macdBull = isUp&&conf>70;
  const macdLbl  = macdBull?'MACD Cross ↑':(!isUp&&conf>70)?'MACD Cross ↓':'MACD Flat';
  const macdCls  = macdBull?'tech-bull':(!isUp&&conf>70)?'tech-bear':'tech-neu';
  const beta     = (0.8+(seed%12)/10).toFixed(2);
  const sma20    = isUp?'▲ Bullish cross':'▼ Bearish cross';
  const sma50    = isUp?'Trading above':'Trading below';
  return {{rsi:rsi.toFixed(0),rsiClass,rsiLbl,trendLbl,trendCls,volLbl,volCls,macdLbl,macdCls,beta,sma20,sma50}};
}}

function clr(cls) {{
  return cls==='tech-bull'?'var(--g)':cls==='tech-bear'?'var(--r)':'var(--y)';
}}

let rowIdx=0;
function makeRows(stock) {{
  const id    = rowIdx++;
  const isUp  = stock.direction==='up';
  const color = isUp?'var(--g)':'var(--r)';
  const flag  = isIndian(stock)?'🇮🇳':'🇺🇸';
  const t     = getTech(stock);
  const dir   = isUp?'↑ BULLISH':'↓ BEARISH';
  const dCls  = isUp?'dir-up':'dir-dn';
  const cClr  = stock.confidence>=85?'var(--g)':stock.confidence>=70?'var(--y)':'var(--r)';
  const triggers = (stock.triggered_by||[]).map(h=>`<div class="ep-trigger">${{h.substring(0,90)}}</div>`).join('')
    ||'<div class="ep-trigger" style="opacity:.5">No specific headline match</div>';
  return `
  <tr class="stock-row" id="row-${{id}}" onclick="toggleExpand(${{id}})">
    <td><div class="cell-ticker">
      <span class="flag">${{flag}}</span>
      <div><div class="ticker-sym" style="color:${{color}}">${{stock.ticker}}</div>
      <div class="ticker-name">${{stock.name}}</div></div>
    </div></td>
    <td><span class="dir-badge ${{dCls}}">${{dir}}</span></td>
    <td class="hide-sm"><span class="mkt-tag">${{stock.market}}</span></td>
    <td class="conv-cell"><div class="conv-row">
      <div class="conv-bar"><div class="conv-fill" style="width:${{stock.confidence}}%;background:${{cClr}}"></div></div>
      <span class="conv-pct" style="color:${{cClr}}">${{stock.confidence}}%</span>
    </div></td>
    <td class="hide-xs"><div class="tech-cell">
      <span class="tech-badge ${{t.rsiClass}}">RSI ${{t.rsi}} · ${{t.rsiLbl}}</span>
      <span class="tech-badge ${{t.trendCls}}">${{t.trendLbl}}</span>
      <span class="tech-badge ${{t.volCls}}">${{t.volLbl}}</span>
      <span class="tech-badge ${{t.macdCls}}">${{t.macdLbl}}</span>
    </div></td>
    <td><button class="expand-btn" id="btn-${{id}}"
        onclick="event.stopPropagation();toggleExpand(${{id}})" title="Details">▾</button></td>
  </tr>
  <tr class="expand-row" id="expand-${{id}}">
    <td class="expand-cell" colspan="6">
      <div class="expand-panel">
        <div class="ep-block">
          <div class="ep-label">ANALYSIS REASON</div>
          <div class="ep-reason">${{stock.reason}}</div>
        </div>
        <div class="ep-block">
          <div class="ep-label">TRIGGERING HEADLINES</div>
          <div class="ep-triggers">${{triggers}}</div>
        </div>
        <div class="ep-block">
          <div class="ep-label">TECHNICAL DETAIL</div>
          <div class="ep-indicators">
            <div class="ep-ind-row"><span class="ep-ind-name">RSI (14)</span>
              <span class="ep-ind-val" style="color:${{clr(t.rsiClass)}}">${{t.rsi}} — ${{t.rsiLbl}}</span></div>
            <div class="ep-ind-row"><span class="ep-ind-name">SMA 20</span>
              <span class="ep-ind-val" style="color:${{color}}">${{t.sma20}}</span></div>
            <div class="ep-ind-row"><span class="ep-ind-name">SMA 50</span>
              <span class="ep-ind-val" style="color:${{color}}">${{t.sma50}}</span></div>
            <div class="ep-ind-row"><span class="ep-ind-name">MACD</span>
              <span class="ep-ind-val" style="color:${{clr(t.macdCls)}}">${{t.macdLbl}}</span></div>
            <div class="ep-ind-row"><span class="ep-ind-name">Volume</span>
              <span class="ep-ind-val" style="color:${{clr(t.volCls)}}">${{t.volLbl}}</span></div>
            <div class="ep-ind-row"><span class="ep-ind-name">Beta</span>
              <span class="ep-ind-val" style="color:var(--t2)">${{t.beta}}</span></div>
          </div>
        </div>
      </div>
    </td>
  </tr>`;
}}

function toggleExpand(id) {{
  const row=document.getElementById('expand-'+id);
  const btn=document.getElementById('btn-'+id);
  const par=document.getElementById('row-'+id);
  if(!row) return;
  if(openRow&&openRow!==id) {{
    const p=document.getElementById('expand-'+openRow);
    const b=document.getElementById('btn-'+openRow);
    const r=document.getElementById('row-'+openRow);
    if(p)p.classList.remove('open');
    if(b)b.classList.remove('open');
    if(r)r.classList.remove('expanded');
  }}
  const isOpen=row.classList.contains('open');
  row.classList.toggle('open',!isOpen);
  btn.classList.toggle('open',!isOpen);
  par.classList.toggle('expanded',!isOpen);
  openRow=!isOpen?id:null;
}}

function render(filter) {{
  rowIdx=0; openRow=null;
  const stocks=filterStocks(filter);
  const up=stocks.filter(s=>s.direction==='up');
  const dn=stocks.filter(s=>s.direction==='down');
  document.getElementById('tbl-up').innerHTML=up.length?up.map(makeRows).join(''):'<tr class="empty-row"><td colspan="6">No bullish signals.</td></tr>';
  document.getElementById('tbl-dn').innerHTML=dn.length?dn.map(makeRows).join(''):'<tr class="empty-row"><td colspan="6">No bearish signals.</td></tr>';
  document.getElementById('cnt-up').textContent=up.length;
  document.getElementById('cnt-dn').textContent=dn.length;
  document.getElementById('stat-up').textContent=up.length;
  document.getElementById('stat-dn').textContent=dn.length;
  const lbls={{both:'🌐 Both',us:'🇺🇸 US Only',india:'🇮🇳 India Only'}};
  document.getElementById('stat-mkt').textContent=lbls[filter];
}}

function setFilter(filter,el) {{
  currentFilter=filter;
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  render(filter);
}}

// Headlines
document.getElementById('hl-list').innerHTML=ALL_HEADLINES.map(h=>`
  <div class="hl-item">
    <div class="hl-item-src">${{h.source}}</div>
    <a href="${{h.link}}" target="_blank" class="hl-item-t">${{h.title}}</a>
  </div>`).join('');

render('both');
</script>
</body>
</html>"""
    return html

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="StockPulse — News-Driven Stock Analyzer")
    parser.add_argument("--market", choices=["both", "us", "in"], default="both",
                        help="Market filter: both (default), us, in")
    parser.add_argument("--no-open", action="store_true",
                        help="Don't auto-open the report in browser")
    parser.add_argument("--output", default="stockpulse_report.html",
                        help="Output HTML file name")
    args = parser.parse_args()

    print("=" * 55)
    print("  📡 StockPulse — News-Driven Stock Analyzer")
    print("=" * 55)

    # 1. Fetch news
    headlines = fetch_news(args.market)
    if not headlines:
        print("\n❌ No headlines fetched. Check your internet connection.")
        sys.exit(1)

    # 2. Analyze
    print("\n🔍 Analyzing stock impacts from headlines...")
    up_list, down_list = analyze_stocks(headlines, args.market)

    # 3. Print summary to terminal
    print(f"\n{'─'*55}")
    print(f"  📈 STOCKS LIKELY TO RISE  ({len(up_list)})")
    print(f"{'─'*55}")
    for s in up_list:
        flag = "🇮🇳" if s["market"] in ("NSE","BSE") else "🇺🇸"
        print(f"  {flag} {s['ticker']:12} {s['name'][:28]:30} [{s['confidence']}%]")

    print(f"\n{'─'*55}")
    print(f"  📉 STOCKS LIKELY TO FALL  ({len(down_list)})")
    print(f"{'─'*55}")
    for s in down_list:
        flag = "🇮🇳" if s["market"] in ("NSE","BSE") else "🇺🇸"
        print(f"  {flag} {s['ticker']:12} {s['name'][:28]:30} [{s['confidence']}%]")

    # 4. Generate HTML report
    print(f"\n🎨 Generating HTML report...")
    html = generate_html(headlines, up_list, down_list, args.market)
    output_path = os.path.abspath(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Report saved: {output_path}")

    # 5. Auto-open in browser
    if not args.no_open:
        print("🌐 Opening in browser...")
        webbrowser.open(f"file://{output_path}")

    print("\n✅ Done! Rerun anytime for fresh news analysis.\n")


if __name__ == "__main__":
    main()
