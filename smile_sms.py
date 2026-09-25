import requests
import json
import re
import threading
from datetime import datetime
import smile_config
from smile_db import record_sms, update_attendance_sms_status

def format_student_sms_message(student_name, lrn, grade_section, scan_type, timestamp_str):
    """
    Constructs an official, polite DepEd advisory SMS for the parent.
    """
    action = "ENTERED the school gate (TIME-IN)" if scan_type == "TIME_IN" else "EXITED the school gate (TIME-OUT)"
    try:
        time_fmt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S").strftime("%I:%M %p, %b %d, %Y")
    except Exception:
        time_fmt = timestamp_str

    school = getattr(smile_config, "SCHOOL_NAME", "Don Montano Central Integrated School")
    return (
        f"DepEd Advisory: Good day! Your child {student_name} (LRN: {lrn}, {grade_section}) "
        f"has successfully {action} at {time_fmt}. - {school}"
    )

def normalize_phone_number(phone_raw, provider="SEMAPHORE"):
    """
    Normalizes Philippine and international phone numbers according to provider requirements.
    - Semaphore: 09XXXXXXXXX or 639XXXXXXXXX
    - Twilio: E.164 format (+639XXXXXXXXX)
    - Android Gateway / GSM: 09XXXXXXXXX
    - PhilSMS: 639XXXXXXXXX or 09XXXXXXXXX
    """
    if not phone_raw:
        return ""
    # Strip spaces, dashes, dots, parens
    cleaned = re.sub(r'[\s\-\(\)\.]', '', str(phone_raw).strip())

    provider = (provider or "SEMAPHORE").upper()

    if provider == "TWILIO":
        # Requires E.164: +639XXXXXXXXX
        if cleaned.startswith("+"):
            return cleaned
        if cleaned.startswith("09") and len(cleaned) == 11:
            return "+63" + cleaned[1:]
        if cleaned.startswith("639") and len(cleaned) == 12:
            return "+" + cleaned
        return "+" + cleaned if not cleaned.startswith("+") else cleaned

    elif provider in ("SEMAPHORE", "PHILSMS"):
        # Semaphore supports 09XXXXXXXXX or 639XXXXXXXXX
        if cleaned.startswith("+63"):
            return "0" + cleaned[3:]
        if cleaned.startswith("639") and len(cleaned) == 12:
            return "0" + cleaned[2:]
        return cleaned

    else:
        # Default local format (09XXXXXXXXX)
        if cleaned.startswith("+63"):
            return "0" + cleaned[3:]
        if cleaned.startswith("639") and len(cleaned) == 12:
            return "0" + cleaned[2:]
        return cleaned

# -----------------------------------------------------------------
# Real Gateway Implementations
# -----------------------------------------------------------------

def send_via_semaphore(phone_number, message, api_key=None, sender_name=None):
    """
    Sends real SMS via Semaphore Philippines API v4.
    Docs: https://semaphore.co/docs
    """
    cfg = smile_config.get_sms_config()
    key = api_key or cfg.get("semaphore_api_key", "")
    sender = sender_name or cfg.get("semaphore_sender_name", "SEMAPHORE")

    if not key or "YOUR_" in key:
        return False, "CONFIG_ERROR", "Semaphore API key is missing or not configured."

    norm_number = normalize_phone_number(phone_number, "SEMAPHORE")
    url = "https://api.semaphore.co/api/v4/messages"
    payload = {
        "apikey": key,
        "number": norm_number,
        "message": message,
    }
    if sender and sender.upper() != "SEMAPHORE":
        payload["sendername"] = sender

    try:
        response = requests.post(url, data=payload, timeout=12)
        try:
            resp_data = response.json()
        except Exception:
            resp_data = response.text

        if response.status_code in (200, 201):
            # Check if Semaphore returned message list or error object
            if isinstance(resp_data, list) and len(resp_data) > 0:
                msg_id = resp_data[0].get("message_id", "N/A")
                status = resp_data[0].get("status", "QUEUED")
                return True, f"SENT_SEMAPHORE_{status.upper()}", f"Message ID: {msg_id} (Status: {status})"
            return True, "SENT_SEMAPHORE", json.dumps(resp_data)
        else:
            err_msg = resp_data.get("message") if isinstance(resp_data, dict) else str(resp_data)
            return False, "FAILED_SEMAPHORE", f"HTTP {response.status_code}: {err_msg}"
    except requests.exceptions.RequestException as e:
        return False, "ERROR_SEMAPHORE", f"Network error: {str(e)}"

def send_via_twilio(phone_number, message, account_sid=None, auth_token=None, from_number=None):
    """
    Sends real SMS via Twilio Messages REST API.
    Docs: https://www.twilio.com/docs/sms/api/message-resource
    """
    cfg = smile_config.get_sms_config()
    sid = account_sid or cfg.get("twilio_account_sid", "")
    token = auth_token or cfg.get("twilio_auth_token", "")
    from_num = from_number or cfg.get("twilio_from_number", "")

    if not sid or not token or not from_num:
        return False, "CONFIG_ERROR", "Twilio credentials (Account SID, Auth Token, From Number) are incomplete."

    norm_number = normalize_phone_number(phone_number, "TWILIO")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    payload = {
        "To": norm_number,
        "From": from_num,
        "Body": message
    }

    try:
        response = requests.post(url, data=payload, auth=(sid, token), timeout=12)
        try:
            resp_data = response.json()
        except Exception:
            resp_data = {"text": response.text}

        if response.status_code in (200, 201):
            msg_sid = resp_data.get("sid", "N/A")
            status = resp_data.get("status", "QUEUED")
            return True, f"SENT_TWILIO_{status.upper()}", f"Twilio SID: {msg_sid} (Status: {status})"
        else:
            err_msg = resp_data.get("message", f"HTTP {response.status_code}")
            return False, "FAILED_TWILIO", f"Twilio Error: {err_msg}"
    except requests.exceptions.RequestException as e:
        return False, "ERROR_TWILIO", f"Network error: {str(e)}"

def send_via_android_gateway(phone_number, message, gateway_url=None, api_key=None):
    """
    Sends real SMS using a local Android smartphone acting as an SMS Gateway over Wi-Fi.
    Allows schools to use an existing phone with an unlimited text SIM (Globe/Smart/DITO)
    for 100% free SMS with zero API fees.
    """
    cfg = smile_config.get_sms_config()
    url = gateway_url or cfg.get("android_gateway_url", "http://192.168.1.100:8080/send")
    key = api_key or cfg.get("android_gateway_key", "")

    if not url:
        return False, "CONFIG_ERROR", "Android Gateway URL is missing."

    norm_number = normalize_phone_number(phone_number, "ANDROID")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    payload = {
        "to": norm_number,
        "message": message,
        "phone": norm_number,
        "text": message
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in (200, 201, 202):
            return True, "SENT_ANDROID_PHONE", f"Dispatched via Android Gateway ({url})"
        else:
            return False, "FAILED_ANDROID", f"HTTP {response.status_code}: {response.text[:100]}"
    except requests.exceptions.RequestException as e:
        return False, "ERROR_ANDROID", f"Could not reach Android phone at {url}: {str(e)}"

def send_via_philsms(phone_number, message, api_key=None, sender_id=None):
    """
    Sends real SMS via PhilSMS API v3.
    Docs: https://app.philsms.com
    """
    cfg = smile_config.get_sms_config()
    key = api_key or cfg.get("philsms_api_key", "")
    sender = sender_id or cfg.get("philsms_sender_id", "PhilSMS")

    if not key:
        return False, "CONFIG_ERROR", "PhilSMS API token is missing."

    norm_number = normalize_phone_number(phone_number, "PHILSMS")
    url = "https://app.philsms.com/api/v3/sms/send"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "recipient": norm_number,
        "sender_id": sender,
        "type": "plain",
        "message": message
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=12)
        resp_data = response.json() if response.text else {}
        if response.status_code in (200, 201) and resp_data.get("status") == "success":
            return True, "SENT_PHILSMS", json.dumps(resp_data)
        else:
            return False, "FAILED_PHILSMS", resp_data.get("message", response.text[:100])
    except requests.exceptions.RequestException as e:
        return False, "ERROR_PHILSMS", f"Network error: {str(e)}"

def send_via_gsm(phone_number, message, port=None, baudrate=None):
    """
    Sends SMS using standard AT commands via USB GSM modem (SIM800/SIM900/Dongle).
    """
    cfg = smile_config.get_sms_config()
    gsm_port = port or cfg.get("gsm_port", "COM3")
    gsm_baud = int(baudrate or cfg.get("gsm_baudrate", 9600))
    norm_number = normalize_phone_number(phone_number, "GSM")

    try:
        import serial
        import time
        ser = serial.Serial(gsm_port, gsm_baud, timeout=5)
        time.sleep(1)
        ser.write(b'AT\r\n')
        time.sleep(0.5)
        ser.write(b'AT+CMGF=1\r\n')  # Set text mode
        time.sleep(0.5)
        ser.write(f'AT+CMGS="{norm_number}"\r\n'.encode())
        time.sleep(0.5)
        ser.write(message.encode() + bytes([26]))  # Ctrl+Z to send
        time.sleep(3)
        resp = ser.read_all().decode(errors="ignore")
        ser.close()
        return True, "SENT_GSM", resp
    except ImportError:
        return False, "FAILED_GSM", "pyserial library not installed. Run 'pip install pyserial'."
    except Exception as e:
        return False, "FAILED_GSM", f"Serial modem error: {str(e)}"

# -----------------------------------------------------------------
# Gateway Health & Credit Balance Checker
# -----------------------------------------------------------------

def check_gateway_status():
    """
    Tests connectivity and retrieves balance/account info from the active provider.
    """
    cfg = smile_config.get_sms_config()
    mode = cfg.get("mode", "MOCK").upper().strip()

    if mode == "SEMAPHORE":
        key = cfg.get("semaphore_api_key", "")
        if not key or "YOUR_" in key:
            return {
                "mode": "SEMAPHORE",
                "status": "CONFIG_REQUIRED",
                "online": False,
                "message": "Semaphore API Key is not set. Enter your key in settings."
            }
        try:
            url = f"https://api.semaphore.co/api/v4/account?apikey={key}"
            res = requests.get(url, timeout=6)
            if res.status_code == 200:
                data = res.json()
                credits = data.get("credit_balance", 0)
                account_name = data.get("account_name", "Semaphore Account")
                return {
                    "mode": "SEMAPHORE",
                    "status": "ONLINE",
                    "online": True,
                    "credits": f"{credits} Credits",
                    "account_name": account_name,
                    "message": f"Connected to Semaphore! Balance: {credits} SMS credits available."
                }
            else:
                return {
                    "mode": "SEMAPHORE",
                    "status": "AUTH_FAILED",
                    "online": False,
                    "message": f"Semaphore Auth Failed (HTTP {res.status_code}). Please verify your API Key."
                }
        except Exception as e:
            return {
                "mode": "SEMAPHORE",
                "status": "CONNECTION_ERROR",
                "online": False,
                "message": f"Could not reach Semaphore API: {str(e)}"
            }

    elif mode == "TWILIO":
        sid = cfg.get("twilio_account_sid", "")
        token = cfg.get("twilio_auth_token", "")
        from_num = cfg.get("twilio_from_number", "")
        if not sid or not token or not from_num:
            return {
                "mode": "TWILIO",
                "status": "CONFIG_REQUIRED",
                "online": False,
                "message": "Twilio Account SID, Auth Token, or From Number missing."
            }
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json"
            res = requests.get(url, auth=(sid, token), timeout=6)
            if res.status_code == 200:
                data = res.json()
                acc_status = data.get("status", "active")
                acc_name = data.get("friendly_name", "Twilio Project")
                return {
                    "mode": "TWILIO",
                    "status": "ONLINE",
                    "online": True,
                    "credits": f"Status: {acc_status.title()}",
                    "account_name": acc_name,
                    "from_number": from_num,
                    "message": f"Connected to Twilio! Account: {acc_name} ({acc_status.title()})"
                }
            else:
                return {
                    "mode": "TWILIO",
                    "status": "AUTH_FAILED",
                    "online": False,
                    "message": f"Twilio Authentication Failed (HTTP {res.status_code})."
                }
        except Exception as e:
            return {
                "mode": "TWILIO",
                "status": "CONNECTION_ERROR",
                "online": False,
                "message": f"Twilio Connection Error: {str(e)}"
            }

    elif mode == "ANDROID_GATEWAY":
        url = cfg.get("android_gateway_url", "")
        if not url:
            return {"mode": "ANDROID_GATEWAY", "status": "CONFIG_REQUIRED", "online": False, "message": "Android Gateway URL not configured."}
        try:
            res = requests.get(url, timeout=4)
            return {
                "mode": "ANDROID_GATEWAY",
                "status": "ONLINE" if res.status_code < 400 else "RESPONDING",
                "online": True,
                "credits": "Unlimited (Local SIM)",
                "message": f"Android Gateway reached at {url} (HTTP {res.status_code})"
            }
        except Exception as e:
            return {
                "mode": "ANDROID_GATEWAY",
                "status": "OFFLINE",
                "online": False,
                "message": f"Cannot reach Android Phone at {url}: {str(e)}"
            }

    elif mode == "GSM":
        return {
            "mode": "GSM",
            "status": "READY",
            "online": True,
            "credits": "SIM Plan",
            "message": f"GSM Modem configured on port {cfg.get('gsm_port', 'COM3')}"
        }

    else:
        return {
            "mode": "MOCK",
            "status": "SIMULATION",
            "online": False,
            "credits": "Unlimited (Simulation)",
            "message": "Operating in Simulation / Mock Sandbox Mode. Safe for offline demos."
        }

# -----------------------------------------------------------------
# Central Dispatcher & Async Worker
# -----------------------------------------------------------------

def dispatch_sms_sync(phone_number, message, student_lrn="SYSTEM", attendance_log_id=None):
    """
    Synchronous central SMS dispatcher routing to the active provider.
    Records delivery transaction in the database.
    """
    cfg = smile_config.get_sms_config()
    mode = cfg.get("mode", "MOCK").upper().strip()

    success = False
    status = "UNKNOWN"
    info = ""

    if mode == "SEMAPHORE":
        success, status, info = send_via_semaphore(phone_number, message)
    elif mode == "TWILIO":
        success, status, info = send_via_twilio(phone_number, message)
    elif mode == "ANDROID_GATEWAY":
        success, status, info = send_via_android_gateway(phone_number, message)
    elif mode == "PHILSMS":
        success, status, info = send_via_philsms(phone_number, message)
    elif mode == "GSM":
        success, status, info = send_via_gsm(phone_number, message)
    else:
        # Default MOCK Mode (Safe for demos, hackathons, and offline testing)
        success = True
        status = "MOCKED"
        info = "Mock delivery: Saved in database and displayed in console"
        print("\n" + "="*60)
        print(f" [SMS NOTIFIER - MOCK GATEWAY]")
        print(f" To:       {phone_number}")
        print(f" Student:  LRN {student_lrn}")
        print(f" Message:  {message}")
        print("="*60 + "\n")

    # Record in database logs
    record_sms(phone_number, student_lrn, message, status, info)
    if attendance_log_id:
        update_attendance_sms_status(attendance_log_id, status)

    return {
        "success": success,
        "status": status,
        "info": info,
        "provider": mode,
        "recipient": phone_number
    }

def _dispatch_worker(phone_number, student_lrn, message, attendance_log_id):
    """Internal thread worker to dispatch SMS without freezing camera or API."""
    dispatch_sms_sync(phone_number, message, student_lrn, attendance_log_id)

def send_parent_notification_async(phone_number, student_name, student_lrn, grade_section, scan_type, timestamp_str, attendance_log_id=None):
    """
    Non-blocking SMS dispatcher.
    Fires off the SMS request in a background daemon thread so the live camera feed remains silky smooth.
    """
    if not phone_number:
        return

    message = format_student_sms_message(student_name, student_lrn, grade_section, scan_type, timestamp_str)
    
    t = threading.Thread(
        target=_dispatch_worker,
        args=(phone_number, student_lrn, message, attendance_log_id),
        daemon=True
    )
    t.start()
