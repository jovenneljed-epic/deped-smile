import os
import cv2
import json
import shutil
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from smile_orm import (
    Session, Section, Student, AttendanceLog, SmsLog, init_orm_db,
    DEFAULT_SECTIONS, seed_default_sections_orm
)
from smile_qr import generate_student_qr
from smile_face_engine import SmileFaceEngine
from smile_config import PHOTOS_DIR

def seed_database():
    print("="*65)
    print("  PROJECT S.M.I.L.E. - AI FACE & SMART ID DATABASE SEEDER")
    print("="*65)
    init_orm_db()
    session = Session()

    face_engine = SmileFaceEngine()
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Seed DepEd Class Sections (K-12 Don Montano CIS)
    print("[1/3] Seeding DepEd Class Sections...")
    seed_default_sections_orm()
    print("  [OK] Class sections seeded successfully.")

    # 2. Seed Students (Demographics + Smart QR/RFID + AI Face Embeddings)
    print("\n[2/3] Seeding Student Demographics and AI Face Embeddings...")
    students_data = [
        {
            "lrn": "109876543210",
            "first_name": "Juan",
            "last_name": "Dela Cruz",
            "gender": "Male",
            "grade_section": "Grade 10 - Rizal",
            "track_strand": "Junior High",
            "parent_name": "Maria Dela Cruz",
            "parent_phone": "09171234567",
            "parent_relationship": "Mother",
            "rfid_card_uid": "RFID-8801",
            "sample_photo": "test_photos/sample_juan.jpg"
        },
        {
            "lrn": "109876543211",
            "first_name": "Maria",
            "last_name": "Santos",
            "gender": "Female",
            "grade_section": "Grade 10 - Mabini",
            "track_strand": "Junior High",
            "parent_name": "Elena Santos",
            "parent_phone": "09189876543",
            "parent_relationship": "Mother",
            "rfid_card_uid": "RFID-8802"
        },
        {
            "lrn": "109876543212",
            "first_name": "Angelo",
            "last_name": "Reyes",
            "gender": "Male",
            "grade_section": "Grade 8 - Luna",
            "track_strand": "Junior High",
            "parent_name": "Roberto Reyes",
            "parent_phone": "09205551234",
            "parent_relationship": "Father",
            "rfid_card_uid": "RFID-8803",
            "sample_photo": "test_photos/sample_angelo.jpg"
        },
        {
            "lrn": "109876543213",
            "first_name": "Chloe",
            "last_name": "Mendoza",
            "gender": "Female",
            "grade_section": "Grade 11 - STEM",
            "track_strand": "STEM",
            "parent_name": "Carmen Mendoza",
            "parent_phone": "09173339876",
            "parent_relationship": "Mother",
            "rfid_card_uid": "RFID-8804"
        },
        {
            "lrn": "109876543214",
            "first_name": "Joshua",
            "last_name": "Bautista",
            "gender": "Male",
            "grade_section": "Grade 9 - Del Pilar",
            "track_strand": "Junior High",
            "parent_name": "Ferdinand Bautista",
            "parent_phone": "09198887766",
            "parent_relationship": "Father",
            "rfid_card_uid": "RFID-8805"
        },
        {
            "lrn": "109876543215",
            "first_name": "Andrea",
            "last_name": "Garcia",
            "gender": "Female",
            "grade_section": "Grade 12 - HUMSS",
            "track_strand": "HUMSS",
            "parent_name": "Teresa Garcia",
            "parent_phone": "09214445566",
            "parent_relationship": "Mother",
            "rfid_card_uid": "RFID-8806"
        }
    ]

    for idx, s in enumerate(students_data):
        existing = session.query(Student).filter_by(lrn=s["lrn"]).first()
        qr_path = generate_student_qr(s["lrn"])
        
        # Check if sample photo exists to extract real YuNet/SFace embedding
        photo_rel = ""
        embedding_json = None
        
        sample_img_path = s.get("sample_photo")
        if sample_img_path and os.path.exists(sample_img_path):
            img = cv2.imread(sample_img_path)
            if img is not None:
                faces = face_engine.detect_faces(img)
                if len(faces) > 0:
                    best_face = max(faces, key=lambda f: f[2] * f[3])
                    emb = face_engine.extract_face_embedding(img, best_face)
                    embedding_json = json.dumps(emb.tolist())
                    
                    target_photo = PHOTOS_DIR / f"{s['lrn']}_{s['last_name'].lower()}.jpg"
                    shutil.copyfile(sample_img_path, str(target_photo))
                    photo_rel = f"/photos/{target_photo.name}"
                    print(f"  [+] Extracted 128-d face embedding for {s['first_name']} {s['last_name']}")
        
        # Fallback random normalized embedding for remaining students so they have valid vectors
        if not embedding_json:
            dummy = np.random.randn(128).astype(np.float32)
            dummy /= np.linalg.norm(dummy)
            embedding_json = json.dumps(dummy.tolist())

        if not existing:
            student = Student(
                lrn=s["lrn"],
                first_name=s["first_name"],
                last_name=s["last_name"],
                gender=s["gender"],
                grade_section=s["grade_section"],
                track_strand=s["track_strand"],
                parent_name=s["parent_name"],
                parent_phone=s["parent_phone"],
                parent_relationship=s["parent_relationship"],
                rfid_card_uid=s["rfid_card_uid"],
                qr_code_path=qr_path,
                photo_path=photo_rel,
                face_embedding=embedding_json,
                is_active=True,
                created_at=datetime.now() - timedelta(days=idx * 2)
            )
            session.add(student)
        else:
            existing.face_embedding = embedding_json
            if photo_rel:
                existing.photo_path = photo_rel
            existing.qr_code_path = qr_path

    session.commit()
    print(f"  [OK] Seeded {len(students_data)} student records with AI face embeddings & QR codes.")

    # 3. Seed Historical Attendance & Parent SMS Transactions
    print("\n[3/3] Seeding School Gate Attendance History...")
    now = datetime.now()
    logs_data = [
        ("109876543210", "Juan Dela Cruz", "Grade 10 - Rizal", "TIME_IN", now.replace(hour=7, minute=14, second=22), "FACE_RECOGNITION", "SENT"),
        ("109876543211", "Maria Santos", "Grade 10 - Mabini", "TIME_IN", now.replace(hour=7, minute=22, second=45), "RFID_TAP", "SENT"),
        ("109876543212", "Angelo Reyes", "Grade 8 - Luna", "TIME_IN", now.replace(hour=7, minute=31, second=10), "FACE_RECOGNITION", "SENT"),
        ("109876543213", "Chloe Mendoza", "Grade 11 - STEM", "TIME_IN", now.replace(hour=7, minute=45, second=30), "QR_CODE", "SENT"),
        ("109876543210", "Juan Dela Cruz", "Grade 10 - Rizal", "TIME_OUT", now.replace(hour=16, minute=30, second=15), "FACE_RECOGNITION", "SENT"),
        ("109876543211", "Maria Santos", "Grade 10 - Mabini", "TIME_OUT", now.replace(hour=16, minute=35, second=50), "RFID_TAP", "SENT")
    ]

    for lrn, name, grade, scan_type, scan_time, method, sms_stat in logs_data:
        log = AttendanceLog(
            lrn=lrn,
            student_name=name,
            grade_section=grade,
            scan_type=scan_type,
            timestamp=scan_time,
            device_id="GATE-1-AI-KIOSK",
            verification_method=method,
            sms_status=sms_stat
        )
        session.add(log)

        action_verb = "ENTERED the school gate (TIME-IN)" if scan_type == "TIME_IN" else "EXITED the school gate (TIME-OUT)"
        # Note: SMS logs are omitted to honor user's request to keep outbound SMS logs clean.

    session.commit()
    print("  [OK] Seeded realistic gate attendance history.")

    print("\n" + "="*65)
    print("  SUCCESS: AI FACE RECOGNITION DATABASE SEEDED!")
    print("="*65)
    session.close()

if __name__ == '__main__':
    seed_database()
