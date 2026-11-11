# Free Multi-Asset Liquidity Scanner

A starter Python scanner for PDH/PDL liquidity sweeps with completed 5-minute candle confirmation.
It logs signals to CSV and can send Discord webhook alerts. It is designed for GitHub Actions.

## Important limitations
- Uses Yahoo Finance via `yfinance`; quotes and intraday history can be delayed, incomplete, rate-limited, or unavailable.
- This is an alerting/research tool, not an execution bot or a guarantee of profitable signals.
- GitHub Actions scheduled runs are best-effort. A 5-minute schedule can be delayed or skipped.
- Yahoo Finance does not provide a dependable institutional-grade real-time feed for every futures/commodity contract.
- `XAUUSD=X` is a Yahoo Finance symbol proxy, not a guaranteed OANDA feed. Replace it with your broker's supported API feed if you need broker-specific prices.
- The starter's 5-minute data availability varies by symbol. Missing data is recorded as an error, not guessed.

## What it scans
25 symbols: NQ=F, ES=F, RTY=F, QQQ, SPY, IWM, XAUUSD=X, GC=F, CL=F, NG=F, GLD, USO,
AAPL, NVDA, MSFT, AMZN, GOOGL, META, TSLA, AMD, AVGO, MU, EURUSD=X, BTC-USD, ETH-USD.

## Signal logic
1. Fetches intraday 5-minute candles and daily candles.
2. Uses the latest **completed** 5-minute candle (not the currently forming candle).
3. Checks whether price swept above prior-day high (potential short) or below prior-day low (potential long).
4. Requires the completed candle to close back inside the prior-day range and show a rejection wick.
5. Adds a basic 1-hour / 4-hour swing-level proximity check as context, not as a mandatory filter.
6. Emits LONG / SHORT / NO TRADE. This initial version alerts only on confirmed PDH/PDL sweeps.

This is a conservative starter rule set. It does not yet implement a full BOS/CHOCH engine, news sentiment, options flow, or monthly/weekly pivots.

## Run locally (Windows)
1. Install Python 3.11 or newer.
2. Open PowerShell in this folder.
3. Run:
   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   Copy-Item .env.example .env
   ```
4. Put your Discord webhook URL in `.env`.
5. Run:
   ```powershell
   python scanner.py
   ```

## Run on GitHub Actions for free
1. Create a new **public** GitHub repository (GitHub-hosted standard runners are generally free for public repositories; verify current GitHub plan limits).
2. Upload the contents of this folder to the repository root.
3. In the repository, open **Settings → Secrets and variables → Actions → New repository secret**.
4. Add secret:
   - Name: `DISCORD_WEBHOOK_URL`
   - Value: your Discord channel webhook URL.
5. Open **Actions** and enable workflows if GitHub asks.
6. The workflow runs every 5 minutes in UTC and can also be started manually.

## CSV output
Signals are appended to `signals.csv`. In GitHub Actions, the workflow uploads the CSV as an artifact after each run. Note that GitHub-hosted runners are temporary; artifacts are the persisted output.

## Before using real money
- Paper-test signals and manually verify chart timestamps/prices.
- Backtest with a reliable historical data source and include spread, slippage, and fees.
- Do not treat the signal as an instruction to enter a trade.
