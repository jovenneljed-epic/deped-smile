import os
import sys
import unittest

# Ensure working directory is added to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from smile_orm import get_all_pricing_plans_orm, get_pricing_plan_by_code_orm

class TestRbacAndMonetization(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def login(self, username, password):
        return self.client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=False)

    def test_01_unauthenticated_redirects_to_login(self):
        """Unauthenticated user accessing protected routes is redirected to login."""
        res = self.client.get('/', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers['Location'])

        res_kiosk = self.client.get('/kiosk', follow_redirects=False)
        self.assertEqual(res_kiosk.status_code, 302)

        res_admin = self.client.get('/admin/settings', follow_redirects=False)
        self.assertEqual(res_admin.status_code, 302)

    def test_02_super_admin_full_access(self):
        """Super Admin account has full access to settings, billing, users, and dashboard."""
        with self.client:
            res_login = self.login('admin', 'admin123')
            self.assertEqual(res_login.status_code, 302)

            res_dash = self.client.get('/')
            self.assertEqual(res_dash.status_code, 200)

            res_settings = self.client.get('/admin/settings')
            self.assertEqual(res_settings.status_code, 200)
            self.assertIn(b'Central System Settings', res_settings.data)

            res_billing = self.client.get('/admin/billing')
            self.assertEqual(res_billing.status_code, 200)
            self.assertIn(b'Subscriptions & Income Management', res_billing.data)

            res_users = self.client.get('/admin/users')
            self.assertEqual(res_users.status_code, 200)

    def test_03_principal_role_lockdown(self):
        """Principal is restricted from Super Admin central settings and billing."""
        with self.client:
            self.login('principal', 'principal123')

            # Allowed
            res_dash = self.client.get('/')
            self.assertEqual(res_dash.status_code, 200)
            res_enroll = self.client.get('/enroll')
            self.assertEqual(res_enroll.status_code, 200)

            # Blocked from Super Admin exclusive routes (403 Forbidden)
            res_settings = self.client.get('/admin/settings')
            self.assertEqual(res_settings.status_code, 403)
            self.assertIn(b'Access Restricted', res_settings.data)

            res_billing = self.client.get('/admin/billing')
            self.assertEqual(res_billing.status_code, 403)

    def test_04_teacher_and_guard_role_lockdown(self):
        """Teacher and Guard have specific role scopes and are blocked from admin."""
        # Teacher
        with self.client:
            self.login('teacher', 'teacher123')
            self.assertEqual(self.client.get('/students').status_code, 200)
            self.assertEqual(self.client.get('/admin/settings').status_code, 403)
            self.assertEqual(self.client.get('/admin/billing').status_code, 403)

        # Guard
        with self.client:
            self.login('guard', 'guard123')
            self.assertEqual(self.client.get('/kiosk').status_code, 200)
            self.assertEqual(self.client.get('/admin/settings').status_code, 403)
            self.assertEqual(self.client.get('/enroll').status_code, 403)

    def test_05_super_admin_can_edit_subscription_pricing(self):
        """Super Admin can update subscription prices in real time."""
        with self.client:
            self.login('admin', 'admin123')

            # Update Standard School Plan price to 5499.00
            res = self.client.post('/api/admin/pricing/update', json={
                'plan_code': 'STANDARD_SCHOOL',
                'price_php': 5499.00,
                'name': 'DepEd Standard Campus Plan (Updated)',
                'billing_cycle': 'month'
            })
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data['success'])
            self.assertEqual(data['plan']['price_php'], 5499.00)

            # Verify in DB / ORM
            plan = get_pricing_plan_by_code_orm('STANDARD_SCHOOL')
            self.assertEqual(plan['price_php'], 5499.00)

    def test_06_non_admin_cannot_edit_subscription_pricing(self):
        """Non-admin roles cannot edit subscription pricing."""
        with self.client:
            self.login('teacher', 'teacher123')
            res = self.client.post('/api/admin/pricing/update', json={
                'plan_code': 'STANDARD_SCHOOL',
                'price_php': 99.00
            })
            self.assertEqual(res.status_code, 403)

    def test_07_payment_simulation_and_revenue_generation(self):
        """Simulate Philippine GCash/Maya payment checkout and record revenue."""
        res = self.client.post('/api/payment/simulate', json={
            'plan_code': 'PARENT_VIP_MONTHLY',
            'payer_name': 'Juan Dela Cruz',
            'payer_email_phone': '09171234567',
            'payment_method': 'GCASH',
            'payer_role': 'PARENT',
            'amount_php': 49.00
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('SMILE-PAY-', data['transaction']['transaction_ref'])
        self.assertEqual(data['transaction']['status'], 'COMPLETED')
        self.assertEqual(data['transaction']['amount_php'], 49.00)

    def test_08_plans_api(self):
        """Public/Client plans API returns filtered categories."""
        res_parent = self.client.get('/api/plans?category=PARENT')
        self.assertEqual(res_parent.status_code, 200)
        parent_plans = res_parent.get_json()['plans']
        self.assertTrue(all(p['category'] == 'PARENT' for p in parent_plans))

        res_school = self.client.get('/api/plans?category=SCHOOL')
        self.assertEqual(res_school.status_code, 200)
        school_plans = res_school.get_json()['plans']
        self.assertTrue(all(p['category'] == 'SCHOOL' for p in school_plans))

    def test_09_user_management_rbac(self):
        """Super Admin can create, toggle status, and delete staff accounts; non-admins blocked."""
        # Non-admin blocked
        with self.client:
            self.login('principal', 'principal123')
            res = self.client.post('/api/admin/users', json={
                'username': 'newguard',
                'full_name': 'New Guard',
                'email': 'guard@test.com',
                'password': 'password123',
                'role': 'GUARD'
            })
            self.assertEqual(res.status_code, 403)

        # Super Admin creates account
        with self.client:
            import time
            ts = int(time.time() * 1000)
            self.login('admin', 'admin123')
            res = self.client.post('/api/admin/users', json={
                'username': f'guard_{ts}',
                'full_name': 'Night Shift Guard',
                'email': f'nightguard_{ts}@test.com',
                'password': 'nightguard123',
                'role': 'GUARD',
                'phone_number': '09181112233'
            })
            self.assertEqual(res.status_code, 200)
            user_data = res.get_json()['user']
            user_id = user_data['id']

            # Toggle status
            res_toggle = self.client.post(f'/api/admin/users/{user_id}/toggle')
            self.assertEqual(res_toggle.status_code, 200)
            self.assertFalse(res_toggle.get_json()['user']['is_active'])

            # Delete created user
            res_del = self.client.delete(f'/api/admin/users/{user_id}')
            self.assertEqual(res_del.status_code, 200)
            self.assertTrue(res_del.get_json()['success'])

    def test_10_settings_sms_and_school_admin_only(self):
        """Settings changes are restricted exclusively to Super Admin."""
        # Non-admin blocked from settings POST
        with self.client:
            self.login('teacher', 'teacher123')
            res_sms = self.client.post('/admin/settings/sms', data={'mode': 'MOCK'})
            self.assertEqual(res_sms.status_code, 403)
            res_db = self.client.get('/api/db-backup')
            self.assertEqual(res_db.status_code, 403)

        # Super Admin allowed
        with self.client:
            self.login('admin', 'admin123')
            res_sms = self.client.post('/admin/settings/sms', data={
                'mode': 'MOCK',
                'semaphore_sender_name': 'SMILE_ALERT'
            }, follow_redirects=True)
            self.assertEqual(res_sms.status_code, 200)
            self.assertIn(b'SMS Gateway credentials', res_sms.data)

            res_db = self.client.get('/api/db-backup')
            self.assertEqual(res_db.status_code, 200)

    def test_11_full_account_settings_lifecycle(self):
        """Add, edit, password reset, deactivate, reactivate, and delete staff account."""
        import time
        ts = int(time.time() * 1000)
        test_uname = f"teacher_sec_{ts}"
        
        with self.client:
            # Login as Super Admin
            self.login('admin', 'admin123')

            # 1. ADD account with section assignment
            res_add = self.client.post('/api/admin/users', json={
                'username': test_uname,
                'full_name': 'Test Teacher Section',
                'email': f'{test_uname}@donmontano.edu.ph',
                'password': 'initial_pass_123',
                'role': 'TEACHER',
                'phone_number': '09171112233',
                'assigned_section_id': 1
            })
            self.assertEqual(res_add.status_code, 200)
            user_id = res_add.get_json()['user']['id']
            self.assertEqual(res_add.get_json()['user']['assigned_section_id'], 1)

            # 2. EDIT account details & reset password
            res_edit = self.client.post(f'/api/admin/users/{user_id}', json={
                'full_name': 'Test Teacher Updated',
                'phone_number': '09179998877',
                'password': 'new_secret_pass_456'
            })
            self.assertEqual(res_edit.status_code, 200)
            updated_user = res_edit.get_json()['user']
            self.assertEqual(updated_user['full_name'], 'Test Teacher Updated')
            self.assertEqual(updated_user['phone_number'], '09179998877')

            # 3. VERIFY LOGIN with new password
            self.client.get('/logout')
            res_login_new = self.login(test_uname, 'new_secret_pass_456')
            self.assertEqual(res_login_new.status_code, 302)

            # 4. DEACTIVATE ACCOUNT
            self.client.get('/logout')
            self.login('admin', 'admin123')
            res_deact = self.client.post(f'/api/admin/users/{user_id}/deactivate')
            self.assertEqual(res_deact.status_code, 200)
            self.assertFalse(res_deact.get_json()['user']['is_active'])

            # 5. VERIFY DEACTIVATED USER BLOCKED FROM LOGIN
            self.client.get('/logout')
            res_login_deact = self.login(test_uname, 'new_secret_pass_456')
            # Should remain on /login with 200 and error message
            self.assertEqual(res_login_deact.status_code, 200)
            self.assertIn(b'Invalid credentials or inactive account', res_login_deact.data)

            # 6. REACTIVATE ACCOUNT
            self.login('admin', 'admin123')
            res_act = self.client.post(f'/api/admin/users/{user_id}/activate')
            self.assertEqual(res_act.status_code, 200)
            self.assertTrue(res_act.get_json()['user']['is_active'])

            # 7. VERIFY LOGIN SUCCEEDS AFTER ACTIVATION
            self.client.get('/logout')
            res_login_react = self.login(test_uname, 'new_secret_pass_456')
            self.assertEqual(res_login_react.status_code, 302)

            # 8. PERMANENTLY DELETE
            self.client.get('/logout')
            self.login('admin', 'admin123')
            res_del = self.client.delete(f'/api/admin/users/{user_id}')
            self.assertEqual(res_del.status_code, 200)

    def test_12_admin_self_protection_guards(self):
        """Admin cannot deactivate, delete, or demote their own active Super Admin account."""
        with self.client:
            self.login('admin', 'admin123')
            # Get admin's own user ID
            res_users = self.client.get('/admin/users')
            self.assertEqual(res_users.status_code, 200)

            # Try to deactivate own account (id=1 is admin)
            res_toggle = self.client.post('/api/admin/users/1/toggle')
            self.assertEqual(res_toggle.status_code, 400)
            self.assertIn(b'cannot deactivate your own', res_toggle.data)

            # Try to delete own account
            res_delete = self.client.delete('/api/admin/users/1')
            self.assertEqual(res_delete.status_code, 400)
            self.assertIn(b'cannot delete your own', res_delete.data)

            # Try to demote role
            res_demote = self.client.post('/api/admin/users/1', json={'role': 'TEACHER'})
            self.assertEqual(res_demote.status_code, 400)
            self.assertIn(b'cannot demote your own', res_demote.data)

    def test_13_domain_configuration_and_qr_code(self):
        """Super Admin can update official domain name, and QR code points to that domain."""
        with self.client:
            self.login('admin', 'admin123')

            # 1. Update domain name
            custom_domain = "https://smile.donmontanocis.edu.ph"
            res = self.client.post('/admin/settings/school', data={
                'school_name': 'Don Montano Central Integrated School',
                'deped_region': 'Region IV-A CALABARZON',
                'school_id': '152008',
                'system_domain': custom_domain
            }, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b'Public Domain settings updated successfully', res.data)

            # 2. Check settings page shows custom domain
            res_settings = self.client.get('/admin/settings')
            self.assertEqual(res_settings.status_code, 200)
            self.assertIn(b'smile.donmontanocis.edu.ph', res_settings.data)

            # 3. Verify QR code endpoint responds with valid PNG
            res_qr = self.client.get('/api/parent/qr-code')
            self.assertEqual(res_qr.status_code, 200)
            self.assertEqual(res_qr.mimetype, 'image/png')
            # PNG signature is \x89PNG
            self.assertTrue(res_qr.data.startswith(b'\x89PNG'))

if __name__ == '__main__':
    unittest.main()


