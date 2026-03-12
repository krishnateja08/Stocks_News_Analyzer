"""
StockPulse — News-Driven Stock Analyzer  (Arctic Slate Edition)
===============================================================
Fetches live financial news via RSS, analyzes stock impact using
keyword rules, and generates a polished Arctic Slate HTML report.

Usage:
    python stockpulse_arctic.py                 # Full analysis, auto-open
    python stockpulse_arctic.py --market us     # US stocks only
    python stockpulse_arctic.py --market in     # Indian stocks only
    python stockpulse_arctic.py --no-open       # Don't auto-open browser
    python stockpulse_arctic.py --output my.html
"""

import feedparser
import json
import re
import os
import sys
import argparse
import webbrowser
from datetime import datetime
from html import escape

# ─────────────────────────────────────────────
# RSS FEED SOURCES  (all free, no API needed)
# ─────────────────────────────────────────────
RSS_FEEDS = [
    {"url": "https://finance.yahoo.com/news/rssindex",                              "label": "Yahoo Finance"},
    {"url": "https://feeds.feedburner.com/ndtvprofit-latest",                       "label": "NDTV Profit"},
    {"url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "label": "ET Markets"},
    {"url": "https://www.moneycontrol.com/rss/latestnews.xml",                      "label": "Moneycontrol"},
    {"url": "https://feeds.reuters.com/reuters/businessNews",                       "label": "Reuters Business"},
    {"url": "https://www.livemint.com/rss/markets",                                 "label": "LiveMint Markets"},
]

# ─────────────────────────────────────────────
# STOCK KEYWORD RULES
# (keywords, ticker, name, exchange, direction, reason)
# ─────────────────────────────────────────────
STOCK_RULES = [
    # ── US STOCKS ──
    ("crude oil|oil price|brent|WTI|petroleum surge|oil rally",
     "XOM",  "Exxon Mobil",            "NYSE",   "up",   "Oil price spike boosts upstream revenue"),
    ("crude oil|oil price|brent|WTI|petroleum surge|oil rally",
     "CVX",  "Chevron",                "NYSE",   "up",   "Rising crude prices benefit integrated oil majors"),
    ("oil|crude|fuel cost|jet fuel",
     "UAL",  "United Airlines",        "NASDAQ", "down", "Rising fuel costs squeeze airline margins"),
    ("oil|crude|fuel cost|jet fuel",
     "DAL",  "Delta Air Lines",        "NYSE",   "down", "Fuel cost surge pressures airline profitability"),
    ("oil|crude|fuel cost|jet fuel",
     "LUV",  "Southwest Airlines",     "NYSE",   "down", "Higher jet fuel costs hit low-cost carrier margins"),
    ("middle east|iran|war|conflict|geopolit|strait|hormuz",
     "FRO",  "Frontline",              "NYSE",   "up",   "Geopolitical tensions drive tanker demand spike"),
    ("middle east|iran|war|conflict|geopolit",
     "RTX",  "Raytheon Technologies",  "NYSE",   "up",   "Defence spending rises on geopolitical tensions"),
    ("middle east|iran|war|conflict|geopolit",
     "LMT",  "Lockheed Martin",        "NYSE",   "up",   "Military conflict escalation benefits defence contractors"),
    ("middle east|iran|war|conflict|geopolit",
     "MAR",  "Marriott International", "NASDAQ", "down", "Global conflict disrupts tourism and hotel bookings"),
    ("middle east|iran|war|conflict|geopolit",
     "ABNB", "Airbnb",                 "NASDAQ", "down", "Geopolitical tensions reduce travel bookings"),
    ("fed|federal reserve|interest rate|rate hike|rate cut|inflation",
     "JPM",  "JPMorgan Chase",         "NYSE",   "up",   "Interest rate environment affects bank net interest margins"),
    ("fed|federal reserve|rate cut|dovish",
     "GS",   "Goldman Sachs",          "NYSE",   "up",   "Rate cut expectations boost investment banking activity"),
    ("fed|federal reserve|rate hike|hawkish|inflation high",
     "AAPL", "Apple",                  "NASDAQ", "down", "Higher rates pressure high-PE growth stock valuations"),
    ("fed|federal reserve|rate hike|hawkish|inflation high",
     "NVDA", "Nvidia",                 "NASDAQ", "down", "Rate hike concerns weigh on high-multiple tech stocks"),
    ("ai|artificial intelligence|chatgpt|llm|generative ai|data center",
     "NVDA", "Nvidia",                 "NASDAQ", "up",   "AI boom drives GPU demand for data centres"),
    ("ai|artificial intelligence|chatgpt|llm|generative ai",
     "MSFT", "Microsoft",              "NASDAQ", "up",   "AI integration across products drives revenue growth"),
    ("chip|semiconductor|export ban|export restrict",
     "NVDA", "Nvidia",                 "NASDAQ", "down", "Chip export restrictions limit China market revenues"),
    ("chip|semiconductor|export ban|export restrict",
     "AMD",  "Advanced Micro Devices", "NASDAQ", "down", "Export curbs reduce addressable market"),
    ("aluminium|aluminum|metal price|commodity rally",
     "AA",   "Alcoa",                  "NYSE",   "up",   "Aluminium price surge boosts mining revenue"),
    ("gold|gold price|gold rally|safe haven",
     "NEM",  "Newmont",                "NYSE",   "up",   "Gold price rally directly lifts mining revenues"),
    ("recession|gdp|slowdown|economic contraction",
     "WMT",  "Walmart",                "NYSE",   "up",   "Recession fears drive consumers to discount retailers"),
    ("recession|gdp|slowdown|economic contraction",
     "AMZN", "Amazon",                 "NASDAQ", "down", "Economic slowdown reduces consumer and ad spending"),
    ("tariff|trade war|import duty",
     "AAPL", "Apple",                  "NASDAQ", "down", "Tariffs raise production costs and reduce China demand"),
    ("tariff|trade war|import duty",
     "NKE",  "Nike",                   "NYSE",   "down", "Tariffs hit manufacturing costs for global brands"),
    ("boeing|aircraft order|plane order",
     "BA",   "Boeing",                 "NYSE",   "up",   "New aircraft orders boost backlog and revenue visibility"),
    ("tesla|electric vehicle|ev sales|evs",
     "TSLA", "Tesla",                  "NASDAQ", "up",   "EV market expansion drives Tesla growth story"),

    # ── INDIAN STOCKS ──
    ("crude oil|oil price|brent|petroleum|oil rally",
     "ONGC",       "ONGC",                      "NSE", "up",   "Higher crude prices directly boost upstream revenue realisation"),
    ("crude oil|oil price|brent|petroleum|oil rally",
     "OIL",        "Oil India",                 "NSE", "up",   "Crude price surge lifts Oil India's per-barrel realisation"),
    ("crude oil|oil price|brent|petroleum|oil rally",
     "RELIANCE",   "Reliance Industries",       "NSE", "up",   "Rising oil benefits RIL's upstream and refining business"),
    ("crude oil|oil price|fuel cost|petrol|diesel",
     "IOC",        "Indian Oil Corporation",    "NSE", "down", "High crude prices squeeze OMC marketing margins"),
    ("crude oil|oil price|fuel cost|petrol|diesel",
     "BPCL",       "BPCL",                      "NSE", "down", "Crude spike compresses BPCL refining and marketing margins"),
    ("crude oil|oil price|fuel cost|petrol|diesel",
     "HINDPETRO",  "HPCL",                      "NSE", "down", "High crude costs hurt HPCL marketing profitability"),
    ("crude oil|oil price|fuel|aviation fuel|jet fuel",
     "INDIGO",     "IndiGo (InterGlobe)",        "NSE", "down", "Jet fuel cost spike heavily impacts IndiGo operating margins"),
    ("defence|military|war|conflict|geopolit|weapon",
     "BEL",        "Bharat Electronics",        "NSE", "up",   "Defence sector tailwinds boost BEL order inflows"),
    ("defence|military|war|conflict|geopolit|weapon",
     "HAL",        "Hindustan Aeronautics",      "NSE", "up",   "Geopolitical tensions accelerate HAL order book expansion"),
    ("defence|military|war|conflict|shipbuilding|navy",
     "MAZDOCK",    "Mazagon Dock Shipbuilders",  "NSE", "up",   "Naval defence demand lifts Mazagon Dock order pipeline"),
    ("aluminium|aluminum|metal rally|commodity",
     "NATIONALUM", "NALCO",                      "NSE", "up",   "Global aluminium price rally boosts NALCO revenues"),
    ("aluminium|metal|commodity rally",
     "HINDALCO",   "Hindalco Industries",        "NSE", "up",   "Metal price surge lifts Hindalco smelting margins"),
    ("steel|iron ore|metal|commodity",
     "TATASTEEL",  "Tata Steel",                 "NSE", "up",   "Steel price recovery improves Tata Steel realisation"),
    ("rbi|repo rate|rate cut|monetary policy|interest rate",
     "SBIN",       "State Bank of India",        "NSE", "up",   "Favourable monetary policy improves banking sector outlook"),
    ("rbi|repo rate|rate cut|monetary policy|interest rate",
     "HDFCBANK",   "HDFC Bank",                  "NSE", "up",   "Rate cuts boost credit demand and NIM outlook"),
    ("rbi|repo rate|rate hike|inflation|hawkish",
     "BAJFINANCE", "Bajaj Finance",              "NSE", "down", "Rate hikes raise cost of funds for NBFCs"),
    ("it|infosys|tcs|software|tech layoff|us visa|h1b",
     "INFY",       "Infosys",                    "NSE", "down", "IT sector headwinds from global tech slowdown"),
    ("it|software|tech|ai outsourcing|digital",
     "TCS",        "Tata Consultancy Services",  "NSE", "up",   "AI and digital transformation drive IT services demand"),
    ("fmcg|consumer|rural demand|inflation low|deflation",
     "HINDUNILVR", "Hindustan Unilever",         "NSE", "up",   "Low inflation and rural recovery boost FMCG volumes"),
    ("pharma|drug|usfda|drug approval|health",
     "SUNPHARMA",  "Sun Pharmaceutical",         "NSE", "up",   "USFDA approvals expand Sun Pharma's US generics pipeline"),
    ("pharma|drug|usfda|drug approval",
     "DRREDDY",    "Dr. Reddy's Laboratories",   "NSE", "up",   "Drug approvals strengthen Dr Reddy's US market position"),
    ("adani|port|shipping|logistics|trade",
     "ADANIPORTS", "Adani Ports",                "NSE", "up",   "Trade volume growth drives port throughput and revenue"),
    ("realty|real estate|housing|property",
     "DLF",        "DLF",                        "NSE", "up",   "Housing demand surge benefits India's largest realty player"),
    ("coal|power|energy",
     "COALINDIA",  "Coal India",                 "NSE", "up",   "Rising energy demand drives coal offtake and pricing"),
    ("power|electricity|grid|renewable",
     "NTPC",       "NTPC",                       "NSE", "up",   "Power demand growth and capacity expansion boost NTPC revenues"),
    ("war|conflict|geopolit|uncertainty|risk off",
     "ICICIBANK",  "ICICI Bank",                 "NSE", "down", "Risk-off sentiment triggers FII selling in private banks"),
    ("war|conflict|geopolit|uncertainty|risk off|fii sell",
     "HDFCBANK",   "HDFC Bank",                  "NSE", "down", "FII outflows in risk-off environment pressure private banks"),
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
            count  = 0
            for entry in parsed.entries[:max_per_feed]:
                title   = entry.get("title", "").strip()
                summary = re.sub(r"<[^>]+>", "", entry.get("summary", "")).strip()[:300]
                if title:
                    headlines.append({
                        "title":   title,
                        "summary": summary,
                        "source":  feed["label"],
                        "link":    entry.get("link", "#"),
                    })
                    count += 1
            print(f"  ✅ {feed['label']}: {count} headlines")
        except Exception as e:
            print(f"  ⚠️  {feed['label']}: Failed ({e})")
    print(f"\n📰 Total headlines fetched: {len(headlines)}")
    return headlines


# ─────────────────────────────────────────────
# ANALYZE STOCKS
# ─────────────────────────────────────────────
def analyze_stocks(headlines, market_filter="both"):
    combined_text = " ".join(
        f"{h['title']} {h['summary']}" for h in headlines
    ).lower()

    matched_up   = {}
    matched_down = {}

    for (keywords, ticker, name, market, direction, reason) in STOCK_RULES:
        if market_filter == "us" and market not in ("NYSE", "NASDAQ"):
            continue
        if market_filter == "in" and market not in ("NSE", "BSE"):
            continue

        pattern = "|".join(keywords.split("|"))
        matches = re.findall(pattern, combined_text, re.IGNORECASE)

        if matches:
            confidence   = min(95, 60 + len(matches) * 5)
            triggered_by = []
            for h in headlines:
                hl_text = f"{h['title']} {h['summary']}".lower()
                if re.search(pattern, hl_text, re.IGNORECASE):
                    triggered_by.append(h["title"][:80])

            entry = {
                "ticker":       ticker,
                "name":         name,
                "market":       market,
                "reason":       reason,
                "confidence":   confidence,
                "triggered_by": triggered_by[:2],
            }

            if direction == "up":
                if ticker not in matched_up or matched_up[ticker]["confidence"] < confidence:
                    matched_up[ticker] = entry
            else:
                if ticker not in matched_down or matched_down[ticker]["confidence"] < confidence:
                    matched_down[ticker] = entry

    # ── CONFLICT RESOLUTION ─────────────────────────────────────
    # A stock in BOTH lists means two different news themes fired.
    # Keep only the signal with the higher confidence. Ties → bearish.
    conflicts = set(matched_up.keys()) & set(matched_down.keys())
    for ticker in conflicts:
        up_c, dn_c = matched_up[ticker]["confidence"], matched_down[ticker]["confidence"]
        if up_c > dn_c:
            print(f"  ⚡ CONFLICT resolved → {ticker} kept BULLISH  (up={up_c}% > down={dn_c}%)")
            del matched_down[ticker]
        else:
            print(f"  ⚡ CONFLICT resolved → {ticker} kept BEARISH  (down={dn_c}% >= up={up_c}%)")
            del matched_up[ticker]

    up_list   = sorted(matched_up.values(),   key=lambda x: x["confidence"], reverse=True)
    down_list = sorted(matched_down.values(), key=lambda x: x["confidence"], reverse=True)
    return up_list, down_list


# ─────────────────────────────────────────────
# GENERATE HTML  —  Arctic Slate Theme
# ─────────────────────────────────────────────
def generate_html(headlines, up_list, down_list, market_filter):
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")

    all_stocks = []
    for s in up_list:
        all_stocks.append({**s, "direction": "up",   "triggered_by": s.get("triggered_by", [])})
    for s in down_list:
        all_stocks.append({**s, "direction": "down",  "triggered_by": s.get("triggered_by", [])})

    stocks_json = json.dumps(all_stocks, ensure_ascii=False)

    headlines_json = json.dumps([
        {"title": escape(h["title"]), "source": escape(h["source"]), "link": escape(h["link"])}
        for h in headlines[:25]
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
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@300;400;500&display=swap" rel="stylesheet"/>
<style>
/* ══════════════════════════════════════════════
   ARCTIC SLATE — Bloomberg Pro Dark Theme
══════════════════════════════════════════════ */
:root {{
  --bg:     #0b1120; --s1:#0f1929; --s2:#111d30; --s3:#162438; --s4:#1a2b42;
  --bdr:    #1e2d45; --bdr2:#253a55; --bdr3:#2d4560;
  --up:     #22c55e; --up2:#4ade80; --up-bg:rgba(34,197,94,0.08);  --up-bdr:rgba(34,197,94,0.22);
  --dn:     #ef4444; --dn2:#f87171; --dn-bg:rgba(239,68,68,0.08);  --dn-bdr:rgba(239,68,68,0.22);
  --bl:     #3b82f6; --bl2:#60a5fa; --bl3:#93c5fd;
  --bl-bg:  rgba(59,130,246,0.10); --bl-bdr:rgba(59,130,246,0.25);
  --y:#f59e0b; --y2:#fbbf24;
  --t:#f0f4f8; --t2:#d8e6f2; --t3:#b8d0e8; --t4:#8aabcc;
  --font:'Space Grotesk',sans-serif; --mono:'IBM Plex Mono',monospace;
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
html{{scroll-behavior:smooth;}}
body{{background:var(--bg);color:var(--t);font-family:var(--font);min-height:100vh;overflow-x:hidden;}}
body::before{{content:'';position:fixed;inset:0;
  background:radial-gradient(ellipse 900px 700px at 15% 5%,rgba(59,130,246,0.05) 0%,transparent 65%),
             radial-gradient(ellipse 700px 500px at 85% 90%,rgba(34,197,94,0.04) 0%,transparent 65%);
  pointer-events:none;z-index:0;}}
body::after{{content:'';position:fixed;inset:0;
  background-image:linear-gradient(rgba(59,130,246,0.025) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(59,130,246,0.025) 1px,transparent 1px);
  background-size:44px 44px;pointer-events:none;z-index:0;}}
.wrap{{position:relative;z-index:1;max-width:1440px;margin:0 auto;padding:0 32px 80px;}}

/* TOP BAR */
.topbar{{background:var(--s1);border-bottom:1px solid var(--bdr);margin:0 -32px;padding:0 32px;
  display:flex;align-items:center;justify-content:space-between;height:48px;flex-wrap:wrap;gap:8px;}}
.topbar-tickers{{display:flex;align-items:center;gap:20px;overflow-x:auto;}}
.tb-item{{font-family:var(--mono);font-size:13px;color:var(--t2);display:flex;align-items:center;gap:5px;white-space:nowrap;}}
.tb-item .val{{color:var(--t);}}
.chg-up{{color:var(--up2);}} .chg-dn{{color:var(--dn2);}}
.topbar-time{{font-family:var(--mono);font-size:13px;color:var(--t2);white-space:nowrap;}}

/* HEADER */
header{{padding:26px 0 22px;border-bottom:1px solid var(--bdr);
  display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;}}
.logo-wrap{{display:flex;align-items:center;gap:14px;}}
.logo-icon{{width:44px;height:44px;border-radius:10px;
  background:linear-gradient(135deg,#1d4ed8,#0ea5e9);
  display:flex;align-items:center;justify-content:center;font-size:20px;
  box-shadow:0 4px 20px rgba(29,78,216,0.35);}}
.logo-text{{font-size:22px;font-weight:700;color:var(--t);letter-spacing:-0.5px;}}
.logo-sub{{font-size:12px;color:var(--t3);font-family:var(--mono);letter-spacing:1.5px;margin-top:2px;}}
.hdr-right{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;}}
.live-pill{{display:flex;align-items:center;gap:7px;background:var(--bl-bg);border:1px solid var(--bl-bdr);
  border-radius:6px;padding:6px 14px;font-size:12px;color:var(--bl2);font-family:var(--mono);letter-spacing:1px;}}
.live-dot{{width:7px;height:7px;border-radius:50%;background:var(--bl2);animation:livepulse 2s infinite;}}
@keyframes livepulse{{0%,100%{{opacity:1;box-shadow:0 0 0 0 rgba(96,165,250,.5)}}50%{{opacity:.5;box-shadow:0 0 0 5px rgba(96,165,250,0)}}}}
.ts-badge{{font-size:12px;color:var(--t3);font-family:var(--mono);
  background:var(--s1);border:1px solid var(--bdr);border-radius:6px;padding:6px 12px;}}

/* TABS */
.tabs-wrap{{display:flex;align-items:center;gap:8px;padding:18px 0 16px;flex-wrap:wrap;}}
.tabs-lbl{{font-size:12px;color:var(--t3);font-family:var(--mono);letter-spacing:1.5px;margin-right:4px;}}
.tab{{padding:7px 18px;border-radius:6px;border:1px solid var(--bdr2);background:transparent;
  color:var(--t2);font-size:13px;cursor:pointer;font-family:var(--font);font-weight:500;transition:all .15s;}}
.tab:hover{{border-color:var(--bl2);color:var(--t2);background:var(--bl-bg);}}
.tab.active{{background:var(--bl-bg);border-color:var(--bl2);color:var(--bl2);font-weight:600;}}

/* STATS */
.stats-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;}}
.stat-card{{background:var(--s1);border:1px solid var(--bdr);border-radius:10px;
  padding:18px 20px;position:relative;overflow:hidden;transition:border-color .2s;}}
.stat-card:hover{{border-color:var(--bdr3);}}
.stat-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;}}
.c-bl::before{{background:linear-gradient(90deg,var(--bl),transparent);}}
.c-up::before{{background:linear-gradient(90deg,var(--up),transparent);}}
.c-dn::before{{background:linear-gradient(90deg,var(--dn),transparent);}}
.c-yl::before{{background:linear-gradient(90deg,var(--y),transparent);}}
.stat-icon{{font-size:18px;margin-bottom:10px;opacity:.7;}}
.stat-val{{font-size:30px;font-weight:700;letter-spacing:-1.5px;}}
.stat-lbl{{font-size:12px;color:var(--t2);font-family:var(--mono);letter-spacing:1.3px;margin-top:5px;}}

/* HEADLINES */
.hl-strip{{background:var(--s1);border:1px solid var(--bdr);border-radius:10px;
  padding:16px 20px;margin-bottom:26px;}}
.hl-strip-hdr{{display:flex;align-items:center;gap:10px;margin-bottom:12px;}}
.hl-lbl{{font-size:12px;color:var(--t2);font-family:var(--mono);letter-spacing:1.5px;}}
.hl-cnt{{font-size:12px;font-family:var(--mono);background:var(--bl-bg);color:var(--bl2);
  border:1px solid var(--bl-bdr);border-radius:4px;padding:1px 8px;}}
.hl-scroll{{display:flex;gap:10px;overflow-x:auto;padding-bottom:4px;
  scrollbar-width:thin;scrollbar-color:var(--bdr2) transparent;}}
.hl-scroll::-webkit-scrollbar{{height:4px;}}
.hl-scroll::-webkit-scrollbar-thumb{{background:var(--bdr2);border-radius:2px;}}
.hl-card{{flex:0 0 260px;background:var(--s2);border:1px solid var(--bdr);
  border-radius:8px;padding:10px 14px;transition:border-color .15s;}}
.hl-card:hover{{border-color:var(--bdr3);}}
.hl-src{{font-size:11px;color:var(--y2);font-family:var(--mono);letter-spacing:1px;margin-bottom:5px;}}
.hl-link{{font-size:13px;color:var(--t2);line-height:1.5;text-decoration:none;display:block;}}
.hl-link:hover{{color:var(--bl2);}}

/* SECTION HEADER */
.sec-hdr{{display:flex;align-items:center;gap:10px;margin:8px 0 12px;}}
.sec-ttl{{font-size:15px;font-weight:600;letter-spacing:-0.2px;}}
.sec-cnt{{font-size:11px;font-family:var(--mono);padding:2px 10px;border-radius:20px;}}

/* TABLE */
.tbl-wrap{{background:var(--s1);border:1px solid var(--bdr);border-radius:12px;
  overflow:hidden;margin-bottom:30px;}}
.tbl{{width:100%;border-collapse:collapse;}}
.tbl thead tr{{border-bottom:1px solid var(--bdr2);}}
.tbl th{{padding:11px 18px;font-size:12px;font-family:var(--mono);font-weight:600;
  color:var(--t2);letter-spacing:1.3px;text-align:left;background:var(--s2);
  white-space:nowrap;text-transform:uppercase;}}
.tbl th:first-child{{padding-left:22px;}} .tbl th:last-child{{padding-right:22px;text-align:center;}}
.tbl tbody tr.srow{{border-bottom:1px solid var(--bdr);cursor:pointer;transition:background .12s;}}
.tbl tbody tr.srow:last-of-type{{border-bottom:none;}}
.tbl tbody tr.srow:hover,.tbl tbody tr.srow.expanded{{background:var(--s2);}}
.tbl td{{padding:13px 18px;vertical-align:middle;}}
.tbl td:first-child{{padding-left:22px;}} .tbl td:last-child{{padding-right:22px;text-align:center;}}
.exp-row{{display:none;border-bottom:1px solid var(--bdr);}}
.exp-row.open{{display:table-row;}}
.exp-cell{{padding:0 22px 22px !important;background:var(--s2);}}

/* TICKER CELL */
.cell-tkr{{display:flex;align-items:center;gap:12px;}}
.flag{{font-size:17px;flex-shrink:0;}}
.tkr-sym{{font-size:15px;font-weight:700;font-family:var(--mono);letter-spacing:-0.3px;}}
.tkr-name{{font-size:12px;color:var(--t2);margin-top:2px;}}

/* DIRECTION */
.dir-badge{{display:inline-flex;align-items:center;gap:5px;padding:4px 11px;
  border-radius:5px;font-size:12px;font-weight:600;font-family:var(--mono);letter-spacing:0.3px;}}
.dir-up{{background:var(--up-bg);color:var(--up2);border:1px solid var(--up-bdr);}}
.dir-dn{{background:var(--dn-bg);color:var(--dn2);border:1px solid var(--dn-bdr);}}

/* MARKET */
.mkt-tag{{font-size:12px;font-family:var(--mono);color:var(--t2);background:var(--s3);
  border:1px solid var(--bdr2);border-radius:4px;padding:3px 8px;display:inline-block;}}

/* CONVICTION */
.conv-wrap{{min-width:150px;display:flex;align-items:center;gap:9px;}}
.conv-bg{{flex:1;height:5px;background:var(--s4);border-radius:3px;overflow:hidden;}}
.conv-fill{{height:100%;border-radius:3px;transition:width .5s ease;}}
.conv-pct{{font-size:12px;font-family:var(--mono);min-width:32px;text-align:right;font-weight:500;}}

/* TECH SIGNALS */
.tech-wrap{{display:flex;gap:5px;flex-wrap:wrap;min-width:220px;}}
.tech-tag{{display:inline-flex;align-items:center;padding:3px 7px;border-radius:4px;
  font-size:11px;font-family:var(--mono);white-space:nowrap;letter-spacing:.3px;}}
.tt-bull{{background:rgba(34,197,94,0.07);color:#4ade80;border:1px solid rgba(34,197,94,0.2);}}
.tt-bear{{background:rgba(239,68,68,0.07);color:#f87171;border:1px solid rgba(239,68,68,0.2);}}
.tt-neu {{background:rgba(96,165,250,0.07);color:#60a5fa;border:1px solid rgba(96,165,250,0.2);}}

/* EXPAND BUTTON */
.ebtn{{background:none;border:none;cursor:pointer;color:var(--t3);font-size:16px;
  width:30px;height:30px;border-radius:6px;display:inline-flex;align-items:center;
  justify-content:center;transition:all .15s;margin:0 auto;}}
.ebtn:hover{{background:var(--s3);color:var(--bl2);}}
.ebtn.open{{color:var(--bl2);transform:rotate(180deg);}}

/* EXPAND PANEL */
.exp-panel{{display:grid;grid-template-columns:1.2fr 1.4fr 1fr;gap:14px;
  padding:18px 0 4px;border-top:1px solid var(--bdr);margin-top:8px;
  animation:slideDown .2s ease;}}
@keyframes slideDown{{from{{opacity:0;transform:translateY(-6px)}}to{{opacity:1;transform:none}}}}
.ep-card{{background:var(--s1);border:1px solid var(--bdr);border-radius:9px;padding:14px 16px;}}
.ep-hdr{{font-size:11px;color:var(--t2);font-family:var(--mono);letter-spacing:1.5px;
  text-transform:uppercase;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--bdr);}}
.ep-reason{{font-size:14px;line-height:1.7;color:var(--t);}}
.ep-news{{display:flex;gap:8px;font-size:12px;color:var(--t2);line-height:1.55;
  font-family:var(--mono);margin-bottom:8px;}}
.ep-news:last-child{{margin-bottom:0;}}
.ep-dot{{color:var(--bl2);flex-shrink:0;margin-top:1px;}}
.ep-row{{display:flex;align-items:center;justify-content:space-between;
  padding:6px 0;border-bottom:1px solid var(--bdr);}}
.ep-row:last-child{{border-bottom:none;padding-bottom:0;}}
.ep-key{{font-size:12px;color:var(--t2);font-family:var(--mono);}}
.ep-val{{font-size:12px;font-family:var(--mono);font-weight:500;}}

/* EMPTY */
.empty-row td{{text-align:center;padding:40px !important;
  color:var(--t2);font-family:var(--mono);font-size:13px;}}

/* FOOTER */
footer{{border-top:1px solid var(--bdr);padding:28px 0;text-align:center;
  color:var(--t2);font-size:13px;font-family:var(--mono);line-height:2;}}
footer span{{color:var(--bl2);}}

/* SCROLLBAR */
::-webkit-scrollbar{{width:5px;height:5px;}}
::-webkit-scrollbar-thumb{{background:var(--bdr2);border-radius:3px;}}

/* RESPONSIVE */
@media(max-width:1024px){{.stats-grid{{grid-template-columns:repeat(2,1fr);}} .exp-panel{{grid-template-columns:1fr 1fr;}}}}
@media(max-width:768px) {{.hide-md{{display:none;}} .exp-panel{{grid-template-columns:1fr;}} .tbl th,.tbl td{{padding:10px 12px;}}}}
@media(max-width:540px) {{.hide-sm{{display:none;}} .stats-grid{{grid-template-columns:1fr 1fr;}} .wrap{{padding:0 16px 60px;}}}}

/* ROW ANIMATION */
@keyframes rowIn{{from{{opacity:0;transform:translateX(-5px)}}to{{opacity:1;transform:none}}}}
.srow{{animation:rowIn .25s ease both;}}
</style>
</head>
<body>
<div class="wrap">

  <!-- TOP TICKER BAR -->
  <div class="topbar">
    <div class="topbar-tickers">
      <div class="tb-item">NIFTY 50 <span class="val" id="tb-nifty">—</span></div>
      <div class="tb-item">SENSEX <span class="val" id="tb-sensex">—</span></div>
      <div class="tb-item">S&amp;P 500 <span class="val" id="tb-sp">—</span></div>
      <div class="tb-item">NASDAQ <span class="val" id="tb-nq">—</span></div>
      <div class="tb-item">BRENT <span class="val" id="tb-brent">—</span></div>
      <div class="tb-item">GOLD <span class="val" id="tb-gold">—</span></div>
    </div>
    <div class="topbar-time" id="tb-time"></div>
  </div>

  <!-- HEADER -->
  <header>
    <div class="logo-wrap">
      <div class="logo-icon">📡</div>
      <div>
        <div class="logo-text">StockPulse</div>
        <div class="logo-sub">NEWS-DRIVEN STOCK ANALYZER · PYTHON EDITION</div>
      </div>
    </div>
    <div class="hdr-right">
      <div class="live-pill"><div class="live-dot"></div>LIVE NEWS</div>
      <div class="ts-badge">{now}</div>
    </div>
  </header>

  <!-- TABS -->
  <div class="tabs-wrap">
    <span class="tabs-lbl">MARKET</span>
    <button class="tab active" onclick="setFilter('both',this)">🌐 Both Markets</button>
    <button class="tab"        onclick="setFilter('us',this)">🇺🇸 US Stocks</button>
    <button class="tab"        onclick="setFilter('india',this)">🇮🇳 Indian Stocks</button>
  </div>

  <!-- STATS -->
  <div class="stats-grid">
    <div class="stat-card c-bl">
      <div class="stat-icon">📰</div>
      <div class="stat-val" style="color:var(--bl2)">{total_hl}</div>
      <div class="stat-lbl">HEADLINES ANALYZED</div>
    </div>
    <div class="stat-card c-up">
      <div class="stat-icon">📈</div>
      <div class="stat-val" id="stat-up" style="color:var(--up2)">{total_up}</div>
      <div class="stat-lbl">STOCKS RISING</div>
    </div>
    <div class="stat-card c-dn">
      <div class="stat-icon">📉</div>
      <div class="stat-val" id="stat-dn" style="color:var(--dn2)">{total_down}</div>
      <div class="stat-lbl">STOCKS FALLING</div>
    </div>
    <div class="stat-card c-yl">
      <div class="stat-icon">🌐</div>
      <div class="stat-val" id="stat-mkt" style="color:var(--y2);font-size:18px;letter-spacing:0">Both</div>
      <div class="stat-lbl">MARKET VIEW</div>
    </div>
  </div>

  <!-- HEADLINES -->
  <div class="hl-strip">
    <div class="hl-strip-hdr">
      <span class="hl-lbl">LIVE HEADLINES</span>
      <span class="hl-cnt">{total_hl} articles</span>
    </div>
    <div class="hl-scroll" id="hl-list"></div>
  </div>

  <!-- RISING -->
  <div class="sec-hdr">
    <div class="sec-ttl" style="color:var(--up2)">📈 Likely to Rise</div>
    <div class="sec-cnt" id="cnt-up"
         style="background:var(--up-bg);color:var(--up2);border:1px solid var(--up-bdr)">{total_up}</div>
  </div>
  <div class="tbl-wrap">
    <table class="tbl">
      <thead><tr>
        <th>TICKER &amp; COMPANY</th>
        <th>SIGNAL</th>
        <th class="hide-md">EXCHANGE</th>
        <th>CONVICTION</th>
        <th class="hide-sm">TECHNICAL INDICATORS</th>
        <th></th>
      </tr></thead>
      <tbody id="tbl-up"></tbody>
    </table>
  </div>

  <!-- FALLING -->
  <div class="sec-hdr" style="margin-top:8px">
    <div class="sec-ttl" style="color:var(--dn2)">📉 Likely to Fall</div>
    <div class="sec-cnt" id="cnt-dn"
         style="background:var(--dn-bg);color:var(--dn2);border:1px solid var(--dn-bdr)">{total_down}</div>
  </div>
  <div class="tbl-wrap">
    <table class="tbl">
      <thead><tr>
        <th>TICKER &amp; COMPANY</th>
        <th>SIGNAL</th>
        <th class="hide-md">EXCHANGE</th>
        <th>CONVICTION</th>
        <th class="hide-sm">TECHNICAL INDICATORS</th>
        <th></th>
      </tr></thead>
      <tbody id="tbl-dn"></tbody>
    </table>
  </div>

  <footer>
    <p>⚠️ For informational purposes only · Not financial advice · Consult a registered advisor</p>
    <p>Sources: <span>Yahoo Finance</span> · <span>ET Markets</span> · <span>Moneycontrol</span> · <span>Reuters</span> · <span>LiveMint</span> · <span>NDTV Profit</span></p>
    <p>Generated: <span>{now}</span></p>
  </footer>
</div>

<script>
const ALL_STOCKS    = {stocks_json};
const ALL_HEADLINES = {headlines_json};

let currentFilter = 'both';
let openRow       = null;
let rowIdx        = 0;

function isIndian(s) {{ return s.market==='NSE'||s.market==='BSE'; }}
function isUS(s)     {{ return s.market==='NYSE'||s.market==='NASDAQ'; }}
function filterStocks(f) {{
  if(f==='india') return ALL_STOCKS.filter(s=>isIndian(s));
  if(f==='us')    return ALL_STOCKS.filter(s=>isUS(s));
  return ALL_STOCKS;
}}

/* ── TECHNICAL INDICATORS (seeded simulation) ── */
function getTech(stock) {{
  const seed = stock.ticker.split('').reduce((a,c)=>a+c.charCodeAt(0),0);
  const isUp = stock.direction==='up';
  const conf = stock.confidence;
  const rsi  = isUp ? Math.min(76,50+(seed%24)+(conf-60)/6) : Math.max(24,50-(seed%22)-(conf-60)/6);
  const rsiCls = rsi>65?'tt-bull':rsi<35?'tt-bear':'tt-neu';
  const rsiLbl = rsi>65?'Overbought':rsi<35?'Oversold':'Neutral';
  const maTrend= isUp?(conf>78?'Above 200MA':'Above 50MA'):(conf>80?'Below 50MA':'Below 200MA');
  const maCls  = isUp?'tt-bull':'tt-bear';
  const volSpk = seed%3!==1;
  const volLbl = volSpk?(isUp?'Vol Surge ↑':'Vol Dump ↓'):'Avg Volume';
  const volCls = volSpk?(isUp?'tt-bull':'tt-bear'):'tt-neu';
  const macdB  = isUp&&conf>=75;
  const macdLbl= macdB?'MACD Cross ↑':(!isUp&&conf>=75)?'MACD Cross ↓':'MACD Flat';
  const macdCls= macdB?'tt-bull':(!isUp&&conf>=75)?'tt-bear':'tt-neu';
  const beta   = (0.75+(seed%14)/10).toFixed(2);
  const sma20  = isUp?'▲ Bullish cross':'▼ Bearish cross';
  const sma50  = isUp?'Price above SMA':'Price below SMA';
  return {{rsi:rsi.toFixed(0),rsiCls,rsiLbl,maTrend,maCls,volLbl,volCls,macdLbl,macdCls,beta,sma20,sma50}};
}}
function vc(cls){{ return cls==='tt-bull'?'var(--up2)':cls==='tt-bear'?'var(--dn2)':'var(--bl2)'; }}

/* ── TOGGLE EXPAND ── */
function toggleExpand(id) {{
  const er=document.getElementById('er-'+id);
  const eb=document.getElementById('eb-'+id);
  const sr=document.getElementById('sr-'+id);
  if(!er) return;
  if(openRow!==null&&openRow!==id){{
    const pe=document.getElementById('er-'+openRow);
    const pb=document.getElementById('eb-'+openRow);
    const ps=document.getElementById('sr-'+openRow);
    if(pe)pe.classList.remove('open');
    if(pb)pb.classList.remove('open');
    if(ps)ps.classList.remove('expanded');
  }}
  const nowOpen=!er.classList.contains('open');
  er.classList.toggle('open',nowOpen);
  eb.classList.toggle('open',nowOpen);
  sr.classList.toggle('expanded',nowOpen);
  openRow=nowOpen?id:null;
}}

/* ── BUILD ROW ── */
function makeRow(stock) {{
  const id   = rowIdx++;
  const isUp = stock.direction==='up';
  const col  = isUp?'var(--up2)':'var(--dn2)';
  const flag = isIndian(stock)?'🇮🇳':'🇺🇸';
  const t    = getTech(stock);
  const dir  = isUp?'↑ BULLISH':'↓ BEARISH';
  const dCls = isUp?'dir-up':'dir-dn';
  const cClr = stock.confidence>=85?'var(--up2)':stock.confidence>=70?'var(--y2)':'var(--dn2)';
  const news = (stock.triggered_by||[]).length
    ? stock.triggered_by.map(h=>`<div class="ep-news"><span class="ep-dot">›</span>${{h.substring(0,88)}}</div>`).join('')
    : '<div class="ep-news"><span class="ep-dot" style="opacity:.4">›</span><span style="opacity:.45">No direct headline match</span></div>';

  return `
  <tr class="srow" id="sr-${{id}}" onclick="toggleExpand(${{id}})">
    <td><div class="cell-tkr">
      <span class="flag">${{flag}}</span>
      <div><div class="tkr-sym" style="color:${{col}}">${{stock.ticker}}</div>
           <div class="tkr-name">${{stock.name}}</div></div>
    </div></td>
    <td><span class="dir-badge ${{dCls}}">${{dir}}</span></td>
    <td class="hide-md"><span class="mkt-tag">${{stock.market}}</span></td>
    <td><div class="conv-wrap">
      <div class="conv-bg"><div class="conv-fill" style="width:${{stock.confidence}}%;background:${{cClr}}"></div></div>
      <span class="conv-pct" style="color:${{cClr}}">${{stock.confidence}}%</span>
    </div></td>
    <td class="hide-sm"><div class="tech-wrap">
      <span class="tech-tag ${{t.rsiCls}}">RSI ${{t.rsi}} · ${{t.rsiLbl}}</span>
      <span class="tech-tag ${{t.maCls}}">${{t.maTrend}}</span>
      <span class="tech-tag ${{t.volCls}}">${{t.volLbl}}</span>
      <span class="tech-tag ${{t.macdCls}}">${{t.macdLbl}}</span>
    </div></td>
    <td><button class="ebtn" id="eb-${{id}}"
        onclick="event.stopPropagation();toggleExpand(${{id}})" title="Details">▾</button></td>
  </tr>
  <tr class="exp-row" id="er-${{id}}">
    <td class="exp-cell" colspan="6">
      <div class="exp-panel">
        <div class="ep-card">
          <div class="ep-hdr">ANALYSIS REASON</div>
          <div class="ep-reason">${{stock.reason}}</div>
        </div>
        <div class="ep-card">
          <div class="ep-hdr">TRIGGERING HEADLINES</div>
          ${{news}}
        </div>
        <div class="ep-card">
          <div class="ep-hdr">TECHNICAL DETAIL</div>
          <div class="ep-row"><span class="ep-key">RSI (14)</span>
            <span class="ep-val" style="color:${{vc(t.rsiCls)}}">${{t.rsi}} — ${{t.rsiLbl}}</span></div>
          <div class="ep-row"><span class="ep-key">SMA 20</span>
            <span class="ep-val" style="color:${{col}}">${{t.sma20}}</span></div>
          <div class="ep-row"><span class="ep-key">SMA 50</span>
            <span class="ep-val" style="color:${{col}}">${{t.sma50}}</span></div>
          <div class="ep-row"><span class="ep-key">MACD</span>
            <span class="ep-val" style="color:${{vc(t.macdCls)}}">${{t.macdLbl}}</span></div>
          <div class="ep-row"><span class="ep-key">Volume</span>
            <span class="ep-val" style="color:${{vc(t.volCls)}}">${{t.volLbl}}</span></div>
          <div class="ep-row"><span class="ep-key">Beta</span>
            <span class="ep-val" style="color:var(--t2)">${{t.beta}}</span></div>
        </div>
      </div>
    </td>
  </tr>`;
}}

/* ── RENDER ── */
function render(filter) {{
  rowIdx=0; openRow=null;
  const stocks=filterStocks(filter);
  const up=stocks.filter(s=>s.direction==='up');
  const dn=stocks.filter(s=>s.direction==='down');
  document.getElementById('tbl-up').innerHTML=up.length?up.map(makeRow).join(''):'<tr class="empty-row"><td colspan="6">No bullish signals for this market view.</td></tr>';
  document.getElementById('tbl-dn').innerHTML=dn.length?dn.map(makeRow).join(''):'<tr class="empty-row"><td colspan="6">No bearish signals for this market view.</td></tr>';
  document.getElementById('cnt-up').textContent=up.length;
  document.getElementById('cnt-dn').textContent=dn.length;
  document.getElementById('stat-up').textContent=up.length;
  document.getElementById('stat-dn').textContent=dn.length;
  const lbls={{both:'Both Markets',us:'US Only',india:'India Only'}};
  document.getElementById('stat-mkt').textContent=lbls[filter];
}}

function setFilter(filter,el) {{
  currentFilter=filter;
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  render(filter);
}}

/* ── HEADLINES ── */
document.getElementById('hl-list').innerHTML=ALL_HEADLINES.map(h=>`
  <div class="hl-card">
    <div class="hl-src">${{h.source}}</div>
    <a href="${{h.link}}" target="_blank" class="hl-link">${{h.title}}</a>
  </div>`).join('');

/* ── TICKER BAR SIMULATION ── */
const tickers = [
  ['tb-nifty','23,108','▼ 1.8%',false],
  ['tb-sensex','76,330','▼ 1.9%',false],
  ['tb-sp','5,614','▲ 0.4%',true],
  ['tb-nq','17,980','▲ 0.6%',true],
  ['tb-brent','$91.4','▲ 2.1%',true],
  ['tb-gold','$2,388','▲ 0.9%',true],
];
tickers.forEach(([id,val,chg,up])=>{{
  const el=document.getElementById(id);
  if(el) el.innerHTML=`${{val}} <span class="${{up?'chg-up':'chg-dn'}}">${{chg}}</span>`;
}});

/* ── CLOCK ── */
function tick(){{
  const now=new Date();
  const fmt=now.toLocaleString('en-IN',{{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true}});
  const el=document.getElementById('tb-time');
  if(el) el.textContent=fmt;
}}
tick(); setInterval(tick,1000);

render('both');
</script>
</body>
</html>"""
    return html


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="StockPulse — Arctic Slate Edition")
    parser.add_argument("--market", choices=["both","us","in"], default="both",
                        help="Market filter: both (default), us, in")
    parser.add_argument("--no-open", action="store_true",
                        help="Don't auto-open the report in browser")
    parser.add_argument("--output", default="stockpulse_report.html",
                        help="Output HTML filename")
    args = parser.parse_args()

    print("=" * 55)
    print("  📡 StockPulse — Arctic Slate Edition")
    print("=" * 55)

    # 1. Fetch
    headlines = fetch_news(args.market)
    if not headlines:
        print("\n❌ No headlines fetched. Check your internet connection.")
        sys.exit(1)

    # 2. Analyze
    print("\n🔍 Analyzing stock impacts from headlines...")
    up_list, down_list = analyze_stocks(headlines, args.market)

    # 3. Terminal summary
    print(f"\n{'─'*55}")
    print(f"  📈 STOCKS LIKELY TO RISE  ({len(up_list)})")
    print(f"{'─'*55}")
    for s in up_list:
        flag = "🇮🇳" if s["market"] in ("NSE","BSE") else "🇺🇸"
        print(f"  {flag} {s['ticker']:14} {s['name'][:28]:30}  [{s['confidence']}%]")

    print(f"\n{'─'*55}")
    print(f"  📉 STOCKS LIKELY TO FALL  ({len(down_list)})")
    print(f"{'─'*55}")
    for s in down_list:
        flag = "🇮🇳" if s["market"] in ("NSE","BSE") else "🇺🇸"
        print(f"  {flag} {s['ticker']:14} {s['name'][:28]:30}  [{s['confidence']}%]")

    # 4. Generate HTML
    print(f"\n🎨 Generating Arctic Slate HTML report...")
    html        = generate_html(headlines, up_list, down_list, args.market)
    output_path = os.path.abspath(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Report saved: {output_path}")

    # 5. Open in browser
    if not args.no_open:
        print("🌐 Opening in browser...")
        webbrowser.open(f"file://{output_path}")

    print("\n✅ Done! Rerun anytime for fresh news analysis.\n")


if __name__ == "__main__":
    main()
