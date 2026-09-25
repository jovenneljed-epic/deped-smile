import sys
import os
import time
import cv2
import numpy as np
from datetime import datetime

print("="*65)
print("     PROJECT S.M.I.L.E. - AI FACE RECOGNITION & GATE DIAGNOSTIC")
print("="*65)

# 1. Test Database System (SQLAlchemy Enterprise ORM)
print("\n[1/5] Testing Relational Database System (Face Embeddings + Demographics)...")
try:
    from smile_orm import (
        init_db, save_student, get_all_enrolled_students,
        check_can_scan, record_attendance, get_today_summary,
        get_student_by_identifier, get_db_session, AttendanceLog, SmsLog
    )
    init_db()

    test_lrn = "999999999999"
    test_rfid = "RFID-TEST-99"
    test_emb = np.random.randn(128).astype(np.float32)
    test_emb /= np.linalg.norm(test_emb)
    
    # Save student with face embedding
    student = save_student(
        lrn=test_lrn,
        first_name="Test",
        last_name="Learner",
        grade_section="Grade 10 - Rizal",
        parent_name="Parent Tester",
        parent_phone="09171234567",
        rfid_card_uid=test_rfid,
        photo_path="",
        embedding_array=test_emb
    )
    assert student is not None, "Failed to save student record."
    
    students = get_all_enrolled_students()
    matched_student = next((s for s in students if s["lrn"] == test_lrn), None)
    if not matched_student:
        raise RuntimeError("Failed to retrieve enrolled test student from database.")
    assert matched_student["embedding"] is not None, "Face embedding vector was not deserialized."
    assert matched_student["embedding"].shape == (128,), "Face embedding shape should be (128,)."
        
    # Check RFID identifier lookup
    found_by_rfid = get_student_by_identifier(test_rfid)
    assert found_by_rfid is not None and found_by_rfid["lrn"] == test_lrn, "RFID lookup failed"
    
    # Test attendance logging
    can_scan, _, _ = check_can_scan(test_lrn, cooldown_seconds=5)
    assert can_scan is True, "First scan should be permitted"
    
    log_id = record_attendance(test_lrn, "Juan Dela Cruz", "TIME_IN", method="FACE_RECOGNITION", sms_status="CONFIRMED")
    assert log_id > 0, "Attendance record ID should be positive"
    
    # Test debounce
    can_scan_again, elapsed, _ = check_can_scan(test_lrn, cooldown_seconds=60)
    assert can_scan_again is False, "Immediate second scan should be blocked by cooldown"
    
    print("  [OK] Relational Database, Schema, Face Vectors, and Smart Debounce working perfectly!")
except Exception as e:
    print(f"  [X] Database test failed: {e}")
    sys.exit(1)

# 2. Test SMS Notifier Engine
print("\n[2/5] Testing Real Multi-Provider SMS Notifier Engine...")
try:
    from smile_sms import (
        send_parent_notification_async, normalize_phone_number,
        check_gateway_status, dispatch_sms_sync
    )
    from smile_config import load_sms_settings, save_sms_settings
    
    # Test phone number normalizer for multiple carriers
    norm_ph = normalize_phone_number("0917-123-4567", "SEMAPHORE")
    assert norm_ph == "09171234567", f"Semaphore normalization failed: {norm_ph}"

    norm_tw = normalize_phone_number("09171234567", "TWILIO")
    assert norm_tw == "+639171234567", f"Twilio E.164 normalization failed: {norm_tw}"

    # Test settings load & save persistence
    current_cfg = load_sms_settings()
    assert "mode" in current_cfg, "SMS configuration missing mode."

    # Test gateway status check
    gw_status = check_gateway_status()
    assert "status" in gw_status, "Gateway status check failed."
    print(f"  [OK] Phone Normalization & Gateway Health check passed (Current Mode: {gw_status['mode']}).")

    # Test SMS Dispatch
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_parent_notification_async(
        phone_number="09171234567",
        student_name="Juan Dela Cruz",
        student_lrn=test_lrn,
        grade_section="Grade 10 - Rizal",
        scan_type="TIME_IN",
        timestamp_str=timestamp,
        attendance_log_id=log_id
    )
    # Give background thread 0.5s to write
    time.sleep(0.5)
    
    with get_db_session() as session:
        log = session.query(SmsLog).filter(SmsLog.student_lrn == test_lrn).first()
        if not log:
            raise RuntimeError("SMS log was not recorded in database.")
    
    print("  [OK] SMS Notification Dispatcher & Logging working perfectly!")
except Exception as e:
    print(f"  [X] SMS test failed: {e}")
    sys.exit(1)

# 3. Test AI Face Recognition Engine (YuNet + SFace)
print("\n[3/5] Testing AI Face Recognition Engine (YuNet Detector + SFace Recognizer)...")
try:
    from smile_face_engine import SmileFaceEngine
    engine = SmileFaceEngine()
    
    sample_path = "test_photos/sample_juan.jpg"
    if not os.path.exists(sample_path):
        raise RuntimeError(f"Sample test face photo not found at {sample_path}")

    test_img = cv2.imread(sample_path)
    assert test_img is not None, "Failed to load sample image"
    
    faces = engine.detect_faces(test_img)
    assert len(faces) > 0, "YuNet failed to detect face in sample image"
    print(f"  [OK] YuNet Face Detector: Successfully detected {len(faces)} face(s).")
    
    emb = engine.extract_face_embedding(test_img, faces[0])
    assert emb.shape == (128,), f"SFace embedding unexpected shape: {emb.shape}"
    print("  [OK] SFace Recognizer: Successfully aligned face and extracted 128-d feature vector.")
    
    # Test Cosine Similarity matching
    mock_db = [{"lrn": test_lrn, "full_name": "Juan Dela Cruz", "embedding": emb}]
    match, score = engine.match_against_enrolled(emb, mock_db)
    assert match is not None, "Self-matching failed"
    assert score > 0.95, f"Self-matching score too low: {score}"
    print(f"  [OK] Cosine Similarity Matcher: Matched Juan Dela Cruz with {score*100:.2f}% confidence!")
except Exception as e:
    print(f"  [X] Face engine test failed: {e}")
    sys.exit(1)

# 4. Test Multi-Factor Smart ID Engine (QR Code & RFID)
print("\n[4/5] Testing Multi-Factor Smart ID Engine (QR + RFID)...")
try:
    from smile_qr import generate_student_qr_code, parse_qr_text
    
    # Generate QR Code
    web_qr_url = generate_student_qr_code(test_lrn)
    qr_disk_path = os.path.join("static", "qrcodes", f"{test_lrn}.png")
    assert os.path.exists(qr_disk_path), f"QR code file not created: {qr_disk_path}"
    
    # Test OpenCV QR Code Optical Detector
    qr_detector = cv2.QRCodeDetector()
    qr_image = cv2.imread(qr_disk_path)
    assert qr_image is not None, "Could not load generated QR image"
    
    decoded_text, points, _ = qr_detector.detectAndDecode(qr_image)
    assert decoded_text != "", "OpenCV QR detector failed to decode generated QR image"
    
    # Test LRN parsing from QR
    parsed_lrn = parse_qr_text(decoded_text)
    assert parsed_lrn == test_lrn, f"Parsed LRN '{parsed_lrn}' did not match '{test_lrn}'"
    
    print(f"  [OK] DepEd Smart QR Code generated & optically decoded: '{decoded_text}'")
    print(f"  [OK] RFID Card UID resolution verified: '{test_rfid}' -> LRN {test_lrn}")
except Exception as e:
    print(f"  [X] Smart ID test failed: {e}")
    sys.exit(1)

# 5. Summary & Readiness Check
print("\n[5/5] Checking System Readiness...")
summary = get_today_summary()
print(f"  - Total Enrolled Students: {len(get_all_enrolled_students())}")
print(f"  - Total Scans Today:       {summary['total_scans']}")
print("  - Mode:                    MOCK SMS (Ready for live testing)")
print("  - Validation Mode:         AI Face Recognition (Primary) + Smart ID (Backup)")

print("\n" + "="*65)
print("  SUCCESS: ALL SYSTEM TESTS PASSED!")
print("  Project S.M.I.L.E. AI Face Recognition Validation is ready to run.")
print("="*65)
