import os
from datetime import timedelta, timezone

import requests
from babel.dates import format_datetime
from dotenv import load_dotenv
from flask import Flask
from flask import request, jsonify

load_dotenv()

app = Flask(__name__)

CALENDLY_TOKEN = os.environ.get("CALENDLY_TOKEN")
EVENT_TYPE_URL = os.environ.get("EVENT_TYPE_URL")


def get_available_dates(limit=7, days_ahead=30):
    url = "https://api.calendly.com/event_type_available_times"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CALENDLY_TOKEN}"
    }

    collected = set()
    step = 7  # Calendly allows 7-day chunks
    start = datetime.now(timezone.utc) + timedelta(seconds=30)

    while len(collected) < limit and (start - datetime.now(timezone.utc)).days < days_ahead:
        end = start + timedelta(days=step)
        querystring = {
            "event_type": EVENT_TYPE_URL,
            "start_time": start.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "end_time": end.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "timezone": "Asia/Jerusalem"
        }

        response = requests.get(url, headers=headers, params=querystring)

        if response.ok:
            slots = response.json().get("collection", [])
            for slot in slots:
                date = slot["start_time"].split("T")[0]
                collected.add(date)
                if len(collected) >= limit:
                    break
        else:
            print("❌ Calendly API error:", response.status_code, response.text)
            break

        start = end  # move to next week

    return [
        f"{d} ({datetime.strptime(d, '%Y-%m-%d').strftime('%A')})"
        for d in sorted(list(collected))[:limit]
    ]


def get_available_datess(limit=7, days_ahead=30, locale="ar"):
    url = "https://api.calendly.com/event_type_available_times"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CALENDLY_TOKEN}"
    }

    collected = set()
    step = 7
    start = datetime.now(timezone.utc) + timedelta(seconds=30)
    counter = 0

    while len(collected) < limit and (start - datetime.now(timezone.utc)).days < days_ahead:
        end = start + timedelta(days=step)
        querystring = {
            "event_type": EVENT_TYPE_URL,
            "start_time": start.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "end_time": end.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "timezone": "Asia/Jerusalem"
        }

        response = requests.get(url, headers=headers, params=querystring)

        if response.ok:
            slots = response.json().get("collection", [])
            for slot in slots:
                date = slot["start_time"].split("T")[0]
                collected.add(date)
                if len(collected) >= limit:
                    break
        else:
            print("❌ Calendly API error:", response.status_code, response.text)
            break

        start = end

    sorted_dates = sorted(list(collected))[:limit]

    return [
        {
            "id": str(i + 1),
            "title": d,
            "description": format_datetime(datetime.strptime(d, "%Y-%m-%d"), "EEEE", locale=locale)
        }
        for i, d in enumerate(sorted_dates)
    ]


from datetime import datetime
import pytz


def get_available_timess(date):
    url = "https://api.calendly.com/event_type_available_times"
    headers = {
        "Authorization": f"Bearer {CALENDLY_TOKEN}",
        "Content-Type": "application/json"
    }

    iso_start = f"{date}T00:00:00Z"
    iso_end = f"{date}T23:59:59Z"

    params = {
        "event_type": EVENT_TYPE_URL,
        "start_time": iso_start,
        "end_time": iso_end,
        "timezone": "Asia/Jerusalem"
    }

    response = requests.get(url, headers=headers, params=params)

    if response.ok:
        slots = response.json().get("collection", [])
        jerusalem = pytz.timezone("Asia/Jerusalem")
        times = []

        for slot in slots:
            utc_time = datetime.fromisoformat(slot["start_time"].replace("Z", "+00:00"))
            local_time = utc_time.astimezone(jerusalem)
            formatted = local_time.strftime("%H:%M")
            times.append(formatted)

        # Sort and return list of dicts with title and description
        return [
            {
                "id": str(i + 1),
                "title": t,
                "description": t
            }
            for i, t in enumerate(sorted(times))
        ]

    else:
        print("❌ Calendly error:", response.status_code, response.text)
        return []


def get_available_times(date):
    headers = {
        "Authorization": f"Bearer {CALENDLY_TOKEN}",
        "Content-Type": "application/json"
    }

    iso_start = f"{date}T00:00:00Z"
    iso_end = f"{date}T23:59:59Z"

    params = {
        "event_type": EVENT_TYPE_URL,
        "start_time": iso_start,
        "end_time": iso_end,
        "timezone": "Asia/Jerusalem"  # this affects availability, but response is still in UTC
    }

    try:
        response = requests.get("https://api.calendly.com/event_type_available_times", headers=headers, params=params)
        response.raise_for_status()

        slots = response.json().get("collection", [])
        jerusalem = pytz.timezone("Asia/Jerusalem")
        times = []

        for slot in slots:
            utc_time = datetime.fromisoformat(slot["start_time"].replace("Z", "+00:00"))
            local_time = utc_time.astimezone(jerusalem)
            times.append(local_time.strftime("%H:%M"))  # Or "%I:%M %p" for AM/PM

        return sorted(times)
    except Exception as e:
        print("❌ Error fetching available times:", e)
        return []


def create_booking(name, email, date_time):
    try:
        payload = {
            "name": name,
            "email": email,
            "start_time": date_time
        }
        response = requests.post("https://hook.eu2.make.com/n95kif19mk40ldvxrz3qx6p6yk9lrjfm", json=payload)
        response.raise_for_status()
        return {"response_status": response.status_code}
    except Exception as e:
        print("❌ Booking failed:", e)
        return {"status": "error", "message": str(e)}


# === REST API Endpoints ===

@app.route("/available-dates-count", methods=["GET"])
def api_available_dates_count():
    dates = get_available_dates()
    return {"count": len(dates)}


@app.route("/available-dates", methods=["GET"])
def api_available_dates():
    dates = get_available_datess()
    return jsonify(dates)


@app.route("/available-times-count", methods=["POST"])
def api_available_times_count():
    data = request.get_json()
    date = data.get("date") if data else None

    if not date:
        return jsonify({"error": "Missing 'date' in body"}), 400

    times = get_available_times(date)
    return jsonify({"count": len(times)})


@app.route("/available-times", methods=["POST"])
def api_available_times():
    data = request.get_json()
    date = data.get("date") if data else None

    if not date:
        return jsonify({"error": "Missing 'date' in body"}), 400

    times = get_available_timess(date)
    return jsonify(times)


@app.route("/create-booking", methods=["POST"])
def api_create_booking():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    date = data.get("date")
    time = data.get("time")

    if not all([name, email, date, time]):
        return jsonify({"error": "Missing required fields: name, email, date, time"}), 400

    try:
        # Combine date + time and assume it's in Asia/Jerusalem
        naive_local = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        local_tz = pytz.timezone("Asia/Jerusalem")
        aware_local = local_tz.localize(naive_local)

        # Convert to UTC for ISO format
        date_time_utc = aware_local.astimezone(pytz.utc)
        date_time_iso = date_time_utc.isoformat()
    except Exception as e:
        return jsonify({"error": f"Invalid date/time format: {e}"}), 400

    result = create_booking(name, email, date_time_iso)
    return jsonify(result)
