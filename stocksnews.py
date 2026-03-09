"""
MARKET//SIGNAL - AI-Powered News to Stock Impact Analyzer
Uses: Anthropic Claude API + Web Search Tool
Author: Your Name
"""

import os
import json
import anthropic
from flask import Flask, render_template, jsonify
from datetime import datetime

app = Flask(__name__)

# ─── Anthropic Client ───────────────────────────────────────────────
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are a financial analyst AI. Based on TODAY's latest news (search the web for real-time news), analyze which stocks are likely to INCREASE or DECREASE in price.

Return ONLY a valid JSON object with this exact structure (no markdown, no explanation):
{
  "date": "today's date",
  "topHeadline": "one-sentence summary of the biggest market-moving news today",
  "newsEvents": [
    {
      "headline": "short headline",
      "impact": "brief 1-sentence explanation of market impact",
      "category": "category name (e.g. War, Oil, Tech, Economy, etc.)"
    }
  ],
  "US": {
    "bullish": [
      { "ticker": "TICKER", "name": "Company Name", "reason": "why it will go up", "sector": "sector", "confidence": "High/Medium/Low" }
    ],
    "bearish": [
      { "ticker": "TICKER", "name": "Company Name", "reason": "why it will go down", "sector": "sector", "confidence": "High/Medium/Low" }
    ]
  },
  "India": {
    "bullish": [
      { "ticker": "TICKER", "name": "Company Name", "reason": "why it will go up", "sector": "sector", "confidence": "High/Medium/Low" }
    ],
    "bearish": [
      { "ticker": "TICKER", "name": "Company Name", "reason": "why it will go down", "sector": "sector", "confidence": "High/Medium/Low" }
    ]
  }
}

Include 5-8 stocks per category per market. Base everything on TODAY's actual breaking news. Search for latest financial news, geopolitical events, earnings, and economic data releases."""


def fetch_stock_analysis():
    """
    Calls Anthropic API with web_search tool enabled.
    Claude searches the web for today's news, then returns structured stock analysis.
    
    SOURCE: Anthropic Claude API (claude-sonnet-4-20250514)
    WEB SEARCH: Built-in Anthropic web search tool (searches live internet)
    """
    today = datetime.now().strftime("%B %d, %Y")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Search the web for today's most important financial and geopolitical news ({today}). "
                    "Then analyze which US and Indian stocks will go UP or DOWN based on this news. "
                    "Return only valid JSON."
                )
            }
        ]
    )

    # Extract text block from response (may contain tool_use blocks too)
    text_block = next(
        (block for block in response.content if block.type == "text"), None
    )

    if not text_block:
        raise ValueError("No text response from Claude API")

    raw = text_block.text.strip()
    # Strip markdown fences if present
    raw = raw.replace("```json", "").replace("```", "").strip()

    return json.loads(raw)


# ─── Routes ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze")
def analyze():
    """API endpoint — returns JSON stock analysis based on today's live news."""
    try:
        data = fetch_stock_analysis()
        return jsonify({"success": True, "data": data})
    except json.JSONDecodeError as e:
        return jsonify({"success": False, "error": f"Failed to parse AI response: {e}"}), 500
    except anthropic.APIError as e:
        return jsonify({"success": False, "error": f"Anthropic API error: {e}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  WARNING: ANTHROPIC_API_KEY not set. Add it to your .env file.")
    app.run(debug=True, port=5000)
