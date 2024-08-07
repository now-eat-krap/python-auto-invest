import ccxt
import pprint
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import vectorbt as vbt
import pandas_ta as ta
import time
import logging
import traceback

symbols = "ETH/USDT:USDT"

with open("/root/python-auto-invest/api/api.txt") as f:
    lines = f.readlines()
    api_key = lines[0].strip()
    secret = lines[1].strip()

with open("/root/python-auto-invest/indicator/variable.txt") as f:
    lines = f.readlines()
    sensitivity  = int(lines[0].strip())
    atr_period = int(lines[1].strip())

exchange = ccxt.bybit(config={
    'apiKey': api_key,
    'secret': secret,
    'enableRateLimit': True,
})

def now_ohlcv():
    df = pd.DataFrame()

    ohlcv_now= exchange.fetch_ohlcv(symbols, '5m', limit=1000)
    ohlcv = []

    for _ in range(4):
        ohlcv += exchange.fetch_ohlcv(symbols, '5m',since=int(ohlcv_now[0][0]- (4-_) * 500000000), limit=1000)

    ohlcv += ohlcv_now
    time = [datetime.fromtimestamp(ohlcv[i][0]/1000) for i in range(len(ohlcv))]

    df['time'] = time
    df['open'] = np.array(ohlcv).T[1]
    df['high'] = np.array(ohlcv).T[2]
    df['low'] = np.array(ohlcv).T[3]
    df['close'] = np.array(ohlcv).T[4]

    return df

class Indicators:
    def ut_bot_alerts(self,df):
        SENSITIVITY = sensitivity
        ATR_PERIOD = atr_period
        df["xATR"] = ta.atr(df['high'],df['low'],df['close'], ATR_PERIOD)
        df["nLoss"] = SENSITIVITY * df["xATR"]
        df["ATRTrailingStop"] = [0.0] + [np.nan for i in range(len(df) - 1)]
        for i in range(1, len(df)):
            if df.loc[i, "close"] > df.loc[i - 1, "ATRTrailingStop"] and df.loc[i - 1, "close"] > df.loc[i - 1, "ATRTrailingStop"]:
                df.loc[i, "ATRTrailingStop"] = max(df.loc[i - 1, "ATRTrailingStop"], df.loc[i, "close"] - df.loc[i, "nLoss"])
            elif df.loc[i, "close"] < df.loc[i - 1, "ATRTrailingStop"] and df.loc[i - 1, "close"] < df.loc[i - 1, "ATRTrailingStop"]:
                df.loc[i, "ATRTrailingStop"] = min(df.loc[i - 1, "ATRTrailingStop"], df.loc[i, "close"] + df.loc[i, "nLoss"])
            elif df.loc[i, "close"] > df.loc[i - 1, "ATRTrailingStop"]:
                df.loc[i, "ATRTrailingStop"] = df.loc[i, "close"] - df.loc[i, "nLoss"]
            else:
                df.loc[i, "ATRTrailingStop"] = df.loc[i, "close"] + df.loc[i, "nLoss"]

        ema = vbt.MA.run(df["close"], 1, short_name='EMA', ewm=True)
        df["Above"] = ema.ma_crossed_above(df["ATRTrailingStop"])
        df["Below"] = ema.ma_crossed_below(df["ATRTrailingStop"])
        df["Buy"] = (df["close"] > df["ATRTrailingStop"]) & (df["Above"]==True)
        df["Sell"] = (df["close"] < df["ATRTrailingStop"]) & (df["Below"]==True)
        #df.drop(["xATR","nLoss","ATRTrailingStop","Above","Below"], axis=1, inplace=True)
        print(df.to_string())

def main():
    exchange.load_markets()
    indicator = Indicators()
    now = datetime.now()
    data_ = now_ohlcv()
    indicator.ut_bot_alerts(data_)

    #while True:
    #    if now.minute % 5 == 0:
    #        time.sleep(1)
    #        data_ = now_ohlcv()
    #        indicator.ut_bot_alerts(data_)

    #        pprint.pprint(data_)
    #        time.sleep(5)


if __name__ == '__main__':
    main()
