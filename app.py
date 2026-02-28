import os
import time
import requests
import pandas as pd
import gradio as gr
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==============================
# CONFIG SEGURA DE REQUESTS
# ==============================
def create_session():
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "CryptoRadar-Pro"
    })
    return session

SESSION = create_session()
TIMEOUT = 12

# ==============================
# FUNCIONES API (SEGURAS)
# ==============================
def safe_get(url, params=None):
    r = SESSION.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

# ==============================
# ARBITRAJE (BINANCE + MEXC)
# ==============================
def fetch_binance():
    data = safe_get("https://api.binance.com/api/v3/ticker/bookTicker")
    return {d["symbol"]: d for d in data if d["symbol"].endswith("USDT")}

def fetch_mexc():
    data = safe_get("https://api.mexc.com/api/v3/ticker/bookTicker")
    return {d["symbol"]: d for d in data if d["symbol"].endswith("USDT")}

def scan_arbitrage(amount=100):
    try:
        binance = fetch_binance()
        mexc = fetch_mexc()
        common = set(binance.keys()).intersection(mexc.keys())

        rows = []
        for sym in list(common)[:80]:
            try:
                b_ask = float(binance[sym]["askPrice"])
                b_bid = float(binance[sym]["bidPrice"])
                m_ask = float(mexc[sym]["askPrice"])
                m_bid = float(mexc[sym]["bidPrice"])

                # Dirección 1
                buy = b_ask
                sell = m_bid
                profit1 = ((sell - buy) / buy) * 100

                # Dirección 2
                buy2 = m_ask
                sell2 = b_bid
                profit2 = ((sell2 - buy2) / buy2) * 100

                if profit1 > profit2:
                    profit = profit1
                    direction = "BUY Binance → SELL MEXC"
                else:
                    profit = profit2
                    direction = "BUY MEXC → SELL Binance"

                status = "🟢 SAFE" if profit > 0.2 else "🟡 LOW"

                rows.append({
                    "Status": status,
                    "Symbol": sym,
                    "Profit %": round(profit, 4),
                    "Direction": direction
                })
            except:
                continue

        df = pd.DataFrame(rows).sort_values("Profit %", ascending=False).head(30)
        return df
    except Exception as e:
        return pd.DataFrame({"Error":[str(e)]})

# ==============================
# SEÑALES SPOT (1H)
# ==============================
def fetch_klines(symbol="BTCUSDT"):
    url = "https://api.mexc.com/api/v3/klines"
    params = {"symbol": symbol, "interval": "60m", "limit": 200}
    data = safe_get(url, params=params)
    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume","x","y"
    ])
    df["close"] = pd.to_numeric(df["close"])
    return df

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def scan_signals(capital=200):
    try:
        tickers = safe_get("https://api.mexc.com/api/v3/ticker/24hr")
        rows = []

        for t in tickers[:120]:
            sym = t["symbol"]
            if not sym.endswith("USDT"):
                continue

            try:
                df = fetch_klines(sym)
                if len(df) < 50:
                    continue

                last = df["close"].iloc[-1]
                r = rsi(df["close"]).iloc[-1]

                if r < 35:
                    entry = last
                    stop = last * 0.95
                    t1 = last * 1.05
                    t2 = last * 1.10

                    position = capital * 0.2
                    qty = position / entry

                    rows.append({
                        "Status": "🟢 BUY",
                        "Symbol": sym,
                        "Entry": round(entry,6),
                        "Stop": round(stop,6),
                        "Target 1": round(t1,6),
                        "Target 2": round(t2,6),
                        "RSI": round(r,2),
                        "Position USDT": round(position,2),
                        "Qty": round(qty,4)
                    })
            except:
                continue

        df = pd.DataFrame(rows).head(25)
        return df
    except Exception as e:
        return pd.DataFrame({"Error":[str(e)]})

# ==============================
# INTERFAZ PROFESIONAL
# ==============================
with gr.Blocks(title="Crypto Radar Pro", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🚀 Crypto Radar PRO")
    gr.Markdown("Arbitraje + Señales SPOT profesionales")

    with gr.Tabs():
        with gr.Tab("📡 Arbitraje"):
            amount = gr.Number(value=100, label="Monto (USDT)")
            btn_arb = gr.Button("Escanear Arbitraje")
            table_arb = gr.Dataframe()

            btn_arb.click(
                fn=scan_arbitrage,
                inputs=amount,
                outputs=table_arb
            )

        with gr.Tab("🎯 Señales SPOT 1H"):
            capital = gr.Number(value=200, label="Capital (USDT)")
            btn_sig = gr.Button("Buscar Señales")
            table_sig = gr.Dataframe()

            btn_sig.click(
                fn=scan_signals,
                inputs=capital,
                outputs=table_sig
            )

# ==============================
# LAUNCH SEGURO (SERVIDOR + HF)
# ==============================
demo.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("PORT", 7860)),
    share=False
)
