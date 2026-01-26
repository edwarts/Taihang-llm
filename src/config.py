# src/config.py

# 核心观察池 (Mag7 + Tech + Banks + Meme)
TARGET_SYMBOLS = [
    # Mag 7 / Big Tech
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AMD", "NFLX", "INTC",
    # Semiconductors / AI
    "AVGO", "QCOM", "TSM", "MU", "SMCI",
    # Financials
    "JPM", "BAC", "GS", "MS",
    # Crypto / Fintech
    "COIN", "MARA", "PYPL", "SQ",
    # Meme / High Volatility / Others
    "GME", "AMC", "PLTR", "HOOD", "DJT", "SOFI", "BA"
]

# Finnhub API 限制配置 (避免 429 Error)
API_LIMIT_PER_SEC = 30 
TICK_LIMIT_PER_CALL = 25000 # Finnhub 单次请求最大 Tick 数