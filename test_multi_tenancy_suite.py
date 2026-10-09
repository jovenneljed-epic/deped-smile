import unittest
import os
import time
from app import app
from smile_orm import (
    Session, School, Section, Student, User, AttendanceLog, StaffAttendanceLog,
    get_all_schools_orm, get_school_by_id_orm, get_school_by_code_orm,
    create_school_orm, update_school_orm, get_all_sections_orm,
    get_all_enrolled_students_orm, save_student_orm, record_attendance_orm,
    get_today_attendance_logs_orm, get_all_users_orm, record_staff_attendance_orm
)

class TestMultiTenancyEnterpriseSuite(unittest.TestCase):
    """
    Comprehensive verification suite for Project S.M.I.L.E. Enterprise Multi-Tenancy.
    Validates tenant isolation, data protection for DMCIS (School #1), 
    dynamic onboarding, section isolation, and attendance scoping.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.client.testing = True

    def test_01_anchor_school_dmcis_intact(self):
        """Verify School #1 (Don Montano Central Integrated School) exists and is intact."""
        dmcis = get_school_by_id_orm(1)
        self.assertIsNotNone(dmcis)
        self.assertEqual(dmcis["id"], 1)
        self.assertEqual(dmcis["school_id"], "152008")
        self.assertIn("Don Montano", dmcis["school_name"])
        self.assertEqual(dmcis["district"], "Umingan II")
        self.assertEqual(dmcis["division"], "SDO Pangasinan II")
        self.assertTrue(dmcis["is_active"])

    def test_02_dmcis_existing_sections_belong_to_school_1(self):
        """Verify all DMCIS sections are properly assigned to school_id = 1."""
        sections = get_all_sections_orm(school_id=1)
        self.assertGreaterEqual(len(sections), 26)
        for sec in sections:
            self.assertEqual(sec.get("school_id"), 1)

    def test_03_dmcis_existing_students_belong_to_school_1(self):
        """Verify all existing DMCIS enrolled students belong to school_id = 1."""
        students = get_all_enrolled_students_orm(school_id=1)
        self.assertGreaterEqual(len(students), 1)
        for st in students:
            self.assertEqual(st.get("school_id"), 1)

    def test_04_onboard_new_tenant_school_2(self):
        """Test onboarding a new DepEd tenant school (Umingan Central National High School)."""
        session = Session()
        try:
            # Check if school 152009 already exists from prior test run, clean up if needed
            existing = session.query(School).filter_by(school_id="152009").first()
            if existing:
                session.delete(existing)
                session.commit()
        finally:
            session.close()

        ok, sch = create_school_orm(
            school_id="152009",
            school_name="Umingan Central National High School",
            school_short_name="UCNHS",
            district="Umingan I",
            division="SDO Pangasinan II",
            region="Region I • Ilocos Region",
            school_address="Poblacion West, Umingan, Pangasinan",
            principal_name="Dr. Juan Dela Cruz, EdD",
            contact_phone="09181112233",
            latitude=15.9350,
            longitude=120.8450,
            geofence_radius=1500.0
        )
        self.assertTrue(ok, f"Failed to onboard school: {sch}")
        self.assertEqual(sch["school_id"], "152009")
        self.assertEqual(sch["school_short_name"], "UCNHS")
        self.assertGreater(sch["id"], 1)
        self.__class__.school_2_id = sch["id"]

    def test_05_school_2_has_isolated_sections_and_principal(self):
        """Verify School #2 automatically received 26 K-12 sections and its own principal."""
        sid2 = self.__class__.school_2_id
        sch2_sections = get_all_sections_orm(school_id=sid2)
        self.assertEqual(len(sch2_sections), 26, "School 2 must have exactly 26 canonical K-12 sections")
        for s in sch2_sections:
            self.assertEqual(s["school_id"], sid2)

        # Verify Principal account was provisioned for School #2
        users = get_all_users_orm(school_id=sid2)
        prin = [u for u in users if u.get("role") == "PRINCIPAL" and u.get("school_id") == sid2]
        self.assertGreaterEqual(len(prin), 1)
        self.assertIn("152009", prin[0]["email"])

    def test_06_strict_student_tenant_isolation(self):
        """Test enrolling a student in School #2 and verify zero leakage into School #1."""
        sid2 = self.__class__.school_2_id
        test_lrn = f"9999{int(time.time())}"[-12:]

        # Enroll in School #2
        saved = save_student_orm(
            lrn=test_lrn,
            first_name="Ricardo",
            last_name="Dalisay",
            middle_name="Tenant",
            gender="Male",
            grade_level="Grade 11",
            section="STEM - Archimedes",
            track_strand="STEM",
            parent_name="Cardo Dalisay",
            parent_phone="09190001122",
            school_id=sid2
        )
        self.assertIsNotNone(saved)
        self.assertEqual(saved["school_id"], sid2)

        # School 1 students must NOT contain this student
        sch1_students = get_all_enrolled_students_orm(school_id=1)
        sch1_lrns = [s["lrn"] for s in sch1_students]
        self.assertNotIn(test_lrn, sch1_lrns, "School 1 leaked student from School 2!")

        # School 2 students MUST contain this student
        sch2_students = get_all_enrolled_students_orm(school_id=sid2)
        sch2_lrns = [s["lrn"] for s in sch2_students]
        self.assertIn(test_lrn, sch2_lrns, "School 2 failed to retrieve its own student!")

    def test_07_strict_attendance_scoping(self):
        """Test gate attendance logs are isolated by school_id."""
        sid2 = self.__class__.school_2_id
        sch2_students = get_all_enrolled_students_orm(school_id=sid2)
        st2 = sch2_students[0]

        log_id = record_attendance_orm(
            lrn=st2["lrn"],
            student_name=st2["full_name"],
            grade_section=st2["grade_section"],
            scan_type="TIME_IN",
            school_id=sid2
        )
        self.assertGreater(log_id, 0)

        # Retrieve today's logs for School #1 vs School #2
        sch1_logs = get_today_attendance_logs_orm(school_id=1)
        sch2_logs = get_today_attendance_logs_orm(school_id=sid2)

        sch1_log_ids = [l["id"] for l in sch1_logs]
        sch2_log_ids = [l["id"] for l in sch2_logs]

        self.assertIn(log_id, sch2_log_ids, "School 2 log not found in School 2 query")
        self.assertNotIn(log_id, sch1_log_ids, "School 2 log leaked into School 1 query!")

    def test_08_api_schools_endpoint(self):
        """Test GET /api/schools returns array of schools with live metrics."""
        res = self.client.get('/api/schools')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "success")
        schools = data.get("schools", [])
        self.assertGreaterEqual(len(schools), 2)

        sch1 = next((s for s in schools if s["id"] == 1), None)
        self.assertIsNotNone(sch1)
        self.assertEqual(sch1["school_id"], "152008")

        sch2 = next((s for s in schools if s["school_id"] == "152009"), None)
        self.assertIsNotNone(sch2)
        self.assertEqual(sch2["total_sections"], 26)

    def test_09_admin_school_switcher_session(self):
        """Test Super Admin can switch active school context via /admin/switch-school/<id>."""
        sid2 = self.__class__.school_2_id
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["role"] = "SUPER_ADMIN"

        res = self.client.post(f'/admin/switch-school/{sid2}', headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("school_id"), sid2)

    def test_10_api_sections_query_param_scoping(self):
        """Test GET /api/sections?school_id=X properly scopes returned sections."""
        sid2 = self.__class__.school_2_id

        # Query School 1
        res1 = self.client.get('/api/sections?school_id=1')
        self.assertEqual(res1.status_code, 200)
        d1 = res1.get_json()
        self.assertEqual(d1["school_id"], 1)

        # Query School 2
        res2 = self.client.get(f'/api/sections?school_id={sid2}')
        self.assertEqual(res2.status_code, 200)
        d2 = res2.get_json()
        self.assertEqual(d2["school_id"], sid2)
        self.assertEqual(len(d2["sections"]), 26)

    def test_11_strict_user_roster_isolation(self):
        """Verify get_all_users_orm(school_id=3) strictly returns Flores NHS accounts with 0 DMCIS accounts."""
        users_fnhs = get_all_users_orm(school_id=3)
        self.assertGreaterEqual(len(users_fnhs), 1)
        for u in users_fnhs:
            self.assertEqual(u["school_id"], 3, f"Account {u['username']} does not belong to Flores NHS (School 3)")
            self.assertNotEqual(u["school_id"], 1, "DMCIS account leaked into Flores NHS roster")

        users_dmcis = get_all_users_orm(school_id=1)
        self.assertGreaterEqual(len(users_dmcis), 1)
        for u in users_dmcis:
            self.assertEqual(u["school_id"], 1, f"Account {u['username']} does not belong to DMCIS (School 1)")
            self.assertNotEqual(u["school_id"], 3, "Flores NHS account leaked into DMCIS roster")

    def test_12_admin_login_at_flores_nhs_isolates_users(self):
        """Verify Administrator logging into Flores NHS sees strictly Flores NHS accounts on /admin/users."""
        # Log in choosing Flores NHS (school_id=3)
        login_res = self.client.post('/login', data={
            'username': 'admin',
            'password': 'admin123',
            'school_id': 3
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)

        # Access /admin/users
        res = self.client.get('/admin/users')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Confirm Flores NHS accounts are shown and DMCIS staff accounts are not
        self.assertIn("Flores National High School", html)
        self.assertIn("principal_300452", html)
        self.assertNotIn("teacher_test", html)

    def test_13_admin_switch_school_updates_roster(self):
        """Verify Administrator switching to School #1 immediately scopes /admin/users to DMCIS accounts."""
        # Switch school to 1
        switch_res = self.client.get('/admin/switch-school/1')
        self.assertEqual(switch_res.status_code, 302)

        # Access /admin/users
        res = self.client.get('/admin/users')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("teacher_test", html)
        self.assertNotIn("principal_300452", html)

    def test_14_flores_nhs_principal_flexible_credentials(self):
        """Verify Flores NHS Principal can log in with flexible usernames and canonical passwords."""
        test_combos = [
            ({'username': 'principal_300452', 'password': 'principal', 'school_id': 3}, "explicit username + 'principal'"),
            ({'username': 'principal_300452', 'password': 'principal123', 'school_id': 3}, "explicit username + 'principal123'"),
            ({'username': 'principal', 'password': 'principal', 'school_id': 3}, "generic 'principal' with Flores NHS campus selected"),
            ({'username': '300452', 'password': 'principal', 'school_id': 3}, "DepEd school ID as username"),
            ({'username': 'principal_flores', 'password': 'principal', 'school_id': 3}, "slug username 'principal_flores'")
        ]
        for creds, desc in test_combos:
            res = self.client.post('/login', data=creds, follow_redirects=True)
            self.assertEqual(res.status_code, 200, f"Login failed for {desc}")
            html = res.get_data(as_text=True)
            self.assertIn("Flores National High School", html, f"Active campus not Flores NHS for {desc}")
            # Clean session
            self.client.get('/logout')

    def test_15_principal_auto_tenant_routing_when_campus_unselected(self):
        """Verify non-superadmin logging in with campus left on School #1 is seamlessly routed to their school."""
        # Client submits Flores NHS principal with school_id=1 (default dropdown position)
        res = self.client.post('/login', data={
            'username': 'principal_300452',
            'password': 'principal',
            'school_id': 1
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        # Must NOT show campus mismatch error
        self.assertNotIn("Please select your assigned campus", html)
        # Must be logged in to Flores NHS
        self.assertIn("Flores National High School", html)
        self.client.get('/logout')

if __name__ == '__main__':
    unittest.main()
