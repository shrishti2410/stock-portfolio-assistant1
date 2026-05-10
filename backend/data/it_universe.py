"""
it_universe.py — Curated universe of IT services companies for the IT-Bear thesis.

Covers:
  - India F&O-liquid IT services (12 names + NIFTY IT index)
  - US IT services bellwethers (8 names)

Each entry has:
  - symbol (Zerodha/NSE convention for India, NYSE/NASDAQ for US)
  - yfinance ticker (for live price / historical data)
  - name, country, tier, lot_size (India only), market_cap_inr
  - segment (mega_cap, mid_cap, federal, bpo, etc.)
  - notes (thesis-relevant context)
"""

INDIA_IT = [
    # ── Mega-cap (Tier 1 — deepest liquidity, F&O) ──
    {
        "symbol": "TCS",
        "yf": "TCS.NS",
        "name": "Tata Consultancy Services",
        "country": "IN",
        "tier": "mega_cap",
        "lot_size": 175,
        "segment": "diversified_services",
        "notes": "Largest by mcap. Most defensive. Sets sector tone with first earnings each quarter.",
        "fno": True,
    },
    {
        "symbol": "INFY",
        "yf": "INFY.NS",
        "name": "Infosys",
        "country": "IN",
        "tier": "mega_cap",
        "lot_size": 400,
        "segment": "diversified_services",
        "notes": "Heavy BFSI exposure, vulnerable to US bank IT pullback.",
        "fno": True,
    },
    {
        "symbol": "HCLTECH",
        "yf": "HCLTECH.NS",
        "name": "HCL Technologies",
        "country": "IN",
        "tier": "mega_cap",
        "lot_size": 350,
        "segment": "engineering_services",
        "notes": "Engineering services + products mix. Less exposed to BFSI.",
        "fno": True,
    },
    {
        "symbol": "WIPRO",
        "yf": "WIPRO.NS",
        "name": "Wipro",
        "country": "IN",
        "tier": "mega_cap",
        "lot_size": 3000,
        "segment": "diversified_services",
        "notes": "Weakest among top-4. Multiple guidance cuts. High beta to thesis.",
        "fno": True,
    },
    {
        "symbol": "TECHM",
        "yf": "TECHM.NS",
        "name": "Tech Mahindra",
        "country": "IN",
        "tier": "mega_cap",
        "lot_size": 600,
        "segment": "telecom_services",
        "notes": "Heavy telecom exposure. New CEO, restructuring uncertain.",
        "fno": True,
    },

    # ── Mid-cap (Tier 2 — F&O available, more volatile) ──
    {
        "symbol": "LTIM",
        "yf": "LTIM.NS",
        "name": "LTIMindtree",
        "country": "IN",
        "tier": "mid_cap",
        "lot_size": 150,
        "segment": "diversified_services",
        "notes": "Post-merger entity. BFSI + retail exposure. Earnings volatility high.",
        "fno": True,
    },
    {
        "symbol": "PERSISTENT",
        "yf": "PERSISTENT.NS",
        "name": "Persistent Systems",
        "country": "IN",
        "tier": "mid_cap",
        "lot_size": 200,
        "segment": "product_engineering",
        "notes": "Premium valuations. Vulnerable to multiple compression.",
        "fno": True,
    },
    {
        "symbol": "MPHASIS",
        "yf": "MPHASIS.NS",
        "name": "Mphasis",
        "country": "IN",
        "tier": "mid_cap",
        "lot_size": 275,
        "segment": "diversified_services",
        "notes": "Blackstone-controlled. Heavy mortgage/BFSI exposure.",
        "fno": True,
    },
    {
        "symbol": "COFORGE",
        "yf": "COFORGE.NS",
        "name": "Coforge",
        "country": "IN",
        "tier": "mid_cap",
        "lot_size": 100,
        "segment": "travel_bfsi",
        "notes": "Travel + BFSI heavy. Recent acquisitions create execution risk.",
        "fno": True,
    },
    {
        "symbol": "LTTS",
        "yf": "LTTS.NS",
        "name": "L&T Technology Services",
        "country": "IN",
        "tier": "mid_cap",
        "lot_size": 150,
        "segment": "engineering_services",
        "notes": "Pure ER&D play. Auto + industrial slowdown impact.",
        "fno": True,
    },
    {
        "symbol": "TATAELXSI",
        "yf": "TATAELXSI.NS",
        "name": "Tata Elxsi",
        "country": "IN",
        "tier": "mid_cap",
        "lot_size": 100,
        "segment": "design_engineering",
        "notes": "Premium ER&D + media. High valuations, high beta.",
        "fno": True,
    },
    {
        "symbol": "OFSS",
        "yf": "OFSS.NS",
        "name": "Oracle Financial Services Software",
        "country": "IN",
        "tier": "mid_cap",
        "lot_size": 75,
        "segment": "products",
        "notes": "Banking products. Less correlated but valuation-rich.",
        "fno": True,
    },
]

# Indian sector index for pure sector bets
INDIA_IT_INDEX = {
    "symbol": "NIFTYIT",
    "yf": "^CNXIT",
    "name": "NIFTY IT Index",
    "country": "IN",
    "tier": "index",
    "lot_size": 25,
    "segment": "sector_index",
    "notes": "Purest sector play. Lot size 25. Use for core hedge/short.",
    "fno": True,
}

US_IT = [
    # ── Pure-play IT services ──
    {
        "symbol": "ACN",
        "yf": "ACN",
        "name": "Accenture",
        "country": "US",
        "tier": "mega_cap",
        "lot_size": 100,
        "segment": "consulting_services",
        "notes": "Global bellwether. Earnings move entire Indian IT sector. Reports mid-Sep/Dec/Mar/Jun.",
        "fno": True,
    },
    {
        "symbol": "IBM",
        "yf": "IBM",
        "name": "International Business Machines",
        "country": "US",
        "tier": "mega_cap",
        "lot_size": 100,
        "segment": "diversified_services",
        "notes": "Consulting + Software. Watson AI angle is bullish hedge.",
        "fno": True,
    },
    {
        "symbol": "CTSH",
        "yf": "CTSH",
        "name": "Cognizant Technology Solutions",
        "country": "US",
        "tier": "large_cap",
        "lot_size": 100,
        "segment": "diversified_services",
        "notes": "Direct competitor to Indian IT. Margin pressure visible.",
        "fno": True,
    },
    {
        "symbol": "EPAM",
        "yf": "EPAM",
        "name": "EPAM Systems",
        "country": "US",
        "tier": "mid_cap",
        "lot_size": 100,
        "segment": "engineering_services",
        "notes": "Ukraine exposure tail risk. Premium ER&D player.",
        "fno": True,
    },
    {
        "symbol": "GLOB",
        "yf": "GLOB",
        "name": "Globant",
        "country": "US",
        "tier": "mid_cap",
        "lot_size": 100,
        "segment": "digital_services",
        "notes": "Premium digital transformation. High beta if multiple compresses.",
        "fno": True,
    },
    {
        "symbol": "G",
        "yf": "G",
        "name": "Genpact",
        "country": "US",
        "tier": "mid_cap",
        "lot_size": 100,
        "segment": "bpo",
        "notes": "BPO pure-play. AI automation risk highest here.",
        "fno": True,
    },
    {
        "symbol": "DXC",
        "yf": "DXC",
        "name": "DXC Technology",
        "country": "US",
        "tier": "mid_cap",
        "lot_size": 100,
        "segment": "infra_services",
        "notes": "Already beaten down. Lower-quality short — limited downside.",
        "fno": True,
    },
    {
        "symbol": "CNXC",
        "yf": "CNXC",
        "name": "Concentrix",
        "country": "US",
        "tier": "mid_cap",
        "lot_size": 100,
        "segment": "bpo_cx",
        "notes": "Customer experience BPO. Highly vulnerable to GenAI.",
        "fno": True,
    },
]

# Sector ETFs for pair trades / hedges
SECTOR_ETFS = [
    {"symbol": "XLK", "yf": "XLK", "name": "Tech Select Sector SPDR", "country": "US", "notes": "Broad US tech"},
    {"symbol": "IGV", "yf": "IGV", "name": "iShares Software ETF", "country": "US", "notes": "US software focused"},
    {"symbol": "PSQ", "yf": "PSQ", "name": "ProShares Short QQQ", "country": "US", "notes": "1x inverse Nasdaq — no margin needed"},
]


def get_all() -> list[dict]:
    """Return all stocks in the IT bear universe."""
    return INDIA_IT + [INDIA_IT_INDEX] + US_IT


def get_india() -> list[dict]:
    """India-only stocks (F&O liquid)."""
    return INDIA_IT + [INDIA_IT_INDEX]


def get_us() -> list[dict]:
    """US-only stocks."""
    return US_IT


def get_etfs() -> list[dict]:
    """Sector ETFs for hedging."""
    return SECTOR_ETFS


def get_by_symbol(symbol: str) -> dict | None:
    """Lookup a stock by symbol."""
    sym = symbol.upper().strip()
    for s in get_all() + SECTOR_ETFS:
        if s["symbol"] == sym:
            return s
    return None


def get_fno_symbols() -> list[str]:
    """Symbols that can be shorted via Indian F&O."""
    return [s["symbol"] for s in INDIA_IT + [INDIA_IT_INDEX] if s.get("fno")]
