import os
import requests
from flask import Flask, request, jsonify
from appwrite.client import Client
from appwrite.services.databases import Databases
import google.generativeai as genai

app = Flask(__name__)

# ================= সিক্রেট কি (Render Environment Variables) =================
ID_INSTANCE = os.environ.get('ID_INSTANCE')
API_TOKEN_INSTANCE = os.environ.get('API_TOKEN_INSTANCE')
APPWRITE_API_KEY = os.environ.get('APPWRITE_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# ================= Appwrite কানেকশন =================
client = Client()
client.set_endpoint('https://sgp.cloud.appwrite.io/v1')
client.set_project('69f23099000b78cb32ca')
client.set_key(APPWRITE_API_KEY)
databases = Databases(client)

DATABASE_ID = '69f230ef000baaa2a329'
COLLECTION_ID = 'tiles_pricing'

# ================= Gemini AI কানেকশন (আপনার সাপোর্ট করা মডেল) =================
genai.configure(api_key=GEMINI_API_KEY)

# আপনার লিস্ট অনুযায়ী সবচেয়ে শক্তিশালী এবং ফাস্ট মডেল
model_name = 'gemini-2.0-flash' 
model = genai.GenerativeModel(model_name)

def get_price_list():
    """Appwrite থেকে টাইলসের ডাটাবেস পড়া"""
    try:
        result = databases.list_documents(
            database_id=DATABASE_ID, 
            collection_id=COLLECTION_ID
        )
        price_data = "Ceramics Trade Price List:\n"
        for doc in result.documents:
            # অবজেক্ট প্রপার্টি থেকে ডাটা সংগ্রহ
            m_val = getattr(doc, 'model', doc.get('model', 'N/A') if hasattr(doc, 'get') else 'N/A')
            s_val = getattr(doc, 'size', doc.get('size', 'N/A') if hasattr(doc, 'get') else 'N/A')
            p_val = getattr(doc, 'price', doc.get('price', 'N/A') if hasattr(doc, 'get') else 'N/A')
            price_data += f"Model: {m_val}, Size: {s_val}, Price: {p_val} TK\n"
        return price_data
    except Exception as e:
        print(f"Appwrite Error: {e}")
        return "সার্ভার আপডেট হচ্ছে, দয়া করে একটু পর মেসেজ দিন।"

def generate_ai_reply(message_text, image_url=None):
    """কাস্টমারের প্রশ্নের উত্তর তৈরি করা"""
    price_list = get_price_list()
    
    system_prompt = f"""
    তুমি 'Ceramics Trade'-এর একজন দক্ষ ও বিনয়ী সেলস এক্সিকিউটিভ। 
    আমাদের বর্তমান টাইলসের তালিকা:
    {price_list}
    কাস্টমার মেসেজ বা ছবি দিলে তুমি তালিকা মিলিয়ে সঠিক মডেল, সাইজ ও দাম বলবে। প্রফেশনাল বাংলায় কথা বলবে।
    """

    try:
        if image_url:
            img_data = requests.get(image_url).content
            image_parts = [{"mime_type": "image/jpeg", "data": img_data}]
            prompt_text = message_text if message_text else "এই টাইলসটির মডেল ও দাম কত?"
            response = model.generate_content([system_prompt, image_parts[0], prompt_text])
        else:
            response = model.generate_content([system_prompt, message_text])
        return response.text
    except Exception as e:
        print(f"Gemini Error: {e}")
        return "দুঃখিত শামীম ভাই, এআই প্রসেসিং-এ সমস্যা হচ্ছে। আবার মেসেজ দিন।"

def send_whatsapp_message(chat_id, message):
    """হোয়াটসঅ্যাপে মেসেজ পাঠানো"""
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendMessage/{API_TOKEN_INSTANCE}"
    payload = {"chatId": chat_id, "message": message}
    headers = {'Content-Type': 'application/json'}
    requests.post(url, json=payload, headers=headers)

# ================= Webhook =================
@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return "Ceramics Trade Bot is Active!", 200

    data = request.json
    if data and data.get('typeWebhook') == 'incomingMessageReceived':
        message_data = data['messageData']
        sender_chat_id = data['senderData']['chatId']
        
        # নিজের মেসেজে অটো-রিপ্লাই বন্ধ
        if sender_chat_id == data.get('idMessage', '').split('_')[0] + "@c.us":
            return jsonify({"status": "ignored"}), 200

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
