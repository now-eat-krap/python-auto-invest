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

SENSITIVITY = sensitivity
ATR_PERIOD = atr_period

def data_setting():
    df = pd.DataFrame()
    ohlcv_now= exchange.fetch_ohlcv(symbols, '5m', limit=1000)
    ohlcv = []

    for _ in range(4):
        ohlcv += exchange.fetch_ohlcv(symbols, '5m',since=int(ohlcv_now[0][0]- (4-_) * 500000000), limit=1000)

    ohlcv += ohlcv_now
    time = [datetime.fromtimestamp(ohlcv[i][0]/1000) for i in range(len(ohlcv))]

    # setting ohlc
    df['time'] = time
    df['open'] = np.array(ohlcv).T[1]
    df['high'] = np.array(ohlcv).T[2]
    df['low'] = np.array(ohlcv).T[3]
    df['close'] = np.array(ohlcv).T[4]

    df["xATR"] = ta.atr(df['high'],df['low'],df['close'], ATR_PERIOD)
    df["nLoss"] = SENSITIVITY * df["xATR"]
    df["ATRTrailingStop"] = [0.0] + [np.nan for i in range(len(df) - 1)]
    # setting ATRTrailingStop
    for i in range(1, len(df)):
        if df.loc[i, "close"] > df.loc[i - 1, "ATRTrailingStop"] and df.loc[i - 1, "close"] > df.loc[i - 1, "ATRTrailingStop"]:
            df.loc[i, "ATRTrailingStop"] = max(df.loc[i - 1, "ATRTrailingStop"], df.loc[i, "close"] - df.loc[i, "nLoss"])
        elif df.loc[i, "close"] < df.loc[i - 1, "ATRTrailingStop"] and df.loc[i - 1, "close"] < df.loc[i - 1, "ATRTrailingStop"]:
            df.loc[i, "ATRTrailingStop"] = min(df.loc[i - 1, "ATRTrailingStop"], df.loc[i, "close"] + df.loc[i, "nLoss"])
        elif df.loc[i, "close"] > df.loc[i - 1, "ATRTrailingStop"]:
            df.loc[i, "ATRTrailingStop"] = df.loc[i, "close"] - df.loc[i, "nLoss"]
        else:
            df.loc[i, "ATRTrailingStop"] = df.loc[i, "close"] + df.loc[i, "nLoss"]

    # setting ut_bot_alerts
    ema = vbt.MA.run(df["close"], 1, short_name='EMA', ewm=True)
    #print(ema.ema)
    df["Above"] = ema.ma_crossed_above(df["ATRTrailingStop"])
    df["Below"] = ema.ma_crossed_below(df["ATRTrailingStop"])
    df["Buy"] = (df["close"] > df["ATRTrailingStop"]) & (df["Above"]==True)
    df["Sell"] = (df["close"] < df["ATRTrailingStop"]) & (df["Below"]==True)

    #필요한 정보만 보존
    #df = df.iloc[len(df)-ATR_PERIOD-2:-1]
    df = df.iloc[-3:-1]

    return df

class Indicators:
    def now_data(self,df):
        now_data_ = pd.DataFrame()
        ohlcv = exchange.fetch_ohlcv(symbols, '5m', limit=2)

        #now_ohlcv = exchange.fetch_ticker(symbols)

        time = [datetime.fromtimestamp(ohlcv[i][0]/1000) for i in range(len(ohlcv))]

        # setting ohlc
        now_data_['time'] = time
        now_data_['open'] = np.array(ohlcv).T[1]
        now_data_['high'] = np.array(ohlcv).T[2]
        now_data_['low'] = np.array(ohlcv).T[3]
        now_data_['close'] = np.array(ohlcv).T[4]

        #초기데이터에 현재데이터 concat
        df = pd.concat([df,now_data_])
        df = df.iloc[:-1]

        if df.iloc[-1]['time'] == df.iloc[-2]['time']:
            df = df.iloc[:-1]

        df.index = [_ for _ in range(len(df))]

        return df

    def ut_bot_alerts(self,df):
        xTR = max(df.iloc[-1]["high"],df.iloc[-2]["close"]) - min(df.iloc[-1]["low"],df.iloc[-2]["close"])

        xATR = (df.iloc[-2]["xATR"] * (ATR_PERIOD - 1) + xTR) / ATR_PERIOD
        df.loc[len(df)-1,"xATR"] = xATR
        df.loc[len(df)-1,"nLoss"] = SENSITIVITY * df.iloc[-1]["xATR"]

        if df.loc[len(df)-1,"close"] > df.loc[len(df)-2,"ATRTrailingStop"] and df.loc[len(df)-2,"close"] > df.loc[len(df)-2,"ATRTrailingStop"]:
            df.loc[len(df)-1,"ATRTrailingStop"] = max(df.loc[len(df)-2,"ATRTrailingStop"], df.loc[len(df)-1,"close"] - df.loc[len(df)-1,"nLoss"])
        elif df.loc[len(df)-1,"close"] < df.loc[len(df)-2,"ATRTrailingStop"] and df.loc[len(df)-2,"close"] < df.loc[len(df)-2,"ATRTrailingStop"]:
            df.loc[len(df)-1,"ATRTrailingStop"] = min(df.loc[len(df)-2,"ATRTrailingStop"], df.loc[len(df)-1,"close"] + df.loc[len(df)-1,"nLoss"])
        elif df.loc[len(df)-1,"close"] > df.loc[len(df)-2,"ATRTrailingStop"]:
            df.loc[len(df)-1,"ATRTrailingStop"] = df.loc[len(df)-1,"close"] - df.loc[len(df)-1,"nLoss"]
        else:
            df.loc[len(df)-1,"ATRTrailingStop"] = df.loc[len(df)-1,"close"] + df.loc[len(df)-1,"nLoss"]

        if df.iloc[-1]['close'] > df.iloc[-1]["ATRTrailingStop"] and df.iloc[-2]['close'] < df.iloc[-2]["ATRTrailingStop"]:
            df.loc[len(df)-1,"Above"] = True
            df.loc[len(df)-1,"Below"] = False
        elif df.iloc[-1]['close'] < df.iloc[-1]["ATRTrailingStop"] and df.iloc[-2]['close'] > df.iloc[-2]["ATRTrailingStop"]:
            df.loc[len(df)-1,"Below"] = True
            df.loc[len(df)-1,"Above"] = False
        else:
            df.loc[len(df)-1,"Above"] = False
            df.loc[len(df)-1,"Below"] = False

        if df.iloc[-1]['close'] > df.iloc[-1]["ATRTrailingStop"] and df.iloc[-1]["Above"] == True:
            df.loc[len(df)-1,"Buy"] = True
            df.loc[len(df)-1,"Sell"] = False
        elif df.iloc[-1]['close'] < df.iloc[-1]["ATRTrailingStop"] and df.iloc[-1]["Below"] == True:
            df.loc[len(df)-1,"Sell"] = True
            df.loc[len(df)-1,"Buy"] = False
        else:
            df.loc[len(df)-1,"Buy"] = False
            df.loc[len(df)-1,"Sell"] = False

def main():
    exchange.load_markets()
    indicator = Indicators()
    initial_data = data_setting()
    data = indicator.now_data(initial_data)
    indicator.ut_bot_alerts(data)
    print(str(datetime.now().minute)[1:])

    while True:
     now = datetime.now()
     if now.minute % 5 == 0 and now.second < 10:
         time.sleep(1)
         data = indicator.now_data(data)
         indicator.ut_bot_alerts(data)
         # 첫번째 데이터 삭제
         if len(data) != 3:
             data = data.iloc[1:]
             data.index = [_ for _ in range(len(data))]
#        data_ = now_ohlcv()
#        indicator.ut_bot_alerts(data_)

         pprint.pprint(data)
         time.sleep(40)
     elif str(now.minute)[1:] == "4" or str(now.minute)[1:] == "8":
         time.sleep(0.1)
     else:
         time.sleep(50)

if __name__ == '__main__':
    main()
