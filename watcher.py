import hmac
import hashlib
import time
import json
import requests

API_KEY    = "NjOflg3Wd05i4SV6w3"
API_SECRET = "TpeW3oHq44G79NwiSY4SQJH0IfNfFvkEYSCE"
BASE_URL   = "https://api-demo.bybit.com"
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

def sign(ts, data):
    payload = ts + API_KEY + RECV_WIN + data
    return hmac.new(API_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()

def bybit_get(path, qs):
    ts  = str(int(time.time() * 1000))
    sig = sign(ts, qs)
    h   = {"X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": ts,
           "X-BAPI-RECV-WINDOW": RECV_WIN, "X-BAPI-SIGN": sig}
    return requests.get(f"{BASE_URL}{path}?{qs}", headers=h, timeout=10).json()

def bybit_post(path, body_dict):
    body = json.dumps(body_dict, separators=(",", ":"))
    ts   = str(int(time.time() * 1000))
    sig  = sign(ts, body)
    h    = {"X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": RECV_WIN, "X-BAPI-SIGN": sig,
            "Content-Type": "application/json"}
    return requests.post(BASE_URL + path, headers=h, data=body, timeout=10).json()

def set_sl(price):
    return bybit_post("/v5/position/trading-stop", {
        "category": "linear", "symbol": "BTCUSDT",
        "stopLoss": str(price), "slTriggerBy": "MarkPrice",
        "positionIdx": 1
    })

def send_tg(msg):
    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                  json={"chat_id": TG_CHAT, "text": msg}, timeout=10)

def main():
    now = time.strftime("%H:%M UTC", time.gmtime())

    t    = bybit_get("/v5/market/tickers", "category=linear&symbol=BTCUSDT")
    mark = float(t["result"]["list"][0]["markPrice"])

    p    = bybit_get("/v5/position/list", "category=linear&symbol=BTCUSDT")
    buys = [x for x in p["result"]["list"] if x["side"] == "Buy"]
    pos  = buys[0] if buys else None
    size = float(pos["size"]) if pos else 0
    sl   = float(pos["stopLoss"]) if pos and pos["stopLoss"] else 0
    upnl = float(pos["unrealisedPnl"]) if pos else 0
    arrow = "+" if upnl >= 0 else ""

    print(f"[{now}] mark={mark} size={size} sl={sl} pnl={arrow}{round(upnl,2)}")

    if size == 0:
        send_tg(f"[CLOSED] BTCUSDT - {now}\n\nPosition closed.\nMark: {mark}")

    elif size <= AFTER_TP2 and sl < TP1_PRICE:
        r = set_sl(TP1_SL)
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
        r = set_sl(BE_SL)
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
        send_tg(f"[UPDATE] BTCUSDT - {now}\n\n"
                f"Mark  : {mark}\n"
                f"Size  : {size} BTC\n"
                f"SL    : {sl}\n"
                f"PnL   : {arrow}${round(upnl,2)} USDT ({arrow}{pct}%)\n"
                f"TP2 : {TP2_PRICE} | TP3 : {TP3_PRICE}")

if __name__ == "__main__":
    while True:
        main()
        time.sleep(30)
