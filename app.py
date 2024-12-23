from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextSendMessage, MessageEvent, TextMessage
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import threading
import yfinance as yf  # Import yfinance for stock price query
import os

app = Flask(__name__)

# LINE Messaging API configuration
CHANNEL_ACCESS_TOKEN = 'sI6VyBPWk0hwrehmA9l9WU4pey8LGog14MgEnwq4xcuVGYT3hO0NOlNzRuF2bmK4JKbpMP1OLUkKsI+PAujI63LqMnXKIh0UdQISMQp3xjb7NbwrIkJnXxyMDZIXHzIRyrwWls0pnbuybz9HXjJb8AdB04t89/1O/w1cDnyilFU='
CHANNEL_SECRET = '5a2c38f35b7b6100b24af0467dcf9270'
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Fixed stock codes list (updated with correct codes)
FIXED_STOCKS = ["3093.TWO", "8070.TW", "6548.TWO", "2646.TW"]  # Updated to new stock codes

# Stock code to name mapping (Chinese names)
STOCK_NAMES = {
    "3093.TWO": "港建",
    "8070.TW": "長華電",
    "6548.TWO": "長科",
    "2646.TW": "星宇航空"
}

def get_stock_name(symbol):
    """
    Retrieve the stock name based on the stock code, return default if not found.
    """
    return STOCK_NAMES.get(symbol, "未知股票名稱")  # Look up name from dictionary

def get_stock_price(symbol):
    """
    Query the latest price of a single stock (supports US stocks, Taiwan stock market, and OTC stocks).
    """
    try:
        # Determine market by stock code suffix
        if symbol.endswith('.TW'):  # Taiwan Main Board
            stock = yf.Ticker(symbol)  # Taiwan Main Board
        elif symbol.endswith('.TWO'):  # Taiwan OTC market
            stock = yf.Ticker(symbol)  # Taiwan OTC market
        else:  # US stocks and others
            stock = yf.Ticker(symbol)  # US stocks and other markets don't need suffix
        
        data = stock.history(period="1d")  # Get the most recent data
        if not data.empty:
            return data['Close'][0]  # Return the closing price
    except Exception as e:
        print(f"Error fetching stock {symbol}: {e}")
    return None  # Return None if price cannot be retrieved

def send_stock_prices():
    """
    Push the latest stock prices for fixed stocks every hour.
    """
    now = datetime.now()
    if now.weekday() < 5 and 9 <= now.hour < 13:  # Check if it's a weekday and within specified hours
        messages = []
        for symbol in FIXED_STOCKS:
            price = get_stock_price(symbol)
            stock_name = get_stock_name(symbol)  # Get the stock name from the mapping
            if price:
                messages.append(f"{stock_name} ({symbol}): {price} TWD" if '.' in symbol else f"{stock_name} ({symbol}): {price} USD")
            else:
                messages.append(f"{stock_name} ({symbol}): 無法取得股價")
        
        if messages:
            message_text = "\n".join(messages)
            message = f"最新股票報價：\n{message_text}"
            line_bot_api.push_message(USER_ID, TextSendMessage(text=message))
            print(f"[{now}] 成功推送股價通知")

# Schedule the task to run every 60 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(send_stock_prices, 'interval', minutes=60)  # Run every 60 minutes
scheduler.start()

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    # Start a new thread to handle the webhook event
    threading.Thread(target=process_event, args=(body, signature)).start()

    # Immediately respond to Line's webhook request
    return 'OK', 200

def process_event(body, signature):
    """
    Process the webhook event in the background
    """
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid Signature Error")
    except Exception as e:
        print(f"Error processing event: {e}")

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """
    Handle messages from LINE users
    """
    user_id = event.source.user_id

    if event.message.text == "指令":
        commands = (
            "可用指令列表：\n"
            "1. 查詢股票 <股票代碼> - 查詢單支股票的股價\n"
            "2. 查詢固定股票 - 查詢所有固定股票的股價\n"
            "3. 指令 - 查看可用指令列表"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=commands))

    elif event.message.text == "查詢固定股票":
        # Show the prices of fixed stocks
        messages = []
        for symbol in FIXED_STOCKS:
            price = get_stock_price(symbol)
            stock_name = get_stock_name(symbol)  # Get the stock name from the mapping
            if price:
                messages.append(f"{stock_name} ({symbol}): {price} TWD" if '.' in symbol else f"{stock_name} ({symbol}): {price} USD")
            else:
                messages.append(f"{stock_name} ({symbol}): 無法取得股價")
        
        if messages:
            message_text = "\n".join(messages)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message_text))

    elif event.message.text.startswith("查詢股票"):
        stock_code = event.message.text.replace("查詢股票", "").strip()
        price = get_stock_price(stock_code)
        stock_name = get_stock_name(stock_code)  # Get the stock name from the mapping
        if price:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{stock_name} ({stock_code}): {price} TWD" if '.' in stock_code else f"{stock_name} ({stock_code}): {price} USD"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="無法取得股價，請確認股票代碼。"))

    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="輸入 '指令' 查看可用指令列表。"))

@app.route("/")
def index():
    return "LINE Stock Notify Service is running"

if __name__ == "__main__":
    # Read the port environment variable from Render, default is 10000
    port = int(os.environ.get("PORT", 10000))
    
    # Run Flask on this port
    app.run(host='0.0.0.0', port=port)
