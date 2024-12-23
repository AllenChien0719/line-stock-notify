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

# 固定股票代碼列表
FIXED_STOCKS = ["3093.TWO", "8070.TW", "6548.TWO", "2646.TW"]  # 更新為新的股票代碼

def get_stock_name(symbol):
    """
    根據股票代碼自動查詢股票名稱
    """
    try:
        stock = yf.Ticker(symbol)  # 查詢股票
        info = stock.info  # 獲取股票詳細資訊
        return info.get("longName", "未知股票名稱")  # 返回股票名稱
    except Exception as e:
        print(f"查詢股票名稱時發生錯誤: {e}")
        return "未知股票名稱"

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
            price = get_stock_price(symbol)
            stock_name = get_stock_name(symbol)  # 自動從代碼中獲取股票名稱
            if price:
                messages.append(f"{stock_name} ({symbol}): {price} USD" if '.' not in symbol else f"{stock_name} ({symbol}): {price} TWD")
            else:
                messages.append(f"{stock_name} ({symbol}): 無法取得股價")
        
        if messages:
            message_text = "\n".join(messages)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message_text))

    elif event.message.text.startswith("查詢股票"):
        stock_code = event.message.text.replace("查詢股票", "").strip()
        price = get_stock_price(stock_code)
        stock_name = get_stock_name(stock_code)  # 自動從代碼中獲取股票名稱
        if price:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{stock_name} ({stock_code}): {price} USD" if '.' not in stock_code else f"{stock_name} ({stock_code}): {price} TWD"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="無法取得股價，請確認股票代碼。"))

    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="輸入 '指令' 查看可用指令列表。"))

@app.route("/")
def index():
    return "LINE Stock Notify Service is running"

if __name__ == "__main__":
    # 讀取 Render 的端口環境變數，預設為 10000
    port = int(os.environ.get("PORT", 10000))
    
    # 讓 Flask 在這個端口上運行
    app.run(host='0.0.0.0', port=port)
