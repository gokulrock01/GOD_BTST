"""
Stock News Guardian & Earnings Catalyst Engine for NSE F&O
Analyzes breaking news, sentiment, and earnings announcements (IV Crush Risk)
for selected BTST/STBT stock options candidates.
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import datetime
import re
from email.utils import parsedate_to_datetime

# Keywords indicating imminent financial results / board meetings (High IV Crush Hazard)
EARNINGS_KEYWORDS = [
    'results today', 'results tomorrow', 'q1 results', 'q2 results', 'q3 results', 'q4 results',
    'earnings tomorrow', 'earnings today', 'board meeting to consider results',
    'quarterly results', 'financial results', 'board meeting on', 'profit drops', 'profit jumps',
    'revenue jumps', 'net profit up', 'net profit down'
]

# High-impact corporate catalysts
BULLISH_CATALYSTS = [
    'order win', 'bagged order', 'secures contract', 'brokerage upgrade', 'target raised',
    'buy rating', 'outperform', 'fii buying', 'capacity expansion', 'fda approval',
    'joint venture', 'usfda clearance', 'record high profit', 'dividend announcement'
]

BEARISH_CATALYSTS = [
    'sebi notice', 'sebi probe', 'tax raid', 'it raid', 'ed search', 'investigation',
    'downgrade', 'target cut', 'sell rating', 'underperform', 'promoter sells', 'block deal',
    'penalty imposed', 'recall', 'usfda warning letter', 'form 483', 'fraud allegation'
]

class StockNewsGuardian:
    def __init__(self):
        pass

    def fetch_stock_news(self, symbol_clean: str, max_age_hours=48):
        """
        Fetches breaking news articles for a specific NSE stock from Google News RSS.
        """
        query = f'"{symbol_clean}" stock OR "{symbol_clean} share price" OR "{symbol_clean} results"'
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}+when:48h&hl=en-IN&gl=IN&ceid=IN:en"
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        req = urllib.request.Request(url, headers=headers)

        articles = []
        try:
            with urllib.request.urlopen(req, timeout=6) as response:
                xml_data = response.read()
            root = ET.fromstring(xml_data)

            now = datetime.datetime.now(datetime.timezone.utc)
            for item in root.findall('.//item')[:8]:
                title = item.find('title').text or ""
                pub_date_str = item.find('pubDate').text or ""
                link = item.find('link').text or ""

                try:
                    pub_date = parsedate_to_datetime(pub_date_str)
                    age_hours = (now - pub_date).total_seconds() / 3600.0
                except Exception:
                    age_hours = 0

                if age_hours <= max_age_hours:
                    articles.append({
                        "title": title,
                        "age_hours": round(age_hours, 1),
                        "link": link
                    })
        except Exception as e:
            pass

        return articles

    def analyze_stock_catalyst(self, symbol_clean: str):
        """
        Evaluates news sentiment and checks for Imminent Earnings / IV Crush Hazard.
        """
        articles = self.fetch_stock_news(symbol_clean)

        earnings_hazard = False
        earnings_mention = None
        bullish_hits = []
        bearish_hits = []

        for art in articles:
            text = art["title"].lower()

            # 1. Check for upcoming earnings / results (IV Crush Warning)
            for kw in EARNINGS_KEYWORDS:
                if re.search(r'\b' + re.escape(kw) + r'\b', text):
                    earnings_hazard = True
                    earnings_mention = art["title"]
                    break

            # 2. Check for bullish catalysts
            for kw in BULLISH_CATALYSTS:
                if re.search(r'\b' + re.escape(kw) + r'\b', text):
                    bullish_hits.append(kw)

            # 3. Check for bearish catalysts
            for kw in BEARISH_CATALYSTS:
                if re.search(r'\b' + re.escape(kw) + r'\b', text):
                    bearish_hits.append(kw)

        # Sentiment scoring
        net_score = len(bullish_hits) - len(bearish_hits)
        if net_score > 0:
            sentiment = "BULLISH CATALYST"
        elif net_score < 0:
            sentiment = "BEARISH DRAG"
        else:
            sentiment = "NEUTRAL"

        top_headline = articles[0]["title"] if articles else "No breaking corporate news in past 48h."

        return {
            "Symbol": symbol_clean,
            "Top_Headline": top_headline,
            "Sentiment": sentiment,
            "Earnings_Hazard": earnings_hazard,
            "Earnings_Note": earnings_mention,
            "Articles_Count": len(articles)
        }

if __name__ == "__main__":
    guardian = StockNewsGuardian()
    for s in ["HDFCBANK", "RELIANCE", "TRENT"]:
        res = guardian.analyze_stock_catalyst(s)
        print(f"\n[{s}] Sentiment: {res['Sentiment']} | Earnings Hazard: {res['Earnings_Hazard']}")
        print(f"  Top News: {res['Top_Headline']}")
