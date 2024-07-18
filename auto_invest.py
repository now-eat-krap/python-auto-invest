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

with open("/root/auto_invest/api/api.txt") as f:
    lines = f.readlines()
    api_key = lines[0].strip()
    secret = lines[1].strip()

with open("/root/auto_invest/indicator/variable.txt") as f:
    lines = f.readlines
    sensitivity  = int(lines[0].strip())
    atr_period = int(lines[1].strip())

exchange = ccxt.bybit(config={
    'apiKey': api_key,
    'secret': secret,
    'enableRateLimit': True,
})

def now_ohlcv():
    df = pd.DataFrame()
    ohlcv = exchange.fetch_ohlcv(symbols, '5m', limit=402)
    now_ohlcv = exchange.fetch_ticker(symbols)

    time = [datetime.fromtimestamp(ohlcv[i][0]/1000) for i in range(len(ohlcv))]
    #+ timedelta(hours=9)
    #time[-1] = datetime.strptime(now_ohlcv['datetime'], '%Y-%m-%dT%H:%M:%S.%fZ')+ timedelta(hours=9)
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

def main():
    exchange.load_markets()
    logging.basicConfig(filename='/root/bybit/ut/error/error.log', level=logging.ERROR)
    indicator = Indicators()

    while True:
        now = datetime.now()
    #if now.minute % 5 == 0:
    #    time.sleep(1)
        try:
            open_ = check.open_orders()
            position_ = check.positions()

            data_ = now_ohlcv()
            indicator.ut_bot_alerts(data_)

            time.sleep(5)

        except:
            print("error:",now)
            logging.error(traceback.format_exc())

if __name__ == '__main__':
    main()
