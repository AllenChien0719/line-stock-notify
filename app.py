from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextSendMessage, MessageEvent, TextMessage
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import requests
import os

app = Flask(__name__)

# LINE Messaging API 配置
CHANNEL_ACCESS_TOKEN = 'YOUR_CHANNEL_ACCESS_TOKEN'
CHANNEL_SECRET = 'YOUR_CHANNEL_SECRET'
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Fugle API 配置
FUGLE_API_KEY = 'YOUR_FUGLE_API_KEY'

# 用戶自選股票代碼存儲
USER_SELECTED_STOCKS = {}

def get_stock_price(symbol):
    """
    使用 Fugle API 查詢單支股票的最新價格。
    """
    try:
        # 確保代碼以 .TW 結尾（台灣股票）
        if not symbol.endswith(".TW"):
            symbol += ".TW"

        url = f"https://api.fugle.tw/v1/stock/{symbol}/quote"
        headers = {
            'Authorization': f'Bearer {FUGLE_API_KEY}'
        }
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"Fugle API 錯誤代碼: {response.status_code}, 原因: {response.text}")
            return None

        data = response.json()
        # 確認返回結構是否正確
        if "data" in data and "quote" in data["data"]:
            price = data["data"]["quote"]["last"]
            if price is not None:
                return price
            else:
                print(f"未找到價格，返回數據: {data}")
        else:
            print(f"無效的 API 返回結構: {data}")
    except requests.exceptions.RequestException as e:
        print(f"網路錯誤: {e}")
    except KeyError as e:
        print(f"解析數據時出現 KeyError: {e}")
    except Exception as e:
        print(f"取得股票價格時發生未知錯誤: {e}")
    return None

def send_all_stock_prices(user_id):
    """
    推送所有自選股票的最新價格
    """
    stocks_to_send = USER_SELECTED_STOCKS.get(user_id, [])
    if not stocks_to_send:
        line_bot_api.push_message(user_id, TextSendMessage(text="您尚未新增任何自選股票。"))
        return

    messages = []
    for symbol in stocks_to_send:
        price = get_stock_price(symbol)
        if price:
            messages.append(f"{symbol}: {price} TWD")
        else:
            messages.append(f"{symbol}: 無法取得股價")

    if messages:
        message_text = "\n".join(messages)
        message = f"股票最新報價：\n{message_text}"
        line_bot_api.push_message(user_id, TextSendMessage(text=message))

# 設定排程
scheduler = BackgroundScheduler()
scheduler.start()

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    # 啟動新執行線處理 Webhook 事件
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
        send_all_stock_prices(user_id)
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
    elif event.message.text == "查詢自選股票":
        stocks = USER_SELECTED_STOCKS.get(user_id, [])
        if stocks:
            stocks_list = "\n".join(stocks)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"您目前的自選股票是：\n{stocks_list}"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="您尚未新增任何自選股票。"))
    elif event.message.text == "指令":
        commands = (
            "可用指令列表：\n"
            "1. 新增股票 <股票代碼> - 新增自選股票\n"
            "2. 刪除股票 <股票代碼> - 刪除自選股票\n"
            "3. 查詢股票 <股票代碼> - 查詢單支股票價格\n"
            "4. 目前股價 - 推送所有自選股票的股價\n"
            "5. 查詢自選股票 - 查看已新增的自選股票\n"
            "6. 指令 - 查看可用指令列表"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=commands))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="輸入 '指令' 查看可用指令列表。"))

@app.route("/debug")
def debug():
    """ 測試 URL，用於檢查服務狀態 """
    return f"Service is running on port {os.environ.get('PORT', '10000')}"

if __name__ == "__main__":
    # 讀取 Render 的端口環境變數，預設為 10000
    port = int(os.environ.get("PORT", 10000))

    # 讓 Flask 在這個端口上運行
    app.run(host='0.0.0.0', port=port)
