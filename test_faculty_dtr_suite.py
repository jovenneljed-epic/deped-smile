import unittest
import json
import base64
import numpy as np
import cv2
from app import app
from smile_orm import (
    Session, User, StaffAttendanceLog,
    enroll_staff_face_orm, get_enrolled_staff_faces_orm,
    record_staff_attendance_orm, get_staff_today_status_orm,
    get_staff_dtr_logs_orm
)
from smile_config import DEFAULT_SCHOOL_LAT, DEFAULT_SCHOOL_LON, ALLOWED_GEOFENCE_RADIUS_METERS

class TestFacultyDTRSuite(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

        # Ensure a test teacher exists
        session = Session()
        try:
            teacher = session.query(User).filter_by(username="teacher_test").first()
            if not teacher:
                teacher = User(
                    username="teacher_test",
                    email="teacher.test@deped.gov.ph",
                    password_hash="pbkdf2:sha256:600000$test$hash",
                    full_name="Mam Jovelyn D. Aviguetero",
                    role="TEACHER",
                    phone_number="09171234567",
                    is_active=True
                )
                session.add(teacher)
                session.commit()
                session.refresh(teacher)
            self.teacher_id = teacher.id
        finally:
            session.close()

        # Login as the teacher
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.teacher_id
            sess["username"] = "teacher_test"
            sess["role"] = "TEACHER"
            sess["full_name"] = "Mam Jovelyn D. Aviguetero"

    def test_01_faculty_scanner_page_loads(self):
        """Test GET /faculty-scanner returns 200 with proper HTML and school configs."""
        res = self.client.get('/faculty-scanner')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Faculty & Staff Face DTR Scanner", res.data)
        self.assertIn(b"Biometric Targeting", res.data)
        self.assertIn(str(ALLOWED_GEOFENCE_RADIUS_METERS).encode(), res.data)

    def test_02_faculty_dtr_page_loads(self):
        """Test GET /faculty/dtr returns 200 and Civil Service Form 48."""
        res = self.client.get('/faculty/dtr')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Civil Service Form No. 48", res.data)
        self.assertIn(b"DAILY TIME RECORD", res.data)
        self.assertIn(b"Jovelyn D. Aviguetero", res.data)

    def test_03_enroll_staff_face_orm(self):
        """Test enrolling synthetic 128-d face embedding into database."""
        fake_emb = np.random.randn(128).astype(np.float32)
        # Normalize
        fake_emb /= np.linalg.norm(fake_emb)

        ok, user_dict = enroll_staff_face_orm(
            user_id=self.teacher_id,
            embedding_array=fake_emb,
            photo_path="/static/uploads/faculty/test_teacher.jpg"
        )
        self.assertTrue(ok)
        self.assertEqual(user_dict["id"], self.teacher_id)

        # Check enrolled staff faces cache
        enrolled = get_enrolled_staff_faces_orm()
        self.assertTrue(any(u["user_id"] == self.teacher_id for u in enrolled))

    def test_04_record_attendance_campus_verified(self):
        """Test logging attendance within campus geofence."""
        # Clean today's test logs first to avoid cooldown
        session = Session()
        try:
            session.query(StaffAttendanceLog).filter_by(user_id=self.teacher_id).delete()
            session.commit()
        finally:
            session.close()

        # Coordinates 10 meters away from school center
        lat = DEFAULT_SCHOOL_LAT + 0.00005
        lon = DEFAULT_SCHOOL_LON + 0.00005

        ok, msg, log = record_staff_attendance_orm(
            user_id=self.teacher_id,
            scan_type="AUTO",
            lat=lat,
            lon=lon,
            accuracy=8.5,
            method="FACIAL_RECOGNITION",
            score=0.965
        )

        self.assertTrue(ok)
        self.assertEqual(log["geotag_status"], "CAMPUS_VERIFIED")
        self.assertEqual(log["scan_type"], "TIME_IN")
        self.assertIn("Campus Verified", msg)

    def test_05_duplicate_cooldown_prevention(self):
        """Test that rapid scans within 45 seconds are blocked."""
        lat = DEFAULT_SCHOOL_LAT
        lon = DEFAULT_SCHOOL_LON

        ok, msg, log = record_staff_attendance_orm(
            user_id=self.teacher_id,
            scan_type="AUTO",
            lat=lat,
            lon=lon,
            accuracy=5.0
        )
        self.assertFalse(ok)
        self.assertIn("Already", msg)
        self.assertTrue("wait" in msg.lower() or "cooldown" in msg.lower())

    def test_06_today_dtr_status_and_logs(self):
        """Test retrieving today's 4-punch DTR status and monthly audit trail."""
        status = get_staff_today_status_orm(self.teacher_id)
        self.assertTrue(status["has_am_in"] or status["has_pm_in"])
        self.assertGreater(status["total_punches"], 0)

        logs = get_staff_dtr_logs_orm(user_id=self.teacher_id)
        self.assertGreater(len(logs), 0)
        self.assertEqual(logs[0]["user_id"], self.teacher_id)

    def test_07_api_dtr_logs_endpoint(self):
        """Test GET /api/faculty/dtr-logs JSON endpoint."""
        res = self.client.get('/api/faculty/dtr-logs')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertIn("logs", data)
        self.assertIn("today_status", data)

    def test_08_api_today_status_endpoint(self):
        """Test GET /api/faculty/today-status JSON endpoint."""
        res = self.client.get('/api/faculty/today-status')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertIn("today_status", data)

if __name__ == '__main__':
    unittest.main()
