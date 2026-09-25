import cv2
import numpy as np
import time
from datetime import datetime
import threading
from smile_config import (
    CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT, SCHOOL_NAME,
    ENABLE_AUDIO_CHIME, COOLDOWN_SECONDS
)
from smile_db import (
    get_all_enrolled_students, check_can_scan, determine_scan_type,
    record_attendance, get_today_summary
)
from smile_face_engine import SmileFaceEngine
from smile_sms import send_parent_notification_async

# Windows chime support
try:
    import winsound
    def play_chime():
        if ENABLE_AUDIO_CHIME:
            threading.Thread(target=lambda: winsound.Beep(1400, 200), daemon=True).start()
except ImportError:
    def play_chime():
        pass

def draw_header_banner(frame, school_name, total_scans, total_enrolled):
    """Renders a sleek top banner with School Title, live date/time, and statistics."""
    h, w, _ = frame.shape
    banner_height = 70
    
    # Dark semi-transparent overlay
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, banner_height), (20, 25, 30), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
    cv2.line(frame, (0, banner_height), (w, banner_height), (0, 180, 255), 2)

    # Title
    cv2.putText(frame, f"PROJECT S.M.I.L.E. | {school_name}", (20, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)

    # Live clock
    now_str = datetime.now().strftime("%I:%M:%S %p | %b %d, %Y")
    cv2.putText(frame, now_str, (20, 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 1)

    # Stats badges on right side
    stats_str = f"Enrolled: {total_enrolled}  |  Today's Scans: {total_scans}"
    text_size = cv2.getTextSize(stats_str, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    cv2.putText(frame, stats_str, (w - text_size[0] - 25, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 255, 180), 2)

def draw_corner_rect(frame, bbox, color, thickness=2, line_length=25):
    """Draws a modern tech-style bounding box with highlighted corners."""
    x, y, w, h = bbox
    # Main rectangle
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 1)

    # Top-Left
    cv2.line(frame, (x, y), (x + line_length, y), color, thickness)
    cv2.line(frame, (x, y), (x, y + line_length), color, thickness)
    # Top-Right
    cv2.line(frame, (x + w, y), (x + w - line_length, y), color, thickness)
    cv2.line(frame, (x + w, y), (x + w, y + line_length), color, thickness)
    # Bottom-Left
    cv2.line(frame, (x, y + h), (x + line_length, y + h), color, thickness)
    cv2.line(frame, (x, y + h), (x, y + h - line_length), color, thickness)
    # Bottom-Right
    cv2.line(frame, (x + w, y + h), (x + w - line_length, y + h), color, thickness)
    cv2.line(frame, (x + w, y + h), (x + w, y + h - line_length), color, thickness)

def run_gate_kiosk():
    print("="*65)
    print("      PROJECT S.M.I.L.E. - GATE RECOGNITION & NOTIFIER KIOSK")
    print("="*65)
    print("[*] Initializing AI Face Detection & Recognition Engine...")
    engine = SmileFaceEngine()

    print("[*] Loading enrolled students from database...")
    enrolled_students = get_all_enrolled_students()
    print(f"[+] Loaded {len(enrolled_students)} enrolled student(s).")

    print(f"[*] Opening Gate Camera (index {CAMERA_INDEX})...")
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    if not cap.isOpened():
        print(f"[!] Critical Error: Unable to access camera {CAMERA_INDEX}.")
        print("    If using a laptop, ensure camera permissions are granted.")
        return

    # Kiosk State Variables
    last_action_banner = None
    banner_expire_time = 0
    today_summary = get_today_summary()
    total_scans = today_summary["total_scans"]

    print("\n" + "="*50)
    print(" [GATE ACTIVE] Real-time facial monitoring is running.")
    print(" - Press 'q' or [ESC] to shut down kiosk.")
    print(" - Press 'r' to reload enrolled student list.")
    print("="*50 + "\n")

    frame_count = 0
    cached_faces = []

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[!] Warning: Dropped camera frame.")
            time.sleep(0.05)
            continue

        frame_count += 1
        current_time = time.time()
        now_dt = datetime.now()
        timestamp_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Run face detection on every frame for responsive tracking
        faces = engine.detect_faces(frame)

        # Process each detected face
        for face in faces:
            x, y, w, h = int(face[0]), int(face[1]), int(face[2]), int(face[3])
            # Bounding box bounds check
            x, y = max(0, x), max(0, y)
            
            # Extract embedding & match
            embedding = engine.extract_face_embedding(frame, face)
            match_student, score = engine.match_against_enrolled(embedding, enrolled_students)

            if match_student:
                lrn = match_student["lrn"]
                name = match_student["full_name"]
                grade = match_student["grade_section"]
                phone = match_student["parent_phone"]

                # Debounce Check
                can_scan, elapsed, last_type = check_can_scan(lrn, COOLDOWN_SECONDS)

                if can_scan:
                    # Determine Time-In / Time-Out
                    scan_type = determine_scan_type()
                    
                    # Record in SQLite Attendance Log
                    log_id = record_attendance(lrn, name, scan_type, sms_status="DISPATCHING")
                    total_scans += 1

                    # Trigger Audio Chime
                    play_chime()

                    # Trigger Asynchronous SMS to Parent
                    send_parent_notification_async(
                        phone_number=phone,
                        student_name=name,
                        student_lrn=lrn,
                        grade_section=grade,
                        scan_type=scan_type,
                        timestamp_str=timestamp_str,
                        attendance_log_id=log_id
                    )

                    # Trigger visual banner alert on screen
                    action_label = "TIME-IN" if scan_type == "TIME_IN" else "TIME-OUT"
                    last_action_banner = {
                        "text": f"RECORDED: {action_label} | {name} (LRN: {lrn})",
                        "sub": f"SMS Notification Sent to {phone}",
                        "color": (0, 230, 115)  # Bright Green
                    }
                    banner_expire_time = current_time + 4.0  # Show for 4 seconds

                    color = (0, 255, 0)
                    status_text = f"{name} - {action_label}"
                else:
                    # In cooldown
                    rem_sec = int(COOLDOWN_SECONDS - (elapsed if elapsed else 0))
                    color = (0, 220, 255)  # Amber / Yellow
                    status_text = f"{name} (Cooldown: {rem_sec}s)"

                # Draw student box and tag
                draw_corner_rect(frame, (x, y, w, h), color, thickness=3)
                
                # Tag Background
                tag_y = max(20, y - 10)
                cv2.rectangle(frame, (x, tag_y - 25), (x + w, tag_y), color, -1)
                cv2.putText(frame, status_text, (x + 5, tag_y - 7),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
                
                # Grade / LRN below face
                cv2.putText(frame, f"{grade} | LRN: {lrn}", (x, y + h + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, color, 1)

            else:
                # Unknown Person
                color = (0, 0, 255)  # Red
                draw_corner_rect(frame, (x, y, w, h), color, thickness=2)
                tag_y = max(20, y - 10)
                cv2.rectangle(frame, (x, tag_y - 25), (x + 180, tag_y), color, -1)
                cv2.putText(frame, "UNKNOWN VISITOR", (x + 5, tag_y - 7),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 2)

        # Render Header Banner
        draw_header_banner(frame, SCHOOL_NAME, total_scans, len(enrolled_students))

        # Render Active Notification Popup Banner (if student just scanned)
        if last_action_banner and current_time < banner_expire_time:
            bh, bw, _ = frame.shape
            card_w, card_h = int(bw * 0.75), 90
            cx = (bw - card_w) // 2
            cy = bh - card_h - 25

            # Translucent background card
            card_overlay = frame.copy()
            cv2.rectangle(card_overlay, (cx, cy), (cx + card_w, cy + card_h), (25, 30, 35), -1)
            cv2.addWeighted(card_overlay, 0.90, frame, 0.10, 0, frame)
            
            # Card accent border
            cv2.rectangle(frame, (cx, cy), (cx + card_w, cy + card_h), last_action_banner["color"], 2)
            
            cv2.putText(frame, last_action_banner["text"], (cx + 25, cy + 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
            cv2.putText(frame, last_action_banner["sub"], (cx + 25, cy + 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, last_action_banner["color"], 2)

        # Display Live Window
        cv2.imshow("PROJECT S.M.I.L.E. - DepEd School Gate Kiosk", frame)

        # Keyboard event handler
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord('q'), ord('Q')):
            print("[*] Gate Kiosk shutting down safely...")
            break
        elif key in (ord('r'), ord('R')):
            print("[*] Reloading enrolled student database...")
            enrolled_students = get_all_enrolled_students()
            today_summary = get_today_summary()
            total_scans = today_summary["total_scans"]
            print(f"[+] Active enrolled records: {len(enrolled_students)}")

    cap.release()
    cv2.destroyAllWindows()
    print("[+] Kiosk closed.")

if __name__ == "__main__":
    run_gate_kiosk()
