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
        self.assertTrue(any(s["section_name"] == "Masipag" for s in grade1), "Grade 1 should have Masipag")
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
        self.assertIn("Masipag", sec_names)
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
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role"] = "SUPER_ADMIN"

        # Base dashboard
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"deped_seal.svg", r.data)
        self.assertIn(b"School Security & Attendance Dashboard", r.data)

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

    def test_advisory_attendance_report(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role"] = "SUPER_ADMIN"

        # 1. Test HTML Page Load
        r_page = self.client.get('/advisory/attendance-report')
        self.assertEqual(r_page.status_code, 200)
        self.assertIn(b"Student Attendance Report by Date", r_page.data)
        self.assertIn(b"DepEd SF2 Attendance Module", r_page.data)
        self.assertIn(b"reportDateInput", r_page.data)

        # 2. Test JSON API Endpoint
        r_api = self.client.get('/api/advisory/attendance-report?date=2026-10-04')
        self.assertEqual(r_api.status_code, 200)
        data = r_api.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("report", data)
        self.assertIn("summary", data["report"])
        self.assertIn("records", data["report"])
        self.assertIn("total_enrolled", data["report"]["summary"])

        # 3. Test CSV Export Endpoint
        r_csv = self.client.get('/advisory/attendance-report/export-csv?date=2026-10-04')
        self.assertEqual(r_csv.status_code, 200)
        self.assertIn("text/csv", r_csv.content_type)
        self.assertIn(b"DEPED SCHOOL FORM 2 (SF2)", r_csv.data)
        self.assertIn(b"DepEd LRN", r_csv.data)


class TestProgressiveAutomationsAndPush(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "principal_admin"
            sess["full_name"] = "Dr. Maria Santos"
            sess["role"] = "SUPER_ADMIN"

    def test_automations_page_render(self):
        """Tests that /automations renders the push notification center."""
        resp = self.client.get('/automations')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Automated E-Notification & Push Center", resp.data)
        self.assertIn(b"Broadcast Principal Announcement", resp.data)
        self.assertIn(b"pushPermissionBanner", resp.data)
        self.assertIn(b"categoryFilterTabs", resp.data)
        self.assertIn(b"workflowsContainer", resp.data)
        self.assertIn(b"principalBroadcastModal", resp.data)

    def test_api_automations_list_and_filter(self):
        """Tests /api/automations returns progressive workflows & category filters."""
        # 1. Fetch all
        resp = self.client.get('/api/automations')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        workflows = data.get("workflows", [])
        self.assertGreaterEqual(len(workflows), 15, "Should have at least 15 progressive automations")
        
        categories = {w.get("category") for w in workflows}
        self.assertTrue(any("PRINCIPAL" in c for c in categories), "Should have principal category")
        self.assertTrue(any("DAILY" in c for c in categories), "Should have daily reminder category")
        self.assertTrue(any("WEEKLY" in c for c in categories), "Should have weekly reminder category")
        self.assertTrue(any("MONTHLY" in c for c in categories), "Should have monthly reminder category")
        self.assertTrue(any("EVENT" in c for c in categories), "Should have event reminder category")
        self.assertTrue(any("EMERGENCY" in c for c in categories), "Should have emergency category")

        # 2. Filter by category
        resp_daily = self.client.get('/api/automations?category=DAILY')
        self.assertEqual(resp_daily.status_code, 200)
        daily_wfs = resp_daily.get_json().get("workflows", [])
        self.assertGreaterEqual(len(daily_wfs), 5)
        for w in daily_wfs:
            self.assertEqual(w["category"], "DAILY_REMINDER")

    def test_api_automations_toggle(self):
        """Tests toggling an automation active / paused state."""
        # Get first workflow
        resp = self.client.get('/api/automations')
        wf = resp.get_json()["workflows"][0]
        wf_id = wf["id"]
        prev_state = wf["is_active"]

        # Toggle
        toggle_res = self.client.post('/api/automations/toggle', json={"id": wf_id})
        self.assertEqual(toggle_res.status_code, 200)
        toggled_data = toggle_res.get_json()
        self.assertTrue(toggled_data.get("success"))
        self.assertEqual(toggled_data["workflow"]["is_active"], not prev_state)

        # Toggle back
        restore_res = self.client.post('/api/automations/toggle', json={"id": wf_id})
        self.assertEqual(restore_res.status_code, 200)
        self.assertEqual(restore_res.get_json()["workflow"]["is_active"], prev_state)

    def test_api_automations_trigger(self):
        """Tests triggering a workflow push notification."""
        resp = self.client.get('/api/automations')
        wf = resp.get_json()["workflows"][0]
        wf_id = wf["id"]

        trigger_res = self.client.post(f'/api/automations/trigger/{wf_id}', json={
            "source": "UNIT_TEST_TRIGGER"
        })
        self.assertEqual(trigger_res.status_code, 200)
        data = trigger_res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("execution", data)
        self.assertIn("payload", data)
        self.assertEqual(data["execution"]["status"], "SUCCESS")

    def test_api_automations_update(self):
        """Tests editing/personalizing notification template contents."""
        resp = self.client.get('/api/automations')
        wf = resp.get_json()["workflows"][0]
        wf_id = wf["id"]
        orig_body = wf["default_body"]

        new_body = "Personalized test notification: Don Montano CIS assembly is today at {time}."
        update_res = self.client.post(f'/api/automations/update/{wf_id}', json={
            "default_body": new_body,
            "priority": "HIGH"
        })
        self.assertEqual(update_res.status_code, 200)
        data = update_res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["workflow"]["default_body"], new_body)
        self.assertEqual(data["workflow"]["priority"], "HIGH")

        # Test trigger with dynamic placeholders evaluated
        trigger_res = self.client.post(f'/api/automations/trigger/{wf_id}', json={})
        self.assertEqual(trigger_res.status_code, 200)
        trig_data = trigger_res.get_json()
        self.assertTrue(trig_data.get("success"))
        self.assertNotIn("{time}", trig_data["payload"]["body"])

        # Restore original body
        self.client.post(f'/api/automations/update/{wf_id}', json={
            "default_body": orig_body,
            "priority": wf.get("priority", "NORMAL")
        })

    def test_api_principal_broadcast(self):
        """Tests Principal Announcement broadcast endpoint."""
        payload = {
            "title": "Principal's Official School Announcement: Campus Safety",
            "body": "DepEd safety protocol reminder: All gate visitors must present government ID at Guardhouse 1.",
            "target_audience": "ALL",
            "priority": "HIGH"
        }
        res = self.client.post('/api/automations/principal-broadcast', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("execution", data)
        self.assertIn("id", data["execution"])
        self.assertEqual(data["payload"]["title"], payload["title"])
        self.assertEqual(data["payload"]["priority"], "HIGH")

    def test_api_automations_create_custom(self):
        """Tests creating a custom progressive reminder."""
        new_wf = {
            "title": "DepEd Reading Month Kickoff Announcement",
            "description": "Annual campus celebration of National Reading Month.",
            "category": "EVENT_REMINDER",
            "trigger_type": "EVENT_SCHEDULE",
            "schedule_cron": "November 1st @ 08:00 AM",
            "default_title": "National Reading Month Celebration",
            "default_body": "Join us tomorrow for the opening ceremony in the DepEd Amphitheater.",
            "target_audience": "ALL",
            "priority": "NORMAL"
        }
        res = self.client.post('/api/automations/create', json=new_wf)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["workflow"]["title"], new_wf["title"])

    def test_api_automations_executions(self):
        """Tests retrieving recent workflow audit logs."""
        res = self.client.get('/api/automations/executions?limit=10')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIsInstance(data.get("executions"), list)

    def test_api_automations_test_push(self):
        """Tests push notification test payload generation."""
        res = self.client.post('/api/automations/test-push')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("payload", data)
        self.assertIn("sound", data["payload"])

    def test_parent_poll_push_notification_stream(self):
        """Tests real-time push notification streaming via parent polling endpoint."""
        from smile_orm import create_parent_notification_orm
        test_notif = create_parent_notification_orm(
            lrn="ALL",
            title="Realtime Stream Test",
            body="Checking real-time delivery to mobile app.",
            category="TEST",
            priority="HIGH",
            workflow_key="unit_test_stream"
        )
        notif_id = test_notif["raw_id"]

        # 1. Polling with an older last_notif_id should immediately return the new notification
        poll_res = self.client.get(f'/api/parent/poll/152008250007?last_notif_id={notif_id - 1}')
        self.assertEqual(poll_res.status_code, 200)
        poll_data = poll_res.get_json()
        self.assertTrue(poll_data.get("has_new_notification"))
        self.assertIsNotNone(poll_data.get("notification"))
        self.assertEqual(poll_data["notification"]["title"], "Realtime Stream Test")

        # 2. Polling with up-to-date last_notif_id should return has_new_notification = False
        poll_res2 = self.client.get(f'/api/parent/poll/152008250007?last_notif_id={notif_id}')
        self.assertEqual(poll_res2.status_code, 200)
        poll_data2 = poll_res2.get_json()
        self.assertFalse(poll_data2.get("has_new_notification"))


if __name__ == '__main__':
    unittest.main()


