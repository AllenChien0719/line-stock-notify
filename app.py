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

# 用戶自選股票代碼存儲
USER_SELECTED_STOCKS = {}

# 指定要推送通知的 LINE 使用者 ID
USER_ID = 'chienallen'

def get_stock_price(symbol):
    """
    查詢單支股票的最新價格 (使用 Yahoo Finance)
    """
    try:
        stock = yf.Ticker(symbol + ".TW")  # 使用 .TW 指向台灣股市
        data = stock.history(period="1d")  # 獲取最近一天的資料
        if not data.empty:
            return data['Close'][0]  # 取收盤價
    except Exception as e:
        print(f"查詢股票 {symbol} 時發生錯誤: {e}")
    return None  # 若無法取得價格，返回 None

def send_stock_prices():
    """
    每小時推送指定股票的最新股價
    """
    now = datetime.now()
    if now.weekday() < 5 and 9 <= now.hour < 13:  # 檢查是否為工作日且在指定時段內
        messages = []
        stocks_to_send = USER_SELECTED_STOCKS.get(USER_ID, [])
        for symbol in stocks_to_send:
            price = get_stock_price(symbol)
            if price:
                messages.append(f"{symbol}: {price} TWD")
            else:
                messages.append(f"{symbol}: 無法取得股價")
        
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

    if event.message.text == "目前股價":
        send_stock_prices()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="目前股價通知已發送！"))

    elif event.message.text.startswith("新增股票"):
        stock_code = event.message.text.replace("新增股票", "").strip()
        if len(USER_SELECTED_STOCKS.get(user_id, [])) < 10:
            USER_SELECTED_STOCKS.setdefault(user_id, []).append(stock_code)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"已新增股票 {stock_code} 到您的自選股。"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="最多只能選擇10支股票。"))

    elif event.message.text.startswith("刪除股票"):
        stock_code = event.message.text.replace("刪除股票", "").strip()
        stocks = USER_SELECTED_STOCKS.get(user_id, [])
        if stock_code in stocks:
            stocks.remove(stock_code)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"已刪除股票 {stock_code}。"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"您沒有選擇這支股票 {stock_code}。"))

    elif event.message.text.startswith("查詢股票"):
        stock_code = event.message.text.replace("查詢股票", "").strip()
        price = get_stock_price(stock_code)
        if price:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{stock_code}: {price} TWD"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="無法取得股價，請確認股票代碼。"))
        
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入指令：\n1. 新增股票 <股票代碼>\n2. 刪除股票 <股票代碼>\n3. 查詢股票 <股票代碼>\n4. 目前股價"))

@app.route("/")
def index():
    return "LINE Stock Notify Service is running"

if __name__ == "__main__":
    # 讀取 Render 的端口環境變數，預設為 10000
    port = int(os.environ.get("PORT", 10000))
    
    # 讓 Flask 在這個端口上運行
    app.run(host='0.0.0.0', port=port)
