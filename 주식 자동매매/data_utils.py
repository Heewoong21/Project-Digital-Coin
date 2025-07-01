import pyupbit

def get_ohlcv(coin, interval="day", count=30):
    df = pyupbit.get_ohlcv(f"KRW-{coin}", interval=interval, count=count)
    if df is not None:
        df.columns = [c.lower() for c in df.columns]
    return df

def format_hover_text(df):
    return [
        f"<b>{idx.strftime('%Y-%m-%d %H:%M')}</b><br>"
        f"Open: {row['open']:,.0f}원<br>"
        f"High: {row['high']:,.0f}원<br>"
        f"Low: {row['low']:,.0f}원<br>"
        f"Close: {row['close']:,.0f}원<br>"
        f"거래대금: {row['volume']:,.0f}원"
        for idx, row in df.iterrows()
    ]
