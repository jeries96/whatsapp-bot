import os
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import requests

app = Flask(__name__)
data_store = {}


# --- Settings ---
SESSION_TIMEOUT_MINUTES = 15
META_API_URL = os.environ.get("META_API_URL")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")

def send_whatsapp_message(phone_number, message):
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(META_API_URL, headers=headers, json=payload)
    print("Meta Response:", response.status_code, response.text)  # ← add this
    return response.status_code

def is_session_expired(last_interaction_time):
    return datetime.now() - last_interaction_time > timedelta(minutes=SESSION_TIMEOUT_MINUTES)

def update_last_interaction(user_record):
    user_record["last_interaction_time"] = datetime.now()

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    data = request.get_json()
    try:
        phone_number = data['entry'][0]['changes'][0]['value']['messages'][0]['from']
        message = data['entry'][0]['changes'][0]['value']['messages'][0]
    except KeyError:
        return jsonify({"error": "Invalid structure"}), 400

    msg_type = message.get("type")
    user = data_store.get(phone_number)

    if not user:
        user = {
            "last_step": "main_menu",
            "service": None,
            "name": None,
            "date": None,
            "time": None,
            "last_interaction_time": datetime.now()
        }
        data_store[phone_number] = user
        return send_main_menu(phone_number)

    update_last_interaction(user)

    # --- Parse interactive reply ---
    if msg_type == "interactive":
        interactive_type = message["interactive"]["type"]
        selected_id = message["interactive"]["list_reply"]["id"]

        if user["last_step"] == "main_menu":
            if selected_id == "d1":
                user["last_step"] = "choose_service"
                return send_service_list(phone_number)
            elif selected_id == "d2":
                return send_whatsapp_message(phone_number, "اوقات العمل ⏰ من 10 صباحًا إلى 8 مساءً")
            elif selected_id == "d3":
                return send_whatsapp_message(phone_number, "تم تغيير اللغة. Language changed ✅")
        elif user["last_step"] == "choose_service":
            service_map = {
                "1": "أكريلك",
                "2": "جل",
                "3": "تركيب أظافر"
            }
            user["service"] = service_map.get(selected_id, "غير معروف")
            user["last_step"] = "ask_name"
            return send_whatsapp_message(phone_number, "شو الاسم؟")
        elif user["last_step"] == "choose_date":
            user["date"] = selected_id
            user["last_step"] = "choose_time"
            return send_time_slots(phone_number)
        elif user["last_step"] == "choose_time":
            user["time"] = selected_id
            user["last_step"] = "confirm"
            return send_confirmation(phone_number, user)

    elif msg_type == "text" and user["last_step"] == "ask_name":
        user["name"] = message["text"]["body"]
        user["last_step"] = "choose_date"
        return send_date_slots(phone_number)

    return jsonify({"status": "handled"}), 200


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_default_token")
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403



def send_main_menu(phone_number):
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "هلا،كيفك؟ ✋"},
            "body": {"text": "كيف ممكن أساعدك اليوم؟"},
            "action": {
                "button": "اختيار",
                "sections": [{
                    "title": "Available Options",
                    "rows": [
                        {"id": "d1", "title": "حجز دور 📅"},
                        {"id": "d2", "title": "اوقات العمل ⏰"},
                        {"id": "d3", "title": "تغيير لغه", "description": "Change language"}
                    ]
                }]
            }
        }
    }
    return send_whatsapp_payload(payload)

def send_service_list(phone_number):
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": "شو حابة تعملي؟ 💅"},
            "action": {
                "button": "Select Date",
                "sections": [{
                    "title": "Available Services",
                    "rows": [
                        {"id": "1", "title": "💅 أكريلك (اكريل)", "description": "450"},
                        {"id": "2", "title": "💅 جل", "description": "100"},
                        {"id": "3", "title": "💅 تركيب أظافر", "description": "300"}
                    ]
                }]
            }
        }
    }
    return send_whatsapp_payload(payload)

def send_date_slots(phone_number):
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": "اختاري التاريخ المناسب 📅"},
            "action": {
                "button": "تواريخ",
                "sections": [{
                    "title": "Available Dates",
                    "rows": [{"id": f"2025-07-{i+18}", "title": f"2025-07-{i+18}"} for i in range(7)]
                }]
            }
        }
    }
    return send_whatsapp_payload(payload)

def send_time_slots(phone_number):
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": "اختاري الوقت المناسب ⏰"},
            "action": {
                "button": "اوقات",
                "sections": [{
                    "title": "Available Times",
                    "rows": [{"id": f"{10+i}:00", "title": f"{10+i}:00"} for i in range(7)]
                }]
            }
        }
    }
    return send_whatsapp_payload(payload)

def send_confirmation(phone_number, user):
    msg = (
        f"تم تأكيد الحجز ✅\n\n"
        f"الاسم: {user['name']}\n"
        f"الخدمة: {user['service']}\n"
        f"التاريخ: {user['date']}\n"
        f"الوقت: {user['time']}\n"
    )
    return send_whatsapp_message(phone_number, msg)

def send_whatsapp_payload(payload):
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    response = requests.post(META_API_URL, headers=headers, json=payload)
    return jsonify({"status": response.status_code}), response.status_code


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
