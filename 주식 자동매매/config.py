import os
from dotenv import load_dotenv
import pyupbit

load_dotenv()
ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")
upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)

virtual_balance = {
    "KRW": 1_000_000,
    "COIN": 0.0,
    "last_price": 0.0,
    "log": []
}

STOP_LOSS_THRESHOLD = -0.05
TAKE_PROFIT_THRESHOLD = 0.10
