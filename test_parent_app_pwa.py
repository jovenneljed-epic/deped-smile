import unittest
import json
from app import app
from smile_orm import get_all_announcements_orm, get_all_enrolled_students_orm

class TestParentAppPWA(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_pwa_manifest(self):
        response = self.client.get('/static/manifest.json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get("display"), "standalone")
        self.assertEqual(data.get("start_url"), "/parent")
        icons = data.get("icons", [])
        self.assertTrue(len(icons) >= 2)
        sizes = [i["sizes"] for i in icons]
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)
        print("[+] Manifest verified:", data.get("name"))

    def test_pwa_service_worker(self):
        response = self.client.get('/static/sw.js')
        self.assertEqual(response.status_code, 200)
        content = response.data.decode('utf-8')
        self.assertIn("smile-parent-v2", content)
        self.assertIn("addEventListener('push'", content)
        print("[+] Service Worker verified.")

    def test_pwa_icons_accessible(self):
        for icon in ['pwa_icon_192.png', 'pwa_icon_512.png', 'apple_touch_icon.png']:
            res = self.client.get(f'/static/images/{icon}')
            self.assertEqual(res.status_code, 200, f"Icon {icon} not found!")
            self.assertTrue(len(res.data) > 1000)
        print("[+] High-res PWA & Apple icons verified.")

    def test_parent_app_page(self):
        response = self.client.get('/parent')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn("DepEd Parent App", html)
        self.assertIn("manifest.json", html)
        self.assertIn("apple-touch-icon", html)
        self.assertIn("iosInstallModal", html)
        self.assertIn("pwaInstallBanner", html)
        self.assertIn("Advisories & News", html)
        print("[+] Parent App HTML & PWA elements verified.")

    def test_announcements_api(self):
        # GET
        res = self.client.get('/api/announcements')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("success"))
        announcements = data.get("announcements", [])
        self.assertTrue(len(announcements) >= 4)
        print(f"[+] Announcements API GET verified ({len(announcements)} advisories).")

        # POST
        payload = {
            "title": "Automated Unit Test Advisory",
            "category": "ANNOUNCEMENT",
            "content": "This is a test announcement created during automated verification.",
            "author": "Testing Suite",
            "is_urgent": False,
            "target_grade": "Grade 1"
        }
        post_res = self.client.post('/api/announcements', json=payload)
        self.assertEqual(post_res.status_code, 200)
        post_data = json.loads(post_res.data)
        self.assertTrue(post_data.get("success"))
        created_id = post_data["announcement"]["id"]
        print(f"[+] Announcement created with ID: {created_id}")

        # DELETE
        del_res = self.client.delete(f'/api/announcements/{created_id}')
        self.assertEqual(del_res.status_code, 200)
        print("[+] Announcement deleted successfully.")

    def test_parent_test_notification_api(self):
        res = self.client.post('/api/parent/test-notification', json={"lrn": "152008250007"})
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get("success"))
        self.assertIn("title", data)
        self.assertIn("body", data)
        self.assertIn("icon", data)
        print("[+] Test notification API verified:", data.get("title"))

if __name__ == '__main__':
    unittest.main()
