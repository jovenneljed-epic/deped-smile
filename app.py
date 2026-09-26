import os
import io
import csv
import base64
import cv2
import numpy as np
from datetime import datetime, date
from pathlib import Path
from functools import wraps
from flask import (
    Flask, render_template, Response, request,
    jsonify, send_file, send_from_directory, redirect, url_for, session
)

from smile_config import (
    SCHOOL_NAME, DB_PATH, PHOTOS_DIR,
    get_sms_config, save_sms_settings
)
import smile_config
from smile_db import (
    get_all_enrolled_students, get_today_summary,
    save_student, record_sms, record_attendance
)
from smile_orm import (
    authenticate_user_orm, create_user_orm, get_all_users_orm,
    update_user_orm, delete_user_orm, get_user_by_id_orm,
    get_all_sections_orm,
    get_all_pricing_plans_orm, get_pricing_plan_by_code_orm,
    update_pricing_plan_orm, record_payment_transaction_orm,
    get_recent_payment_transactions_orm, get_revenue_statistics_orm,
    get_today_attendance_logs_orm, get_today_sms_count_orm,
    get_recent_sms_logs_orm, get_all_attendance_logs_for_export_orm
)
from smile_face_engine import SmileFaceEngine
from smile_sms import (
    send_via_semaphore, send_via_twilio, send_via_android_gateway,
    send_via_philsms, check_gateway_status, dispatch_sms_sync,
    send_parent_notification_async
)
from web_streamer import GateStreamer

app = Flask(__name__)
app.config['SECRET_KEY'] = 'deped-project-smile-2026-secret'

# Initialize background AI camera streamer
streamer = GateStreamer.get_instance()
streamer.start()

# Initialize AI Face Recognition Engine (YuNet + SFace)
try:
    face_engine = SmileFaceEngine()
except Exception as e:
    print(f"[!] Note: Face engine lazy initialized or disabled: {e}")
    face_engine = None

def decode_image_payload(req):
    """Extracts OpenCV BGR frame from file upload or base64 data string."""
    # 1. From multipart file
    if 'photo' in req.files and req.files['photo'].filename:
        file = req.files['photo']
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        return img
    
    # 2. From JSON or Form base64 image
    b64_str = None
    if req.is_json and req.json and 'image' in req.json:
        b64_str = req.json['image']
    elif req.form.get('webcam_image'):
        b64_str = req.form.get('webcam_image')
    elif req.form.get('image'):
        b64_str = req.form.get('image')

    if b64_str:
        if ',' in b64_str:
            b64_str = b64_str.split(',', 1)[1]
        img_bytes = base64.b64decode(b64_str)
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        return img

    return None

@app.route('/health', methods=['GET'])
def health_check():
    """Cloud Healthcheck & Diagnostics Endpoint."""
    from smile_orm import engine, Session, Student
    db_ok = False
    student_count = 0
    err_msg = None
    try:
        session = Session()
        student_count = session.query(Student).count()
        session.close()
        db_ok = True
    except Exception as e:
        err_msg = str(e)

    return jsonify({
        "status": "healthy" if db_ok else "degraded",
        "database": {
            "connected": db_ok,
            "dialect": engine.dialect.name if engine else "unknown",
            "enrolled_students": student_count,
            "error": err_msg
        },
        "system": {
            "school": smile_config.SCHOOL_NAME,
            "is_serverless": bool(smile_config.IS_VERCEL)
        }
    }), (200 if db_ok else 503)

# -------------------------------------------------------------
# Role-Based Access Control (RBAC) & Authentication Decorators
# -------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page', next=request.path))
        if session.get('role') != 'SUPER_ADMIN':
            return render_template(
                'errors/403.html', 
                school_name=smile_config.SCHOOL_NAME, 
                message="Access Restricted: Central System Settings, SMS credentials, database archives, and billing management can ONLY be accessed by the Super Administrator account."
            ), 403
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login_page', next=request.path))
            if session.get('role') not in allowed_roles:
                return render_template(
                    'errors/403.html',
                    school_name=smile_config.SCHOOL_NAME,
                    message=f"Access Denied: Your current account role ({session.get('role')}) does not have permission to view this section."
                ), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.context_processor
def inject_user_context():
    return {
        "current_user": {
            "id": session.get("user_id"),
            "username": session.get("username"),
            "full_name": session.get("full_name"),
            "role": session.get("role"),
            "is_admin": session.get("role") == "SUPER_ADMIN",
            "is_principal": session.get("role") in ["SUPER_ADMIN", "PRINCIPAL"],
            "is_teacher": session.get("role") in ["SUPER_ADMIN", "PRINCIPAL", "TEACHER"],
            "is_guard": session.get("role") in ["SUPER_ADMIN", "GUARD"]
        } if "user_id" in session else None
    }

# -------------------------------------------------------------
# Staff Authentication Routes
# -------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Staff & Administrator Authentication Portal."""
    next_url = request.args.get('next', '')
    if request.method == 'GET':
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return render_template('login.html', school_name=smile_config.SCHOOL_NAME, next_url=next_url)

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    
    user, msg = authenticate_user_orm(username, password)
    if not user:
        return render_template('login.html', school_name=smile_config.SCHOOL_NAME, error=msg, next_url=next_url)

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['full_name'] = user['full_name']
    session['role'] = user['role']

    # Role-specific smart redirection
    if next_url and next_url != '/login':
        return redirect(next_url)
    if user['role'] == 'GUARD':
        return redirect(url_for('kiosk'))
    elif user['role'] == 'SUPER_ADMIN':
        return redirect(url_for('admin_settings'))
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout_page():
    """Terminates staff session."""
    session.clear()
    return redirect(url_for('login_page'))

# -------------------------------------------------------------
# Super Administrator & Monetization Routes (Exclusive Access)
# -------------------------------------------------------------

@app.route('/admin/settings', methods=['GET'])
@admin_required
def admin_settings():
    """Super Admin Exclusive: Central System Configuration Portal."""
    sms_cfg = smile_config.get_sms_config()
    school_settings = smile_config.load_school_settings()
    return render_template(
        'admin_settings.html',
        school_name=smile_config.SCHOOL_NAME,
        school_settings=school_settings,
        system_domain=school_settings.get("system_domain", smile_config.SYSTEM_DOMAIN),
        sms_config=sms_cfg,
        sms_mode=sms_cfg.get("mode", "MOCK"),
        feedback_msg=request.args.get('msg')
    )

@app.route('/admin/settings/sms', methods=['POST'])
@admin_required
def admin_save_sms_settings():
    """Super Admin: Persists SMS provider credentials & mode."""
    new_settings = {
        "mode": request.form.get("mode", "MOCK"),
        "semaphore_api_key": request.form.get("semaphore_api_key", "").strip(),
        "semaphore_sender_name": request.form.get("semaphore_sender_name", "SEMAPHORE").strip(),
        "twilio_account_sid": request.form.get("twilio_account_sid", "").strip(),
        "twilio_auth_token": request.form.get("twilio_auth_token", "").strip(),
        "twilio_from_number": request.form.get("twilio_from_number", "").strip(),
        "philsms_api_key": request.form.get("philsms_api_key", "").strip(),
        "philsms_sender_id": request.form.get("philsms_sender_id", "PhilSMS").strip(),
        "gsm_port": request.form.get("gsm_port", "COM3").strip(),
    }
    try:
        new_settings["gsm_baudrate"] = int(request.form.get("gsm_baudrate", 9600))
    except (ValueError, TypeError):
        pass

    smile_config.save_sms_settings(new_settings)
    return redirect(url_for('admin_settings', msg="SMS Gateway credentials and active carrier updated successfully."))

@app.route('/admin/settings/school', methods=['POST'])
@admin_required
def admin_save_school_settings():
    """Super Admin: Updates official school profile, DepEd metadata, and Public Domain URL."""
    school_name = request.form.get("school_name", "").strip()
    deped_region = request.form.get("deped_region", "").strip()
    school_id = request.form.get("school_id", "").strip()
    system_domain = request.form.get("system_domain", "").strip()

    if school_name:
        smile_config.save_school_settings({
            "school_name": school_name,
            "deped_region": deped_region,
            "school_id": school_id,
            "system_domain": system_domain
        })
    return redirect(url_for('admin_settings', msg="School identity and Public Domain settings updated successfully."))

@app.route('/admin/billing', methods=['GET'])
@admin_required
def admin_billing():
    """Super Admin: Monetization, Recurring Revenue (MRR), and Editable Pricing Plans."""
    plans = get_all_pricing_plans_orm()
    revenue_stats = get_revenue_statistics_orm()
    transactions = get_recent_payment_transactions_orm(limit=50)
    return render_template(
        'admin_billing.html',
        school_name=smile_config.SCHOOL_NAME,
        plans=plans,
        revenue_stats=revenue_stats,
        transactions=transactions
    )

@app.route('/admin/users', methods=['GET'])
@admin_required
def admin_users():
    """Super Admin: Staff User Management & Account Settings Portal."""
    users = get_all_users_orm()
    sections = get_all_sections_orm()
    return render_template(
        'admin_users.html',
        school_name=smile_config.SCHOOL_NAME,
        users=users,
        sections=sections
    )

@app.route('/api/admin/users', methods=['POST'])
@admin_required
def api_admin_create_user():
    """Super Admin: Creates a new staff account."""
    data = request.json or request.form or {}
    username = data.get('username', '').strip()
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'TEACHER').strip().upper()
    phone_number = data.get('phone_number', '').strip()
    assigned_section_id = data.get('assigned_section_id')

    if not username or not full_name or not email or not password:
        return jsonify({"success": False, "message": "Full Name, Username, Email, and Password are required."}), 400

    success, user_or_msg = create_user_orm(
        username=username,
        email=email,
        password=password,
        full_name=full_name,
        role=role,
        phone_number=phone_number,
        assigned_section_id=assigned_section_id
    )
    if not success:
        return jsonify({"success": False, "message": user_or_msg}), 400
    user_dict = user_or_msg
    return jsonify({"success": True, "user": user_dict, "message": f"Account for {user_dict['full_name']} created successfully."})

@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
@admin_required
def api_admin_get_user(user_id):
    """Super Admin: Retrieves single user account details for editing."""
    user = get_user_by_id_orm(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404
    return jsonify({"success": True, "user": user})

@app.route('/api/admin/users/<int:user_id>', methods=['POST', 'PUT'])
@admin_required
def api_admin_update_user(user_id):
    """Super Admin: Updates existing staff account details, credentials, and section assignments."""
    data = request.json or request.form or {}
    update_fields = {}

    if 'full_name' in data and data['full_name'] is not None:
        val = data['full_name'].strip()
        if not val:
            return jsonify({"success": False, "message": "Full Name cannot be empty."}), 400
        update_fields['full_name'] = val

    if 'username' in data and data['username'] is not None:
        val = data['username'].strip()
        if not val:
            return jsonify({"success": False, "message": "Username cannot be empty."}), 400
        update_fields['username'] = val

    if 'email' in data and data['email'] is not None:
        val = data['email'].strip()
        if not val:
            return jsonify({"success": False, "message": "Email cannot be empty."}), 400
        update_fields['email'] = val

    if 'role' in data and data['role']:
        req_role = data['role'].strip().upper()
        if session.get('user_id') == user_id and req_role != 'SUPER_ADMIN':
            return jsonify({"success": False, "message": "You cannot demote your own active Super Administrator account."}), 400
        update_fields['role'] = req_role

    if 'phone_number' in data:
        update_fields['phone_number'] = data['phone_number'].strip() if data['phone_number'] else ""

    if 'assigned_section_id' in data:
        update_fields['assigned_section_id'] = data['assigned_section_id']

    if 'is_active' in data:
        new_active = bool(data['is_active'])
        if session.get('user_id') == user_id and not new_active:
            return jsonify({"success": False, "message": "You cannot deactivate your own active administrator account."}), 400
        update_fields['is_active'] = new_active

    if 'password' in data and data['password'] and data['password'].strip():
        update_fields['password'] = data['password'].strip()

    success, user_or_msg = update_user_orm(user_id, **update_fields)
    if not success:
        return jsonify({"success": False, "message": user_or_msg}), 400

    # Sync session if editing own account
    if session.get('user_id') == user_id:
        if 'full_name' in user_or_msg:
            session['full_name'] = user_or_msg['full_name']
        if 'username' in user_or_msg:
            session['username'] = user_or_msg['username']

    return jsonify({"success": True, "user": user_or_msg, "message": f"Account for {user_or_msg['full_name']} updated successfully."})

@app.route('/api/admin/users/<int:user_id>/activate', methods=['POST'])
@admin_required
def api_admin_activate_user(user_id):
    """Super Admin: Explicitly activates a user account."""
    success, updated_or_msg = update_user_orm(user_id, is_active=True)
    if not success:
        return jsonify({"success": False, "message": updated_or_msg}), 400
    return jsonify({"success": True, "user": updated_or_msg, "message": f"Account for {updated_or_msg['full_name']} activated successfully."})

@app.route('/api/admin/users/<int:user_id>/deactivate', methods=['POST'])
@admin_required
def api_admin_deactivate_user(user_id):
    """Super Admin: Explicitly deactivates a user account."""
    if session.get('user_id') == user_id:
        return jsonify({"success": False, "message": "You cannot deactivate your own active administrator account."}), 400
    success, updated_or_msg = update_user_orm(user_id, is_active=False)
    if not success:
        return jsonify({"success": False, "message": updated_or_msg}), 400
    return jsonify({"success": True, "user": updated_or_msg, "message": f"Account for {updated_or_msg['full_name']} deactivated successfully."})

@app.route('/api/admin/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def api_admin_toggle_user(user_id):
    """Super Admin: Toggles user account active/deactivated state."""
    user = get_user_by_id_orm(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404
    
    if session.get('user_id') == user_id:
        return jsonify({"success": False, "message": "You cannot deactivate your own active administrator account."}), 400

    new_state = not user['is_active']
    success, updated_or_msg = update_user_orm(user_id, is_active=new_state)
    if not success:
        return jsonify({"success": False, "message": updated_or_msg}), 400
    action_text = "activated" if new_state else "deactivated"
    return jsonify({"success": True, "user": updated_or_msg, "message": f"Account for {updated_or_msg['full_name']} {action_text} successfully."})

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def api_admin_delete_user(user_id):
    """Super Admin: Permanently deletes a staff account."""
    if session.get('user_id') == user_id:
        return jsonify({"success": False, "message": "You cannot delete your own active administrator account."}), 400
    
    ok, msg = delete_user_orm(user_id)
    return jsonify({"success": ok, "message": msg}), (200 if ok else 400)


@app.route('/api/admin/pricing/update', methods=['POST'])
@admin_required
def api_admin_update_pricing():
    """
    Super Admin: Edits subscription pricing amounts and details in real-time.
    Supports customizable pricing for school SaaS and parent SMS plans.
    """
    data = request.json or {}
    plan_code = data.get('plan_code', '').strip().upper()
    if not plan_code:
        return jsonify({"success": False, "message": "Plan code is required."}), 400

    price_php = data.get('price_php')
    name = data.get('name')
    description = data.get('description')
    billing_cycle = data.get('billing_cycle')

    success, result = update_pricing_plan_orm(
        plan_code=plan_code,
        price_php=price_php,
        name=name,
        description=description,
        billing_cycle=billing_cycle
    )
    if not success:
        return jsonify({"success": False, "message": result}), 400
    plan_dict = result
    return jsonify({"success": True, "plan": plan_dict, "message": f"Plan '{plan_dict['name']}' pricing updated to {plan_dict['price_formatted']}."})

@app.route('/api/payment/simulate', methods=['POST'])
def api_simulate_payment():
    """
    Simulates Philippine payment gateway checkout (GCash, Maya, Card).
    Records approved transaction and updates system revenue.
    Available to Super Admin and Parent Mobile Portal checkout.
    """
    data = request.json or {}
    plan_code = data.get('plan_code', '').strip().upper()
    payer_name = data.get('payer_name', 'DepEd Subscriber').strip()
    payer_email_phone = data.get('payer_email_phone', '').strip()
    payment_method = data.get('payment_method', 'GCASH').strip().upper()
    amount_php = data.get('amount_php')
    payer_role = data.get('payer_role', 'PARENT').strip().upper()
    student_lrn = data.get('student_lrn')

    if not plan_code:
        return jsonify({"success": False, "message": "Plan code is required."}), 400

    # Resolve aliases
    if plan_code in ['PARENT_VIP_MONTHLY', 'VIP_MONTHLY']:
        plan_code = 'PARENT_MONTHLY'
    elif plan_code in ['PARENT_VIP_ANNUAL', 'VIP_ANNUAL']:
        plan_code = 'PARENT_ANNUAL'

    plan = get_pricing_plan_by_code_orm(plan_code)
    if not plan:
        return jsonify({"success": False, "message": f"Plan {plan_code} not found."}), 404

    if amount_php is None or float(amount_php) < 0:
        amount_php = plan['price_php']

    success, tx_or_msg = record_payment_transaction_orm(
        payer_name=payer_name,
        plan_code=plan_code,
        amount_php=amount_php,
        payment_method=payment_method,
        payer_email_phone=payer_email_phone,
        payer_role=payer_role,
        notes=f"Student LRN: {student_lrn}" if student_lrn else ""
    )
    if not success:
        return jsonify({"success": False, "message": tx_or_msg}), 400

    tx = tx_or_msg
    return jsonify({
        "success": True,
        "transaction": tx,
        "message": f"Payment of {tx['amount_formatted']} via {tx['payment_method']} successfully verified and approved."
    })


@app.route('/api/plans', methods=['GET'])
def api_get_pricing_plans():
    """Returns active pricing plans (optionally filtered by category: 'SCHOOL' or 'PARENT')."""
    category = request.args.get('category', '').strip().upper() or None
    plans = get_all_pricing_plans_orm(category=category)
    return jsonify({"success": True, "plans": plans, "total": len(plans)})

# -------------------------------------------------------------
# Web Page Routes
# -------------------------------------------------------------

@app.route('/')
@login_required
def dashboard():
    """Administrative Attendance Dashboard."""
    summary = get_today_summary()
    enrolled = get_all_enrolled_students()
    logs = get_today_attendance_logs_orm()
    total_sms_today = get_today_sms_count_orm()

    return render_template(
        'dashboard.html',
        school_name=SCHOOL_NAME,
        total_enrolled=len(enrolled),
        total_scans_today=summary["total_scans"],
        unique_students_today=summary["unique_students"],
        total_sms_today=total_sms_today,
        logs=logs,
        today_date=datetime.now().strftime("%A, %B %d, %Y")
    )

@app.route('/kiosk')
@login_required
@role_required('SUPER_ADMIN', 'GUARD', 'PRINCIPAL')
def kiosk():
    """Fullscreen DepEd Gate Kiosk Interface with Live AI HUD."""
    summary = get_today_summary()
    enrolled = get_all_enrolled_students()
    return render_template(
        'kiosk.html',
        school_name=SCHOOL_NAME,
        total_enrolled=len(enrolled),
        total_scans=summary["total_scans"]
    )

@app.route('/enroll')
@login_required
@role_required('SUPER_ADMIN', 'PRINCIPAL')
def enroll_page():
    """Interactive Student Registration Form with Live Webcam Capture & Real Database Sections."""
    from smile_orm import get_all_sections_orm
    sections = get_all_sections_orm()
    return render_template(
        'enroll.html',
        school_name=SCHOOL_NAME,
        grade_levels=smile_config.GRADE_LEVELS,
        curriculum_strands=smile_config.CURRICULUM_STRANDS,
        sections=sections
    )

@app.route('/students')
@login_required
@role_required('SUPER_ADMIN', 'PRINCIPAL', 'TEACHER')
def students_directory():
    """Directory of enrolled students with photos and parent contacts."""
    students = get_all_enrolled_students()
    return render_template('students.html', school_name=SCHOOL_NAME, students=students)

@app.route('/sms')
@admin_required
def sms_center():
    """SMS Gateway status, outbound logs, and test sender."""
    sms_cfg = smile_config.get_sms_config()
    gateway_status = check_gateway_status()
    sms_logs = get_recent_sms_logs_orm(50)
    return render_template(
        'sms_center.html',
        school_name=SCHOOL_NAME,
        sms_config=sms_cfg,
        sms_mode=sms_cfg.get("mode", "MOCK"),
        gateway_status=gateway_status,
        logs=sms_logs
    )


@app.route('/parent/login', methods=['GET', 'POST'])
def parent_login():
    """Standalone Parent Authentication Screen via mobile phone or LRN."""
    if request.method == 'GET':
        return render_template('parent/login.html', school_name=SCHOOL_NAME)

    data = request.json or {}
    identifier = data.get('identifier', '').strip()
    auth_type = data.get('type', 'phone').strip().lower()

    if not identifier:
        return jsonify({"success": False, "message": "Please enter your mobile phone number or LRN."}), 400

    from smile_orm import Session, Student, get_students_by_parent_phone_orm
    orm_session = Session()
    try:
        students = []
        if auth_type == 'lrn' or (identifier.isdigit() and len(identifier) == 12 and not identifier.startswith('09')):
            st = orm_session.query(Student).filter_by(lrn=identifier).first()
            if st:
                students = [st.to_dict()]
        else:
            students = get_students_by_parent_phone_orm(identifier)

        if not students:
            clean = identifier.replace("-", "").replace(" ", "").replace("+63", "0")
            st = orm_session.query(Student).filter(Student.parent_phone.like(f"%{clean[-10:]}%")).first()
            if st:
                students = [st.to_dict()]

        if not students:
            return jsonify({"success": False, "message": f"No student records found linked to {identifier}. Please check with the school."}), 404

        first_lrn = students[0]["lrn"]
        resp = jsonify({
            "success": True,
            "message": f"Welcome, {students[0]['parent_name']}!",
            "redirect": f"/parent?lrn={first_lrn}",
            "students": students
        })
        resp.set_cookie('parent_lrn', first_lrn, max_age=86400 * 30)
        resp.set_cookie('parent_phone', students[0]['parent_phone'], max_age=86400 * 30)
        return resp
    finally:
        orm_session.close()

@app.route('/parent/logout')
def parent_logout():
    """Clears parent session and returns to parent login."""
    resp = redirect(url_for('parent_login'))
    resp.set_cookie('parent_lrn', '', expires=0)
    resp.set_cookie('parent_phone', '', expires=0)
    return resp

@app.route('/parent')
@app.route('/parent/<lrn>')
def parent_portal(lrn=None):
    """
    Dedicated Standalone Parent Mobile App.
    """
    target_lrn = lrn or request.args.get('lrn') or request.cookies.get('parent_lrn')
    parent_phone = request.args.get('phone') or request.cookies.get('parent_phone')

    from smile_orm import Session, Student, AttendanceLog, get_student_excuse_notes_orm, get_students_by_parent_phone_orm, get_all_announcements_orm
    orm_session = Session()
    try:
        if not target_lrn and parent_phone:
            children = get_students_by_parent_phone_orm(parent_phone)
            if children:
                target_lrn = children[0]["lrn"]

        if not target_lrn:
            first_student = orm_session.query(Student).first()
            if not first_student:
                return redirect(url_for('parent_login'))
            target_lrn = first_student.lrn

        student = orm_session.query(Student).filter_by(lrn=str(target_lrn)).first()
        if not student:
            return redirect(url_for('parent_login'))

        # Fetch sibling students linked to the same parent phone
        linked_students = []
        if student.parent_phone:
            linked_students = [s.to_dict() for s in orm_session.query(Student).filter_by(parent_phone=student.parent_phone).all()]
        if not linked_students:
            linked_students = [student.to_dict()]

        # Today's gate logs
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_logs = [l.to_dict() for l in orm_session.query(AttendanceLog).filter(
            AttendanceLog.lrn == str(target_lrn),
            AttendanceLog.timestamp >= today_start
        ).order_by(AttendanceLog.id.desc()).all()]

        # Historical logs (last 20 scans)
        all_logs = [l.to_dict() for l in orm_session.query(AttendanceLog).filter(
            AttendanceLog.lrn == str(target_lrn)
        ).order_by(AttendanceLog.id.desc()).limit(20).all()]

        latest_log = today_logs[0] if today_logs else (all_logs[0] if all_logs else None)

        # Excuse notes
        excuse_notes = get_student_excuse_notes_orm(target_lrn)

        # Real Database Announcements
        announcements = get_all_announcements_orm()

        resp = Response(render_template(
            'parent/app.html',
            school_name=SCHOOL_NAME,
            active_student=student.to_dict(),
            students=linked_students,
            logs=today_logs,
            latest_log=latest_log,
            all_logs=all_logs,
            excuse_notes=excuse_notes,
            announcements=announcements,
            today_date=datetime.now().strftime("%A, %B %d, %Y"),
            today_iso=date.today().isoformat()
        ))
        resp.set_cookie('parent_lrn', target_lrn, max_age=86400 * 30)
        resp.set_cookie('parent_phone', student.parent_phone, max_age=86400 * 30)
        return resp
    finally:
        orm_session.close()


@app.route('/database')
@admin_required
def database_explorer():
    """Enterprise Database Management and SQL Explorer (Super Admin Only)."""
    from smile_orm import Session, Section, Student, AttendanceLog, SmsLog, get_database_stats_orm
    orm_session = Session()
    try:
        db_stats = get_database_stats_orm()
        students = [s.to_dict() for s in orm_session.query(Student).all()]
        sections = [sec.to_dict() for sec in orm_session.query(Section).order_by(Section.id.asc()).all()]
        attendance_logs = [a.to_dict() for a in orm_session.query(AttendanceLog).order_by(AttendanceLog.id.desc()).limit(100).all()]
        return render_template(
            'database_admin.html',
            school_name=SCHOOL_NAME,
            db_stats=db_stats,
            students=students,
            sections=sections,
            attendance_logs=attendance_logs
        )
    finally:
        orm_session.close()

@app.route('/api/db-backup')
@admin_required
def api_db_backup():
    """Generates JSON dump of entire relational database for backup (Super Admin Only)."""
    from smile_orm import Session, Section, Student, AttendanceLog, SmsLog
    import json
    orm_session = Session()
    try:
        data = {
            "school_name": SCHOOL_NAME,
            "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sections": [sec.to_dict() for sec in orm_session.query(Section).all()],
            "students": [s.to_dict() for s in orm_session.query(Student).all()],
            "attendance_logs": [a.to_dict() for a in orm_session.query(AttendanceLog).all()],
            "sms_logs": [s.to_dict() for s in orm_session.query(SmsLog).all()]
        }
        json_str = json.dumps(data, indent=2)
        return Response(
            json_str,
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment;filename=DepEd_Smile_Database_Backup_{date.today()}.json"}
        )
    finally:
        orm_session.close()

@app.route('/api/db-seed', methods=['POST'])
@admin_required
def api_db_seed():
    """Triggers DepEd population re-seeder (Super Admin Only)."""
    from seed_deped_database import seed_database
    try:
        seed_database()
        streamer.reload_enrolled_students()
        return jsonify({"success": True, "message": "Database successfully populated with DepEd students and sections!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/sections', methods=['GET'])
def api_get_sections():
    """Returns real sections from database with optional grade_level filter."""
    grade = request.args.get('grade_level', '').strip()
    from smile_orm import get_all_sections_orm, get_sections_by_grade_orm
    try:
        if grade:
            secs = get_sections_by_grade_orm(grade)
        else:
            secs = get_all_sections_orm()
        return jsonify({"success": True, "sections": secs, "total": len(secs)})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/sections', methods=['POST'])
def api_create_section():
    """Creates or updates a class section in the real database."""
    data = request.json or request.form or {}
    grade_level = data.get('grade_level', '').strip()
    section_name = data.get('section_name', '').strip()
    adviser_teacher = data.get('adviser_teacher', '').strip()
    room_number = data.get('room_number', '').strip()

    if not grade_level or not section_name:
        return jsonify({"success": False, "message": "Grade Level and Section Name are required."}), 400

    from smile_orm import save_section_orm
    try:
        sec = save_section_orm(grade_level, section_name, adviser_teacher, room_number)
        return jsonify({
            "success": True, 
            "section": sec, 
            "message": f"Section {grade_level} - {section_name} saved successfully!"
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/sections/<int:section_id>', methods=['GET'])
def api_get_section(section_id):
    """Returns a single section by ID."""
    from smile_orm import get_section_by_id_orm
    try:
        sec = get_section_by_id_orm(section_id)
        if not sec:
            return jsonify({"success": False, "message": "Section not found"}), 404
        return jsonify({"success": True, "section": sec})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/sections/<int:section_id>', methods=['POST', 'PUT'])
def api_update_section(section_id):
    """Updates an existing class section in the database."""
    data = request.json or request.form or {}
    grade_level = data.get('grade_level')
    section_name = data.get('section_name')
    adviser_teacher = data.get('adviser_teacher')
    room_number = data.get('room_number')

    from smile_orm import update_section_orm
    try:
        sec, msg = update_section_orm(section_id, grade_level, section_name, adviser_teacher, room_number)
        if not sec:
            return jsonify({"success": False, "message": msg}), 404
        return jsonify({"success": True, "section": sec, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/sections/<int:section_id>/delete', methods=['POST', 'DELETE'])
@app.route('/api/sections/<int:section_id>', methods=['DELETE'])
def api_delete_section(section_id):
    """Deletes a class section from the real database."""
    from smile_orm import delete_section_orm
    try:
        success, msg = delete_section_orm(section_id)
        status_code = 200 if success else 404
        return jsonify({"success": success, "message": msg}), status_code
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500



# -------------------------------------------------------------
# Media & Streaming Endpoints
# -------------------------------------------------------------

def gen_frames():
    """Generator function yielding MJPEG frames for the web kiosk."""
    while True:
        frame_bytes = streamer.get_frame()
        if frame_bytes:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            # Yield empty frame sleep
            import time
            time.sleep(0.05)

@app.route('/video_feed')
def video_feed():
    """Route providing live video feed for <img> elements."""
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/camera-snapshot')
def api_camera_snapshot():
    """Returns the current raw JPEG frame from the GateStreamer camera engine."""
    frame_bytes = streamer.get_frame()
    if frame_bytes:
        return Response(frame_bytes, mimetype='image/jpeg')
    return jsonify({"error": "No camera frame available"}), 503

@app.route('/api/detect-face-preview', methods=['POST'])
def api_detect_face_preview():
    """Instant biometric pre-check to verify if a face is detectable before submitting registration."""
    try:
        img = decode_image_payload(request)
        if img is None:
            return jsonify({"success": False, "message": "No image payload received."}), 400

        faces = face_engine.detect_faces(img)
        if len(faces) == 0:
            return jsonify({"success": False, "faces": 0, "message": "No face detected. Please center your face inside the guide and ensure good lighting."})

        best_face = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = int(best_face[0]), int(best_face[1]), int(best_face[2]), int(best_face[3])
        return jsonify({
            "success": True,
            "faces": len(faces),
            "bbox": {"x": x, "y": y, "w": w, "h": h},
            "message": f"Biometric Face Detected ({len(faces)} face{'s' if len(faces)>1 else ''} found) - Ready to Enroll!"
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/photos/<filename>')
def serve_photo(filename):
    """Serves enrolled student photos."""
    return send_from_directory(PHOTOS_DIR, filename)

# -------------------------------------------------------------
# REST API Endpoints
# -------------------------------------------------------------

@app.route('/api/latest-event')
def api_latest_event():
    """Returns the latest student scan event for Kiosk animated badge popup."""
    event = streamer.get_latest_event()
    return jsonify(event if event else {})

@app.route('/api/gate-mode', methods=['GET', 'POST'])
def api_gate_mode():
    """Gets or sets the current Gate Direction Mode (AUTO, ENTRY, EXIT)."""
    if request.method == 'POST':
        data = request.json or {}
        new_mode = data.get('mode', 'AUTO')
        ok = streamer.set_gate_mode(new_mode)
        return jsonify({"success": ok, "mode": streamer.get_gate_mode()})
    return jsonify({"success": True, "mode": streamer.get_gate_mode()})

@app.route('/api/stats')
def api_stats():
    """Returns real-time statistics for header/kiosk widgets."""
    summary = get_today_summary()
    enrolled = get_all_enrolled_students()
    return jsonify({
        "total_enrolled": len(enrolled),
        "total_scans": summary["total_scans"],
        "unique_students": summary["unique_students"]
    })

@app.route('/api/recent-scans')
def api_recent_scans():
    """Returns today's recent attendance logs for live auto-updating tables."""
    logs = get_today_attendance_logs_orm(limit=20)
    return jsonify(logs)

@app.route('/id-card/<lrn>')
def view_id_card(lrn):
    """Renders printable DepEd Smart ID Card."""
    from smile_orm import Student, Session
    session = Session()
    try:
        student = session.query(Student).filter_by(lrn=str(lrn)).first()
        if not student:
            return "Student not found", 404
        return render_template('id_card.html', student=student.to_dict(), school_name=SCHOOL_NAME)
    finally:
        session.close()

@app.route('/api/parent/poll/<lrn>')
def api_parent_poll(lrn):
    """
    Real-Time Background Poller for Parent Mobile App.
    Checks if a new gate attendance transaction has been recorded for this learner since last_id.
    """
    from smile_orm import AttendanceLog, Session
    last_id = request.args.get('last_id', 0, type=int)
    session = Session()
    try:
        new_log = session.query(AttendanceLog).filter(
            AttendanceLog.lrn == str(lrn),
            AttendanceLog.id > last_id
        ).order_by(AttendanceLog.id.desc()).first()

        if new_log:
            return jsonify({"has_new": True, "event": new_log.to_dict()})
        return jsonify({"has_new": False})
    finally:
        session.close()

@app.route('/api/parent/status/<lrn>')
def api_parent_status(lrn):
    """Returns child's current campus status and today's attendance summary."""
    from smile_orm import Student, AttendanceLog, Session
    session = Session()
    try:
        student = session.query(Student).filter_by(lrn=str(lrn)).first()
        if not student:
            return jsonify({"success": False, "message": "Student not found"}), 404

        latest_log = session.query(AttendanceLog).filter(
            AttendanceLog.lrn == str(lrn)
        ).order_by(AttendanceLog.id.desc()).first()

        status = "AWAITING"
        if latest_log:
            status = "INSIDE" if latest_log.scan_type == "TIME_IN" else "EXITED"

        return jsonify({
            "success": True,
            "student": student.to_dict(),
            "campus_status": status,
            "latest_event": latest_log.to_dict() if latest_log else None
        })
    finally:
        session.close()

@app.route('/api/parent/excuse-note', methods=['POST'])
def api_submit_excuse_note():
    """Saves a parent excuse letter to the database."""
    data = request.json or {}
    lrn = data.get('lrn', '').strip()
    parent_name = data.get('parent_name', '').strip()
    parent_phone = data.get('parent_phone', '').strip()
    date_eff = data.get('date_effective', '').strip()
    reason = data.get('reason', '').strip()
    details = data.get('details', '').strip()

    if not lrn or not reason or not details:
        return jsonify({"success": False, "message": "All fields (LRN, reason, details) are required."}), 400

    from smile_orm import save_excuse_note_orm
    try:
        note = save_excuse_note_orm(lrn, parent_name, parent_phone, date_eff, reason, details)
        return jsonify({"success": True, "note": note})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/parent/qr-code')
def api_parent_qr_code():
    """Generates a QR code pointing to official public domain or local IP for physical phone scanning."""
    import qrcode
    from io import BytesIO
    import socket
    
    system_domain = getattr(smile_config, "SYSTEM_DOMAIN", "").strip()
    if system_domain:
        target_url = f"{system_domain.rstrip('/')}/parent"
    else:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "localhost"
        target_url = f"http://{local_ip}:5000/parent"

    img = qrcode.make(target_url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/png")

@app.route('/api/parent/test-notification', methods=['POST'])
def api_parent_test_notification():
    """Generates a test push & alert payload for the active learner."""
    data = request.json or {}
    lrn = data.get('lrn', '').strip()
    from smile_orm import Student, Session
    session = Session()
    try:
        student = session.query(Student).filter_by(lrn=str(lrn)).first() if lrn else session.query(Student).first()
        student_name = student.full_name if student else "Learner"
        student_lrn = student.lrn if student else "152008250007"
        now_time = datetime.now().strftime("%I:%M %p")
        return jsonify({
            "success": True,
            "title": f"Project S.M.I.L.E. Gate Alert: {student_name}",
            "body": f"Official Gate Scan Verified: {student_name} arrived at Don Montano CIS Gate 1 at {now_time}.",
            "icon": "/static/images/pwa_icon_192.png",
            "badge": "/static/images/apple_touch_icon.png",
            "tag": f"scan-{student_lrn}",
            "data": {
                "url": f"/parent?lrn={student_lrn}",
                "lrn": student_lrn,
                "scan_type": "TIME_IN",
                "time_formatted": now_time,
                "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
                "verification_method": "AI Face Scan"
            }
        })
    finally:
        session.close()

@app.route('/api/announcements', methods=['GET', 'POST'])
def api_announcements():
    """Returns all bulletins or saves a new DepEd advisory."""
    from smile_orm import get_all_announcements_orm, save_announcement_orm
    if request.method == 'GET':
        category = request.args.get('category')
        limit = request.args.get('limit', 30, type=int)
        items = get_all_announcements_orm(limit=limit, category=category)
        return jsonify({"success": True, "announcements": items})

    data = request.json or {}
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    category = data.get('category', 'ANNOUNCEMENT').strip()
    author = data.get('author', 'School Administration').strip()
    badge_color = data.get('badge_color', 'blue').strip()
    is_urgent = bool(data.get('is_urgent', False))
    target_grade = data.get('target_grade', 'ALL').strip()

    if not title or not content:
        return jsonify({"success": False, "message": "Title and content are required."}), 400

    try:
        new_ann = save_announcement_orm(
            title=title,
            category=category,
            content=content,
            author=author,
            badge_color=badge_color,
            is_urgent=is_urgent,
            target_grade=target_grade
        )
        return jsonify({"success": True, "announcement": new_ann})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/announcements/<int:announcement_id>', methods=['DELETE'])
def api_delete_announcement(announcement_id):
    """Deletes an announcement by ID."""
    from smile_orm import delete_announcement_orm
    success, msg = delete_announcement_orm(announcement_id)
    status_code = 200 if success else 404
    return jsonify({"success": success, "message": msg}), status_code

@app.route('/api/scan-id', methods=['POST'])
def api_scan_id():
    """Processes an RFID card tap or barcode/QR code scan event."""
    data = request.json or {}
    identifier = data.get('identifier', '').strip()
    if not identifier:
        return jsonify({"success": False, "message": "Card UID or LRN is required."}), 400

    success, msg = streamer.trigger_scan_by_id(identifier, method="RFID_TAP")
    latest_ev = streamer.get_latest_event() or {}
    return jsonify({
        "success": success,
        "message": msg,
        "scan_type": latest_ev.get("scan_type"),
        "period": latest_ev.get("period"),
        "voice_text": latest_ev.get("voice_text")
    })

@app.route('/api/enroll', methods=['POST'])
def api_enroll_student():
    """
    Registers a student with demographic data, auto-generates QR Code Smart ID,
    and extracts 128-d AI Face Biometric Embeddings if photo is provided.
    """
    try:
        lrn = request.form.get('lrn', '').strip()
        first_name = request.form.get('first_name', '').strip()
        middle_name = request.form.get('middle_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        grade_level = request.form.get('grade_level', '').strip()
        section_name = request.form.get('section_name', '').strip()
        class_adviser = request.form.get('class_adviser', '').strip()
        grade_section = request.form.get('grade_section', '').strip()
        parent_name = request.form.get('parent_name', '').strip()
        parent_phone = request.form.get('parent_phone', '').strip()
        rfid_card_uid = request.form.get('rfid_card_uid', '').strip()
        gender = request.form.get('gender', 'Unspecified').strip()
        track_strand = request.form.get('track_strand', 'Junior High').strip()

        if not lrn or not first_name or not last_name or not parent_phone:
            return jsonify({"success": False, "message": "Please fill in all required fields (LRN, Name, Phone)."}), 400

        # Process Photo & Extract Face Embeddings
        img = decode_image_payload(request)
        photo_rel_path = ""
        embedding_vector = None

        if img is not None:
            faces = face_engine.detect_faces(img)
            if len(faces) == 0:
                return jsonify({
                    "success": False,
                    "message": "No face detected in the photo. Please align your face clearly with the camera."
                }), 400
            
            # Select largest face
            best_face = max(faces, key=lambda f: f[2] * f[3])
            embedding_vector = face_engine.extract_face_embedding(img, best_face)
            
            # Save portrait photo
            filename = f"{lrn}_{last_name.lower().replace(' ', '_')}.jpg"
            save_path = PHOTOS_DIR / filename
            cv2.imwrite(str(save_path), img)
            photo_rel_path = f"/photos/{filename}"

        from smile_orm import save_student_orm
        student = save_student_orm(
            lrn=lrn,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            grade_level=grade_level,
            section_name=section_name,
            class_adviser=class_adviser,
            grade_section=grade_section,
            parent_name=parent_name,
            parent_phone=parent_phone,
            rfid_card_uid=rfid_card_uid,
            gender=gender,
            track=track_strand,
            photo_path=photo_rel_path,
            embedding_array=embedding_vector
        )

        streamer.reload_enrolled_students()

        full_display_name = student.get("full_name", f"{first_name} {last_name}")
        face_msg = "with Face Recognition Active" if embedding_vector is not None else "with Smart ID"
        return jsonify({
            "success": True,
            "message": f"Student {full_display_name} (LRN: {lrn}) enrolled successfully {face_msg}!",
            "lrn": lrn,
            "has_face": embedding_vector is not None,
            "qr_url": student.get("qr_code_path"),
            "photo_url": photo_rel_path
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Server Error: {str(e)}"}), 500

@app.route('/api/verify-face', methods=['POST'])
def api_verify_face():
    """
    Real-Time Face Recognition Validation Endpoint.
    Accepts webcam snapshot or uploaded photo, detects face with YuNet,
    extracts 128-d biometric embedding with SFace, matches against enrolled students,
    and logs gate attendance with parent SMS alert.
    """
    try:
        img = decode_image_payload(request)
        if img is None:
            return jsonify({"success": False, "message": "No image payload received."}), 400

        faces = face_engine.detect_faces(img)
        if len(faces) == 0:
            return jsonify({"success": False, "message": "No face detected in camera view. Please position your face directly in front of the lens."}), 400

        best_face = max(faces, key=lambda f: f[2] * f[3])
        query_emb = face_engine.extract_face_embedding(img, best_face)

        match, score = face_engine.match_against_enrolled(query_emb, streamer.enrolled_students)

        if match:
            success, msg = streamer.trigger_scan_by_student(match, method="FACE_RECOGNITION", score=score)
            clean_student = {k: v for k, v in match.items() if k != "embedding"}
            latest_ev = streamer.get_latest_event() or {}
            return jsonify({
                "success": success,
                "matched": True,
                "student": clean_student,
                "score": f"{score * 100:.1f}%",
                "message": f"Face Verified: {match['full_name']} ({score * 100:.1f}% Match)",
                "gate_message": msg,
                "scan_type": latest_ev.get("scan_type"),
                "period": latest_ev.get("period"),
                "voice_text": latest_ev.get("voice_text")
            })
        else:
            pct = f"{score * 100:.1f}%" if score > 0 else "0.0%"
            return jsonify({
                "success": False,
                "matched": False,
                "score": pct,
                "message": f"Face not recognized (Similarity: {pct} - minimum threshold: 36.3%)."
            })

    except Exception as e:
        return jsonify({"success": False, "message": f"Verification error: {str(e)}"}), 500

@app.route('/api/delete-student/<lrn>', methods=['POST', 'DELETE'])
def api_delete_student(lrn):
    """Removes a student profile and cleans up photo/QR files."""
    try:
        from smile_orm import delete_student_orm
        success, msg = delete_student_orm(lrn)
        streamer.reload_enrolled_students()
        if success:
            return jsonify({"success": True, "message": msg})
        return jsonify({"success": False, "message": msg}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/sms-settings', methods=['GET', 'POST'])
def api_sms_settings():
    """Gets or updates persistent SMS settings (Super Admin Only for modifications)."""
    if request.method == 'GET':
        cfg = smile_config.get_sms_config()
        safe_cfg = dict(cfg)
        if safe_cfg.get("semaphore_api_key"):
            k = safe_cfg["semaphore_api_key"]
            safe_cfg["semaphore_api_key_masked"] = (k[:4] + "••••" + k[-4:]) if len(k) > 8 else "••••••••"
        if safe_cfg.get("twilio_auth_token"):
            safe_cfg["twilio_auth_token_masked"] = "••••••••••••"
        if safe_cfg.get("philsms_api_key"):
            pk = safe_cfg["philsms_api_key"]
            safe_cfg["philsms_api_key_masked"] = (pk[:4] + "••••" + pk[-4:]) if len(pk) > 8 else "••••••••"
        return jsonify({"success": True, "settings": safe_cfg})

    if session.get('role') != 'SUPER_ADMIN':
        return jsonify({"success": False, "message": "Unauthorized. Only Super Admin can modify SMS Gateway settings."}), 403

    data = request.json or {}
    new_settings = {}
    if "mode" in data:
        new_settings["mode"] = data["mode"].upper().strip()
    if "semaphore_api_key" in data and not data["semaphore_api_key"].startswith("•"):
        new_settings["semaphore_api_key"] = data["semaphore_api_key"].strip()
    if "semaphore_sender_name" in data:
        new_settings["semaphore_sender_name"] = data["semaphore_sender_name"].strip()
    if "twilio_account_sid" in data:
        new_settings["twilio_account_sid"] = data["twilio_account_sid"].strip()
    if "twilio_auth_token" in data and not data["twilio_auth_token"].startswith("•"):
        new_settings["twilio_auth_token"] = data["twilio_auth_token"].strip()
    if "twilio_from_number" in data:
        new_settings["twilio_from_number"] = data["twilio_from_number"].strip()
    if "android_gateway_url" in data:
        new_settings["android_gateway_url"] = data["android_gateway_url"].strip()
    if "android_gateway_key" in data:
        new_settings["android_gateway_key"] = data["android_gateway_key"].strip()
    if "philsms_api_key" in data and not data["philsms_api_key"].startswith("•"):
        new_settings["philsms_api_key"] = data["philsms_api_key"].strip()
    if "philsms_sender_id" in data:
        new_settings["philsms_sender_id"] = data["philsms_sender_id"].strip()
    if "gsm_port" in data:
        new_settings["gsm_port"] = data["gsm_port"].strip()
    if "gsm_baudrate" in data:
        try:
            new_settings["gsm_baudrate"] = int(data["gsm_baudrate"])
        except ValueError:
            pass

    updated = smile_config.save_sms_settings(new_settings)
    status_info = check_gateway_status()
    return jsonify({
        "success": True,
        "message": f"SMS Gateway configured to {updated.get('mode', 'MOCK')}!",
        "settings": updated,
        "gateway_status": status_info
    })

@app.route('/api/test-sms-connection', methods=['POST'])
def api_test_sms_connection():
    """Pings the active provider to verify credentials and check SMS credit balance."""
    info = check_gateway_status()
    return jsonify(info)

@app.route('/api/test-sms', methods=['POST'])
def api_test_sms():
    """Sends a real or simulated test SMS via the configured gateway."""
    data = request.json or {}
    phone = data.get('phone', '').strip()
    custom_msg = data.get('message', '').strip()

    if not phone:
        return jsonify({"success": False, "message": "Recipient phone number is required."}), 400

    test_msg = custom_msg or f"DepEd Project S.M.I.L.E. Gateway Test: System is active and operational at {SCHOOL_NAME} on {datetime.now().strftime('%I:%M %p, %b %d, %Y')}."
    
    result = dispatch_sms_sync(phone, test_msg, student_lrn="GATEWAY_TEST")
    return jsonify(result)

@app.route('/api/clear-sms-logs', methods=['POST'])
@admin_required
def api_clear_sms_logs():
    """Wipes all outbound SMS delivery logs from the database (Super Admin Only)."""
    try:
        from smile_orm import get_db_session, SmsLog
        with get_db_session() as session:
            count = session.query(SmsLog).count()
            session.query(SmsLog).delete()
        return jsonify({"success": True, "message": f"Successfully deleted {count} SMS log records."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/simulate-scan', methods=['POST'])
def api_simulate_scan():
    """Simulates a student scanning their Face or Smart ID card at the gate kiosk."""
    enrolled = streamer.enrolled_students
    if not enrolled:
        return jsonify({"success": False, "message": "No students enrolled yet. Please enroll a student first."}), 400

    import random
    student = random.choice(enrolled)
    method = "FACE_RECOGNITION" if student.get("embedding") is not None else "RFID_TAP"
    success, msg = streamer.trigger_scan_by_student(
        student,
        method=method,
        score=0.942 if method == "FACE_RECOGNITION" else None
    )
    return jsonify({
        "success": success,
        "message": msg,
        "student": student["full_name"],
        "lrn": student["lrn"],
        "method": method
    })

@app.route('/export/csv')
def export_attendance_csv():
    """Generates DepEd SF2 (School Form 2) compliant Daily Attendance CSV."""
    today_str = date.today().strftime("%Y-%m-%d")
    rows = get_all_attendance_logs_for_export_orm()

    output = io.StringIO()
    writer = csv.writer(output)
    
    # DepEd Standard Header
    writer.writerow(["DEPED SCHOOL ATTENDANCE REPORT (PROJECT S.M.I.L.E.)"])
    writer.writerow(["School Name:", SCHOOL_NAME])
    writer.writerow(["Generated Date:", datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")])
    writer.writerow([])
    writer.writerow(["Timestamp", "DepEd LRN", "Student Full Name", "Grade & Section", "Class Adviser", "Entry / Exit Type", "Parent Phone", "SMS Alert Status"])

    for r in rows:
        writer.writerow([r["timestamp"], r["lrn"], r["student_name"], r["grade_section"], r["class_adviser"], r["scan_type"], r["parent_phone"], r["sms_status"]])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=DepEd_Smile_Attendance_{today_str}.csv"}
    )

if __name__ == '__main__':
    print("\n" + "="*65)
    print("   PROJECT S.M.I.L.E. - DEPED WEB APPLICATION SUITE")
    print(f"   School: {SCHOOL_NAME}")
    print("   Web Portal URL: http://localhost:5000")
    print("   Gate Kiosk URL: http://localhost:5000/kiosk")
    print("="*65 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
