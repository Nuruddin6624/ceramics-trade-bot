import os
import requests
from flask import Flask, request
from appwrite.client import Client
from appwrite.services.databases import Databases
import google.generativeai as genai

app = Flask(__name__)

# Render-এর Environment Variables থেকে সিক্রেট কি-গুলো নেওয়া হবে
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
APPWRITE_API_KEY = os.environ.get('APPWRITE_API_KEY')

# ১. Appwrite কনফিগারেশন (আপনার দেওয়া আইডিগুলো যুক্ত করা হয়েছে)
client = Client()
client.set_endpoint('https://sgp.cloud.appwrite.io/v1')
client.set_project('69f23099000b78cb32ca')
client.set_key(APPWRITE_API_KEY)
databases = Databases(client)

DATABASE_ID = '69f230ef000baaa2a329'
COLLECTION_ID = 'tiles_pricing'

# ২. Gemini AI কনফিগারেশন
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_price_list():
    # Appwrite ডাটাবেস থেকে রিয়েল-টাইম ডাটা পড়া
    try:
        result = databases.list_documents(DATABASE_ID, COLLECTION_ID)
        price_data = "Ceramics Trade Price List:\n"
        for doc in result['documents']:
            price_data += f"Model: {doc.get('model', 'N/A')}, Size: {doc.get('size', 'N/A')}, Price: {doc.get('price', 'N/A')} TK\n"
        return price_data
    except Exception as e:
        print("Appwrite Error:", e)
        return "বর্তমানে প্রাইস লিস্ট সার্ভার থেকে পাওয়া যাচ্ছে না।"

def generate_ai_reply(message_text, image_url=None):
    price_list = get_price_list()
    
    # AI-এর সিস্টেম প্রম্পট
    system_prompt = f"""
    তুমি 'Ceramics Trade'-এর একজন অত্যন্ত দক্ষ ও বিনয়ী সেলস অ্যাসিস্ট্যান্ট। 
    নিচে আমাদের টাইলসের বর্তমান সাইজ ও দামের তালিকা দেওয়া হলো:
    {price_list}
    কাস্টমার যদি কোনো টাইলসের ছবি দেয়, তবে ছবির ডিজাইন দেখে আমাদের তালিকার সাথে মিলিয়ে কাছাকাছি মডেল সাজেস্ট করবে এবং তার সাইজ ও দাম বলবে। কথা বলবে খুব সুন্দর ও প্রফেশনাল বাংলায়।
    """

    if image_url:
        # ছবি থাকলে ছবিসহ প্রসেস করবে
        img_data = requests.get(image_url).content
        image_parts = [{"mime_type": "image/jpeg", "data": img_data}]
        prompt_text = message_text if message_text else "এই টাইলসটির মডেল এবং দাম কত হবে?"
        response = model.generate_content([system_prompt, image_parts[0], prompt_text])
    else:
        # শুধু টেক্সট থাকলে
        response = model.generate_content([system_prompt, message_text if message_text else "হ্যালো"])
    
    return response.text

def send_message(recipient_id, message_text):
    # ফেসবুক মেসেঞ্জারে রিপ্লাই পাঠানো
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": message_text}}
    requests.post(url, json=payload)

@app.route('/', methods=['GET', 'POST'])
def webhook():
    # ফেসবুক Webhook ভেরিফিকেশন
    if request.method == 'GET':
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return "Forbidden", 403

    # কাস্টমারের মেসেজ রিসিভ করা
    if request.method == 'POST':
        data = request.json
        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for event in entry.get('messaging', []):
                    if 'message' in event and not event['message'].get('is_echo'):
                        sender_id = event['sender']['id']
                        message_text = event['message'].get('text', '')
                        
                        # মেসেজে কোনো ছবি আছে কি না তা চেক করা
                        image_url = None
                        if 'attachments' in event['message']:
                            for attachment in event['message']['attachments']:
                                if attachment['type'] == 'image':
                                    image_url = attachment['payload']['url']
                                    break
                        
                        # রিপ্লাই তৈরি করে পাঠানো
                        reply_text = generate_ai_reply(message_text, image_url)
                        send_message(sender_id, reply_text)
        return "EVENT_RECEIVED", 200

if __name__ == '__main__':
    # Render-এর ডিফল্ট পোর্টে সার্ভার রান করা
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))