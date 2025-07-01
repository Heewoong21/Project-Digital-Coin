import os
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"

import sys
import pyupbit
from PyQt5 import uic
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QTableWidgetItem,
    QPushButton, QLineEdit, QTableWidget, QTextEdit, QCheckBox, QPlainTextEdit, QSpinBox
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QTimer, QDateTime, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QColor
import time

from config import virtual_balance
from data_utils import get_ohlcv
from charting import plot_candle_chart
from model_utils import predict_rnn, detect_anomaly_lstm

# 가격 및 ohlcv 캐시 (전역)
price_cache = {}
price_cache_time = {}
price_cache_ttl = 10  # 초
ohlcv_cache = {}
ohlcv_cache_time = {}
ohlcv_cache_ttl = 10  # 초

class CoinListWorker(QThread):
    result = pyqtSignal(list)
    def run(self):
        print("🛠️ CoinListWorker.run() 시작")
        try:
            tickers = pyupbit.get_tickers(fiat="KRW")
            print(f"✅ 티커 수신 성공: {len(tickers)}개")
            now = time.time()
            # 가격 일괄 조회
            prices = pyupbit.get_current_price(tickers)
            data = []
            for ticker in tickers:
                coin_name = ticker.split("-")[1]
                try:
                    price = prices.get(ticker)
                    if price is None or isinstance(price, dict):
                        continue
                    price_cache[ticker] = price
                    price_cache_time[ticker] = now
                    price_text = f"{price:,.0f}"
                    data.append((coin_name, price_text, "-"))
                except:
                    continue
            print("📤 emit 호출")
            self.result.emit(data)
        except Exception as e:
            print(f"❌ CoinListWorker 전체 실패: {e}")
            self.result.emit([])

class AutoTradeWorker(QThread):
    def __init__(self, coin, callback, update_ui_callback=None, profit_pct=5, stoploss_pct=3):
        super().__init__()
        self.coin = coin
        self.callback = callback
        self.update_ui_callback = update_ui_callback
        self.running = True
        self.profit_pct = profit_pct
        self.stoploss_pct = stoploss_pct
        self.buy_price = None

    def run(self):
        from strategy import check_trade_signal
        from config import virtual_balance
        import pyupbit
        from data_utils import get_ohlcv
        from PyQt5.QtCore import QDateTime
        import time
        
        while self.running:
            df = get_ohlcv(self.coin, interval="day", count=60)
            if df is not None:
                signal = check_trade_signal(df, strategy="vbreak")
                price = pyupbit.get_current_price(f"KRW-{self.coin}")
                if price is None or isinstance(price, dict):
                    self.callback(f"[{QDateTime.currentDateTime().toString()}] {self.coin} 가격 조회 실패")
                    break
                amount = 0
                # 매수
                if signal == "buy" and virtual_balance["KRW"] >= price:
                    invest_krw = virtual_balance["KRW"] * 0.1
                    amount = invest_krw / price
                    virtual_balance["COIN"] += amount
                    virtual_balance["KRW"] -= amount * price
                    virtual_balance["last_price"] = price
                    self.buy_price = price
                    self.callback(f"[{QDateTime.currentDateTime().toString()}] {self.coin} 변동성돌파 매수: {amount:.6f}개 @ {price:,.0f} KRW")
                    if self.update_ui_callback:
                        self.update_ui_callback()
                # 매도 (익절/손절)
                elif virtual_balance["COIN"] > 0 and self.buy_price:
                    profit_rate = (price - self.buy_price) / self.buy_price * 100
                    if profit_rate >= self.profit_pct:
                        amount = virtual_balance["COIN"]
                        proceeds = amount * price
                        virtual_balance["KRW"] += proceeds
                        virtual_balance["COIN"] = 0.0
                        virtual_balance["last_price"] = price
                        self.callback(f"[{QDateTime.currentDateTime().toString()}] {self.coin} 익절 매도: {amount:.6f}개 @ {price:,.0f} KRW (수익률: {profit_rate:+.2f}%)")
                        if self.update_ui_callback:
                            self.update_ui_callback()
                        self.buy_price = None
                    elif profit_rate <= -self.stoploss_pct:
                        amount = virtual_balance["COIN"]
                        proceeds = amount * price
                        virtual_balance["KRW"] += proceeds
                        virtual_balance["COIN"] = 0.0
                        virtual_balance["last_price"] = price
                        self.callback(f"[{QDateTime.currentDateTime().toString()}] {self.coin} 손절 매도: {amount:.6f}개 @ {price:,.0f} KRW (수익률: {profit_rate:+.2f}%)")
                        if self.update_ui_callback:
                            self.update_ui_callback()
                        self.buy_price = None
                    else:
                        self.callback(f"[{QDateTime.currentDateTime().toString()}] {self.coin} 변동성돌파 시그널 없음 또는 조건 불충족 (수익률: {profit_rate:+.2f}%)")
                else:
                    self.callback(f"[{QDateTime.currentDateTime().toString()}] {self.coin} 변동성돌파 시그널 없음 또는 조건 불충족")
            else:
                self.callback(f"[{QDateTime.currentDateTime().toString()}] {self.coin} 데이터 로딩 실패")
            time.sleep(10)

    def stop(self):
        self.running = False

class TradingWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.ui")
        uic.loadUi(ui_path, self)
        self.df = None

        self.CoinList = self.findChild(QTableWidget, "CoinList")
        self.Cointable = self.findChild(QTableWidget, "Cointable")
        self.VirtualCoin = self.findChild(QTableWidget, "VirtualCoin")
        self.RealCoin = self.findChild(QTableWidget, "RealCoin")
        self.Datalog = self.findChild(QPlainTextEdit, "Datalog")
        self.Insertbtn = self.findChild(QPushButton, "Insert")
        self.Insertcoin = self.findChild(QLineEdit, "Insertcoin")
        self.Sellbtn = self.findChild(QPushButton, "Sell")
        self.APIbtn = self.findChild(QPushButton, "APIbtn")
        self.Startbtn = self.findChild(QPushButton, "Startbtn")
        self.Stopbtn = self.findChild(QPushButton, "Stopbtn")
        self.Resetbtn = self.findChild(QPushButton, "Resetbtn")
        self.Resetbtn_2 = self.findChild(QPushButton, "Resetbtn_2")
        self.Virtual = self.findChild(QCheckBox, "Virtual")
        self.CandleChart = self.findChild(QWebEngineView, "CandleChart")
        self.profitbox = self.findChild(QSpinBox, "profitbox")
        self.stoplossbox = self.findChild(QSpinBox, "stoplossbox")
        self.settingbtn = self.findChild(QPushButton, "settingbtn")
        self.PrevPageBtn = self.findChild(QPushButton, "previousBtn")
        self.NextPageBtn = self.findChild(QPushButton, "nextBtn")

        self.Insertbtn.clicked.connect(self.buy_virtual_coin)
        self.Sellbtn.clicked.connect(self.sell_virtual_coin)
        self.APIbtn.clicked.connect(self.api_key_input)
        self.Startbtn.clicked.connect(self.start_trading)
        self.Stopbtn.clicked.connect(self.stop_trading)
        self.Resetbtn.clicked.connect(self.refresh_market)
        self.Resetbtn_2.clicked.connect(self.refresh_holdings)
        self.PrevPageBtn.clicked.connect(self.show_prev_coinlist_page)
        self.NextPageBtn.clicked.connect(self.show_next_coinlist_page)

        self.CoinList.cellDoubleClicked.connect(self.on_coin_selected)
        self.Virtual.setChecked(True)
        self.VirtualCoin.setVisible(self.Virtual.isChecked())
        self.Virtual.stateChanged.connect(self.toggle_virtual_ui)
        self.settingbtn.clicked.connect(self.apply_trade_settings)

        virtual_balance["KRW"] = 1_000_000
        virtual_balance["COIN"] = 0.0
        virtual_balance["last_price"] = 0.0

        self.trade_settings = {"profit": 5, "stoploss": 3}  # 기본값(%)

        self.update_virtual_coin_table()
        self.update_real_coin_table()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(10000)

        self.load_coin_list()
        self.setup_cointable_header()

        # 페이지 상태 추가
        self.coinlist_page = 0
        self.coinlist_data = []

    def api_key_input(self):
        QMessageBox.information(self, "API 입력", "API 입력 버튼이 눌렸습니다.")

    def refresh_market(self):
        self.load_coin_list()
        QMessageBox.information(self, "시장 갱신", "실시간 시장 데이터 갱신 완료")

    def refresh_holdings(self):
        # 보유 코인 테이블의 수익률 갱신
        for row in range(self.Cointable.rowCount()):
            coin = self.Cointable.item(row, 0).text()
            buy_price = float(self.Cointable.item(row, 1).text().replace(",", ""))
            self.update_profit_rate(row, coin, buy_price)
        self.update_real_coin_table()
        QMessageBox.information(self, "보유자산 갱신", "보유 코인 데이터 갱신 완료")

    def update_virtual_coin_table(self):
        krw = virtual_balance['KRW']
        coin = virtual_balance['COIN']
        last_price = virtual_balance['last_price']
        est_value = coin * last_price
        # 보유 코인 없으면 구매금액 0, 수익률 0
        if coin == 0.0:
            buy_amount = 0.0
            profit_rate = 0.0
        else:
            buy_amount = 1_000_000 - krw  # 실제 투자한 금액
            total_asset = krw + est_value
            if buy_amount > 0:
                profit_rate = ((total_asset - 1_000_000) / buy_amount) * 100
            else:
                profit_rate = 0.0
        fee = virtual_balance.get('FEE', 0.0)
        self.VirtualCoin.setItem(0, 0, QTableWidgetItem(f"{krw:,.0f} 원"))                # 보유금액(현금)
        self.VirtualCoin.setItem(1, 0, QTableWidgetItem(f"{buy_amount:,.0f} 원"))         # 구매금액(투자한 금액)
        self.VirtualCoin.setItem(2, 0, QTableWidgetItem(f"{est_value:,.0f} 원"))          # 총 수익 금액(코인 평가금액)
        self.VirtualCoin.setItem(3, 0, QTableWidgetItem(f"{profit_rate:+.2f}%"))          # 총 수익률
        self.VirtualCoin.setItem(4, 0, QTableWidgetItem(f"{est_value:,.0f} 원"))          # 총 평가금액
        self.VirtualCoin.setItem(5, 0, QTableWidgetItem(f"{krw + est_value:,.0f} 원"))    # 총 자산
        self.VirtualCoin.setItem(6, 0, QTableWidgetItem(f"{fee:,.0f} 원"))                # 수수료

    def update_real_coin_table(self):
        krw = virtual_balance['KRW']
        coin = virtual_balance['COIN']
        last_price = virtual_balance['last_price']
        est_value = coin * last_price
        if coin == 0.0:
            buy_amount = 0.0
            profit_rate = 0.0
        else:
            buy_amount = 1_000_000 - krw
            total_asset = krw + est_value
            if buy_amount > 0:
                profit_rate = ((total_asset - 1_000_000) / buy_amount) * 100
            else:
                profit_rate = 0.0
        fee = virtual_balance.get('FEE', 0.0)
        self.RealCoin.setItem(0, 0, QTableWidgetItem(f"{krw:,.0f} 원"))
        self.RealCoin.setItem(1, 0, QTableWidgetItem(f"{buy_amount:,.0f} 원"))
        self.RealCoin.setItem(2, 0, QTableWidgetItem(f"{est_value:,.0f} 원"))
        self.RealCoin.setItem(3, 0, QTableWidgetItem(f"{profit_rate:+.2f}%"))
        self.RealCoin.setItem(4, 0, QTableWidgetItem(f"{est_value:,.0f} 원"))
        self.RealCoin.setItem(5, 0, QTableWidgetItem(f"{krw + est_value:,.0f} 원"))
        self.RealCoin.setItem(6, 0, QTableWidgetItem(f"{fee:,.0f} 원"))

    def update_data(self):
        self.load_coin_list()
        self.log_virtual_balance()
        # 보유 코인 테이블의 현재가/등락률/수익률도 10초마다 자동 갱신
        for row in range(self.Cointable.rowCount()):
            coin = self.Cointable.item(row, 0).text()
            buy_price = float(self.Cointable.item(row, 1).text().replace(",", ""))
            # 등락률 갱신
            change_pct = self.get_coin_change_pct(coin)
            self.Cointable.setItem(row, 3, QTableWidgetItem(change_pct))
            # 현재가/수익률 갱신
            self.update_profit_rate(row, coin, buy_price)
        # VirtualCoin, RealCoin 테이블도 10초마다 갱신
        self.update_virtual_coin_table()
        self.update_real_coin_table()

    def log_virtual_balance(self):
        krw = virtual_balance['KRW']
        coin = virtual_balance['COIN']
        price = virtual_balance['last_price']
        value = coin * price
        total = krw + value
        self.append_to_datalog(f"[{QDateTime.currentDateTime().toString()}] KRW: {krw:,.0f} | COIN: {coin:.6f} | 평가액: {value:,.0f} 원 | 총자산: {total:,.0f} 원")

    def append_to_datalog(self, text):
        existing = self.Datalog.toPlainText()
        lines = existing.splitlines()[-9:] + [text]
        self.Datalog.setPlainText("\n".join(lines))

    def load_coin_list(self):
        print("🔄 코인 리스트 로드 시작")
        self.worker = CoinListWorker()
        self.worker.result.connect(self.display_coin_list)
        self.worker.start()

    def display_coin_list(self, data):
        # 현재 페이지 유지
        prev_page = self.coinlist_page if hasattr(self, 'coinlist_page') else 0
        self.coinlist_data = data
        # 최대 페이지 범위 내로 보정
        max_page = max(0, (len(self.coinlist_data) - 1) // 20)
        self.coinlist_page = min(prev_page, max_page)
        self.show_coinlist_page()

    def show_coinlist_page(self):
        page_size = 20
        start = self.coinlist_page * page_size
        end = start + page_size
        data = self.coinlist_data[start:end]
        self.CoinList.setRowCount(0)
        self.CoinList.setColumnCount(3)
        self.CoinList.setHorizontalHeaderLabels(["종목명", "현재가", "등락률"])
        now = time.time()
        for i, (coin_name, price_text, dash) in enumerate(data):
            try:
                current_price = int(price_text.replace(",", ""))
                ticker = f"KRW-{coin_name}"
                if ticker in ohlcv_cache and now - ohlcv_cache_time[ticker] < ohlcv_cache_ttl:
                    df = ohlcv_cache[ticker]
                else:
                    df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
                    ohlcv_cache[ticker] = df
                    ohlcv_cache_time[ticker] = now
                if df is None or len(df) < 2:
                    change_pct = "-"
                else:
                    prev_close = df['close'].iloc[-2]
                    change = (current_price - prev_close) / prev_close * 100
                    change_pct = f"{change:+.2f}%"
            except:
                change_pct = "-"
            row = self.CoinList.rowCount()
            self.CoinList.insertRow(row)
            item_coin = QTableWidgetItem(coin_name)
            item_price = QTableWidgetItem(price_text)
            item_change = QTableWidgetItem(change_pct)
            if change_pct != "-":
                try:
                    change_value = float(change_pct.strip('%'))
                    if not self.Virtual.isChecked():
                        color = QColor("red") if change_value > 0 else QColor("blue") if change_value < 0 else QColor("black")
                        item_change.setForeground(color)
                        item_price.setForeground(color)
                        item_coin.setForeground(color)
                    else:
                        color = Qt.gray
                        item_change.setForeground(color)
                        item_price.setForeground(color)
                        item_coin.setForeground(color)
                except:
                    pass
            self.CoinList.setItem(row, 0, item_coin)
            self.CoinList.setItem(row, 1, item_price)
            self.CoinList.setItem(row, 2, item_change)
        self.CoinList.resizeColumnsToContents()
        self.CoinList.resizeRowsToContents()
        # 페이지 버튼 활성화/비활성화
        self.PrevPageBtn.setEnabled(self.coinlist_page > 0)
        self.NextPageBtn.setEnabled((self.coinlist_page + 1) * page_size < len(self.coinlist_data))

    def show_prev_coinlist_page(self):
        if self.coinlist_page > 0:
            self.coinlist_page -= 1
            self.show_coinlist_page()

    def show_next_coinlist_page(self):
        page_size = 20
        if (self.coinlist_page + 1) * page_size < len(self.coinlist_data):
            self.coinlist_page += 1
            self.show_coinlist_page()

    def buy_virtual_coin(self):
        row = self.CoinList.currentRow()
        if row < 0:
            QMessageBox.warning(self, "경고", "코인을 선택하세요")
            return
        coin = self.CoinList.item(row, 0).text()
        try:
            price = pyupbit.get_current_price(f"KRW-{coin}")
            if price is None or isinstance(price, dict):
                raise ValueError("가격 조회 실패")
        except:
            QMessageBox.warning(self, "실패", "가격 조회 실패")
            return
        try:
            input_amount = float(self.Insertcoin.text())
        except:
            QMessageBox.warning(self, "입력 오류", "숫자로 입력하세요")
            return
        if input_amount > virtual_balance["KRW"]:
            QMessageBox.warning(self, "실패", "금액 부족")
            return
        amount = input_amount / price
        # 수수료 계산 (매수 0.05%)
        fee = input_amount * 0.0005
        virtual_balance["COIN"] += amount
        virtual_balance["KRW"] -= (amount * price + fee)
        virtual_balance["last_price"] = price
        virtual_balance["COIN_NAME"] = coin  # 보유 코인명 저장
        virtual_balance["FEE"] = virtual_balance.get("FEE", 0.0) + fee
        self.update_virtual_coin_table()
        self.update_real_coin_table()
        self.update_cointable(coin, amount, price)
        self.append_to_datalog(f"[{QDateTime.currentDateTime().toString()}] {coin} {amount:.6f}개 매수 완료")

    def sell_virtual_coin(self):
        row = self.Cointable.currentRow()
        if row < 0:
            QMessageBox.warning(self, "경고", "판매할 코인을 선택하세요")
            return
        coin = self.Cointable.item(row, 0).text()
        try:
            price = pyupbit.get_current_price(f"KRW-{coin}")
            if price is None or isinstance(price, dict):
                raise ValueError("가격 조회 실패")
        except:
            QMessageBox.warning(self, "실패", "가격 조회 실패")
            return
        amount = virtual_balance["COIN"]
        proceeds = amount * price
        # 수수료 계산 (매도 0.05%)
        fee = proceeds * 0.0005
        proceeds -= fee
        virtual_balance["KRW"] += proceeds
        virtual_balance["COIN"] = 0.0
        virtual_balance["last_price"] = price
        virtual_balance["FEE"] = virtual_balance.get("FEE", 0.0) + fee
        # 수익률 표시
        buy_price = float(self.Cointable.item(row, 1).text().replace(",", ""))
        profit_rate = (price - buy_price) / buy_price * 100
        self.append_to_datalog(f"[{QDateTime.currentDateTime().toString()}] {coin} {amount:.6f}개 전량 매도 완료 (수익률: {profit_rate:+.2f}%)")
        self.Cointable.removeRow(row)
        self.update_virtual_coin_table()
        self.update_real_coin_table()

    def update_cointable(self, coin, amount, price):
        row = self.Cointable.rowCount()
        self.Cointable.insertRow(row)
        self.Cointable.setItem(row, 0, QTableWidgetItem(coin))
        self.Cointable.setItem(row, 1, QTableWidgetItem(f"{price:,.0f}"))  # 매수평균가
        # 현재가(실시간)
        self.Cointable.setItem(row, 2, QTableWidgetItem("-"))
        # 등락률(전일대비)
        change_pct = self.get_coin_change_pct(coin)
        self.Cointable.setItem(row, 3, QTableWidgetItem(change_pct))
        # 수익률(매수평균가 대비)
        self.Cointable.setItem(row, 4, QTableWidgetItem("0%"))
        self.Cointable.setItem(row, 5, QTableWidgetItem(f"{amount:.6f}"))
        # 현재가/수익률 갱신
        self.update_profit_rate(row, coin, price)

    def get_coin_change_pct(self, coin):
        try:
            ticker = f"KRW-{coin}"
            df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
            if df is not None and len(df) >= 2:
                current_price = pyupbit.get_current_price(ticker)
                prev_close = df['close'].iloc[-2]
                if current_price is not None and prev_close != 0:
                    change = (current_price - prev_close) / prev_close * 100
                    return f"{change:+.2f}%"
        except:
            pass
        return "-"

    def update_profit_rate(self, row, coin, buy_price):
        try:
            current_price = pyupbit.get_current_price(f"KRW-{coin}")
            if current_price is None or isinstance(current_price, dict):
                return
            self.Cointable.setItem(row, 2, QTableWidgetItem(f"{current_price:,.0f}"))
            profit_rate = (current_price - buy_price) / buy_price * 100
            self.Cointable.setItem(row, 4, QTableWidgetItem(f"{profit_rate:+.2f}%"))
        except:
            pass

    def setup_cointable_header(self):
        # UI에서 직접 설정한 헤더를 유지하도록 setHorizontalHeaderLabels 호출 제거
        pass

    def on_coin_selected(self, row, column):
        coin = self.CoinList.item(row, 0).text()
        df = get_ohlcv(coin, interval="day", count=60)
        if df is not None:
            self.display_candle_chart(df, coin)

    def display_candle_chart(self, df, coin):
        import plotly.graph_objects as go
        import plotly.io as pio
        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close']
        )])
        fig.update_layout(title=f"{coin} 캔들차트", xaxis_title="날짜", yaxis_title="가격 (KRW)")
        self.CandleChart.setHtml(pio.to_html(fig, include_plotlyjs='cdn'))

    def apply_trade_settings(self):
        profit = self.profitbox.value()
        stoploss = self.stoplossbox.value()
        self.trade_settings["profit"] = profit
        self.trade_settings["stoploss"] = stoploss
        QMessageBox.information(self, "설정", f"익절가: {profit}% / 손절가: {stoploss}% 설정 완료!")

    def start_trading(self):
        # 2020~2022년 데이터로 백테스트 모드: 변동성 돌파 알고리즘 실행
        import pandas as pd
        import datetime
        # 예시: BTC 2020~2022년 데이터 (실제는 여러 코인, 여러 전략 확장 가능)
        coin = "BTC"
        df = get_ohlcv(coin, interval="day", count=800)  # 약 2년치
        if df is not None:
            # 2020-01-01 ~ 2022-12-31 필터링
            df = df[(df.index >= pd.Timestamp("2020-01-01")) & (df.index <= pd.Timestamp("2022-12-31"))]
            krw = 1_000_000
            coin_amt = 0.0
            last_buy_price = 0.0
            k = 0.5
            log = []
            for i in range(1, len(df)):
                sub_df = df.iloc[:i+1]
                signal = check_trade_signal_vbreak(sub_df, k)
                today = df.iloc[i]
                price = today['close']
                if signal == "buy" and krw > price:
                    buy_amt = krw * 0.1
                    buy_coin = buy_amt / price
                    coin_amt += buy_coin
                    krw -= buy_coin * price
                    last_buy_price = price
                    log.append(f"{df.index[i].date()} 매수: {buy_coin:.6f}개 @ {price:,.0f} KRW")
                # 익절/손절 (예시: 5% 익절, -3% 손절)
                if coin_amt > 0 and last_buy_price > 0:
                    profit_rate = (price - last_buy_price) / last_buy_price * 100
                    if profit_rate >= 5 or profit_rate <= -3:
                        proceeds = coin_amt * price
                        krw += proceeds
                        log.append(f"{df.index[i].date()} 매도: {coin_amt:.6f}개 @ {price:,.0f} KRW (수익률: {profit_rate:+.2f}%)")
                        coin_amt = 0.0
                        last_buy_price = 0.0
            # 결과 요약
            if len(df) == 0 or 'close' not in df.columns:
                QMessageBox.warning(self, "백테스트 오류", "데이터에 'close' 컬럼이 없거나 데이터가 비어 있습니다.")
                return
            final_asset = krw + coin_amt * df.iloc[-1]['close']
            log.append(f"최종 자산: {final_asset:,.0f} KRW")
            QMessageBox.information(self, "백테스트 결과", "\n".join(log[-10:]))
            return
        # ...기존 실시간 자동매매 코드...
        profit = self.trade_settings.get("profit", 5)
        stoploss = self.trade_settings.get("stoploss", 3)
        if self.Cointable.rowCount() == 0:
            coin = virtual_balance.get("COIN_NAME", None)
            if virtual_balance.get("COIN", 0) > 0 and coin:
                self.auto_trade_workers = []
                worker = AutoTradeWorker(coin, self.append_to_datalog, self.update_virtual_coin_table, profit, stoploss)
                self.auto_trade_workers.append(worker)
                worker.start()
                QMessageBox.information(self, "자동매매", f"자동매매가 시작되었습니다. 10초마다 {coin} 매수/매도 신호를 확인합니다. (익절: {profit}%, 손절: {stoploss}%)")
                return
            else:
                QMessageBox.warning(self, "경고", "보유한 코인이 없습니다")
                return
        self.auto_trade_workers = []
        for row in range(self.Cointable.rowCount()):
            coin = self.Cointable.item(row, 0).text()
            worker = AutoTradeWorker(coin, self.append_to_datalog, self.update_virtual_coin_table, profit, stoploss)
            self.auto_trade_workers.append(worker)
            worker.start()
        QMessageBox.information(self, "자동매매", f"자동매매가 시작되었습니다. 10초마다 매수/매도 신호를 확인합니다. (익절: {profit}%, 손절: {stoploss}%)")

    def stop_trading(self):
        for worker in getattr(self, 'auto_trade_workers', []):
            worker.stop()
        self.auto_trade_workers = []
        QMessageBox.information(self, "중지", "자동매매 중지")

    def toggle_virtual_ui(self):
        self.VirtualCoin.setVisible(self.Virtual.isChecked())
        # 버튼 위치는 resizeEvent에서 자동 처리

def check_trade_signal_vbreak(df, k=0.5):
    """
    변동성 돌파 전략: 목표가 = 전일 종가 + (전일 고가 - 전일 저가) * k
    오늘 고가가 목표가를 돌파하면 'buy', 아니면 'hold' 반환
    """
    if len(df) < 2:
        return "hold"
    prev = df.iloc[-2]
    today = df.iloc[-1]
    target = prev['close'] + (prev['high'] - prev['low']) * k
    if today['high'] >= target and today['open'] < target:
        return "buy"
    return "hold"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TradingWindow()
    win.setWindowTitle("자동매매 시스템")
    win.show()
    sys.exit(app.exec_())
