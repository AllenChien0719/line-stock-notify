from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextSendMessage, MessageEvent, TextMessage
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from pytz import timezone
import threading
import yfinance as yf
import os

app = Flask(__name__)

# LINE Messaging API 配置
CHANNEL_ACCESS_TOKEN = 'sI6VyBPWk0hwrehmA9l9WU4pey8LGog14MgEnwq4xcuVGYT3hO0NOlNzRuF2bmK4JKbpMP1OLUkKsI+PAujI63LqMnXKIh0UdQISMQp3xjb7NbwrIkJnXxyMDZIXHzIRyrwWls0pnbuybz9HXjJb8AdB04t89/1O/w1cDnyilFU='
CHANNEL_SECRET = '5a2c38f35b7b6100b24af0467dcf9270'
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# 固定股票代碼列表
FIXED_STOCKS = ["3093.TWO", "8070.TW", "6548.TWO", "2646.TW"]  
USER_ID = "chienallen"  # 替換為實際的使用者 ID

# 時區設置
tz = timezone('Asia/Taipei')

def get_stock_name(symbol):
    """ 根據股票代碼查詢股票名稱 """
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        return info.get("longName", symbol)
    except Exception as e:
        print(f"查詢股票名稱 {symbol} 時發生錯誤: {e}")
        return symbol

def get_stock_price(symbol):
    """ 查詢單支股票的最新價格 """
    try:
        stock = yf.Ticker(symbol)
        data = stock.history(period="1d")
        if not data.empty:
            price = data['Close'][0]
            return round(price, 1)
    except Exception as e:
        print(f"查詢股票 {symbol} 時發生錯誤: {e}")
    return None

def send_stock_prices():
    """ 股市交易日每小時整點推送固定股票的最新價格 """
    now = datetime.now(timezone("Asia/Taipei"))
    print(f"當前時間：{now}")
    if now.weekday() < 5 and now.hour in [9, 10, 11, 12, 13]:
        messages = []
        for symbol in FIXED_STOCKS:
            price = get_stock_price(symbol)
            stock_name = get_stock_name(symbol)
            if price:
                messages.append(f"{stock_name} ({symbol}): {price} TWD")
            else:
                messages.append(f"{stock_name} ({symbol}): 無法取得股價")

        if messages:
            message_text = "\n".join(messages)
            try:
                line_bot_api.push_message(USER_ID, TextSendMessage(text=f"股票最新報價：\n{message_text}"))
                print(f"推送成功：\n{message_text}")
            except Exception as e:
                print(f"推送訊息時發生錯誤: {e}")

# 設定排程
scheduler = BackgroundScheduler()
scheduler.add_job(send_stock_prices, 'cron', day_of_week='mon-fri', hour='9-13', minute=0)
scheduler.start()

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    threading.Thread(target=process_event, args=(body, signature)).start()
    return 'OK', 200

def process_event(body, signature):
    """ 背景執行 Webhook 事件處理 """
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid Signature Error")
    except Exception as e:
        print(f"處理事件時發生錯誤: {e}")

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """ 處理使用者訊息 """
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
        messages = []
        for symbol in FIXED_STOCKS:
            price = get_stock_price(symbol)
            stock_name = get_stock_name(symbol)
            if price:
                messages.append(f"{stock_name} ({symbol}): {price} TWD")
            else:
                messages.append(f"{stock_name} ({symbol}): 無法取得股價")

        if messages:
            message_text = "\n".join(messages)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message_text))

    elif event.message.text.startswith("查詢股票"):
        stock_code = event.message.text.replace("查詢股票", "").strip()
        price = get_stock_price(stock_code)
        stock_name = get_stock_name(stock_code)
        if price:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{stock_name} ({stock_code}): {price} TWD"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="無法取得股價，請確認股票代碼。"))

    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="輸入 '指令' 查看可用指令列表。"))

@app.route("/")
def index():
    return "LINE Stock Notify Service is running"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
