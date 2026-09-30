import unittest
import json
from app import app

class TestSmileWebApp(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role"] = "SUPER_ADMIN"

    def test_dashboard_route(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"PROJECT S.M.I.L.E.", response.data)
        self.assertIn(b"Dashboard", response.data)

    def test_kiosk_route(self):
        response = self.client.get('/kiosk')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"STANDBY FOR SCAN", response.data)
        self.assertIn(b"kioskStream", response.data)

    def test_enroll_route(self):
        response = self.client.get('/enroll')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Learner Reference Number", response.data)

    def test_students_route(self):
        response = self.client.get('/students')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Enrolled Students Directory", response.data)

    def test_sms_center_route(self):
        response = self.client.get('/sms')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SMS Notifier Control Center", response.data)

    def test_api_stats(self):
        response = self.client.get('/api/stats')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("total_enrolled", data)
        self.assertIn("total_scans", data)

    def test_export_csv(self):
        response = self.client.get('/export/csv')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"DEPED SCHOOL ATTENDANCE REPORT", response.data)

    def test_api_test_sms(self):
        response = self.client.post('/api/test-sms', json={"phone": "09171234567"})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get("success"))

if __name__ == '__main__':
    unittest.main()
