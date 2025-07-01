def check_trade_signal(df, strategy="sma"):
    if strategy == "sma":
        df["MA5"] = df["Close"].rolling(5).mean()
        df["MA10"] = df["Close"].rolling(10).mean()
        if df["MA5"].iloc[-2] < df["MA10"].iloc[-2] and df["MA5"].iloc[-1] > df["MA10"].iloc[-1]:
            return "buy"
        elif df["MA5"].iloc[-2] > df["MA10"].iloc[-2] and df["MA5"].iloc[-1] < df["MA10"].iloc[-1]:
            return "sell"
    elif strategy == "rsi":
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        if rsi.iloc[-1] < 30:
            return "buy"
        elif rsi.iloc[-1] > 70:
            return "sell"
    elif strategy == "macd":
        ema12 = df["Close"].ewm(span=12, adjust=False).mean()
        ema26 = df["Close"].ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        if macd.iloc[-2] < signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1]:
            return "buy"
        elif macd.iloc[-2] > signal.iloc[-2] and macd.iloc[-1] < signal.iloc[-1]:
            return "sell"
    elif strategy == "bollinger":
        ma20 = df["Close"].rolling(20).mean()
        std = df["Close"].rolling(20).std()
        upper = ma20 + 2 * std
        lower = ma20 - 2 * std
        if df["Close"].iloc[-2] > lower.iloc[-2] and df["Close"].iloc[-1] < lower.iloc[-1]:
            return "buy"
        elif df["Close"].iloc[-2] < upper.iloc[-2] and df["Close"].iloc[-1] > upper.iloc[-1]:
            return "sell"
    elif strategy == "vbreak":
        k = 0.5
        yesterday = df.iloc[-2]
        today_open = df.iloc[-1]['Open']
        target_price = yesterday['Close'] + (yesterday['High'] - yesterday['Low']) * k
        if today_open < target_price and df.iloc[-1]['Close'] > target_price:
            return "buy"
    return None
