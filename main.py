import os
import requests
from flask import Flask, request, jsonify
from appwrite.client import Client
from appwrite.services.databases import Databases
import google.generativeai as genai

app = Flask(__name__)

# ================= সিক্রেট কি (Render Environment Variables থেকে আসবে) =================
ID_INSTANCE = os.environ.get('ID_INSTANCE')
API_TOKEN_INSTANCE = os.environ.get('API_TOKEN_INSTANCE')
APPWRITE_API_KEY = os.environ.get('APPWRITE_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# ================= Appwrite কনফিগারেশন =================
client = Client()
client.set_endpoint('https://sgp.cloud.appwrite.io/v1')
client.set_project('69f23099000b78cb32ca')
client.set_key(APPWRITE_API_KEY)
databases = Databases(client)

DATABASE_ID = '69f230ef000baaa2a329'
COLLECTION_ID = 'tiles_pricing'

# ================= Gemini AI কনফিগারেশন =================
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_price_list():
    """Appwrite থেকে রিয়েল-টাইম ডাটাবেস পড়া"""
    try:
        # এখানে database_id এবং collection_id স্পষ্টভাবে বলে দেওয়া হয়েছে (Appwrite Error Fix)
        result = databases.list_documents(
            database_id=DATABASE_ID, 
            collection_id=COLLECTION_ID
        )
        price_data = "Ceramics Trade Price List:\n"
        for doc in result['documents']:
            price_data += f"Model: {doc.get('model', 'N/A')}, Size: {doc.get('size', 'N/A')}, Price: {doc.get('price', 'N/A')} TK\n"
        return price_data
    except Exception as e:
        print("Appwrite Error:", e)
        return "আমাদের প্রাইস লিস্ট সার্ভার বর্তমানে আপডেট হচ্ছে।"

def generate_ai_reply(message_text, image_url=None):
    """Gemini AI দিয়ে স্মার্ট রিপ্লাই তৈরি করা"""
    price_list = get_price_list()
    
    system_prompt = f"""
    তুমি 'Ceramics Trade'-এর একজন অত্যন্ত প্রফেশনাল এবং বিনয়ী সেলস এক্সিকিউটিভ। 
    নিচে আমাদের টাইলসের বর্তমান দাম ও সাইজের তালিকা দেওয়া হলো:
    {price_list}
    কাস্টমার মেসেজ দিলে বা ছবি দিলে, তুমি তালিকা থেকে সঠিক দাম ও সাইজ জানাবে। সব সময় বাংলায় উত্তর দেবে এবং কাস্টমারকে সম্মান দিয়ে কথা বলবে।
    """

    try:
        if image_url:
            img_data = requests.get(image_url).content
            image_parts = [{"mime_type": "image/jpeg", "data": img_data}]
            prompt_text = message_text if message_text else "এই টাইলসটির মডেল এবং দাম কত?"
            response = model.generate_content([system_prompt, image_parts[0], prompt_text])
        else:
            response = model.generate_content([system_prompt, message_text])
        return response.text
    except Exception as e:
        print("Gemini Error:", e)
        return "দুঃখিত, একটু কারিগরি সমস্যা হচ্ছে। দয়া করে কিছুক্ষণ পর আবার মেসেজ দিন।"

def send_whatsapp_message(chat_id, message):
    """Green-API ব্যবহার করে হোয়াটসঅ্যাপে মেসেজ পাঠানো"""
    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendMessage/{API_TOKEN_INSTANCE}"
    payload = {
        "chatId": chat_id,
        "message": message
    }
    headers = {'Content-Type': 'application/json'}
    requests.post(url, json=payload, headers=headers)

# ================= Webhook রিসিভার =================
@app.route('/', methods=['POST', 'GET'])
def webhook():
    # Render-এর হেলথ চেকের জন্য GET মেথড
    if request.method == 'GET':
        return "Ceramics Trade WhatsApp Bot is Running!", 200

    data = request.json
    
    # ইনকামিং মেসেজ রিসিভ করা
    if data and 'typeWebhook' in data and data['typeWebhook'] == 'incomingMessageReceived':
        message_data = data['messageData']
        sender_chat_id = data['senderData']['chatId']
        
        # নিজের পাঠানো মেসেজে যেন রিপ্লাই না দেয়
        if sender_chat_id == data.get('idMessage', '').split('_')[0] + "@c.us":
            return jsonify({"status": "ignored"}), 200

        message_text = ""
        image_url = None

        if message_data['typeMessage'] == 'textMessage':
            message_text = message_data['textMessageData']['textMessage']
        elif message_data['typeMessage'] == 'imageMessage':
            message_text = message_data.get('extendedTextMessageData', {}).get('text', '')
            image_url = message_data['fileMessageData']['downloadUrl']

        if message_text or image_url:
            reply = generate_ai_reply(message_text, image_url)
            send_whatsapp_message(sender_chat_id, reply)
            
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
