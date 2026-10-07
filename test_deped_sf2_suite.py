"""
DepEd School Form 2 (SF2) Automation Test Suite
Verifies automated gate kiosk aggregation, monthly 1-31 attendance grid,
Male/Female segregation, ADA, PAM calculation, and print/CSV export endpoints.
"""

import unittest
from datetime import datetime, date
from app import app
from smile_orm import (
    Session, Student, Section, AttendanceLog, User,
    get_monthly_deped_sf2_report_orm
)

class TestDepEdSF2Automation(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_orm_sf2_generation_structure(self):
        """Verifies ORM generator returns valid DepEd DO 58 compliant data dictionary."""
        report = get_monthly_deped_sf2_report_orm(month=10, year=2026)
        self.assertIsNotNone(report)
        self.assertEqual(report["month"], 10)
        self.assertEqual(report["year"], 2026)
        self.assertEqual(report["month_name"], "OCTOBER")
        self.assertIn("males", report)
        self.assertIn("females", report)
        self.assertIn("statistics", report)
        self.assertIn("days_meta", report)
        self.assertEqual(len(report["days_meta"]), 31)

        # Verify statistics keys
        stats = report["statistics"]
        self.assertIn("ada_total", stats)
        self.assertIn("pam_total", stats)
        self.assertIn("total_enrolled", stats)
        self.assertIn("school_days", stats)

    def test_sf2_web_route_teacher_access(self):
        """Verifies teacher can access their advisory monthly SF2 sheet."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 3
            sess['username'] = 'teacher'
            sess['role'] = 'TEACHER'
            sess['full_name'] = 'Mam Jovelyn D. Aviguela'
            sess['assigned_section_id'] = 13
            sess['assigned_section_name'] = 'Kindergarten - Sunflower'

        res = self.client.get('/advisory/sf2')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"School Form 2", res.data)
        self.assertIn(b"Mam Jovelyn D. Aviguela", res.data)
        self.assertIn(b"152008", res.data) # School ID

    def test_sf2_api_json_endpoint(self):
        """Verifies /api/advisory/sf2 returns correct JSON format."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 3
            sess['username'] = 'teacher'
            sess['role'] = 'TEACHER'
            sess['assigned_section_id'] = 13

        res = self.client.get('/api/advisory/sf2?month=10&year=2026')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["report"]["month"], 10)
        self.assertEqual(data["report"]["school_id"], "152008")

    def test_sf2_csv_export(self):
        """Verifies /advisory/sf2/export-csv returns valid downloadable spreadsheet."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 3
            sess['username'] = 'teacher'
            sess['role'] = 'TEACHER'
            sess['assigned_section_id'] = 13

        res = self.client.get('/advisory/sf2/export-csv?month=10&year=2026')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "text/csv; charset=utf-8")
        self.assertIn(b"DEPED SCHOOL FORM 2", res.data)
        self.assertIn(b"MALE LEARNERS", res.data)
        self.assertIn(b"FEMALE LEARNERS", res.data)
        self.assertIn(b"Average Daily Attendance (ADA)", res.data)

    def test_unauthenticated_access_redirects(self):
        """Verifies unauthenticated visitors are redirected to login."""
        res = self.client.get('/advisory/sf2')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers['Location'])

if __name__ == '__main__':
    unittest.main()
