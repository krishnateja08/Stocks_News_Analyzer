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


# ─────────────────────────────────────────────
# GENERATE HTML REPORT (with interactive tabs)
# ─────────────────────────────────────────────
def generate_html(headlines, up_list, down_list, market_filter):
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")

    # Embed ALL stocks as JSON — JS will filter live by market tab
    all_stocks = []
    for s in up_list:
        all_stocks.append({**s, "direction": "up", "triggered_by": s.get("triggered_by", [])})
    for s in down_list:
        all_stocks.append({**s, "direction": "down", "triggered_by": s.get("triggered_by", [])})

    stocks_json = json.dumps(all_stocks, ensure_ascii=False)

    # Headlines HTML
    hl_items = "".join(f"""
        <div class="hl-item">
          <span class="hl-num">{str(i+1).zfill(2)}</span>
          <div>
            <a href="{escape(h['link'])}" target="_blank" class="hl-title">{escape(h['title'])}</a>
            <div class="hl-src">{escape(h['source'])}</div>
          </div>
        </div>""" for i, h in enumerate(headlines[:20]))

    total_up   = len(up_list)
    total_down = len(down_list)
    total_hl   = len(headlines)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>StockPulse — {now}</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet"/>
<style>
:root{{--bg:#080c10;--s:#0e1318;--s2:#141b22;--b:#1e2a34;--g:#00e5a0;--r:#ff4466;--bl:#3b8bff;--y:#f5c842;--t:#e8f0f7;--m:#5a7080;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--t);font-family:'DM Sans',sans-serif;min-height:100vh;}}
body::before{{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(59,139,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(59,139,255,0.03) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0;}}
.wrap{{position:relative;z-index:1;max-width:1280px;margin:0 auto;padding:0 24px;}}
header{{padding:28px 0 20px;border-bottom:1px solid var(--b);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;}}
.logo{{display:flex;align-items:center;gap:12px;}}
.logo-icon{{width:42px;height:42px;border-radius:10px;background:linear-gradient(135deg,var(--bl),var(--g));display:flex;align-items:center;justify-content:center;font-size:20px;}}
.logo-text{{font-family:'Syne',sans-serif;font-size:22px;font-weight:800;}}
.logo-sub{{font-size:11px;color:var(--m);font-family:'DM Mono',monospace;letter-spacing:1px;}}
.badge{{display:flex;align-items:center;gap:6px;background:rgba(0,229,160,0.1);border:1px solid rgba(0,229,160,0.3);border-radius:20px;padding:5px 12px;font-size:12px;color:var(--g);font-family:'DM Mono',monospace;}}
.dot{{width:7px;height:7px;border-radius:50%;background:var(--g);animation:pulse 1.5s infinite;}}
@keyframes pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.4;transform:scale(0.8)}}}}
.ts{{font-size:12px;color:var(--m);font-family:'DM Mono',monospace;}}

/* MARKET FILTER TABS */
.tabs-wrap{{display:flex;align-items:center;gap:10px;padding:20px 0 16px;flex-wrap:wrap;}}
.tabs-label{{font-size:11px;color:var(--m);font-family:'DM Mono',monospace;letter-spacing:1px;margin-right:4px;}}
.tab{{padding:8px 20px;border-radius:8px;border:1px solid var(--b);background:var(--s);color:var(--m);
      font-size:13px;cursor:pointer;font-family:'Syne',sans-serif;font-weight:600;transition:all .2s;}}
.tab:hover{{border-color:var(--bl);color:var(--t);}}
.tab.active{{background:var(--bl);border-color:var(--bl);color:#fff;}}

/* STATS ROW */
.stats{{display:flex;gap:14px;margin-bottom:24px;flex-wrap:wrap;}}
.stat{{flex:1;min-width:130px;background:var(--s);border:1px solid var(--b);border-radius:12px;padding:14px 16px;}}
.stat-val{{font-family:'Syne',sans-serif;font-size:26px;font-weight:800;}}
.stat-lbl{{font-size:11px;color:var(--m);font-family:'DM Mono',monospace;margin-top:3px;}}

.section-hdr{{display:flex;align-items:center;gap:12px;margin-bottom:16px;margin-top:28px;}}
.section-lbl{{font-family:'Syne',sans-serif;font-size:18px;font-weight:800;}}
.section-cnt{{padding:2px 10px;border-radius:20px;font-size:12px;font-family:'DM Mono',monospace;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;margin-bottom:32px;}}
.card{{border-radius:14px;padding:18px 20px;border:1px solid;transition:transform .2s,box-shadow .2s;}}
.card:hover{{transform:translateY(-3px);box-shadow:0 8px 30px rgba(0,0,0,0.3);}}
.card-top{{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:10px;}}
.ticker{{font-family:'Syne',sans-serif;font-size:20px;font-weight:800;}}
.cname{{font-size:13px;color:var(--m);margin-bottom:4px;}}
.mkt-badge{{font-size:10px;font-family:'DM Mono',monospace;color:var(--m);background:var(--s2);
            border:1px solid var(--b);border-radius:20px;padding:2px 8px;display:inline-block;margin-bottom:10px;}}
.arrow{{width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;}}
.reason{{font-size:13px;line-height:1.6;color:#b0bec8;border-top:1px solid var(--b);padding-top:12px;margin-bottom:8px;}}
.trigger{{font-size:11px;color:var(--m);font-family:'DM Mono',monospace;margin-top:4px;line-height:1.5;}}
.conf-row{{display:flex;align-items:center;gap:8px;margin-top:12px;}}
.conf-label{{font-size:10px;color:var(--m);font-family:'DM Mono',monospace;}}
.conf-bar{{flex:1;height:4px;background:var(--b);border-radius:2px;overflow:hidden;}}
.conf-fill{{height:100%;border-radius:2px;transition:width .6s;}}
.conf-pct{{font-size:10px;font-family:'DM Mono',monospace;}}
.empty{{color:var(--m);padding:28px 20px;font-size:14px;font-family:'DM Mono',monospace;}}
.hl-box{{background:var(--s);border:1px solid var(--b);border-radius:12px;padding:16px 20px;margin-bottom:24px;}}
.hl-box h3{{font-size:11px;color:var(--m);font-family:'DM Mono',monospace;letter-spacing:1px;margin-bottom:12px;}}
.hl-list{{max-height:200px;overflow-y:auto;display:flex;flex-direction:column;gap:8px;}}
.hl-item{{display:flex;gap:10px;background:var(--s2);border-radius:8px;padding:8px 12px;}}
.hl-num{{color:var(--m);font-family:'DM Mono',monospace;font-size:11px;min-width:22px;margin-top:2px;}}
.hl-title{{font-size:13px;color:var(--t);text-decoration:none;line-height:1.5;}}
.hl-title:hover{{color:var(--bl);}}
.hl-src{{font-size:10px;color:var(--y);font-family:'DM Mono',monospace;margin-top:3px;}}
footer{{border-top:1px solid var(--b);padding:24px 0;text-align:center;color:var(--m);font-size:12px;font-family:'DM Mono',monospace;}}
footer span{{color:var(--bl);}}
::-webkit-scrollbar{{width:5px;}}
::-webkit-scrollbar-thumb{{background:var(--b);border-radius:3px;}}
</style>
</head>
<body>
<div class="wrap">

  <header>
    <div class="logo">
      <div class="logo-icon">📡</div>
      <div>
        <div class="logo-text">StockPulse</div>
        <div class="logo-sub">NEWS-DRIVEN STOCK ANALYZER · PYTHON EDITION</div>
      </div>
    </div>
    <div style="display:flex;gap:12px;align-items:center;">
      <div class="badge"><div class="dot"></div>LIVE NEWS</div>
      <div class="ts">{now}</div>
    </div>
  </header>

  <!-- INTERACTIVE MARKET FILTER TABS -->
  <div class="tabs-wrap">
    <span class="tabs-label">FILTER BY MARKET</span>
    <button class="tab active" onclick="setFilter('both', this)">🌐 Both Markets</button>
    <button class="tab" onclick="setFilter('us', this)">🇺🇸 US Stocks</button>
    <button class="tab" onclick="setFilter('india', this)">🇮🇳 Indian Stocks</button>
  </div>

  <!-- DYNAMIC STATS -->
  <div class="stats">
    <div class="stat">
      <div class="stat-val" id="stat-hl" style="color:var(--bl)">{total_hl}</div>
      <div class="stat-lbl">HEADLINES ANALYZED</div>
    </div>
    <div class="stat">
      <div class="stat-val" id="stat-up" style="color:var(--g)">{total_up}</div>
      <div class="stat-lbl">📈 STOCKS RISING</div>
    </div>
    <div class="stat">
      <div class="stat-val" id="stat-down" style="color:var(--r)">{total_down}</div>
      <div class="stat-lbl">📉 STOCKS FALLING</div>
    </div>
    <div class="stat">
      <div class="stat-val" id="stat-mkt" style="color:var(--y)">🌐</div>
      <div class="stat-lbl">MARKET VIEW</div>
    </div>
  </div>

  <!-- HEADLINES -->
  <div class="hl-box">
    <h3>FETCHED HEADLINES — {total_hl} ARTICLES</h3>
    <div class="hl-list">{hl_items}</div>
  </div>

  <!-- RISING STOCKS -->
  <div class="section-hdr">
    <div class="section-lbl" style="color:var(--g)">📈 Likely to Rise</div>
    <div class="section-cnt" id="cnt-up" style="background:rgba(0,229,160,0.12);color:var(--g)">{total_up}</div>
  </div>
  <div class="grid" id="grid-up"></div>

  <!-- FALLING STOCKS -->
  <div class="section-hdr">
    <div class="section-lbl" style="color:var(--r)">📉 Likely to Fall</div>
    <div class="section-cnt" id="cnt-down" style="background:rgba(255,68,102,0.12);color:var(--r)">{total_down}</div>
  </div>
  <div class="grid" id="grid-down"></div>

  <footer>
    <p>⚠️ For informational purposes only · Not financial advice · Consult a registered advisor</p>
    <p style="margin-top:6px">Sources: <span>Yahoo Finance</span> · <span>ET Markets</span> · <span>Moneycontrol</span> · <span>Reuters</span> · <span>LiveMint</span></p>
    <p style="margin-top:6px">Generated: <span>{now}</span></p>
  </footer>
</div>

<script>
// All stock data embedded by Python at build time
const ALL_STOCKS = {stocks_json};

let currentFilter = 'both';

function isIndian(s) {{
  return s.market === 'NSE' || s.market === 'BSE';
}}
function isUS(s) {{
  return s.market === 'NYSE' || s.market === 'NASDAQ';
}}

function filterStocks(filter) {{
  if (filter === 'india') return ALL_STOCKS.filter(s => isIndian(s));
  if (filter === 'us')    return ALL_STOCKS.filter(s => isUS(s));
  return ALL_STOCKS;
}}

function makeCard(s) {{
  const isUp    = s.direction === 'up';
  const color   = isUp ? '#00e5a0' : '#ff4466';
  const bg      = isUp ? 'rgba(0,229,160,0.06)' : 'rgba(255,68,102,0.06)';
  const border  = isUp ? 'rgba(0,229,160,0.25)' : 'rgba(255,68,102,0.25)';
  const arrowBg = isUp ? 'rgba(0,229,160,0.12)' : 'rgba(255,68,102,0.12)';
  const arrow   = isUp ? '↑' : '↓';
  const flag    = isIndian(s) ? '🇮🇳' : '🇺🇸';
  const conf    = s.confidence;
  const triggers = (s.triggered_by || [])
    .map(t => `<div class="trigger">📰 ${{t.substring(0,90)}}</div>`).join('');

  return `
  <div class="card" style="border-color:${{border}};background:linear-gradient(135deg,#0e1318,${{bg}})">
    <div class="card-top">
      <div>
        <div class="ticker" style="color:${{color}}">${{s.ticker}}</div>
        <div class="cname">${{s.name}}</div>
        <div class="mkt-badge">${{flag}} ${{s.market}}</div>
      </div>
      <div class="arrow" style="background:${{arrowBg}};color:${{color}}">${{arrow}}</div>
    </div>
    <div class="reason">${{s.reason}}</div>
    ${{triggers}}
    <div class="conf-row">
      <span class="conf-label">CONVICTION</span>
      <div class="conf-bar"><div class="conf-fill" style="width:${{conf}}%;background:${{color}}"></div></div>
      <span class="conf-pct" style="color:${{color}}">${{conf}}%</span>
    </div>
  </div>`;
}}

function render(filter) {{
  const stocks = filterStocks(filter);
  const upStocks   = stocks.filter(s => s.direction === 'up');
  const downStocks = stocks.filter(s => s.direction === 'down');

  const upGrid   = document.getElementById('grid-up');
  const downGrid = document.getElementById('grid-down');

  upGrid.innerHTML   = upStocks.length   ? upStocks.map(makeCard).join('')
    : '<div class="empty">No bullish signals for this market view.</div>';
  downGrid.innerHTML = downStocks.length ? downStocks.map(makeCard).join('')
    : '<div class="empty">No bearish signals for this market view.</div>';

  document.getElementById('cnt-up').textContent   = upStocks.length;
  document.getElementById('cnt-down').textContent = downStocks.length;
  document.getElementById('stat-up').textContent  = upStocks.length;
  document.getElementById('stat-down').textContent= downStocks.length;

  const labels = {{ both:'🌐 Both', us:'🇺🇸 US Only', india:'🇮🇳 India Only' }};
  document.getElementById('stat-mkt').textContent = labels[filter] || '🌐';
}}

function setFilter(filter, el) {{
  currentFilter = filter;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  render(filter);
}}

// Initial render
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
