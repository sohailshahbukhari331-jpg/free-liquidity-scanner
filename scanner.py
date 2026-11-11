import os
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

WATCHLIST = [
    "NQ=F", "ES=F", "RTY=F", "QQQ", "SPY", "IWM",
    "XAUUSD=X", "GC=F", "CL=F", "NG=F", "GLD", "USO",
    "AAPL", "NVDA", "MSFT", "AMZN", "GOOGL", "META",
    "TSLA", "AMD", "AVGO", "MU", "EURUSD=X", "BTC-USD", "ETH-USD"
]

CSV_PATH = Path("signals.csv")
CSV_FIELDS = [
    "scan_utc", "symbol", "signal", "bar_time", "close",
    "pdh", "pdl", "sweep_extreme", "reason", "data_note"
]


def as_float(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def fetch_daily_levels(symbol):
    # Yahoo daily candles; use the last two completed daily sessions.
    daily = yf.download(
        symbol, period="10d", interval="1d",
        auto_adjust=False, progress=False, threads=False
    )
    if daily is None or daily.empty or len(daily) < 2:
        return None, None
    if isinstance(daily.columns, pd.MultiIndex):
        daily.columns = daily.columns.get_level_values(0)
    prev = daily.iloc[-2]
    return as_float(prev["High"]), as_float(prev["Low"])


def fetch_intraday(symbol):
    # Yahoo 5m history availability is provider-dependent.
    intraday = yf.download(
        symbol, period="5d", interval="5m",
        auto_adjust=False, progress=False, threads=False
    )
    if intraday is None or intraday.empty:
        return None
    if isinstance(intraday.columns, pd.MultiIndex):
        intraday.columns = intraday.columns.get_level_values(0)
    intraday = intraday.dropna(subset=["Open", "High", "Low", "Close"])
    if len(intraday) < 3:
        return None

    # Exclude the latest row because it may still be forming.
    return intraday.iloc[:-1]


def detect_sweep(symbol):
    pdh, pdl = fetch_daily_levels(symbol)
    bars = fetch_intraday(symbol)
    if pdh is None or pdl is None or bars is None or bars.empty:
        return None, "No usable daily or 5m data"

    bar = bars.iloc[-1]
    o, h, l, c = [as_float(bar[k]) for k in ["Open", "High", "Low", "Close"]]
    if None in (o, h, l, c):
        return None, "Incomplete candle values"

    rng = max(h - l, 1e-12)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    bar_time = str(bars.index[-1])

    # Rejection: sweep outside previous-day level, close back inside,
    # and wick is at least 25% of the candle's total range.
    if h > pdh and c < pdh and upper_wick / rng >= 0.25:
        return {
            "symbol": symbol, "signal": "SHORT", "bar_time": bar_time,
            "close": c, "pdh": pdh, "pdl": pdl, "sweep_extreme": h,
            "reason": "PDH swept; completed 5m candle closed back below PDH with upper-wick rejection",
            "data_note": "Yahoo Finance 5m; verify quote timestamp and feed delay"
        }, None

    if l < pdl and c > pdl and lower_wick / rng >= 0.25:
        return {
            "symbol": symbol, "signal": "LONG", "bar_time": bar_time,
            "close": c, "pdh": pdh, "pdl": pdl, "sweep_extreme": l,
            "reason": "PDL swept; completed 5m candle closed back above PDL with lower-wick rejection",
            "data_note": "Yahoo Finance 5m; verify quote timestamp and feed delay"
        }, None

    return None, None


def already_alerted(row):
    if not CSV_PATH.exists():
        return False
    try:
        old = pd.read_csv(CSV_PATH)
        if old.empty:
            return False
        # Avoid duplicate alert for same symbol, signal and 5m bar.
        return (
            (old["symbol"] == row["symbol"]) &
            (old["signal"] == row["signal"]) &
            (old["bar_time"].astype(str) == str(row["bar_time"]))
        ).any()
    except Exception:
        return False


def append_csv(row):
    exists = CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def send_discord(row):
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        return
    msg = (
        f"**{row['signal']} — {row['symbol']}**\n"
        f"Completed 5m candle: `{row['bar_time']}`\n"
        f"Close: `{row['close']}` | PDH: `{row['pdh']}` | PDL: `{row['pdl']}`\n"
        f"Sweep extreme: `{row['sweep_extreme']}`\n"
        f"{row['reason']}\n"
        f"Data: {row['data_note']}\n"
        "_Alert for review only; verify on your broker chart before acting._"
    )
    try:
        r = requests.post(webhook, json={"content": msg}, timeout=15)
        r.raise_for_status()
    except requests.RequestException as exc:
        print(f"Discord delivery failed: {exc}")


def main():
    scan_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"Scan started: {scan_time}")
    found = 0

    for symbol in WATCHLIST:
        try:
            row, error = detect_sweep(symbol)
            if error:
                print(f"{symbol}: DATA UNAVAILABLE — {error}")
                continue
            if row is None:
                print(f"{symbol}: NO TRADE")
                continue

            row["scan_utc"] = scan_time
            if already_alerted(row):
                print(f"{symbol}: duplicate signal skipped")
                continue

            append_csv(row)
            send_discord(row)
            found += 1
            print(f"{symbol}: {row['signal']} — {row['reason']}")
        except Exception as exc:
            print(f"{symbol}: DATA UNAVAILABLE — {type(exc).__name__}: {exc}")

    print(f"Scan complete. New confirmed alerts: {found}")


if __name__ == "__main__":
    main()
