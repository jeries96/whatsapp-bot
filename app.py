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
        message_text = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body'].strip().lower()
    except KeyError:
        return jsonify({"error": "Invalid webhook structure"}), 400

    user = data_store.get(phone_number)

    if not user:
        data_store[phone_number] = {
            "last_step": "ask_action",
            "last_interaction_time": datetime.now(),
            "service": None,
            "name": None,
            "date": None,
            "time": None
        }
        send_whatsapp_message(phone_number, "Hi! What would you like to do?")
        return jsonify({"status": "new user initialized"})

    if is_session_expired(user["last_interaction_time"]) or user["last_step"] == "confirm":
        user.update({
            "last_step": "ask_action",
            "service": None,
            "name": None,
            "date": None,
            "time": None
        })
        update_last_interaction(user)
        send_whatsapp_message(phone_number, "Hi again! What would you like to do?")
        return jsonify({"status": "session reset"})

    step = user["last_step"]
    update_last_interaction(user)

    if step == "ask_action":
        user["last_step"] = "ask_service"
        send_whatsapp_message(phone_number, "Great. What service do you need?")
    elif step == "ask_service":
        user["service"] = message_text
        user["last_step"] = "ask_name"
        send_whatsapp_message(phone_number, "Got it. What is your name?")
    elif step == "ask_name":
        user["name"] = message_text
        user["last_step"] = "ask_date"
        send_whatsapp_message(phone_number, "Thanks. What date works for you?")
    elif step == "ask_date":
        user["date"] = message_text
        user["last_step"] = "ask_time"
        send_whatsapp_message(phone_number, "And what time?")
    elif step == "ask_time":
        user["time"] = message_text
        user["last_step"] = "confirm"
        confirm_msg = (
            f"Please confirm:\n"
            f"Service: {user['service']}\n"
            f"Name: {user['name']}\n"
            f"Date: {user['date']}\n"
            f"Time: {user['time']}"
        )
        send_whatsapp_message(phone_number, confirm_msg)
    else:
        send_whatsapp_message(phone_number, "Something went wrong. Let's start over.")
        user["last_step"] = "ask_action"

    return jsonify({"status": "message processed"})

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_default_token")
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
