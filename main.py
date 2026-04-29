import os
import requests
from flask import Flask, request, jsonify
from appwrite.client import Client
from appwrite.services.databases import Databases
from google import genai

app = Flask(__name__)

# ================= ENV VARIABLES =================
ID_INSTANCE = os.environ.get('ID_INSTANCE')
API_TOKEN_INSTANCE = os.environ.get('API_TOKEN_INSTANCE')
APPWRITE_API_KEY = os.environ.get('APPWRITE_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# ================= Appwrite =================
client = Client()
client.set_endpoint('https://sgp.cloud.appwrite.io/v1')
client.set_project('69f23099000b78cb32ca')
client.set_key(APPWRITE_API_KEY)

databases = Databases(client)

DATABASE_ID = '69f230ef000baaa2a329'
COLLECTION_ID = 'tiles_pricing'

# ================= Gemini (NEW SDK) =================
client_ai = genai.Client(api_key=GEMINI_API_KEY)

# ================= Price List =================
def get_price_list():
    try:
        result = databases.list_documents(
            database_id=DATABASE_ID,
            collection_id=COLLECTION_ID
        )

        docs = result.get('documents', [])

        price_data = "📊 Ceramics Trade Price List:\n"

        for doc in docs:
            model = doc.get('model', 'N/A')
            size = doc.get('size', 'N/A')
            price = doc.get('price', 'N/A')

            price_data += f"• Model: {model} | Size: {size} | Price: {price} TK\n"

        return price_data

    except Exception as e:
        print("Appwrite Error:", e)
        return "⚠️ প্রাইস লিস্ট লোড করা যাচ্ছে না।"

# ================= AI Reply =================
def generate_ai_reply(message_text, image_url=None):
    price_list = get_price_list()

    system_prompt = f"""
    তুমি 'Ceramics Trade'-এর একজন প্রফেশনাল সেলস এক্সিকিউটিভ।
    
    RULES:
    - সবসময় ভদ্র ও প্রফেশনাল বাংলা ব্যবহার করবে
    - কাস্টমারকে 'স্যার' বা 'ভাই' বলে সম্বোধন করবে
    - তালিকা থেকে সঠিক দাম বলবে
    - না পেলে আনুমানিক সাজেশন দিবে
    
    {price_list}
    """

    try:
        contents = [system_prompt]

        if image_url:
            img_data = requests.get(image_url, timeout=5).content
            contents.append({"mime_type": "image/jpeg", "data": img_data})

        if message_text:
            contents.append(message_text)
        else:
            contents.append("এই টাইলসের দাম কত?")

        response = client_ai.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents
        )

        return response.text

    except Exception as e:
        print("Gemini Error:", e)
        return "দুঃখিত, সার্ভারে সমস্যা হচ্ছে। একটু পরে আবার চেষ্টা করুন।"

# ================= WhatsApp Send =================
def send_whatsapp_message(chat_id, message):
    try:
        url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendMessage/{API_TOKEN_INSTANCE}"
        payload = {
            "chatId": chat_id,
            "message": message
        }
        headers = {'Content-Type': 'application/json'}

        requests.post(url, json=payload, headers=headers, timeout=5)

    except Exception as e:
        print("WhatsApp Error:", e)

# ================= Webhook =================
@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return "✅ Ceramics Trade Bot Running", 200

    try:
        data = request.json

        if data and data.get('typeWebhook') == 'incomingMessageReceived':

            message_data = data['messageData']
            sender_chat_id = data['senderData']['chatId']

            msg_text = ""
            img_url = None

            if message_data['typeMessage'] == 'textMessage':
                msg_text = message_data['textMessageData']['textMessage']

            elif message_data['typeMessage'] == 'imageMessage':
                msg_text = message_data.get('extendedTextMessageData', {}).get('text', '')
                img_url = message_data['fileMessageData']['downloadUrl']

            if msg_text or img_url:
                reply = generate_ai_reply(msg_text, img_url)
                send_whatsapp_message(sender_chat_id, reply)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print("Webhook Error:", e)
        return jsonify({"status": "error"}), 500

# ================= Run =================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
