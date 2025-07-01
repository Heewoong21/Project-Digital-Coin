from config import upbit, virtual_balance
from data_utils import get_ohlcv
from charting import plot_candle_chart, plot_line_chart
from model_utils import predict_rnn, detect_anomaly_lstm
from strategy import check_trade_signal
import time
import pyupbit

def track_profit_loop(entry_price, coin):
    print("\n📈 수익/손실 추적 중 (5초 간격)... 중단하려면 Ctrl+C")
    try:
        while virtual_balance["COIN"] > 0:
            price = pyupbit.get_current_price(f"KRW-{coin}")  # ✅ 수정
            if price:
                rate = (price - entry_price) / entry_price * 100
                total = virtual_balance["COIN"] * price
                profit = total - (virtual_balance["COIN"] * entry_price)
                print(f"현재가: {price:,.0f} KRW | 총 평가금액: {total:,.0f} KRW | 손익: {profit:,.0f}원 | 수익률: {rate:.2f}%")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n⏹️ 수익/손익 추적 종료")


def main():
    print("⚙️ 모드 선택: 1. 모의투자  2. 실전 매매")
    mode_choice = input("선택 (1~2): ")
    is_real_trade = (mode_choice == "2")

    print("\n✅ 공통 코인 목록:")
    coins = pyupbit.get_tickers(fiat="KRW")
    print(", ".join([coin.split("-")[1] for coin in coins]))

    coin = input("\n조회할 코인 입력 (예: BTC): ").upper()
    if f"KRW-{coin}" not in coins:
        print("❌ 잘못된 코인")
        return

    print("\n📆 조회 단위 선택:")
    print("1. 분봉(5분)")
    print("2. 일봉")
    print("3. 월봉")
    print("4. 년 단위 평균")
    tf_choice = input("선택 (1~4): ")

    interval_map = {"1": "minute5", "2": "day", "3": "month"}
    interval = interval_map.get(tf_choice, "day")
    count = 60 if interval == "day" else 30 if interval == "minute5" else 12

    df = get_ohlcv(coin, interval=interval, count=count)
    if tf_choice == "4":
        df = df.resample("Y").mean()

    print("\n📊 차트 타입 선택:")
    print("1. 캔들 차트")
    print("2. 전체 지표 그래프")
    chart_choice = input("선택 (1~2): ")
    if chart_choice == "1":
        plot_candle_chart(df, coin)
    elif chart_choice == "2":
        plot_line_chart(df, coin)

    predict_rnn(df)
    detect_anomaly_lstm(df)

    print("\n📌 매매 전략 선택:")
    print("1. SMA (이동 평균 교차)")
    print("2. RSI (상대 강도 지수)")
    print("3. MACD")
    print("4. Bollinger Bands")
    print("5. 변동성 돌파 전략")
    strategy_map = {"1": "sma", "2": "rsi", "3": "macd", "4": "bollinger", "5": "vbreak"}
    strategy_choice = input("선택 (1~5): ")
    strategy = strategy_map.get(strategy_choice, "sma")

    signal = check_trade_signal(df, strategy)

    print("\n📌 얼마어치 매수할지 입력 (예: 100000):")
    try:
        krw_input = float(input("금액 (KRW): "))
    except:
        krw_input = 100000

    price = df["Close"].iloc[-1]
    amount = krw_input / price
    cost = amount * price

    if signal == "buy" and virtual_balance["KRW"] >= cost:
        virtual_balance["COIN"] += amount
        virtual_balance["KRW"] -= cost
        virtual_balance["last_price"] = price
        print(f"🟢 매수 완료 (전략 {strategy}): {amount:.6f}개 @ {price:,.0f} KRW")
    elif signal == "sell" and virtual_balance["COIN"] > 0:
        revenue = virtual_balance["COIN"] * price
        print(f"🔴 매도 완료 (전략 {strategy}): {virtual_balance['COIN']:.6f}개 @ {price:,.0f} KRW")
        virtual_balance["KRW"] += revenue
        virtual_balance["COIN"] = 0
    elif signal is None:
        confirm = input("📉 시그널 없음. 강제로 매수하시겠습니까? (y/n): ").lower()
        if confirm == 'y' and virtual_balance["KRW"] >= cost:
            virtual_balance["COIN"] += amount
            virtual_balance["KRW"] -= cost
            virtual_balance["last_price"] = price
            print(f"🟢 강제 매수: {amount:.6f}개 @ {price:,.0f} KRW")
    else:
        print("⚠️ 조건에 맞는 시그널 없음 또는 잔액 부족")


if __name__ == "__main__":
    while True:
        main()
        if virtual_balance["COIN"] > 0:
            coin = input("\n실시간 수익률 확인용 코인 입력 (예: BTC): ").upper()
            track_profit_loop(virtual_balance["last_price"], coin)
        again = input("\n다시 실행할까요? (y/n): ")
        if again.lower() != 'y':
            break
