from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextSendMessage
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import threading
import requests
import os

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
STOCK_SYMBOLS = ['8070', '6548', '3093', '2646']  # 這裡用的是台灣股票代碼（可根據需求更改）

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
    return None  # 確保無法取得價格時返回 None

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
scheduler = BackgroundScheduler()
scheduler.add_job(send_stock_prices, 'interval', minutes=60)  # 每 60 分鐘執行一次
scheduler.start()

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    # 啟動新執行緒處理 Webhook 事件
    threading.Thread(target=process_event, args=(body, signature)).start()

    # 立即回應 Line 的 Webhook 請求
    return 'OK', 200

def process_event(body, signature):
    """
    背景執行 Webhook 事件處理
    """
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid Signature Error")
    except Exception as e:
        print(f"處理事件時發生錯誤: {e}")

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """
    處理來自 LINE 使用者的訊息
    """
    if event.message.text == "目前股價":
        send_stock_prices()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="目前股價通知已發送！"))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入「目前股價」來查詢股價！"))

@app.route("/")
def index():
    return "LINE Stock Notify Service is running"

if __name__ == "__main__":
    # 讀取 Render 的端口環境變數，預設為 10000
    port = int(os.environ.get("PORT", 10000))
    
    # 讓 Flask 在這個端口上運行
    app.run(host='0.0.0.0', port=port)
