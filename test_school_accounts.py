import sys
import time
import app
import smile_orm

def run_tests():
    client = app.app.test_client()

    # Login as super admin
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'admin'
        sess['role'] = 'SUPER_ADMIN'
        sess['is_admin'] = True

    # 1. Test /admin/schools
    res = client.get('/admin/schools')
    assert res.status_code == 200, f'Expected 200, got {res.status_code}'
    assert b'Schools &amp; Campuses' in res.data or b'Schools & Campuses' in res.data, 'admin_schools title missing'
    print('[PASS] /admin/schools returns 200 with schools hub')

    # 2. Test /admin/users
    res = client.get('/admin/users')
    assert res.status_code == 200, f'Expected 200, got {res.status_code}'
    assert b'Campus / School' in res.data, 'Campus column missing in admin_users'
    print('[PASS] /admin/users returns 200 with Campus filter & column')

    # 3. Test creating a user for a specific school (school_id=3)
    unique_user = f'teacher_sch3_{int(time.time())}'
    res = client.post('/api/admin/users', json={
        'username': unique_user,
        'full_name': 'Teacher Test School 3',
        'email': f'{unique_user}@test.edu.ph',
        'password': 'password123',
        'role': 'TEACHER',
        'school_id': 3
    })
    assert res.status_code == 200, f'Failed creating user: {res.data}'
    data = res.get_json()
    assert data['user']['school_id'] == 3, f"Expected school_id 3, got {data['user']['school_id']}"
    user_id = data['user']['id']
    print(f"[PASS] Created user {unique_user} assigned to school_id 3")

    # 4. Test updating that user to school_id 4
    res = client.post(f'/api/admin/users/{user_id}', json={
        'school_id': 4
    })
    assert res.status_code == 200, f'Failed updating user: {res.data}'
    data = res.get_json()
    assert data['user']['school_id'] == 4, f"Expected school_id 4, got {data['user']['school_id']}"
    print(f"[PASS] Updated user {unique_user} to school_id 4")

    # 5. Clean up test user
    with smile_orm.get_db_session() as s:
        u = s.query(smile_orm.User).filter_by(id=user_id).first()
        if u:
            s.delete(u)
            s.commit()
    print('[PASS] Cleaned up test user successfully')

    # 6. Verify all schools have principal accounts
    schools = smile_orm.get_all_schools_orm()
    for sch in schools:
        assert sch.get('principal_username'), f"School {sch['school_id']} missing principal_username"
        assert sch.get('has_principal_account'), f"School {sch['school_id']} missing principal account"
        print(f"[PASS] School {sch['school_id']} ({sch['school_name']}) has principal: {sch['principal_username']}")

if __name__ == '__main__':
    run_tests()
    print('\nALL SCHOOL ACCOUNT TESTS PASSED SUCCESSFULLY! 100% OK')
