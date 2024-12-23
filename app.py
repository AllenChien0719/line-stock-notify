from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextSendMessage, MessageEvent, TextMessage
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import threading
import yfinance as yf  # 引入 yfinance 用於查詢股價
import os

app = Flask(__name__)

# LINE Messaging API 配置
CHANNEL_ACCESS_TOKEN = 'sI6VyBPWk0hwrehmA9l9WU4pey8LGog14MgEnwq4xcuVGYT3hO0NOlNzRuF2bmK4JKbpMP1OLUkKsI+PAujI63LqMnXKIh0UdQISMQp3xjb7NbwrIkJnXxyMDZIXHzIRyrwWls0pnbuybz9HXjJb8AdB04t89/1O/w1cDnyilFU='
CHANNEL_SECRET = '5a2c38f35b7b6100b24af0467dcf9270'
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# 更新後的固定股票代碼列表
FIXED_STOCKS = ["3093.TWO", "8070.TW", "6548.TWO", "2646.TW"]  # 更新為新的股票代碼

# 股票代碼對應名稱的函數
def get_stock_name(symbol):
    """
    根據股票代碼返回股票名稱
    """
    stock_names = {
        "3093.TWO": "港建",
        "8070.TW": "長華電",
        "6548.TWO": "宏達電",
        "2646.TW": "台灣高鐵"
    }
    return stock_names.get(symbol, "未知股票名稱")

def get_stock_price(symbol):
    """
    查詢單支股票的最新價格 (支持查詢美股、台灣股市及OTC股票)
    """
    try:
        # 根據股票代碼的結尾判斷市場
        if symbol.endswith('.TW'):  # 台灣股市主板
            stock = yf.Ticker(symbol)  # 台灣股市主板
        elif symbol.endswith('.TWO'):  # 台灣OTC股市
            stock = yf.Ticker(symbol)  # 台灣OTC股市
        else:  # 美股
            stock = yf.Ticker(symbol)  # 美股及其他市場不需要加後綴
        
        data = stock.history(period="1d")  # 獲取最近一天的資料
        if not data.empty:
            return data['Close'][0]  # 取收盤價
    except Exception as e:
        print(f"查詢股票 {symbol} 時發生錯誤: {e}")
    return None  # 若無法取得價格，返回 None

def send_stock_prices():
    """
    每小時推送固定股票的最新股價
    """
    now = datetime.now()
    if now.weekday() < 5 and 9 <= now.hour < 13:  # 檢查是否為工作日且在指定時段內
        messages = []
        for symbol in FIXED_STOCKS:
            price = get_stock_price(symbol)
            stock_name = get_stock_name(symbol)  # 自動從代碼中獲取股票名稱
            if price:
                messages.append(f"{stock_name} ({symbol}): {price} USD" if '.' not in symbol else f"{stock_name} ({symbol}): {price} TWD")
            else:
                messages.append(f"{stock_name} ({symbol}): 無法取得股價")
        
        if messages:
            message_text = "\n".join(messages)
            message = f"股票最新報價：\n{message_text}"
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
    user_id = event.source.user_id

    if event.message.text == "指令":
        commands = (
            "可用指令列表：\n"
            "1. 查詢股票 <股票代碼> - 查詢單支股票價格\n"
            "2. 查詢固定股票 - 查詢所有固定股票的價格\n"
            "3. 指令 - 查看可用指令列表"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=commands))

    elif event.message.text == "查詢固定股票":
        # 顯示固定股票的價格及名稱
        messages = []
        for symbol in FIXED_STOCKS:
            price = get_stock_price(
