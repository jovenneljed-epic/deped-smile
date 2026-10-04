import app

client = app.app.test_client()

print("--- 1. Testing /mobile & /download/apk ---")
r_mob = client.get('/mobile')
print("GET /mobile:", r_mob.status_code, "->", r_mob.headers.get("Location", ""))

r_apk = client.get('/download/apk')
print("GET /download/apk:", r_apk.status_code)

print("--- 2. Testing /api/mobile/events ---")
r_ev = client.get('/api/mobile/events')
print("GET /api/mobile/events:", r_ev.status_code)
events = r_ev.get_json().get("events", [])
print(f"Loaded {len(events)} events:")
for e in events[:3]:
    print(f"  - {e['title']} ({e['category']}) on {e['event_date']}")

print("--- 3. Testing POST /api/events ---")
r_create = client.post('/api/events', json={
    "title": "Automated Test Activity",
    "category": "ACADEMIC",
    "description": "Integration test for parent mobile app activities calendar.",
    "event_date": "2026-11-15",
    "start_time": "08:30 AM",
    "end_time": "12:00 PM",
    "location": "Science Hall",
    "target_grades": "Grade 7 to 10"
})
print("POST /api/events:", r_create.status_code)
created = r_create.get_json().get("event")
if created:
    ev_id = created["id"]
    print(f"Created event #{ev_id}: {created['title']}")
    r_del = client.delete(f"/api/admin/events/{ev_id}")
    print(f"DELETE /api/admin/events/{ev_id}:", r_del.status_code)

print("--- 4. Testing /api/mobile/notifications ---")
r_notif = client.get('/api/mobile/notifications/109876543210')
print("GET /api/mobile/notifications:", r_notif.status_code)
notif_data = r_notif.get_json()
print("Notifications count:", len(notif_data.get("notifications", [])))

print("--- 5. Testing /api/mobile/staff/login & /api/mobile/staff/home ---")
r_staff_login = client.post('/api/mobile/staff/login', json={"employee_number": "TCH-1001"})
print("POST /api/mobile/staff/login:", r_staff_login.status_code)
staff_json = r_staff_login.get_json()
assert staff_json.get("success") is True, f"Staff login failed: {staff_json}"
staff_id = staff_json["staff"]["id"]
print(f"Logged in staff: {staff_json['staff']['full_name']} (ID: {staff_id}, EmpNo: {staff_json['staff']['employee_number']})")

r_staff_home = client.get(f'/api/mobile/staff/home/{staff_id}')
print(f"GET /api/mobile/staff/home/{staff_id}:", r_staff_home.status_code)
home_json = r_staff_home.get_json()
assert home_json.get("success") is True, f"Staff home failed: {home_json}"
print("Staff DTR punches:", home_json["today_status"]["total_punches"], "Rendered:", home_json["today_status"]["rendered_str"])

r_clock = client.post('/api/mobile/staff/dtr-clock', json={
    "user_id": staff_id,
    "scan_type": "TIME_IN",
    "latitude": 14.3012,
    "longitude": 120.9578,
    "method": "MOBILE_APP"
})
print("POST /api/mobile/staff/dtr-clock:", r_clock.status_code)

print("--- 6. Testing /api/parent/poll, pending acknowledgments, & /api/parent/acknowledge-alert ---")
lrn_test = "152008250007"
r_poll1 = client.get(f'/api/parent/poll/{lrn_test}?initial=1')
print("GET /api/parent/poll initial:", r_poll1.status_code)
poll1_json = r_poll1.get_json()
latest_id = poll1_json.get("latest_log_id", 0)

# Polling with latest_id should NOT return has_new = True (prevents infinite repeat!)
r_poll2 = client.get(f'/api/parent/poll/{lrn_test}?last_id={latest_id}')
poll2_json = r_poll2.get_json()
assert poll2_json.get("has_new") is False, "Poll deadlock! Returned has_new=True when last_id == latest_log_id"
print(f"Poll check with last_id={latest_id} returned has_new=False (Repeat loop prevented!)")

# Check pending acknowledgments
r_pending = client.get(f'/api/parent/pending-acknowledgments/{lrn_test}')
print("GET /api/parent/pending-acknowledgments:", r_pending.status_code)
pending_json = r_pending.get_json()
print("Pending unacknowledged count:", pending_json.get("count", 0))

# If there is a log, test acknowledging it
if latest_id > 0:
    r_ack = client.post('/api/parent/acknowledge-alert', json={
        "log_id": latest_id,
        "lrn": lrn_test,
        "acknowledged_by": "Parent Automated Test"
    })
    print(f"POST /api/parent/acknowledge-alert for log #{latest_id}:", r_ack.status_code)
    ack_json = r_ack.get_json()
    assert ack_json.get("success") is True, f"Acknowledgment failed: {ack_json}"
    assert ack_json["log"]["parent_acknowledged"] is True, "parent_acknowledged flag not True"
    print("Acknowledged by:", ack_json["log"]["parent_acknowledged_by"], "at", ack_json["log"]["parent_acknowledged_at"])

print("ALL TESTS PASSED SUCCESSFULLY!")
