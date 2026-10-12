import unittest
import json
from datetime import datetime
from app import app
from smile_orm import (
    Session, Student, AttendanceLog, save_student_orm,
    update_student_orm, get_student_by_lrn_or_rfid_orm,
    delete_student_orm, get_all_enrolled_students_orm
)

class TestStudentEditDelete(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Create a test student in DB
        self.test_lrn = "888888888888"
        session = Session()
        try:
            # Clean up prior if exists
            session.query(AttendanceLog).filter(AttendanceLog.lrn.in_([self.test_lrn, "888888888889"])).delete()
            session.query(Student).filter(Student.lrn.in_([self.test_lrn, "888888888889"])).delete()
            session.commit()
        finally:
            session.close()

        # Save student
        res = save_student_orm(
            lrn=self.test_lrn,
            first_name="Juan",
            middle_name="Protacio",
            last_name="Dela Cruz",
            grade_level="Grade 10",
            section_name="Rizal",
            parent_name="Maria Dela Cruz",
            parent_phone="09123456789",
            parent_relationship="Mother",
            school_id=1
        )
        self.assertIsNotNone(res)
        self.assertEqual(res.get("lrn"), self.test_lrn)

    def tearDown(self):
        session = Session()
        try:
            session.query(AttendanceLog).filter(AttendanceLog.lrn.in_([self.test_lrn, "888888888889"])).delete()
            session.query(Student).filter(Student.lrn.in_([self.test_lrn, "888888888889"])).delete()
            session.commit()
        finally:
            session.close()

    def test_orm_update_student_details(self):
        """Verify update_student_orm correctly updates learner attributes."""
        ok, updated = update_student_orm(
            self.test_lrn,
            first_name="Juanito",
            last_name="Mercado",
            parent_phone="09998887777",
            rfid_card_uid="RFID998877",
            gender="Male",
            birthdate="2008-05-15",
            track_strand="STEM"
        )
        self.assertTrue(ok)
        self.assertEqual(updated["first_name"], "Juanito")
        self.assertEqual(updated["last_name"], "Mercado")
        self.assertEqual(updated["full_name"], "Juanito Protacio Mercado")
        self.assertEqual(updated["parent_phone"], "09998887777")
        self.assertEqual(updated["rfid_card_uid"], "RFID998877")
        self.assertEqual(updated["gender"], "Male")
        self.assertEqual(updated["birthdate"], "2008-05-15")
        self.assertEqual(updated["track_strand"], "STEM")

    def test_orm_update_student_lrn_cascade(self):
        """Verify changing LRN cascades to AttendanceLog and updates LRN."""
        session = Session()
        try:
            # Create a mock attendance log for the test student
            log = AttendanceLog(
                lrn=self.test_lrn,
                student_name="Juan Dela Cruz",
                grade_section="Grade 10 - Rizal",
                school_id=1,
                scan_type="IN",
                timestamp=datetime.now()
            )
            session.add(log)
            session.commit()
        finally:
            session.close()

        new_lrn = "888888888889"
        ok, updated = update_student_orm(self.test_lrn, new_lrn=new_lrn, first_name="Juan")
        self.assertTrue(ok)
        self.assertEqual(updated["lrn"], new_lrn)

        # Check that AttendanceLog was cascaded
        session = Session()
        try:
            logs = session.query(AttendanceLog).filter_by(lrn=new_lrn).all()
            self.assertEqual(len(logs), 1)
        finally:
            session.close()

    def test_api_student_endpoints(self):
        """Test API endpoints /api/student/<lrn>, /api/update-student/<lrn>, and /api/delete-student/<lrn>."""
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['role'] = 'SUPER_ADMIN'
            sess['school_id'] = 1

        # 1. GET /api/student/<lrn>
        res = self.app.get(f'/api/student/{self.test_lrn}')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['student']['first_name'], 'Juan')

        # 2. POST /api/update-student/<lrn>
        res = self.app.post(
            f'/api/update-student/{self.test_lrn}',
            json={
                "first_name": "Johnny",
                "last_name": "Bravo",
                "parent_name": "Mama Bravo",
                "parent_phone": "09112223334"
            }
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['student']['first_name'], 'Johnny')
        self.assertEqual(data['student']['last_name'], 'Bravo')

        # 3. GET /students/edit/<lrn>
        page_res = self.app.get(f'/students/edit/{self.test_lrn}')
        self.assertEqual(page_res.status_code, 200)
        self.assertIn(b"Edit Student Profile", page_res.data)
        self.assertIn(b"Johnny", page_res.data)

        # 4. POST /api/delete-student/<lrn>
        del_res = self.app.post(f'/api/delete-student/{self.test_lrn}')
        self.assertEqual(del_res.status_code, 200)
        del_data = json.loads(del_res.data)
        self.assertTrue(del_data['success'])

        # Verify learner no longer exists
        st_after = get_student_by_lrn_or_rfid_orm(self.test_lrn)
        self.assertIsNone(st_after)

if __name__ == '__main__':
    unittest.main()
