import hmac
import hashlib
import time
import json
import requests

API_KEY    = "NjOflg3Wd05i4SV6w3"
API_SECRET = "TpeW3oHq44G79NwiSY4SQJH0IfNfFvkEYSCE"
DEMO_URL   = "https://api-demo.bybit.com"
RECV_WIN   = "5000"
TG_TOKEN   = "6921057621:AAG1ZV7RJlx6zGo_mML2vSPDxAZX86t9-S8"
TG_CHAT    = "6664537343"

ENTRY     = 78175.70
TP1_PRICE = 78430.0
TP2_PRICE = 78700.0
TP3_PRICE = 78900.0
AFTER_TP1 = 0.043
AFTER_TP2 = 0.022
BE_SL     = ENTRY
TP1_SL    = TP1_PRICE

HEADERS_BASE = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def sign(ts, data):
    payload = ts + API_KEY + RECV_WIN + data
    return hmac.new(API_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()

def private_get(path, qs):
    ts  = str(int(time.time() * 1000))
    sig = sign(ts, qs)
    h   = {**HEADERS_BASE, "X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": ts,
           "X-BAPI-RECV-WINDOW": RECV_WIN, "X-BAPI-SIGN": sig}
    r = requests.get(f"{DEMO_URL}{path}?{qs}", headers=h, timeout=10)
    print(f"POS STATUS: {r.status_code} | BODY: {r.text[:300]}")
    return r.json()

def private_post(path, body_dict):
    body = json.dumps(body_dict, separators=(",", ":"))
    ts   = str(int(time.time() * 1000))
    sig  = sign(ts, body)
    h    = {**HEADERS_BASE, "X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": RECV_WIN, "X-BAPI-SIGN": sig,
            "Content-Type": "application/json"}
    r = requests.post(DEMO_URL + path, headers=h, data=body, timeout=10)
    print(f"POST STATUS: {r.status_code} | BODY: {r.text[:300]}")
    return r.json()

def set_sl(price):
    return private_post("/v5/position/trading-stop", {
        "category": "linear", "symbol": "BTCUSDT",
        "stopLoss": str(price), "slTriggerBy": "MarkPrice",
        "positionIdx": 1
    })

def send_tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                      json={"chat_id": TG_CHAT, "text": msg}, timeout=10)
        print(f"TG SENT: {msg[:80]}")
    except Exception as e:
        print(f"TG ERROR: {e}")

def main():
    now = time.strftime("%H:%M UTC", time.gmtime())
    print(f"\n=== CHECK {now} ===")

    mark = None
    errors = []
    sources = [
        ("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", lambda d: float(d["price"])),
        ("https://api.kraken.com/0/public/Ticker?pair=XBTUSD",         lambda d: float(d["result"]["XXBTZUSD"]["c"][0])),
        ("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", lambda d: float(d["bitcoin"]["usd"])),
    ]
    for url, extractor in sources:
        try:
            resp = requests.get(url, headers=HEADERS_BASE, timeout=10)
            mark = extractor(resp.json())
            print(f"MARK from {url[:30]}: {mark}")
            break
        except Exception as e:
            errors.append(f"{url[8:30]}: {e}")
            print(f"TICKER FAIL: {e}")
    if mark is None:
        send_tg("[ERROR] All tickers failed:\n" + "\n".join(errors))
        return

    try:
        p    = private_get("/v5/position/list", "category=linear&symbol=BTCUSDT")
        buys = [x for x in p["result"]["list"] if x["side"] == "Buy"]
        pos  = buys[0] if buys else None
        size = float(pos["size"]) if pos else 0
        sl   = float(pos["stopLoss"]) if pos and pos["stopLoss"] else 0
        upnl = float(pos["unrealisedPnl"]) if pos else 0
    except Exception as e:
        print(f"POSITION ERROR: {e}")
        send_tg(f"[ERROR] Position failed: {e}")
        return

    arrow = "+" if upnl >= 0 else ""
    print(f"mark={mark} size={size} sl={sl} pnl={arrow}{round(upnl,2)}")

    if size == 0:
        send_tg(f"[CLOSED] BTCUSDT - {now}\n\nPosition closed.\nMark: {mark}")

    elif size <= AFTER_TP2 and sl < TP1_PRICE:
        r   = set_sl(TP1_SL)
        pnl = round(0.021 * (TP2_PRICE - ENTRY), 2)
        send_tg(f"[TP2 HIT] BTCUSDT - {now}\n\n"
                f"TP2 filled : {TP2_PRICE}\n"
                f"Profit     : +${pnl} USDT\n"
                f"SL -> TP1  : {TP1_SL}\n"
                f"Remaining  : {size} BTC\n"
                f"Mark       : {mark}\n"
                f"PnL        : {arrow}${round(upnl,2)} USDT\n"
                f"TP3 : {TP3_PRICE} | code={r['retCode']}")

    elif size <= AFTER_TP1 and sl < ENTRY:
        r   = set_sl(BE_SL)
        pnl = round(0.021 * (TP1_PRICE - ENTRY), 2)
        send_tg(f"[TP1 HIT] BTCUSDT - {now}\n\n"
                f"TP1 filled : {TP1_PRICE}\n"
                f"Profit     : +${pnl} USDT\n"
                f"SL -> BE   : {BE_SL}\n"
                f"Remaining  : {size} BTC\n"
                f"Mark       : {mark}\n"
                f"PnL        : {arrow}${round(upnl,2)} USDT\n"
                f"TP2 : {TP2_PRICE} | TP3 : {TP3_PRICE}\n"
                f"Risk-free | code={r['retCode']}")

    else:
        pct = round(((mark - ENTRY) / ENTRY) * 100, 3)
        print(f"[WATCHING] mark={mark} size={size} sl={sl} pnl={arrow}{round(upnl,2)} ({arrow}{pct}%)")

if __name__ == "__main__":
    import os
    if os.getenv("ONCE"):
        main()
    else:
        while True:
            try:
                main()
            except Exception as e:
                print(f"LOOP ERROR: {e}")
            time.sleep(30)
