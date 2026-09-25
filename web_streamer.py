import cv2
import time
import threading
import numpy as np
from datetime import datetime
from pathlib import Path
from smile_config import (
    CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT, SCHOOL_NAME,
    COOLDOWN_SECONDS, PHOTOS_DIR
)
from smile_orm import (
    get_all_enrolled_students_orm, get_student_by_lrn_or_rfid_orm,
    check_can_scan_orm, record_attendance_orm, evaluate_daily_scan_rule_orm
)
from smile_db import determine_scan_type
from smile_sms import send_parent_notification_async
from smile_qr import parse_scanned_code
from smile_face_engine import SmileFaceEngine

class GateStreamer:
    """
    Real-Time AI Gate Streamer for Project S.M.I.L.E.
    Combines:
      1. OpenCV YuNet + SFace Real-Time Facial Recognition Validation
      2. OpenCV Optical QR Code Detection
      3. Contactless USB RFID Tap Card / Barcode Scanner Support
    """
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.running = False
        self.cap = None
        self.lock = threading.Lock()
        self.current_frame_bytes = None
        self.enrolled_students = []
        self.latest_event = None
        self.event_counter = 0
        self.qr_detector = None
        self.face_engine = None
        self.thread = None
        self.simulation_qr_active = False
        self.simulation_active_until = 0
        self.last_scanned_student = None
        self.student_debounce_cache = {}
        self.current_gate_mode = "AUTO"

    def start(self):
        with self.lock:
            if self.running:
                return
            self.running = True
            
        print("[*] Initializing GateStreamer AI Face Recognition & Smart ID Engine...")
        try:
            self.face_engine = SmileFaceEngine()
        except Exception:
            self.face_engine = None
        try:
            self.qr_detector = cv2.QRCodeDetector()
        except Exception:
            self.qr_detector = None
        self.reload_enrolled_students()

        # Only start hardware camera background capture loop if NOT on Vercel/serverless
        import smile_config
        if not getattr(smile_config, "IS_VERCEL", False):
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()

    def reload_enrolled_students(self):
        """Refreshes enrolled students from database."""
        self.enrolled_students = get_all_enrolled_students_orm()
        faces_count = sum(1 for s in self.enrolled_students if s.get("embedding") is not None)
        print(f"[+] GateStreamer loaded {len(self.enrolled_students)} enrolled learners ({faces_count} with 128-d face embeddings).")

    def trigger_scan_by_student(self, student: dict, method="FACE_RECOGNITION", score=None):
        """
        Executes a verified gate scan for a student.
        Records Attendance (TIME_IN / TIME_OUT), dispatches parent SMS, and updates Kiosk HUD.
        Throttles repeating alerts for the same student when continuously seen in camera view.
        """
        lrn = str(student.get("lrn", "")).strip()
        now_time = time.time()

        # Check per-student event throttle for continuous camera face recognition
        # Prevents re-firing the exact same announcement dozens of times per second!
        if method == "FACE_RECOGNITION":
            last_info = self.student_debounce_cache.get(lrn)
            if last_info and (now_time - last_info["time"]) < 12.0:
                # Student face still in frame; previous notification is still valid
                return last_info["success"], "Face verified; recent notification still active."

        eval_res = evaluate_daily_scan_rule_orm(
            lrn=student["lrn"],
            student_name=student["full_name"],
            cooldown_seconds=10,
            gate_mode=self.current_gate_mode
        )
        now_dt = datetime.now()
        timestamp_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        if eval_res["can_scan"]:
            scan_type = eval_res["scan_type"]
            log_id = record_attendance_orm(
                lrn=student["lrn"],
                student_name=student["full_name"],
                scan_type=scan_type,
                grade_section=student["grade_section"],
                method=method,
                sms_status="DISPATCHING"
            )

            # Trigger Async Parent SMS
            send_parent_notification_async(
                phone_number=student["parent_phone"],
                student_name=student["full_name"],
                student_lrn=student["lrn"],
                grade_section=student["grade_section"],
                scan_type=scan_type,
                timestamp_str=timestamp_str,
                attendance_log_id=log_id
            )

            score_str = f"{score*100:.1f}%" if score is not None else None
            photo_name = ""
            if student.get("photo_path"):
                photo_name = Path(student["photo_path"]).name

            with self.lock:
                self.event_counter += 1
                self.latest_event = {
                    "event_id": self.event_counter,
                    "type": "SUCCESS",
                    "lrn": student["lrn"],
                    "name": student["full_name"],
                    "grade": student["grade_section"],
                    "parent_phone": student["parent_phone"],
                    "scan_type": scan_type,
                    "period": eval_res.get("period", ""),
                    "voice_text": eval_res.get("voice_text", ""),
                    "message": eval_res.get("message", ""),
                    "method": method,
                    "score": score_str,
                    "timestamp": now_dt.strftime("%I:%M %p"),
                    "date": now_dt.strftime("%b %d, %Y"),
                    "photo_name": photo_name,
                    "photo_path": student.get("photo_path") or "",
                    "qr_path": student.get("qr_code_path") or f"/static/qrcodes/{student['lrn']}.png"
                }
                self.last_scanned_student = student
                self.simulation_qr_active = True
                self.simulation_active_until = time.time() + 4.5

            self.student_debounce_cache[lrn] = {
                "time": now_time,
                "success": True,
                "scan_type": scan_type
            }
            print(f"[GATE SUCCESS] {method}: {student['full_name']} (LRN: {student['lrn']}) -> {scan_type} ({eval_res['period']})")
            return True, eval_res["message"]
        else:
            # Blocked / Duplicate scan!
            # Emit voice error and visual notice, BUT record in student_debounce_cache
            # so subsequent frames in the next 12 seconds do NOT re-fire!
            print(f"[GATE REJECTED] {method}: {student['full_name']} -> {eval_res['message']}")
            with self.lock:
                self.event_counter += 1
                self.latest_event = {
                    "event_id": self.event_counter,
                    "type": "BLOCKED",
                    "lrn": student["lrn"],
                    "name": student["full_name"],
                    "grade": student["grade_section"],
                    "scan_type": "BLOCKED",
                    "period": eval_res.get("period", "Duplicate Entry"),
                    "voice_text": eval_res.get("voice_text", ""),
                    "message": eval_res.get("message", "Duplicate or repeated entry rejected."),
                    "method": method,
                    "timestamp": now_dt.strftime("%I:%M %p"),
                    "date": now_dt.strftime("%b %d, %Y"),
                    "photo_path": student.get("photo_path") or "",
                    "qr_path": student.get("qr_code_path") or f"/static/qrcodes/{student['lrn']}.png"
                }

            self.student_debounce_cache[lrn] = {
                "time": now_time,
                "success": False,
                "scan_type": "BLOCKED"
            }
            return False, eval_res["message"]

    def trigger_scan_by_id(self, identifier: str, method="RFID_TAP"):
        """Processes scan by RFID Card UID or 12-digit LRN."""
        lrn = parse_scanned_code(identifier)
        student = get_student_by_lrn_or_rfid_orm(lrn)
        if not student:
            print(f"[!] Unrecognized Student LRN/Card: {lrn}")
            return False, "Unrecognized Student ID Card."
        return self.trigger_scan_by_student(student, method=method)

    def _virtual_camera_loop(self):
        """Interactive simulated Gate Streamer with AI Face Recognition & QR HUD."""
        print("[*] GateStreamer active in High-Tech AI Face Recognition & Smart ID Scanner Mode.")
        scan_bar_y = 130
        scan_dir = 1

        while self.running:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            # Navy / Dark slate background
            for i in range(480):
                frame[i, :] = (int(16 + i * 0.04), int(24 + i * 0.04), int(36 + i * 0.04))

            # Header info
            cv2.putText(frame, "PROJECT S.M.I.L.E. - AI GATE VALIDATION", (30, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 215, 255), 2)
            cv2.putText(frame, f"{SCHOOL_NAME} | YUNET + SFACE ENGINE ONLINE", (30, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 190, 220), 1)

            current_time = time.time()
            if self.simulation_qr_active and current_time < self.simulation_active_until and self.last_scanned_student:
                # Render verified Identity Card on stream
                student = self.last_scanned_student
                method = self.latest_event.get("method", "FACE_RECOGNITION") if self.latest_event else "FACE_RECOGNITION"
                score_str = self.latest_event.get("score") if self.latest_event else None

                # Center ID Card graphic
                cv2.rectangle(frame, (140, 95), (500, 385), (30, 50, 75), -1)
                cv2.rectangle(frame, (140, 95), (500, 385), (0, 255, 128), 2)
                
                # Card Header
                cv2.rectangle(frame, (140, 95), (500, 135), (0, 180, 90), -1)
                header_text = "AI FACE VALIDATION CONFIRMED" if "FACE" in method else "DEPED SMART ID VERIFIED"
                cv2.putText(frame, header_text, (155, 123),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
                
                # Photo / Face Badge Box
                cv2.rectangle(frame, (160, 155), (260, 275), (20, 35, 55), -1)
                cv2.rectangle(frame, (160, 155), (260, 275), (0, 220, 255), 2)
                cv2.putText(frame, "VALID", (185, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 128), 2)

                # Info
                cv2.putText(frame, student["full_name"], (280, 180),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255, 255, 255), 2)
                cv2.putText(frame, student["grade_section"], (280, 210),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 220, 255), 1)
                cv2.putText(frame, f"LRN: {student['lrn']}", (280, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 255, 180), 1)
                if score_str:
                    cv2.putText(frame, f"Match: {score_str}", (280, 270),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 215, 0), 1)

                # Confirmation Ribbon
                cv2.putText(frame, "GATE ACCESS GRANTED - PARENT SMS DISPATCHED", (150, 340),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 255, 128), 1)
            else:
                # Scanning Reticle
                scan_bar_y += scan_dir * 4
                if scan_bar_y > 360 or scan_bar_y < 120:
                    scan_dir *= -1

                # Biometric Face Crosshair in Center
                rx, ry, rw, rh = 210, 120, 220, 220
                cv2.rectangle(frame, (rx, ry), (rx + rw, ry + rh), (40, 75, 110), 2)
                cl = 22
                # Green/Cyan Biometric HUD corners
                cv2.line(frame, (rx, ry), (rx + cl, ry), (0, 255, 220), 3)
                cv2.line(frame, (rx, ry), (rx, ry + cl), (0, 255, 220), 3)
                cv2.line(frame, (rx + rw, ry), (rx + rw - cl, ry), (0, 255, 220), 3)
                cv2.line(frame, (rx + rw, ry), (rx + rw, ry + cl), (0, 255, 220), 3)
                cv2.line(frame, (rx, ry + rh), (rx + cl, ry + rh), (0, 255, 220), 3)
                cv2.line(frame, (rx, ry + rh), (rx, ry + rh - cl), (0, 255, 220), 3)
                cv2.line(frame, (rx + rw, ry + rh), (rx + rw - cl, ry + rh), (0, 255, 220), 3)
                cv2.line(frame, (rx + rw, ry + rh), (rx + rw, ry + rh - cl), (0, 255, 220), 3)

                # Scanning laser
                cv2.line(frame, (rx + 5, scan_bar_y), (rx + rw - 5, scan_bar_y), (0, 240, 255), 2)

                cv2.putText(frame, "LOOK AT CAMERA FOR FACE SCAN", (175, 225),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, (140, 200, 255), 1)
                cv2.putText(frame, "OR TAP RFID CARD / SCAN QR CODE", (185, 255),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 255, 180), 1)

            # Footer
            now_str = datetime.now().strftime("%I:%M:%S %p | %b %d, %Y")
            cv2.putText(frame, now_str, (30, 455),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (140, 170, 200), 1)
            cv2.putText(frame, "AI GATE ENGINE: ONLINE", (430, 455),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 120), 1)

            ret_encode, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ret_encode:
                with self.lock:
                    self.current_frame_bytes = jpeg.tobytes()

            time.sleep(0.03)

    def _capture_loop(self):
        """Reads camera frames, runs AI face recognition and QR detection in real time."""
        self.cap = cv2.VideoCapture(CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

        if not self.cap.isOpened():
            self._virtual_camera_loop()
            return

        print("[+] Physical Camera Connected! Live 60 FPS Face Recognition active.")
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            # 1. Real-Time Face Recognition (YuNet + SFace)
            faces = self.face_engine.detect_faces(frame)
            for face in faces:
                x, y, w, h = int(face[0]), int(face[1]), int(face[2]), int(face[3])
                emb = self.face_engine.extract_face_embedding(frame, face)
                match, score = self.face_engine.match_against_enrolled(emb, self.enrolled_students)

                if match:
                    label = f"{match['full_name']} ({score*100:.1f}%)"
                    color = (0, 255, 128)
                    self.trigger_scan_by_student(match, method="FACE_RECOGNITION", score=score)
                else:
                    label = f"UNKNOWN FACE ({score*100:.1f}%)" if score > 0 else "UNKNOWN FACE"
                    color = (0, 165, 255)

                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(frame, label, (x, max(20, y - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

            # 2. QR Code fallback
            try:
                data, bbox, _ = self.qr_detector.detectAndDecode(frame)
                if data and bbox is not None:
                    pts = bbox[0].astype(int)
                    for j in range(4):
                        cv2.line(frame, tuple(pts[j]), tuple(pts[(j+1)%4]), (0, 255, 255), 2)
                    self.trigger_scan_by_id(data, method="CAMERA_QR")
            except Exception:
                pass

            ret_encode, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            if ret_encode:
                with self.lock:
                    self.current_frame_bytes = jpeg.tobytes()

            time.sleep(0.02)

        if self.cap:
            self.cap.release()

    def get_frame(self):
        with self.lock:
            return self.current_frame_bytes

    def get_latest_event(self):
        return self.latest_event

    def get_gate_mode(self):
        return self.current_gate_mode

    def set_gate_mode(self, mode: str):
        clean_mode = str(mode).upper().strip()
        if clean_mode in ["AUTO", "ENTRY", "EXIT"]:
            self.current_gate_mode = clean_mode
            self.student_debounce_cache.clear()
            print(f"[*] GateStreamer gate mode updated to: {self.current_gate_mode}")
            return True
        return False
