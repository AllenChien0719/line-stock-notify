from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import requests

app = Flask(__name__)

# LINE Messaging API 配置
CHANNEL_ACCESS_TOKEN = 'sI6VyBPWk0hwrehmA9l9WU4pey8LGog14MgEnwq4xcuVGYT3hO0NOlNzRuF2bmK4JKbpMP1OLUkKsI+PAujI63LqMnXKIh0UdQISMQp3xjb7NbwrIkJnXxyMDZIXHzIRyrwWls0pnbuybz9HXjJb8AdB04t89/1O/w1cDnyilFU='
CHANNEL_SECRET = '5a2c38f35b7b6100b24af0467dcf9270'
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Fugle API 配置
FUGLE_API_URL = 'https://api.fugle.tw/v1/market/stock'
FUGLE_API_KEY = 'ZDc5Y2FlMDYtYzI3Yy00ODAyLWJmMzMtMmZlODFjZDIzMGJiIDA2NDBjMTc0LTRlZTAtNDc5NC1iZGQ0LTI2MjI0MmNhMGZiZQ=='

# 指定要查詢的股票代碼清單
STOCK_SYMBOLS = ['2330', '2317', '6505', '2454', '3008']  # 這裡用的是台灣股票代碼（可根據需求更改）

# 指定要推送通知的 LINE 使用者 ID
USER_ID = 'chienallen'

def get_stock_price(symbol):
    """
    查詢單支股票的最新價格 (使用 Fugle API)
    """
    headers = {
        'Authorization': f'Bearer {FUGLE_API_KEY}'
    }
    response = requests.get(f"{FUGLE_API_URL}/{symbol}", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if "price" in data:
            return data["price"]
    return None

def send_stock_prices():
    """
    每小時推送指定股票的最新股價
    """
    now = datetime.now()
    if now.weekday() < 5 and 9 <= now.hour < 13:  # 檢查是否為工作日且在指定時段內
        messages = []
        for symbol in STOCK_SYMBOLS:
            price = get_stock_price(symbol)
            if price:
                messages.append(f"{symbol}: {price} TWD")
            else:
                messages.append(f"{symbol}: 無法取得股價")
        
        # 將所有股價合併成一條訊息
        message_text = "\n".join(messages)
        message = f"股票最新報價：\n{message_text}"
        
        # 發送通知到 LINE
        line_bot_api.push_message(USER_ID, TextSendMessage(text=message))
        print(f"[{now}] 成功推送股價通知")

# 設定排程
scheduler = BackgroundSchedule
