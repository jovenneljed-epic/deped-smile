import unittest
from smile_orm import (
    get_all_sections_orm, get_sections_by_grade_orm,
    save_section_orm, delete_section_orm, Section, Session
)
from app import app

class TestSectionsAndAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_sections_count_and_grades(self):
        sections = get_all_sections_orm()
        self.assertGreaterEqual(len(sections), 25, "Should have at least 25 sections for K-12")
        
        kinder = get_sections_by_grade_orm("Kindergarten")
        self.assertTrue(any(s["section_name"] == "Sunflower" for s in kinder), "Kindergarten should have Sunflower")
        
        grade1 = get_sections_by_grade_orm("Grade 1")
        self.assertTrue(any(s["section_name"] == "Mabait" for s in grade1), "Grade 1 should have Mabait")
        self.assertFalse(any(s["section_name"] == "Gold" for s in grade1), "Grade 1 should NOT contain Grade 10 sections like Gold")

        grade10 = get_sections_by_grade_orm("Grade 10")
        self.assertTrue(any(s["section_name"] == "Gold" for s in grade10), "Grade 10 should have Gold")

        grade12 = get_sections_by_grade_orm("Grade 12")
        self.assertTrue(any(s["section_name"] == "STEM - Einstein" for s in grade12), "Grade 12 should have STEM - Einstein")

    def test_api_sections_get(self):
        resp = self.client.get('/api/sections')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertGreaterEqual(len(data.get("sections", [])), 25)

        # Test grade level filter
        resp_g1 = self.client.get('/api/sections?grade_level=Grade%201')
        self.assertEqual(resp_g1.status_code, 200)
        data_g1 = resp_g1.get_json()
        self.assertTrue(data_g1.get("success"))
        sec_names = [s["section_name"] for s in data_g1.get("sections", [])]
        self.assertIn("Mabait", sec_names)
        self.assertNotIn("Gold", sec_names)

    def test_section_crud(self):
        # 1. Create section
        res = self.client.post('/api/sections', json={
            "grade_level": "Grade 5",
            "section_name": "TestMabini",
            "adviser_teacher": "Mr. Test Teacher",
            "room_number": "Test Bldg - 99"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        sec_id = data["section"]["id"]

        # 2. Verify exists
        session = Session()
        try:
            sec = session.query(Section).filter_by(id=sec_id).first()
            self.assertIsNotNone(sec)
            self.assertEqual(sec.adviser_teacher, "Mr. Test Teacher")
        finally:
            session.close()

        # 3. Edit section (Update via API)
        edit_res = self.client.post(f'/api/sections/{sec_id}', json={
            "grade_level": "Grade 5",
            "section_name": "TestMabiniRenamed",
            "adviser_teacher": "Dr. Updated Adviser",
            "room_number": "Room 505"
        })
        self.assertEqual(edit_res.status_code, 200)
        self.assertTrue(edit_res.get_json().get("success"))

        # Verify updated values in DB
        session = Session()
        try:
            updated_sec = session.query(Section).filter_by(id=sec_id).first()
            self.assertEqual(updated_sec.section_name, "TestMabiniRenamed")
            self.assertEqual(updated_sec.adviser_teacher, "Dr. Updated Adviser")
            self.assertEqual(updated_sec.room_number, "Room 505")
        finally:
            session.close()

        # 4. Delete section
        del_res = self.client.post(f'/api/sections/{sec_id}/delete')
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.get_json().get("success"))

    def test_pages_load_cleanly(self):
        # Base dashboard
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"deped_seal.svg", r.data)
        self.assertIn(b"Don Montano Central Integrated School", r.data)

        # Enroll page
        r_enroll = self.client.get('/enroll')
        self.assertEqual(r_enroll.status_code, 200)
        self.assertIn(b"selectSectionName", r_enroll.data)
        self.assertIn(b"deped_seal.svg", r_enroll.data)

        # Kiosk page
        r_kiosk = self.client.get('/kiosk')
        self.assertEqual(r_kiosk.status_code, 200)
        self.assertIn(b"deped_seal.svg", r_kiosk.data)

        # Database admin page
        r_db = self.client.get('/database')
        self.assertEqual(r_db.status_code, 200)
        self.assertIn(b"addSectionModal", r_db.data)
        self.assertIn(b"editSectionModal", r_db.data)
        self.assertIn(b"openEditSectionModal", r_db.data)
        self.assertIn(b"deped_seal.svg", r_db.data)

if __name__ == '__main__':
    unittest.main()
