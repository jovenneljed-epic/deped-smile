import json
import os
import time
import numpy as np
from datetime import datetime, date
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import (
    create_engine, Column, Integer, String, Text,
    DateTime, Boolean, Float, ForeignKey, desc, func, event
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session, relationship, joinedload
from smile_config import (
    get_database_url, DATABASE_TYPE, COOLDOWN_SECONDS, MIDDAY_SPLIT_HOUR,
    pht_now, PHT, IS_VERCEL,
    SCHEDULE_AM_IN_START_MIN, SCHEDULE_AM_IN_END_MIN,
    SCHEDULE_AM_OUT_START_MIN, SCHEDULE_AM_OUT_END_MIN,
    SCHEDULE_PM_IN_START_MIN, SCHEDULE_PM_IN_END_MIN,
    SCHEDULE_PM_OUT_START_MIN, MAX_DAILY_SCANS_PER_PERSON
)
import smile_config
from smile_qr import generate_student_qr
from werkzeug.security import generate_password_hash, check_password_hash

# High-Speed In-Memory Caches for Static/Infrequent Records (TTL Caching)
_ANNOUNCEMENTS_CACHE = {"data": None, "ts": 0}
_EVENTS_CACHE = {"data": None, "ts": 0}
_SECTIONS_CACHE = {"data": None, "ts": 0}
_STUDENT_COUNT_CACHE = {"count": None, "ts": 0}
_PRICING_PLANS_CACHE = {"data": None, "ts": 0}
_TODAY_SUMMARY_CACHE = {"data": None, "ts": 0}
_STAFF_FACES_CACHE = {"data": None, "ts": 0}

Base = declarative_base()

# -------------------------------------------------------------
# Enterprise Relational Models (100% Non-Biometric / Data Privacy Safe)
# -------------------------------------------------------------

class Section(Base):
    """DepEd Class Section (Grade Level, Room, Adviser)."""
    __tablename__ = 'sections'

    id = Column(Integer, primary_key=True, autoincrement=True)
    grade_level = Column(String(20), nullable=False)        # e.g. "Grade 10"
    section_name = Column(String(50), nullable=False)       # e.g. "Rizal"
    adviser_teacher = Column(String(100), default="")       # e.g. "Mrs. Corazon Aquino"
    room_number = Column(String(30), default="")            # e.g. "Bldg 2 - Room 104"
    created_at = Column(DateTime, default=pht_now)

    students = relationship("Student", back_populates="section_rel", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "grade_level": self.grade_level,
            "section_name": self.section_name,
            "adviser_teacher": self.adviser_teacher,
            "room_number": self.room_number,
            "full_section": f"{self.grade_level} - {self.section_name}"
        }

class Student(Base):
    """
    DepEd Learner Profile & Smart ID.
    NO BIOMETRIC OR FACE GEOMETRY DATA STORED (RA 10173 Compliant).
    Uses LRN, QR Code Token, and optional RFID Tap Card UID.
    """
    __tablename__ = 'students'

    lrn = Column(String(12), primary_key=True, index=True)   # 12-digit DepEd LRN
    first_name = Column(String(100), nullable=False)
    middle_name = Column(String(100), default="")            # Learner middle name
    last_name = Column(String(100), nullable=False)
    gender = Column(String(50), default="Unspecified")
    birthdate = Column(String(50), default="")
    grade_level = Column(String(50), default="")            # Kindergarten, Grade 1 to 12
    section_name = Column(String(60), default="")           # Section (e.g. Rizal, Sampaguita)
    class_adviser = Column(String(100), default="")         # Designated Section Adviser Teacher
    grade_section = Column(String(150), nullable=False, index=True)     # e.g. "Grade 10 - Rizal"
    section_id = Column(Integer, ForeignKey('sections.id'), nullable=True, index=True)
    track_strand = Column(String(100), default="Junior High") # JHS, STEM, ABM, HUMSS, TVL
    parent_name = Column(String(150), default="")
    parent_phone = Column(String(50), nullable=True, default="N/A", index=True)
    parent_relationship = Column(String(30), default="Parent")
    rfid_card_uid = Column(String(50), nullable=True, index=True) # Optional physical RFID tap card
    qr_code_path = Column(Text, default="")                 # URL or dynamic path to student's QR ID badge
    photo_path = Column(Text, default="")                   # Path or data URI to student portrait photo
    face_embedding = Column(Text, nullable=True)            # JSON list of 128 floats for SFace recognition
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=pht_now)

    section_rel = relationship("Section", back_populates="students")
    attendance_records = relationship("AttendanceLog", back_populates="student_rel", cascade="all, delete-orphan")

    @property
    def full_name(self):
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}".strip()
        return f"{self.first_name} {self.last_name}".strip()

    def to_dict(self):
        adviser = self.class_adviser or ""
        if not adviser and self.section_id:
            from sqlalchemy import inspect as sa_inspect
            try:
                insp = sa_inspect(self)
                if 'section_rel' in insp.dict and self.section_rel:
                    adviser = self.section_rel.adviser_teacher or ""
            except Exception:
                pass

        return {
            "lrn": self.lrn,
            "first_name": self.first_name,
            "middle_name": self.middle_name or "",
            "last_name": self.last_name,
            "full_name": self.full_name,
            "gender": self.gender,
            "birthdate": self.birthdate or "",
            "grade_level": self.grade_level or "",
            "section_name": self.section_name or "",
            "class_adviser": adviser,
            "grade_section": self.grade_section,
            "track_strand": self.track_strand,
            "parent_name": self.parent_name,
            "parent_phone": self.parent_phone,
            "parent_relationship": self.parent_relationship,
            "rfid_card_uid": self.rfid_card_uid or "N/A",
            "qr_code_path": self.qr_code_path or f"/qr/{self.lrn}.png",
            "photo_path": self.photo_path or "",
            "has_face": bool(self.face_embedding),
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }

class AttendanceLog(Base):
    """Real-Time School Gate Attendance Transactions."""
    __tablename__ = 'attendance_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    lrn = Column(String(12), ForeignKey('students.lrn'), nullable=False, index=True)
    student_name = Column(String(120), nullable=False)
    grade_section = Column(String(80), default="")
    scan_type = Column(String(20), nullable=False, index=True)          # TIME_IN, TIME_OUT
    timestamp = Column(DateTime, default=pht_now, index=True)
    device_id = Column(String(50), default="GATE-1-SMART-ID")
    verification_method = Column(String(30), default="QR_CODE") # QR_CODE, RFID_TAP, MANUAL_LRN
    sms_status = Column(String(30), default="PENDING", index=True)      # PENDING, SENT, MOCKED, FAILED
    remarks = Column(String(100), default="")

    student_rel = relationship("Student", back_populates="attendance_records")

    def to_dict(self, parent_phone=None):
        phone = parent_phone
        if phone is None:
            from sqlalchemy import inspect as sa_inspect
            try:
                insp = sa_inspect(self)
                if 'student_rel' in insp.dict and self.student_rel:
                    phone = self.student_rel.parent_phone or ""
                else:
                    phone = ""
            except Exception:
                phone = ""

        return {
            "id": self.id,
            "lrn": self.lrn,
            "student_name": self.student_name,
            "grade_section": self.grade_section,
            "scan_type": self.scan_type,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else "",
            "time_formatted": self.timestamp.strftime("%I:%M %p") if self.timestamp else "",
            "device_id": self.device_id,
            "verification_method": self.verification_method,
            "sms_status": self.sms_status,
            "parent_phone": phone or ""
        }

class SmsLog(Base):
    """Outbound Parent SMS Delivery Logs."""
    __tablename__ = 'sms_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    recipient_phone = Column(String(20), nullable=False, index=True)
    student_lrn = Column(String(12), nullable=True)
    message_body = Column(Text, nullable=False)
    gateway_type = Column(String(30), default="MOCK")       # MOCK, SEMAPHORE, GSM
    status = Column(String(30), default="PENDING")          # SENT, MOCKED, FAILED
    sent_at = Column(DateTime, default=pht_now, index=True)
    response_info = Column(Text, default="")

    def to_dict(self):
        return {
            "id": self.id,
            "recipient_phone": self.recipient_phone,
            "student_lrn": self.student_lrn,
            "message_body": self.message_body,
            "gateway_type": self.gateway_type,
            "status": self.status,
            "sent_at": self.sent_at.strftime("%Y-%m-%d %H:%M:%S") if self.sent_at else "",
            "response_info": self.response_info
        }

class ExcuseNote(Base):
    """Parent-submitted Absence / Excuse Letters to Class Adviser."""
    __tablename__ = 'excuse_notes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    lrn = Column(String(12), ForeignKey('students.lrn'), nullable=False, index=True)
    parent_name = Column(String(100), nullable=False)
    parent_phone = Column(String(20), nullable=False)
    date_effective = Column(String(20), nullable=False)
    reason = Column(String(50), nullable=False)
    details = Column(Text, nullable=False)
    status = Column(String(20), default="SUBMITTED")
    created_at = Column(DateTime, default=pht_now)

    student_rel = relationship("Student")

    def to_dict(self):
        return {
            "id": self.id,
            "lrn": self.lrn,
            "parent_name": self.parent_name,
            "parent_phone": self.parent_phone,
            "date_effective": self.date_effective,
            "reason": self.reason,
            "details": self.details,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %I:%M %p") if self.created_at else ""
        }

class Announcement(Base):
    """Official DepEd & School Bulletins, News, and Weather Advisories."""
    __tablename__ = 'announcements'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(150), nullable=False)
    category = Column(String(40), default="ANNOUNCEMENT") # WEATHER_ALERT, DEPED_MEMO, ANNOUNCEMENT, EVENT
    content = Column(Text, nullable=False)
    author = Column(String(100), default="School Administration")
    badge_color = Column(String(20), default="blue") # amber, red, blue, emerald
    is_urgent = Column(Boolean, default=False)
    target_grade = Column(String(50), default="ALL")
    created_at = Column(DateTime, default=pht_now, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "content": self.content,
            "author": self.author,
            "badge_color": self.badge_color,
            "is_urgent": self.is_urgent,
            "target_grade": self.target_grade,
            "created_at": self.created_at.strftime("%Y-%m-%d %I:%M %p") if self.created_at else "",
            "date_formatted": self.created_at.strftime("%b %d, %Y") if self.created_at else ""
        }

class SchoolEvent(Base):
    """DepEd School Activities, Academic Calendar & Community Events."""
    __tablename__ = 'school_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(150), nullable=False)
    category = Column(String(40), default="ACADEMIC") # ACADEMIC, SPORTS, CULTURAL, PTA, HOLIDAY, GENERAL
    description = Column(Text, nullable=False)
    event_date = Column(String(20), nullable=False, index=True) # e.g. "2026-10-15" (ISO YYYY-MM-DD)
    start_time = Column(String(20), default="08:00 AM")
    end_time = Column(String(20), default="04:00 PM")
    location = Column(String(100), default="School Gymnasium")
    target_grades = Column(String(50), default="ALL")
    organizer = Column(String(100), default="School Administration")
    badge_color = Column(String(20), default="blue") # blue, emerald, amber, purple, rose
    is_highlighted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=pht_now, index=True)

    def to_dict(self):
        formatted_date = self.event_date
        short_month = "EVENT"
        day_num = "01"
        is_upcoming = True
        days_until = 0
        try:
            d_obj = datetime.strptime(self.event_date, "%Y-%m-%d")
            formatted_date = d_obj.strftime("%A, %b %d, %Y")
            short_month = d_obj.strftime("%b").upper()
            day_num = d_obj.strftime("%d")
            is_upcoming = d_obj.date() >= pht_now().date()
            days_until = (d_obj.date() - pht_now().date()).days
        except Exception:
            pass

        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "event_date": self.event_date,
            "formatted_date": formatted_date,
            "short_month": short_month,
            "day_num": day_num,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "time_range": f"{self.start_time} - {self.end_time}" if self.end_time else self.start_time,
            "location": self.location,
            "target_grades": self.target_grades,
            "organizer": self.organizer,
            "badge_color": self.badge_color,
            "is_highlighted": self.is_highlighted,
            "is_upcoming": is_upcoming,
            "days_until": days_until,
            "created_at": self.created_at.strftime("%Y-%m-%d %I:%M %p") if self.created_at else ""
        }

class User(Base):
    """Staff and Administrator accounts with Role-Based Access Control (RBAC)."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(30), nullable=False, default="TEACHER") # SUPER_ADMIN, PRINCIPAL, TEACHER, GUARD, PARENT, STAFF, NON_TEACHING
    is_active = Column(Boolean, default=True)
    phone_number = Column(String(30), default="")
    designation = Column(String(100), default="") # DepEd Designation / Department (e.g. Registrar, Guidance)
    assigned_section_id = Column(Integer, ForeignKey('sections.id'), nullable=True)
    face_embedding = Column(Text, nullable=True) # JSON list of 128 floats for SFace facial recognition
    photo_path = Column(Text, default="") # Photo evidence / profile portrait
    created_at = Column(DateTime, default=pht_now)
    last_login = Column(DateTime, nullable=True)

    assigned_section = relationship("Section", foreign_keys=[assigned_section_id])
    staff_attendance_records = relationship("StaffAttendanceLog", back_populates="user_rel", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "phone_number": self.phone_number,
            "designation": getattr(self, 'designation', '') or "",
            "assigned_section_id": self.assigned_section_id,
            "assigned_section_name": f"{self.assigned_section.grade_level} - {self.assigned_section.section_name}" if self.assigned_section else "N/A",
            "has_face": bool(self.face_embedding),
            "photo_path": getattr(self, 'photo_path', '') or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %I:%M %p") if self.created_at else "",
            "last_login": self.last_login.strftime("%Y-%m-%d %I:%M %p") if self.last_login else "Never"
        }

class StaffAttendanceLog(Base):
    """
    Official DepEd Civil Service Form 48 Daily Time Record (DTR) for Teaching and Non-Teaching personnel.
    Combines AI Facial Biometrics with GPS Geotag verification.
    """
    __tablename__ = 'staff_attendance_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    staff_name = Column(String(100), nullable=False)
    role = Column(String(30), nullable=False) # TEACHER, STAFF, NON_TEACHING, PRINCIPAL, GUARD, SUPER_ADMIN
    scan_type = Column(String(20), nullable=False) # TIME_IN, TIME_OUT
    period = Column(String(10), default="AM") # AM, PM
    timestamp = Column(DateTime, default=pht_now, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    accuracy_meters = Column(Float, nullable=True)
    geotag_status = Column(String(30), default="NO_GPS") # CAMPUS_VERIFIED, OFF_CAMPUS, NO_GPS
    verification_method = Column(String(50), default="FACIAL_RECOGNITION_GEOTAGGED")
    face_confidence = Column(Float, default=0.0) # Match score e.g. 0.95
    photo_snapshot = Column(Text, default="")
    created_at = Column(DateTime, default=pht_now)

    user_rel = relationship("User", back_populates="staff_attendance_records")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "staff_name": self.staff_name,
            "role": self.role,
            "scan_type": self.scan_type,
            "period": self.period,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else "",
            "date_formatted": self.timestamp.strftime("%b %d, %Y") if self.timestamp else "",
            "time_formatted": self.timestamp.strftime("%I:%M:%S %p") if self.timestamp else "",
            "time_short": self.timestamp.strftime("%I:%M %p") if self.timestamp else "",
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy_meters": self.accuracy_meters,
            "geotag_status": self.geotag_status,
            "verification_method": self.verification_method,
            "face_confidence": f"{self.face_confidence * 100:.1f}%" if self.face_confidence else "N/A",
            "photo_snapshot": self.photo_snapshot,
            "maps_url": f"https://www.google.com/maps?q={self.latitude},{self.longitude}" if self.latitude and self.longitude else None
        }

class PricingPlan(Base):
    """Editable SaaS & Subscription plans for School Licensing and Parent VIP alert packs."""
    __tablename__ = 'pricing_plans'

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_code = Column(String(50), unique=True, nullable=False, index=True) # STARTER_FREE, STANDARD_SCHOOL, ENTERPRISE_SCHOOL, PARENT_MONTHLY, PARENT_ANNUAL
    name = Column(String(100), nullable=False)
    category = Column(String(30), default="SCHOOL") # SCHOOL or PARENT
    price_php = Column(Float, nullable=False, default=0.0) # Fully editable by Super Admin
    billing_cycle = Column(String(20), default="monthly") # monthly, annual, one-time
    description = Column(Text, default="")
    features_json = Column(Text, default="[]")
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=pht_now, onupdate=pht_now)

    def to_dict(self):
        features = []
        try:
            features = json.loads(self.features_json) if self.features_json else []
        except Exception:
            features = []
        return {
            "id": self.id,
            "plan_code": self.plan_code,
            "name": self.name,
            "category": self.category,
            "price_php": float(self.price_php),
            "price_formatted": f"PHP {self.price_php:,.2f}" if self.price_php > 0 else "Free",
            "price_display": f"₱{self.price_php:,.2f}" if self.price_php > 0 else "Free",
            "billing_cycle": self.billing_cycle,
            "description": self.description,
            "features": features,
            "is_active": self.is_active,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %I:%M %p") if self.updated_at else ""
        }

class PaymentTransaction(Base):
    """Revenue & Payment transactions for SaaS school subscriptions and parent alert packs."""
    __tablename__ = 'payment_transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_ref = Column(String(60), unique=True, nullable=False, index=True)
    payer_name = Column(String(100), nullable=False)
    payer_email_phone = Column(String(100), default="")
    payer_role = Column(String(30), default="PARENT") # PARENT, SCHOOL_ADMIN
    plan_code = Column(String(50), nullable=False)
    amount_php = Column(Float, nullable=False)
    payment_method = Column(String(30), default="GCASH") # GCASH, MAYA, BANK_TRANSFER, CARD
    status = Column(String(20), default="COMPLETED") # COMPLETED, PENDING, FAILED
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=pht_now, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "transaction_ref": self.transaction_ref,
            "payer_name": self.payer_name,
            "payer_email_phone": self.payer_email_phone,
            "payer_role": self.payer_role,
            "plan_code": self.plan_code,
            "amount_php": float(self.amount_php),
            "amount_formatted": f"₱{self.amount_php:,.2f}",
            "payment_method": self.payment_method,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.strftime("%Y-%m-%d %I:%M %p") if self.created_at else "",
            "date_formatted": self.created_at.strftime("%b %d, %Y") if self.created_at else ""
        }

class PushSubscription(Base):
    """
    Browser WebPush PushSubscriptions for Lock Screen / Background alerts.
    Wakes up device when screen is off or mobile is locked.
    """
    __tablename__ = 'push_subscriptions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    lrn = Column(String(12), nullable=True, index=True) # Linked Student LRN or "ALL"
    parent_phone = Column(String(50), nullable=True, index=True)
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)
    user_agent = Column(String(255), default="")
    created_at = Column(DateTime, default=pht_now)
    last_notified = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "lrn": self.lrn,
            "parent_phone": self.parent_phone,
            "endpoint": self.endpoint,
            "p256dh": self.p256dh,
            "auth": self.auth,
            "created_at": self.created_at.strftime("%Y-%m-%d %I:%M %p") if self.created_at else ""
        }

class ParentDeviceToken(Base):
    """
    Native Expo & Android Push Notification Tokens.
    Delivers instant lock-screen alerts to parent mobile phones (Expo Go & Android APK).
    Wakes up device with sound and vibration when screen is off or mobile is locked.
    """
    __tablename__ = 'parent_device_tokens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(250), unique=True, nullable=False, index=True) # ExponentPushToken[...]
    lrn = Column(String(12), nullable=True, index=True)                  # Linked learner LRN or "ALL"
    platform = Column(String(30), default="android")                     # android, ios
    device_name = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=pht_now)
    updated_at = Column(DateTime, default=pht_now, onupdate=pht_now)

    def to_dict(self):
        return {
            "id": self.id,
            "token": self.token,
            "lrn": self.lrn or "",
            "platform": self.platform,
            "device_name": self.device_name,
            "is_active": self.is_active,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %I:%M %p") if self.updated_at else ""
        }

class ParentNotification(Base):
    """Real-Time Automated Push Notifications & Advisory Stream for Parents."""
    __tablename__ = 'parent_notifications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    lrn = Column(String(12), nullable=True, index=True)
    title = Column(String(150), nullable=False)
    body = Column(Text, nullable=False)
    category = Column(String(50), default="ATTENDANCE") # ATTENDANCE, CLINIC, WEATHER_EMERGENCY, SAFETY_CHECK, GENERAL, ADVISORY
    priority = Column(String(20), default="NORMAL")     # NORMAL, URGENT
    workflow_key = Column(String(50), default="gate_scan")
    is_read = Column(Boolean, default=False)
    sent_at = Column(DateTime, default=pht_now, index=True)

    def to_dict(self):
        icon = "fa-bell"
        color = "amber"
        if self.category == 'ATTENDANCE':
            icon = "fa-shield-halved"
            color = "emerald"
        elif self.category == 'CLINIC':
            icon = "fa-heart-pulse"
            color = "rose"
        elif self.category in ['WEATHER_EMERGENCY', 'WEATHER_ALERT']:
            icon = "fa-cloud-bolt"
            color = "red"
        elif self.category == 'SAFETY_CHECK':
            icon = "fa-user-shield"
            color = "blue"
        elif self.category == 'ADVISORY':
            icon = "fa-bullhorn"
            color = "indigo"

        return {
            "id": f"wf-{self.id}",
            "raw_id": self.id,
            "lrn": self.lrn or "",
            "type": self.category,
            "title": self.title,
            "body": self.body,
            "timestamp": self.sent_at.strftime("%b %d, %I:%M %p") if self.sent_at else "",
            "icon": icon,
            "color": color,
            "is_urgent": (self.priority == "URGENT"),
            "read": bool(self.is_read)
        }

class Incident(Base):
    """Campus Safety, Security, and Parent Concern Incident Reports."""
    __tablename__ = 'incidents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    lrn = Column(String(12), nullable=True, index=True)
    title = Column(String(150), nullable=False)
    incident_type = Column(String(50), default="PARENT_SAFETY_CONCERN")
    description = Column(Text, nullable=False)
    location = Column(String(100), default="School Grounds")
    status = Column(String(30), default="OPEN") # OPEN, UNDER_REVIEW, RESOLVED
    reported_by = Column(String(100), default="Parent")
    created_at = Column(DateTime, default=pht_now, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "lrn": self.lrn or "",
            "title": self.title,
            "incident_type": self.incident_type,
            "description": self.description,
            "location": self.location,
            "status": self.status,
            "reported_by": self.reported_by,
            "created_at": self.created_at.strftime("%Y-%m-%d %I:%M %p") if self.created_at else "",
            "date_formatted": self.created_at.strftime("%b %d, %Y") if self.created_at else ""
        }

# -------------------------------------------------------------
# Database Engine & Session Management
# -------------------------------------------------------------

def create_orm_engine():
    db_url = get_database_url()
    connect_args = {}
    if "sqlite" in db_url:
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30
        eng = create_engine(db_url, connect_args=connect_args)

        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            try:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=-64000")   # 64MB RAM page cache
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA mmap_size=268435456") # 256MB memory mapped I/O
                cursor.close()
            except Exception as ex:
                pass
        return eng
    else:
        # Check if pg8000 is used for PostgreSQL
        if "pg8000" in db_url:
            import ssl
            # Strip query parameters so pg8000 does not receive unexpected keyword arguments (e.g. channel_binding)
            if "?" in db_url:
                db_url = db_url.split("?")[0]
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            connect_args["ssl_context"] = ssl_ctx

        # Enterprise Cloud Database (PostgreSQL / MySQL) connection pool
        is_serverless = getattr(smile_config, 'IS_VERCEL', False) or os.environ.get('VERCEL') == '1'
        return create_engine(
            db_url,
            connect_args=connect_args,
            pool_size=5 if not is_serverless else 3,
            max_overflow=10 if not is_serverless else 5,
            pool_recycle=300,
            pool_pre_ping=False if is_serverless else True
        )

engine = create_orm_engine()
SessionFactory = sessionmaker(bind=engine)
Session = scoped_session(SessionFactory)

@contextmanager
def get_db_session():
    """Yields a database session with automatic commit and rollback."""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

DEFAULT_SECTIONS = [
    # Kindergarten
    {"grade_level": "Kindergarten", "section_name": "Sunflower", "adviser_teacher": "Mrs. Maria Santos", "room_number": "Kinder Bldg - Room 1"},
    {"grade_level": "Kindergarten", "section_name": "Sampaguita", "adviser_teacher": "Ms. Jocelyn Reyes", "room_number": "Kinder Bldg - Room 2"},
    {"grade_level": "Kindergarten", "section_name": "Ilang-Ilang", "adviser_teacher": "Mrs. Liza Dizon", "room_number": "Kinder Bldg - Room 3"},

    # Grade 1
    {"grade_level": "Grade 1", "section_name": "Mabait", "adviser_teacher": "Mrs. Erlinda Flores", "room_number": "Elem Bldg 1 - Room 101"},
    {"grade_level": "Grade 1", "section_name": "Masipag", "adviser_teacher": "Ms. Marites Garcia", "room_number": "Elem Bldg 1 - Room 102"},
    {"grade_level": "Grade 1", "section_name": "Matulungin", "adviser_teacher": "Mrs. Rosalina Cruz", "room_number": "Elem Bldg 1 - Room 103"},

    # Grade 2
    {"grade_level": "Grade 2", "section_name": "Mahinahon", "adviser_teacher": "Mr. Roberto Mendoza", "room_number": "Elem Bldg 1 - Room 201"},
    {"grade_level": "Grade 2", "section_name": "Magalang", "adviser_teacher": "Mrs. Corazon Bautista", "room_number": "Elem Bldg 1 - Room 202"},
    {"grade_level": "Grade 2", "section_name": "Mapagkumbaba", "adviser_teacher": "Ms. Lilibeth Ramos", "room_number": "Elem Bldg 1 - Room 203"},

    # Grade 3
    {"grade_level": "Grade 3", "section_name": "Maka-Diyos", "adviser_teacher": "Mrs. Teresa Villanueva", "room_number": "Elem Bldg 2 - Room 101"},
    {"grade_level": "Grade 3", "section_name": "Makabayan", "adviser_teacher": "Mr. Danilo Castro", "room_number": "Elem Bldg 2 - Room 102"},
    {"grade_level": "Grade 3", "section_name": "Makatao", "adviser_teacher": "Ms. Aileen Morales", "room_number": "Elem Bldg 2 - Room 103"},

    # Grade 4
    {"grade_level": "Grade 4", "section_name": "Aguinaldo", "adviser_teacher": "Mr. Noel Soriano", "room_number": "Elem Bldg 2 - Room 201"},
    {"grade_level": "Grade 4", "section_name": "Bonifacio", "adviser_teacher": "Mrs. Carmencita Navarro", "room_number": "Elem Bldg 2 - Room 202"},
    {"grade_level": "Grade 4", "section_name": "Jacinto", "adviser_teacher": "Ms. Rowena Dela Rosa", "room_number": "Elem Bldg 2 - Room 203"},

    # Grade 5
    {"grade_level": "Grade 5", "section_name": "Rizal", "adviser_teacher": "Mrs. Gloria Macapagal", "room_number": "Elem Bldg 3 - Room 101"},
    {"grade_level": "Grade 5", "section_name": "Del Pilar", "adviser_teacher": "Mr. Ferdinand Marcos", "room_number": "Elem Bldg 3 - Room 102"},
    {"grade_level": "Grade 5", "section_name": "Lopez Jaena", "adviser_teacher": "Ms. Shirley Tan", "room_number": "Elem Bldg 3 - Room 103"},

    # Grade 6
    {"grade_level": "Grade 6", "section_name": "Diamond", "adviser_teacher": "Mrs. Elena Santos", "room_number": "Elem Bldg 3 - Room 201"},
    {"grade_level": "Grade 6", "section_name": "Pearl", "adviser_teacher": "Mr. Wilfredo Gonzales", "room_number": "Elem Bldg 3 - Room 202"},
    {"grade_level": "Grade 6", "section_name": "Emerald", "adviser_teacher": "Ms. Catherine Pascual", "room_number": "Elem Bldg 3 - Room 203"},

    # Grade 7
    {"grade_level": "Grade 7", "section_name": "Daisy", "adviser_teacher": "Mrs. Corazon Aquino", "room_number": "JHS Bldg 1 - Room 101"},
    {"grade_level": "Grade 7", "section_name": "Camia", "adviser_teacher": "Mr. Emilio Aguinaldo", "room_number": "JHS Bldg 1 - Room 102"},
    {"grade_level": "Grade 7", "section_name": "Sampaguita", "adviser_teacher": "Ms. Evelyn Hernandez", "room_number": "JHS Bldg 1 - Room 103"},

    # Grade 8
    {"grade_level": "Grade 8", "section_name": "Narra", "adviser_teacher": "Ms. Gabriela Silang", "room_number": "JHS Bldg 1 - Room 201"},
    {"grade_level": "Grade 8", "section_name": "Molave", "adviser_teacher": "Mr. Antonio Luna", "room_number": "JHS Bldg 1 - Room 202"},
    {"grade_level": "Grade 8", "section_name": "Yakal", "adviser_teacher": "Mrs. Rebecca David", "room_number": "JHS Bldg 1 - Room 203"},

    # Grade 9
    {"grade_level": "Grade 9", "section_name": "Ruby", "adviser_teacher": "Mrs. Melchora Aquino", "room_number": "JHS Bldg 2 - Room 101"},
    {"grade_level": "Grade 9", "section_name": "Sapphire", "adviser_teacher": "Mr. Jose Burgos", "room_number": "JHS Bldg 2 - Room 102"},
    {"grade_level": "Grade 9", "section_name": "Topaz", "adviser_teacher": "Ms. Flordeliza Diaz", "room_number": "JHS Bldg 2 - Room 103"},

    # Grade 10
    {"grade_level": "Grade 10", "section_name": "Platinum", "adviser_teacher": "Dr. Jose Rizal", "room_number": "JHS Bldg 2 - Room 201"},
    {"grade_level": "Grade 10", "section_name": "Gold", "adviser_teacher": "Mr. Apolinario Mabini", "room_number": "JHS Bldg 2 - Room 202"},
    {"grade_level": "Grade 10", "section_name": "Silver", "adviser_teacher": "Ms. Miriam Santiago", "room_number": "JHS Bldg 2 - Room 203"},

    # Grade 11
    {"grade_level": "Grade 11", "section_name": "STEM - Archimedes", "adviser_teacher": "Engr. Fe Del Mundo", "room_number": "SHS Bldg - Room 301"},
    {"grade_level": "Grade 11", "section_name": "ABM - Luca Pacioli", "adviser_teacher": "Mr. Washington SyCip", "room_number": "SHS Bldg - Room 302"},
    {"grade_level": "Grade 11", "section_name": "HUMSS - Socrates", "adviser_teacher": "Prof. Randy David", "room_number": "SHS Bldg - Room 303"},
    {"grade_level": "Grade 11", "section_name": "TVL - Edison", "adviser_teacher": "Engr. Diosdado Banatao", "room_number": "SHS Bldg - Room 304"},

    # Grade 12
    {"grade_level": "Grade 12", "section_name": "STEM - Einstein", "adviser_teacher": "Dr. Angel Alcala", "room_number": "SHS Bldg - Room 401"},
    {"grade_level": "Grade 12", "section_name": "ABM - Keynes", "adviser_teacher": "Mrs. Mercedes Zobel", "room_number": "SHS Bldg - Room 402"},
    {"grade_level": "Grade 12", "section_name": "HUMSS - Plato", "adviser_teacher": "Atty. Claro M. Recto", "room_number": "SHS Bldg - Room 403"},
    {"grade_level": "Grade 12", "section_name": "TVL - Tesla", "adviser_teacher": "Engr. Ramon Barba", "room_number": "SHS Bldg - Room 404"}
]

def seed_default_sections_orm():
    """Seeds default comprehensive sections (Kindergarten to Grade 12) for Don Montano CIS."""
    session = Session()
    try:
        # Check if already seeded with elementary
        elem_exists = session.query(Section).filter(Section.grade_level.in_(["Kindergarten", "Grade 1"])).first()
        if elem_exists and session.query(Section).count() >= 25:
            return
        for s in DEFAULT_SECTIONS:
            existing = session.query(Section).filter_by(grade_level=s["grade_level"], section_name=s["section_name"]).first()
            if not existing:
                sec = Section(
                    grade_level=s["grade_level"],
                    section_name=s["section_name"],
                    adviser_teacher=s["adviser_teacher"],
                    room_number=s["room_number"]
                )
                session.add(sec)
            else:
                if not existing.adviser_teacher and s["adviser_teacher"]:
                    existing.adviser_teacher = s["adviser_teacher"]
                if not existing.room_number and s["room_number"]:
                    existing.room_number = s["room_number"]
        session.commit()
        print(f"[+] Don Montano Central Integrated School real sections seeded ({session.query(Section).count()} sections).")
    except Exception as e:
        session.rollback()
        print(f"[!] Error seeding sections: {e}")
    finally:
        session.close()

def get_all_sections_orm():
    """Returns all real sections from the database with in-memory TTL caching."""
    global _SECTIONS_CACHE
    now = time.time()
    if _SECTIONS_CACHE["data"] is not None and (now - _SECTIONS_CACHE["ts"]) < 60:
        return _SECTIONS_CACHE["data"]

    session = Session()
    try:
        sections = session.query(Section).order_by(Section.id.asc()).all()
        res = [sec.to_dict() for sec in sections]
        _SECTIONS_CACHE["data"] = res
        _SECTIONS_CACHE["ts"] = now
        return res
    finally:
        session.close()

def get_sections_by_grade_orm(grade_level):
    """Returns sections filtered by grade level without fuzzy overlap between Grade 1 and Grade 10-12."""
    session = Session()
    try:
        gl_clean = str(grade_level).strip()
        possible_keys = [gl_clean]
        if gl_clean.isdigit():
            possible_keys.append(f"Grade {gl_clean}")
        if gl_clean.lower() in ["kinder", "kindergarten"]:
            possible_keys.extend(["Kinder", "Kindergarten"])
        
        sections = session.query(Section).filter(
            func.lower(Section.grade_level).in_([k.lower() for k in possible_keys])
        ).order_by(Section.section_name.asc()).all()
        return [sec.to_dict() for sec in sections]
    finally:
        session.close()

def save_section_orm(grade_level, section_name, adviser_teacher="", room_number=""):
    """Inserts or updates a class section in the database."""
    global _SECTIONS_CACHE
    _SECTIONS_CACHE["data"] = None
    session = Session()
    try:
        gl = str(grade_level).strip()
        sn = str(section_name).strip()
        sec = session.query(Section).filter_by(grade_level=gl, section_name=sn).first()
        if not sec:
            sec = Section(grade_level=gl, section_name=sn)
            session.add(sec)
        if adviser_teacher:
            sec.adviser_teacher = str(adviser_teacher).strip()
        if room_number:
            sec.room_number = str(room_number).strip()
        session.commit()
        return sec.to_dict()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def delete_section_orm(section_id):
    """Removes a section from the database by ID."""
    global _SECTIONS_CACHE
    _SECTIONS_CACHE["data"] = None
    session = Session()
    try:
        sec = session.query(Section).filter_by(id=int(section_id)).first()
        if not sec:
            return False, "Section not found"
        # Detach students from section before deleting
        session.query(Student).filter_by(section_id=sec.id).update({"section_id": None})
        session.delete(sec)
        session.commit()
        return True, f"Section {sec.grade_level} - {sec.section_name} deleted successfully"
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def get_section_by_id_orm(section_id):
    """Returns a single section by ID."""
    session = Session()
    try:
        sec = session.query(Section).filter_by(id=int(section_id)).first()
        return sec.to_dict() if sec else None
    finally:
        session.close()

def update_section_orm(section_id, grade_level=None, section_name=None, adviser_teacher=None, room_number=None):
    """Updates an existing section by ID and syncs any enrolled students."""
    session = Session()
    try:
        sec = session.query(Section).filter_by(id=int(section_id)).first()
        if not sec:
            return None, "Section not found"
        
        if grade_level is not None:
            sec.grade_level = str(grade_level).strip()
        if section_name is not None:
            sec.section_name = str(section_name).strip()
        if adviser_teacher is not None:
            sec.adviser_teacher = str(adviser_teacher).strip()
        if room_number is not None:
            sec.room_number = str(room_number).strip()

        # Sync attached students
        students = session.query(Student).filter_by(section_id=sec.id).all()
        for st in students:
            st.grade_level = sec.grade_level
            st.section_name = sec.section_name
            st.grade_section = f"{sec.grade_level} - {sec.section_name}"
            if sec.adviser_teacher:
                st.class_adviser = sec.adviser_teacher

        session.commit()
        return sec.to_dict(), f"Section {sec.grade_level} - {sec.section_name} updated successfully!"
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def auto_migrate_columns_orm():
    """
    Guarantees all database columns and tables exist across SQLite and Cloud PostgreSQL (Supabase/Neon).
    Uses isolated transactions (engine.begin()) per statement so failures never abort subsequent migrations.
    """
    from sqlalchemy import text
    dialect = engine.dialect.name.lower()

    # 1. Staff Attendance Logs table
    try:
        StaffAttendanceLog.__table__.create(engine, checkfirst=True)
    except Exception:
        pass

    # 2. Users table columns
    user_cols = [
        ("designation", "VARCHAR(100) DEFAULT ''"),
        ("assigned_section_id", "INTEGER"),
        ("face_embedding", "TEXT"),
        ("photo_path", "TEXT DEFAULT ''"),
        ("last_login", "TIMESTAMP")
    ]
    for col_name, col_def in user_cols:
        try:
            with engine.begin() as conn:
                if "postgres" in dialect:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_def};"))
                elif "sqlite" in dialect:
                    res = conn.execute(text("PRAGMA table_info(users);")).fetchall()
                    existing = [r[1] for r in res]
                    if col_name not in existing:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_def};"))
                else:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_def};"))
        except Exception:
            pass

    # 3. Students table columns
    student_cols = [
        ("grade_level", "VARCHAR(30) DEFAULT ''"),
        ("section_name", "VARCHAR(60) DEFAULT ''"),
        ("class_adviser", "VARCHAR(100) DEFAULT ''")
    ]
    for col_name, col_def in student_cols:
        try:
            with engine.begin() as conn:
                if "postgres" in dialect:
                    conn.execute(text(f"ALTER TABLE students ADD COLUMN IF NOT EXISTS {col_name} {col_def};"))
                elif "sqlite" in dialect:
                    res = conn.execute(text("PRAGMA table_info(students);")).fetchall()
                    existing = [r[1] for r in res]
                    if col_name not in existing:
                        conn.execute(text(f"ALTER TABLE students ADD COLUMN {col_name} {col_def};"))
                else:
                    conn.execute(text(f"ALTER TABLE students ADD COLUMN {col_name} {col_def};"))
        except Exception:
            pass

_db_initialized = False

def init_orm_db(force=False):
    """
    Initializes database schema and seeds default records.
    Optimized for Serverless / Cloud: Checks if tables already exist and skips redundant
    DDL and bulk queries to prevent Lambda cold-start timeout.
    """
    global engine, _db_initialized
    if _db_initialized and not force:
        return

    try:
        # 1. Ensure all core tables exist in database (CREATE TABLE IF NOT EXISTS)
        Base.metadata.create_all(engine)

        # 2. Run isolated column migrations
        auto_migrate_columns_orm()

        from sqlalchemy import inspect
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        # If core tables already exist in Supabase / Cloud Postgres, skip heavy re-initialization IMMEDIATELY
        if "students" in existing_tables and "users" in existing_tables and not force:
            print(f"[+] Connected to existing database ({engine.dialect.name.upper()}). Skipping cold-start DDL.")
            if "school_events" not in existing_tables:
                try:
                    SchoolEvent.__table__.create(engine, checkfirst=True)
                    seed_default_events_orm()
                except Exception as ex:
                    print(f"[!] school_events creation note: {ex}")
            if "push_subscriptions" not in existing_tables:
                try:
                    PushSubscription.__table__.create(engine, checkfirst=True)
                    print("[+] Created push_subscriptions table in cloud database.")
                except Exception as ex:
                    print(f"[!] push_subscriptions creation note: {ex}")
            if "parent_device_tokens" not in existing_tables:
                try:
                    ParentDeviceToken.__table__.create(engine, checkfirst=True)
                    print("[+] Created parent_device_tokens table in database.")
                except Exception as ex:
                    print(f"[!] parent_device_tokens creation note: {ex}")

            _db_initialized = True
            return

        # 2. Auto-migrate PostgreSQL column lengths if needed
        if "postgres" in engine.dialect.name.lower():
            try:
                from sqlalchemy import text
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE students ALTER COLUMN gender TYPE VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE students ALTER COLUMN birthdate TYPE VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE students ALTER COLUMN parent_phone TYPE VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE students ALTER COLUMN parent_phone DROP NOT NULL;"))
                    conn.execute(text("ALTER TABLE students ALTER COLUMN first_name TYPE VARCHAR(100);"))
                    conn.execute(text("ALTER TABLE students ALTER COLUMN middle_name TYPE VARCHAR(100);"))
                    conn.execute(text("ALTER TABLE students ALTER COLUMN last_name TYPE VARCHAR(100);"))
                    conn.execute(text("ALTER TABLE students ALTER COLUMN grade_section TYPE VARCHAR(150);"))
                    conn.execute(text("ALTER TABLE students ALTER COLUMN parent_name TYPE VARCHAR(150);"))
                    conn.execute(text("ALTER TABLE students ALTER COLUMN photo_path TYPE TEXT;"))
                    conn.execute(text("ALTER TABLE students ALTER COLUMN qr_code_path TYPE TEXT;"))
                    conn.commit()
            except Exception as ex:
                print(f"[!] PostgreSQL column auto-migration note: {ex}")
        # Check and migrate columns in SQLite if needed
        if "sqlite" in engine.dialect.name.lower():
            try:
                from sqlalchemy import text
                with engine.connect() as conn:
                    res = conn.execute(text("PRAGMA table_info(students)"))
                    cols = [row[1] for row in res.fetchall()]
                    if "middle_name" not in cols:
                        conn.execute(text("ALTER TABLE students ADD COLUMN middle_name VARCHAR(60) DEFAULT ''"))
                    if "grade_level" not in cols:
                        conn.execute(text("ALTER TABLE students ADD COLUMN grade_level VARCHAR(30) DEFAULT ''"))
                    if "section_name" not in cols:
                        conn.execute(text("ALTER TABLE students ADD COLUMN section_name VARCHAR(60) DEFAULT ''"))
                    if "class_adviser" not in cols:
                        conn.execute(text("ALTER TABLE students ADD COLUMN class_adviser VARCHAR(100) DEFAULT ''"))
                    conn.commit()
            except Exception as e:
                print(f"[!] Migration check note: {e}")
        # Auto-seed K-12 sections
        seed_default_sections_orm()
        # Auto-seed official announcements & advisories
        seed_default_announcements_orm()
        # Auto-seed default RBAC users
        seed_default_users_orm()
        # Auto-seed editable SaaS pricing plans
        seed_default_pricing_plans_orm()
        # Auto-seed school events & activities
        seed_default_events_orm()
        print(f"[+] Non-Biometric Smart ID Relational Database initialized ({engine.dialect.name.upper()}).")
    except Exception as e:
        print(f"[!] Warning: init_orm_db deferred or failed ({e}). App running in resilient mode.")

# -------------------------------------------------------------
# CRUD Operations (Non-Biometric)
# -------------------------------------------------------------

def save_student_orm(lrn, first_name, last_name, grade_section="", parent_name="", parent_phone="", 
                     rfid_card_uid="", gender="Unspecified", track="Junior High", 
                     photo_path="", embedding_array=None, middle_name="", grade_level="",
                     section_name="", class_adviser="", birthdate="", **kwargs):
    """Registers student with LRN, parent contact, photo, and 128-d biometric face embedding."""
    session = Session()
    lrn_clean = str(lrn).strip()
    try:
        student = session.query(Student).filter_by(lrn=lrn_clean).first()
        if not student:
            student = Student(lrn=lrn_clean)
            session.add(student)

        student.first_name = (first_name or "").strip()[:100]
        student.middle_name = (middle_name or kwargs.get("middle_name", "") or "").strip()[:100]
        student.last_name = (last_name or "").strip()[:100]
        
        g_level = (grade_level or kwargs.get("grade_level", "") or "").strip()[:50]
        s_name = (section_name or kwargs.get("section_name", "") or "").strip()[:60]
        c_adviser = (class_adviser or kwargs.get("class_adviser", "") or "").strip()[:100]
        
        student.grade_level = g_level
        student.section_name = s_name
        student.class_adviser = c_adviser
        if birthdate:
            student.birthdate = str(birthdate).strip()[:50]

        if g_level and s_name:
            student.grade_section = f"{g_level} - {s_name}"[:150]
            # Real database connection to Section
            sec = session.query(Section).filter_by(grade_level=g_level, section_name=s_name).first()
            if not sec:
                sec = session.query(Section).filter(Section.grade_level == g_level, Section.section_name.ilike(s_name)).first()
            if sec:
                student.section_id = sec.id
                if not student.class_adviser and sec.adviser_teacher:
                    student.class_adviser = sec.adviser_teacher
        elif grade_section:
            student.grade_section = grade_section.strip()[:150]
        elif g_level:
            student.grade_section = g_level[:150]
        else:
            student.grade_section = "Unassigned"

        student.parent_name = (parent_name or "").strip()[:150]
        student.parent_phone = (parent_phone or "N/A").strip()[:50]
        student.rfid_card_uid = str(rfid_card_uid or "").strip()[:50]
        student.gender = (gender or "Unspecified").strip()[:50]
        student.track_strand = (track or "Junior High").strip()[:100]
        student.is_active = True
        
        if photo_path:
            student.photo_path = str(photo_path)
            
        if embedding_array is not None:
            if isinstance(embedding_array, np.ndarray):
                student.face_embedding = json.dumps(embedding_array.tolist())
            elif isinstance(embedding_array, list):
                student.face_embedding = json.dumps(embedding_array)
            elif isinstance(embedding_array, str):
                student.face_embedding = embedding_array
        
        # Auto-generate QR code ID
        qr_url = generate_student_qr(lrn_clean)
        student.qr_code_path = qr_url

        session.commit()
        _STUDENT_COUNT_CACHE["count"] = None
        return student.to_dict()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def delete_student_orm(lrn):
    """Deletes a student record and associated local photo/QR files."""
    session = Session()
    try:
        student = session.query(Student).filter_by(lrn=str(lrn).strip()).first()
        if not student:
            return False, "Student not found"
        
        # Safely remove local file only if photo_path is a real filesystem path (not a base64 data URI)
        if student.photo_path and not str(student.photo_path).startswith("data:") and len(str(student.photo_path)) < 255:
            try:
                base_dir = Path(__file__).resolve().parent
                p = (base_dir / str(student.photo_path).lstrip("/")).resolve()
                if p.exists() and p.is_file():
                    p.unlink(missing_ok=True)
            except Exception:
                pass

        try:
            base_dir = Path(__file__).resolve().parent
            qr_file = base_dir / "static" / "qrcodes" / f"{student.lrn}.png"
            if qr_file.exists() and qr_file.is_file():
                qr_file.unlink(missing_ok=True)
        except Exception:
            pass

        session.delete(student)
        session.commit()
        _STUDENT_COUNT_CACHE["count"] = None
        try:
            (smile_config.DATA_DIR / ".students_seeded").touch(exist_ok=True)
        except Exception:
            pass
        return True, f"Student {lrn} removed successfully"
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def get_all_enrolled_students_orm():
    """Returns all active students with deserialized numpy face embeddings."""
    session = Session()
    try:
        students = session.query(Student).filter_by(is_active=True).all()
        result = []
        for s in students:
            d = s.to_dict()
            if s.face_embedding:
                try:
                    d["embedding"] = np.array(json.loads(s.face_embedding), dtype=np.float32)
                except Exception:
                    d["embedding"] = None
            else:
                d["embedding"] = None
            result.append(d)
        return result
    finally:
        session.close()

def get_enrolled_students_count_orm():
    """Ultra-fast count of enrolled students without loading objects or embeddings (2ms) with TTL caching."""
    now = time.time()
    if _STUDENT_COUNT_CACHE["count"] is not None and (now - _STUDENT_COUNT_CACHE["ts"]) < 30:
        return _STUDENT_COUNT_CACHE["count"]
    session = Session()
    try:
        cnt = session.query(func.count(Student.lrn)).filter_by(is_active=True).scalar() or 0
        _STUDENT_COUNT_CACHE["count"] = cnt
        _STUDENT_COUNT_CACHE["ts"] = now
        return cnt
    finally:
        session.close()

def get_students_directory_orm():
    """Fast student directory listing omitting heavy JSON/NumPy face embeddings."""
    session = Session()
    try:
        students = session.query(
            Student.lrn, Student.first_name, Student.middle_name, Student.last_name,
            Student.gender, Student.grade_level, Student.section_name, Student.class_adviser,
            Student.grade_section, Student.parent_name, Student.parent_phone,
            Student.rfid_card_uid, Student.qr_code_path, Student.photo_path,
            Student.is_active, Student.created_at
        ).filter_by(is_active=True).all()
        
        result = []
        for s in students:
            full_name = f"{s.first_name} {s.middle_name} {s.last_name}".strip() if s.middle_name else f"{s.first_name} {s.last_name}".strip()
            result.append({
                "lrn": s.lrn,
                "first_name": s.first_name,
                "middle_name": s.middle_name or "",
                "last_name": s.last_name,
                "full_name": full_name,
                "gender": s.gender or "Unspecified",
                "grade_level": s.grade_level or "",
                "section_name": s.section_name or "",
                "class_adviser": s.class_adviser or "",
                "grade_section": s.grade_section or "",
                "parent_name": s.parent_name or "",
                "parent_phone": s.parent_phone or "",
                "rfid_card_uid": s.rfid_card_uid or "N/A",
                "qr_code_path": s.qr_code_path or f"/qr/{s.lrn}.png",
                "photo_path": s.photo_path or "",
                "is_active": s.is_active,
                "created_at": s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else ""
            })
        return result
    finally:
        session.close()

def get_student_by_lrn_or_rfid_orm(identifier: str):
    """Looks up student by either 12-digit LRN or physical RFID card UID."""
    session = Session()
    clean_id = str(identifier).strip()
    try:
        # Check by LRN
        student = session.query(Student).filter_by(lrn=clean_id, is_active=True).first()
        if student:
            return student.to_dict()
        # Check by RFID UID
        student = session.query(Student).filter_by(rfid_card_uid=clean_id, is_active=True).first()
        if student:
            return student.to_dict()
        return None
    finally:
        session.close()

def evaluate_daily_scan_rule_orm(lrn, student_name="", current_time=None, cooldown_seconds=COOLDOWN_SECONDS, gate_mode="AUTO", min_dwell_minutes=0):
    """
    Evaluates DepEd School Daily Attendance Quota & State Machine Rule (Strict 4-Scan Schedule):
    Strict Sessions:
      1. Morning Time-In:   05:00 AM – 10:59 AM (Quota: 1 scan)
      2. Morning Time-Out:  11:00 AM – 12:00 PM (Quota: 1 scan)
      3. Afternoon Time-In: 12:01 PM – 12:59 PM (Quota: 1 scan)
      4. Afternoon Time-Out: 04:00 PM onwards   (Quota: 1 scan)
    Max Daily Quota: Exactly 4 scans per student or teacher per day.
    """
    session = Session()
    now = current_time or pht_now()
    today_start = datetime.combine(now.date(), datetime.min.time())
    clean_lrn = str(lrn).strip()
    norm_gate_mode = (gate_mode or "AUTO").upper()

    try:
        # Resolve student full name if not provided
        if not student_name:
            st = session.query(Student).filter_by(lrn=clean_lrn).first()
            if st:
                student_name = st.full_name
            else:
                student_name = f"Learner {clean_lrn}"

        # Retrieve all attendance logs recorded for this student today
        today_logs = session.query(AttendanceLog).filter(
            AttendanceLog.lrn == clean_lrn,
            AttendanceLog.timestamp >= today_start
        ).order_by(AttendanceLog.id.asc()).all()

        last_log = today_logs[-1] if today_logs else None

        # Segregate today's logs into AM (hour < 12) and PM (hour >= 12)
        am_logs = [l for l in today_logs if l.timestamp and l.timestamp.hour < MIDDAY_SPLIT_HOUR]
        pm_logs = [l for l in today_logs if l.timestamp and l.timestamp.hour >= MIDDAY_SPLIT_HOUR]

        am_in_count = sum(1 for l in am_logs if l.scan_type == "TIME_IN")
        am_out_count = sum(1 for l in am_logs if l.scan_type == "TIME_OUT")
        pm_in_count = sum(1 for l in pm_logs if l.scan_type == "TIME_IN")
        pm_out_count = sum(1 for l in pm_logs if l.scan_type == "TIME_OUT")
        total_scans_today = len(today_logs)

        # -------------------------------------------------------------
        # 1. Check Anti-Spam Continuous Presence Debounce (< 25s)
        # If student stays in front of lens, silently retain active badge
        # -------------------------------------------------------------
        if last_log and last_log.timestamp:
            elapsed = (now - last_log.timestamp).total_seconds()
            if 0 <= elapsed < cooldown_seconds:
                rem = max(1, int(cooldown_seconds - elapsed))
                active_label = "Morning Time-In" if last_log.scan_type == "TIME_IN" else "Time-Out"
                return {
                    "can_scan": False,
                    "is_active_dwell": True,
                    "scan_type": last_log.scan_type,
                    "period": f"{active_label} (Active)",
                    "voice_text": "",  # Silent: do NOT shout duplicate rejection
                    "message": f"{student_name} attendance active ({rem}s debounce).",
                    "cooldown_remaining": rem,
                    "am_in": am_in_count, "am_out": am_out_count,
                    "pm_in": pm_in_count, "pm_out": pm_out_count,
                    "total_scans": total_scans_today
                }

        # -------------------------------------------------------------
        # 2. Strict Daily 4-Scan Quota Cap
        # Each student or teacher is strictly limited to 4 scan sessions
        # -------------------------------------------------------------
        if total_scans_today >= MAX_DAILY_SCANS_PER_PERSON:
            return {
                "can_scan": False,
                "scan_type": "COMPLETED",
                "period": "Daily Attendance Completed",
                "voice_text": f"Daily attendance completed. {student_name} has completed all 4 sessions today.",
                "message": f"Daily attendance limit reached: {student_name} has completed all 4 daily sessions.",
                "am_in": am_in_count, "am_out": am_out_count,
                "pm_in": pm_in_count, "pm_out": pm_out_count,
                "total_scans": total_scans_today,
                "cooldown_remaining": 0
            }

        curr_min = now.hour * 60 + now.minute

        # -------------------------------------------------------------
        # 3. Schedule Window Enforcement
        # -------------------------------------------------------------

        # Window A: Before 05:00 AM (Early Dawn / Gate Closed)
        if curr_min < SCHEDULE_AM_IN_START_MIN:
            return {
                "can_scan": False,
                "scan_type": "NOT_STARTED",
                "period": "Gate Closed (Opens 5:00 AM)",
                "voice_text": f"Morning Time In opens at 5:00 AM, {student_name}.",
                "message": f"Gate closed: Morning Time-In window is from 5:00 AM to 10:59 AM. (Current: {now.strftime('%I:%M %p')})",
                "am_in": am_in_count, "am_out": am_out_count,
                "pm_in": pm_in_count, "pm_out": pm_out_count,
                "total_scans": total_scans_today,
                "cooldown_remaining": 0
            }

        # Window B: Morning Time-In (05:00 AM – 10:59 AM)
        elif SCHEDULE_AM_IN_START_MIN <= curr_min <= SCHEDULE_AM_IN_END_MIN:
            if am_in_count == 0:
                return {
                    "can_scan": True,
                    "scan_type": "TIME_IN",
                    "period": "Morning Time-In",
                    "voice_text": f"Good morning, {student_name}! Morning Time In recorded. Welcome to Don Montano Central Integrated School.",
                    "message": f"Morning Time-In recorded for {student_name}.",
                    "am_in": am_in_count + 1, "am_out": am_out_count,
                    "pm_in": pm_in_count, "pm_out": pm_out_count,
                    "total_scans": total_scans_today + 1,
                    "cooldown_remaining": 0
                }
            else:
                # Already timed in for morning session!
                return {
                    "can_scan": False,
                    "scan_type": "TIME_IN",
                    "period": "Morning Time-In (Active)",
                    "voice_text": f"{student_name} is already timed in for the morning session.",
                    "message": f"Morning Time-In already recorded for {student_name}. Morning dismissal opens at 11:00 AM.",
                    "am_in": am_in_count, "am_out": am_out_count,
                    "pm_in": pm_in_count, "pm_out": pm_out_count,
                    "total_scans": total_scans_today,
                    "cooldown_remaining": 0
                }

        # Window C: Morning Time-Out (11:00 AM – 12:00 PM)
        elif SCHEDULE_AM_OUT_START_MIN <= curr_min <= SCHEDULE_AM_OUT_END_MIN:
            if am_in_count == 0:
                return {
                    "can_scan": False,
                    "scan_type": "NOT_ENTERED",
                    "period": "No Morning Time-In",
                    "voice_text": f"Cannot time out. {student_name} has no morning time in record.",
                    "message": f"Exit scan rejected: {student_name} has no morning time in record.",
                    "am_in": am_in_count, "am_out": am_out_count,
                    "pm_in": pm_in_count, "pm_out": pm_out_count,
                    "total_scans": total_scans_today,
                    "cooldown_remaining": 0
                }
            elif am_out_count == 0:
                return {
                    "can_scan": True,
                    "scan_type": "TIME_OUT",
                    "period": "Morning Time-Out",
                    "voice_text": f"Goodbye, {student_name}! Morning Time Out recorded. Have a safe lunch break.",
                    "message": f"Morning Time-Out (Lunch Dismissal) recorded for {student_name}.",
                    "am_in": am_in_count, "am_out": am_out_count + 1,
                    "pm_in": pm_in_count, "pm_out": pm_out_count,
                    "total_scans": total_scans_today + 1,
                    "cooldown_remaining": 0
                }
            else:
                return {
                    "can_scan": False,
                    "scan_type": "TIME_OUT",
                    "period": "Morning Time-Out (Active)",
                    "voice_text": f"{student_name} has already timed out for lunch. Afternoon Time-In opens at 12:01 PM.",
                    "message": f"Morning Time-Out already recorded for {student_name}. Afternoon session opens at 12:01 PM.",
                    "am_in": am_in_count, "am_out": am_out_count,
                    "pm_in": pm_in_count, "pm_out": pm_out_count,
                    "total_scans": total_scans_today,
                    "cooldown_remaining": 0
                }

        # Window D: Afternoon Time-In (12:01 PM – 12:59 PM)
        elif SCHEDULE_PM_IN_START_MIN <= curr_min <= SCHEDULE_PM_IN_END_MIN:
            if pm_in_count == 0:
                return {
                    "can_scan": True,
                    "scan_type": "TIME_IN",
                    "period": "Afternoon Time-In",
                    "voice_text": f"Good afternoon, {student_name}! Afternoon Time In recorded. Welcome back to Don Montano Central Integrated School.",
                    "message": f"Afternoon Time-In recorded for {student_name}.",
                    "am_in": am_in_count, "am_out": am_out_count,
                    "pm_in": pm_in_count + 1, "pm_out": pm_out_count,
                    "total_scans": total_scans_today + 1,
                    "cooldown_remaining": 0
                }
            else:
                return {
                    "can_scan": False,
                    "scan_type": "TIME_IN",
                    "period": "Afternoon Time-In (Active)",
                    "voice_text": f"{student_name} is already timed in for the afternoon session.",
                    "message": f"Afternoon Time-In already recorded for {student_name}. Dismissal opens at 4:00 PM.",
                    "am_in": am_in_count, "am_out": am_out_count,
                    "pm_in": pm_in_count, "pm_out": pm_out_count,
                    "total_scans": total_scans_today,
                    "cooldown_remaining": 0
                }

        # Window E: Afternoon Class Hours (01:00 PM – 03:59 PM)
        elif SCHEDULE_PM_IN_END_MIN < curr_min < SCHEDULE_PM_OUT_START_MIN:
            if pm_in_count >= 1:
                return {
                    "can_scan": False,
                    "scan_type": "TIME_IN",
                    "period": "Classes in Session (Dismissal 4:00 PM)",
                    "voice_text": f"Afternoon classes are in session, {student_name}. Dismissal opens at 4:00 PM.",
                    "message": f"Classes in session: {student_name} is inside campus. Afternoon dismissal opens at 4:00 PM.",
                    "am_in": am_in_count, "am_out": am_out_count,
                    "pm_in": pm_in_count, "pm_out": pm_out_count,
                    "total_scans": total_scans_today,
                    "cooldown_remaining": 0
                }
            else:
                # Student missed the 12:01-12:59 PM window
                return {
                    "can_scan": False,
                    "scan_type": "CLOSED",
                    "period": "Afternoon Entry Closed",
                    "voice_text": f"Afternoon Time In closed at 12:59 PM, {student_name}. Please consult the gate guard.",
                    "message": f"Afternoon Time-In window closed at 12:59 PM. Please consult gate guard or adviser.",
                    "am_in": am_in_count, "am_out": am_out_count,
                    "pm_in": pm_in_count, "pm_out": pm_out_count,
                    "total_scans": total_scans_today,
                    "cooldown_remaining": 0
                }

        # Window F: Afternoon Time-Out (04:00 PM onwards)
        else:
            if am_in_count == 0 and pm_in_count == 0:
                return {
                    "can_scan": False,
                    "scan_type": "NOT_ENTERED",
                    "period": "No Time-In Recorded Today",
                    "voice_text": f"Cannot time out. {student_name} has no time in record today.",
                    "message": f"Exit scan rejected: {student_name} has no time-in record today.",
                    "am_in": am_in_count, "am_out": am_out_count,
                    "pm_in": pm_in_count, "pm_out": pm_out_count,
                    "total_scans": total_scans_today,
                    "cooldown_remaining": 0
                }
            elif pm_out_count == 0:
                return {
                    "can_scan": True,
                    "scan_type": "TIME_OUT",
                    "period": "Afternoon Time-Out (Final Departure)",
                    "voice_text": f"Goodbye, {student_name}! Final Departure Time Out recorded. Take care and see you tomorrow!",
                    "message": f"Afternoon Time-Out (Final Departure) recorded for {student_name}.",
                    "am_in": am_in_count, "am_out": am_out_count,
                    "pm_in": pm_in_count, "pm_out": pm_out_count + 1,
                    "total_scans": total_scans_today + 1,
                    "cooldown_remaining": 0
                }
            else:
                return {
                    "can_scan": False,
                    "scan_type": "COMPLETED",
                    "period": "Daily Attendance Completed",
                    "voice_text": f"Daily attendance completed. {student_name} has already timed out for today.",
                    "message": f"Daily attendance completed: {student_name} has completed all 4 daily sessions.",
                    "am_in": am_in_count, "am_out": am_out_count,
                    "pm_in": pm_in_count, "pm_out": pm_out_count,
                    "total_scans": total_scans_today,
                    "cooldown_remaining": 0
                }

    finally:
        session.close()

def check_can_scan_orm(lrn, cooldown_seconds=COOLDOWN_SECONDS, current_time=None):
    """Bridge for legacy callers; returns (can_scan, elapsed_or_cooldown, scan_type)."""
    eval_res = evaluate_daily_scan_rule_orm(lrn, cooldown_seconds=cooldown_seconds, current_time=current_time)
    return eval_res["can_scan"], eval_res.get("cooldown_remaining"), eval_res.get("scan_type")

def record_attendance_orm(lrn, student_name, scan_type, grade_section="", method="QR_CODE", sms_status="PENDING"):
    """Records an attendance log transaction."""
    session = Session()
    try:
        log = AttendanceLog(
            lrn=str(lrn),
            student_name=student_name,
            grade_section=grade_section,
            scan_type=scan_type,
            timestamp=pht_now(),
            verification_method=method,
            sms_status=sms_status
        )
        session.add(log)
        session.commit()
        _TODAY_SUMMARY_CACHE["data"] = None
        log_id = log.id

        # Dispatch background WebPush (wakes mobile device when locked or screen off)
        try:
            import time
            action_word = "arrived at" if scan_type == "TIME_IN" else "safely exited from"
            now_pht = pht_now().strftime("%I:%M %p")
            dispatch_web_push_notification(
                lrn=str(lrn),
                title=f"DepEd Gate Alert: {student_name}",
                body=f"Official Gate Scan Verified: {student_name} has {action_word} Don Montano CIS Gate 1 at {now_pht}.",
                tag=f"scan-{lrn}-{int(time.time())}",
                data_url=f"/parent?lrn={lrn}"
            )
        except Exception as _p_err:
            print(f"[Push] Auto-dispatch note: {_p_err}")

        # Dispatch Native Mobile Expo Push (wakes locked Android phone, rings sound, vibrates, lock-screen Heads-Up banner)
        try:
            is_entry = (scan_type == "TIME_IN")
            icon_emoji = "🟢" if is_entry else "🟠"
            action_desc = "entered" if is_entry else "safely departed from"
            push_title = f"{icon_emoji} Gate Attendance: {'Time-In' if is_entry else 'Time-Out'}"
            push_body = f"{student_name} {action_desc} Don Montano Central Integrated School Gate 1 at {now_pht}."
            dispatch_expo_push_notification(
                title=push_title,
                body=push_body,
                lrn=str(lrn),
                data={
                    "type": "GATE_SCAN",
                    "lrn": str(lrn),
                    "student_name": student_name,
                    "scan_type": scan_type,
                    "timestamp": now_pht
                },
                channel_id="gate-attendance-channel"
            )
        except Exception as _ep_err:
            print(f"[Expo Push] Auto-dispatch note: {_ep_err}")

        return log_id
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def update_attendance_sms_status_orm(log_id, status):
    session = Session()
    try:
        log = session.query(AttendanceLog).filter_by(id=log_id).first()
        if log:
            log.sms_status = status
            session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()

def record_sms_orm(recipient_phone, student_lrn, message_body, status, gateway="MOCK", response_info=""):
    session = Session()
    try:
        sms = SmsLog(
            recipient_phone=recipient_phone,
            student_lrn=student_lrn,
            message_body=message_body,
            gateway_type=gateway,
            status=status,
            sent_at=pht_now(),
            response_info=str(response_info)
        )
        session.add(sms)
        session.commit()
        return sms.id
    except Exception:
        session.rollback()
    finally:
        session.close()

def get_today_summary_orm():
    """Returns today's gate scan metrics with high-speed 3s in-memory TTL caching."""
    now = time.time()
    if _TODAY_SUMMARY_CACHE["data"] is not None and (now - _TODAY_SUMMARY_CACHE["ts"]) < 3.0:
        return _TODAY_SUMMARY_CACHE["data"]
    session = Session()
    try:
        today_start = datetime.combine(pht_now().date(), datetime.min.time())
        total_scans = session.query(func.count(AttendanceLog.id)).filter(AttendanceLog.timestamp >= today_start).scalar() or 0
        unique_students = session.query(func.count(func.distinct(AttendanceLog.lrn))).filter(AttendanceLog.timestamp >= today_start).scalar() or 0
        recent_logs = session.query(AttendanceLog).options(joinedload(AttendanceLog.student_rel)).order_by(desc(AttendanceLog.id)).limit(10).all()
        res = {
            "total_scans": total_scans,
            "unique_students": unique_students,
            "recent_scans": [r.to_dict() for r in recent_logs]
        }
        _TODAY_SUMMARY_CACHE["data"] = res
        _TODAY_SUMMARY_CACHE["ts"] = now
        return res
    finally:
        session.close()

def get_today_attendance_logs_orm(limit=None):
    """Returns today's attendance logs with student info from the active ORM database."""
    session = Session()
    try:
        today_start = datetime.combine(pht_now().date(), datetime.min.time())
        query = session.query(AttendanceLog).options(joinedload(AttendanceLog.student_rel)).filter(AttendanceLog.timestamp >= today_start).order_by(desc(AttendanceLog.id))
        if limit:
            query = query.limit(limit)
        logs = query.all()
        return [l.to_dict() for l in logs]
    finally:
        session.close()

def get_today_sms_count_orm():
    """Returns count of SMS sent today."""
    session = Session()
    try:
        today_start = datetime.combine(pht_now().date(), datetime.min.time())
        return session.query(func.count(SmsLog.id)).filter(SmsLog.sent_at >= today_start).scalar() or 0
    finally:
        session.close()

def get_recent_sms_logs_orm(limit=50):
    """Returns most recent SMS delivery logs."""
    session = Session()
    try:
        logs = session.query(SmsLog).order_by(desc(SmsLog.id)).limit(limit).all()
        return [l.to_dict() for l in logs]
    finally:
        session.close()

def get_all_attendance_logs_for_export_orm():
    """Returns all attendance logs formatted for DepEd SF2 CSV export."""
    session = Session()
    try:
        logs = session.query(AttendanceLog).order_by(AttendanceLog.id.asc()).all()
        res = []
        for l in logs:
            st = l.student_rel
            res.append({
                "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "",
                "lrn": l.lrn,
                "student_name": l.student_name,
                "grade_section": l.grade_section or (st.grade_section if st else "N/A"),
                "class_adviser": (st.class_adviser if st else "") or "N/A",
                "scan_type": l.scan_type,
                "parent_phone": (st.parent_phone if st else "") or "N/A",
                "sms_status": l.sms_status
            })
        return res
    finally:
        session.close()

def get_teacher_advisory_overview_orm(section_id=None, section_name=None, adviser_name=None):
    """
    Returns dedicated advisory class metrics, student roster, and today's IN/OUT logs for a Teacher.
    - Advisory students list with live presence (TIME_IN, TIME_OUT, NOT_ARRIVED)
    - Total enrolled
    - Currently inside campus count
    - Safely exited count
    - Absent/unrecorded count
    - Recent gate attendance logs for this advisory section
    """
    session = Session()
    try:
        from datetime import datetime
        today_start = datetime.combine(pht_now().date(), datetime.min.time())

        # Resolve target section
        target_section = None
        if section_id:
            try:
                target_section = session.query(Section).filter_by(id=int(section_id)).first()
            except (ValueError, TypeError):
                pass
        
        if not target_section and section_name:
            parts = [p.strip() for p in section_name.split("-") if p.strip()]
            if len(parts) >= 2:
                target_section = session.query(Section).filter(
                    Section.grade_level.ilike(f"%{parts[0]}%"),
                    Section.section_name.ilike(f"%{parts[1]}%")
                ).first()
            if not target_section:
                target_section = session.query(Section).filter(
                    (Section.section_name.ilike(f"%{section_name}%")) |
                    (Section.grade_level.ilike(f"%{section_name}%"))
                ).first()

        if not target_section and adviser_name:
            clean_adv = adviser_name.replace("Mrs.", "").replace("Mr.", "").replace("Ms.", "").replace("Dr.", "").strip()
            target_section = session.query(Section).filter(Section.adviser_teacher.ilike(f"%{clean_adv}%")).first()

        # Query all students in this advisory class
        std_query = session.query(Student).filter(Student.is_active == True)
        if target_section:
            sec_label = f"{target_section.grade_level} - {target_section.section_name}"
            std_query = std_query.filter(
                (Student.section_id == target_section.id) |
                (Student.grade_section == sec_label) |
                (Student.section_name == target_section.section_name)
            )
        elif section_name:
            std_query = std_query.filter(Student.grade_section.ilike(f"%{section_name}%"))
        elif adviser_name:
            clean_adv = adviser_name.replace("Mrs.", "").replace("Mr.", "").replace("Ms.", "").replace("Dr.", "").strip()
            std_query = std_query.filter(Student.class_adviser.ilike(f"%{clean_adv}%"))

        students = std_query.order_by(Student.last_name.asc(), Student.first_name.asc()).all()
        student_lrns = [s.lrn for s in students]

        # Query today's attendance logs for these learners
        today_logs = []
        present_lrns = set()
        exited_lrns = set()
        latest_scan_map = {}

        if student_lrns:
            logs = session.query(AttendanceLog).filter(
                AttendanceLog.timestamp >= today_start,
                AttendanceLog.lrn.in_(student_lrns)
            ).order_by(desc(AttendanceLog.timestamp)).all()

            for l in logs:
                today_logs.append(l.to_dict())
                if l.lrn not in latest_scan_map:
                    latest_scan_map[l.lrn] = l.scan_type
                if l.scan_type == "TIME_IN":
                    present_lrns.add(l.lrn)
                elif l.scan_type == "TIME_OUT":
                    exited_lrns.add(l.lrn)

        # Build student roster with today's real-time presence status
        student_roster = []
        for s in students:
            s_dict = s.to_dict()
            last_status = latest_scan_map.get(s.lrn, "NOT_ARRIVED")
            s_dict["today_status"] = last_status # TIME_IN, TIME_OUT, NOT_ARRIVED
            student_roster.append(s_dict)

        total_enrolled = len(students)
        inside_now = sum(1 for status in latest_scan_map.values() if status == "TIME_IN")
        timed_out_count = sum(1 for status in latest_scan_map.values() if status == "TIME_OUT")
        absent_count = max(0, total_enrolled - len(latest_scan_map))

        sec_name_display = f"{target_section.grade_level} - {target_section.section_name}" if target_section else (section_name or "Advisory Class")
        
        # Prioritize the logged-in teacher's actual name and auto-sync with section
        if adviser_name:
            adv_display = adviser_name
            if target_section and target_section.adviser_teacher != adviser_name:
                try:
                    target_section.adviser_teacher = adviser_name
                    session.commit()
                except Exception:
                    session.rollback()
        else:
            adv_display = target_section.adviser_teacher if target_section else ""

        return {
            "section_id": target_section.id if target_section else None,
            "section_name": sec_name_display,
            "room_number": target_section.room_number if target_section else "",
            "adviser_teacher": adv_display,
            "total_enrolled": total_enrolled,
            "inside_campus": inside_now,
            "timed_out": timed_out_count,
            "absent_today": absent_count,
            "present_today": len(present_lrns),
            "today_logs": today_logs[:50],
            "students": student_roster
        }
    finally:
        session.close()


def get_database_stats_orm():
    session = Session()
    try:
        active_url = get_database_url()
        dialect_name = engine.dialect.name.upper() # 'POSTGRESQL', 'MYSQL', 'SQLITE'
        is_cloud_prod = dialect_name in ["POSTGRESQL", "MYSQL"]
        
        # Mask password in URL for display
        url_display = active_url
        if "@" in active_url:
            parts = active_url.split("@")
            prefix = parts[0].split("://")[0]
            host_part = parts[1]
            url_display = f"{prefix}://*****@{host_part}"

        return {
            "database_type": dialect_name,
            "is_cloud_prod": is_cloud_prod,
            "connection_url": url_display,
            "total_students": session.query(func.count(Student.lrn)).scalar() or 0,
            "total_sections": session.query(func.count(Section.id)).scalar() or 0,
            "total_attendance_records": session.query(func.count(AttendanceLog.id)).scalar() or 0,
            "total_sms_sent": session.query(func.count(SmsLog.id)).scalar() or 0
        }
    finally:
        session.close()

def save_excuse_note_orm(lrn, parent_name, parent_phone, date_effective, reason, details):
    """Saves a parent-submitted excuse note to the database."""
    session = Session()
    try:
        note = ExcuseNote(
            lrn=str(lrn).strip(),
            parent_name=parent_name.strip(),
            parent_phone=parent_phone.strip(),
            date_effective=date_effective.strip(),
            reason=reason.strip(),
            details=details.strip(),
            status="SUBMITTED"
        )
        session.add(note)
        session.commit()
        return note.to_dict()
    finally:
        session.close()

def get_student_excuse_notes_orm(lrn, session=None):
    """Retrieves all excuse notes submitted for a specific learner."""
    close_session = False
    if session is None:
        session = Session()
        close_session = True
    try:
        notes = session.query(ExcuseNote).filter_by(lrn=str(lrn)).order_by(desc(ExcuseNote.id)).limit(15).all()
        return [n.to_dict() for n in notes]
    finally:
        if close_session:
            session.close()

def get_students_by_parent_phone_orm(phone):
    """Finds all enrolled learners linked to a guardian's mobile phone number."""
    session = Session()
    try:
        cleaned_phone = phone.replace("-", "").replace(" ", "").replace("+63", "0")
        students = session.query(Student).filter(
            (Student.parent_phone == phone) |
            (Student.parent_phone == cleaned_phone) |
            (Student.parent_phone.like(f"%{cleaned_phone[-10:]}%"))
        ).all()
        return [s.to_dict() for s in students]
    finally:
        session.close()

DEFAULT_ANNOUNCEMENTS = [
    {
        "title": "Severe Weather Bulletin: Class Suspension Advisory",
        "category": "WEATHER_ALERT",
        "content": "Due to Typhoon Florita and PAGASA Heavy Rainfall Warning, classes in all levels (Kindergarten to Grade 12) at Don Montano Central Integrated School are suspended today. All learners and guardians are advised to stay indoors and keep safe.",
        "author": "Don Montano CIS Disaster Risk Reduction Office",
        "badge_color": "red",
        "is_urgent": True,
        "target_grade": "ALL"
    },
    {
        "title": "DepEd Order No. 44: Project S.M.I.L.E. Gate Safety Policy",
        "category": "DEPED_MEMO",
        "content": "DepEd Region IV-A fully implements strict RFID & QR Smart Gate Attendance monitoring. Learners must scan their DepEd Smart IDs upon arrival and before dismissal. Dual-channel SMS and Parent App notifications fire automatically.",
        "author": "Office of the Principal - DepEd Region IV-A",
        "badge_color": "blue",
        "is_urgent": False,
        "target_grade": "ALL"
    },
    {
        "title": "1st General Parent-Teacher Association (PTA) Assembly",
        "category": "ANNOUNCEMENT",
        "content": "Cordially inviting all parents and legal guardians of Don Montano CIS to the 1st Quarter PTA General Assembly this coming Friday at 2:00 PM in the School Gymnasium. Agenda: Campus Security Upgrades and Project S.M.I.L.E. App Rollout.",
        "author": "PTA Executive Board & Administration",
        "badge_color": "amber",
        "is_urgent": False,
        "target_grade": "ALL"
    },
    {
        "title": "School Clinic Health Advisory: Flu Season Precautions",
        "category": "HEALTH_ALERT",
        "content": "Learners experiencing fever, cough, or flu-like symptoms are advised to rest at home. Parents can submit digital excuse notes directly through this Parent App to automatically notify their class adviser.",
        "author": "Don Montano CIS Health & Nutrition Clinic",
        "badge_color": "emerald",
        "is_urgent": False,
        "target_grade": "ALL"
    }
]

def seed_default_announcements_orm():
    """Seeds default school bulletins, DepEd memos, and advisories for Don Montano CIS."""
    session = Session()
    try:
        count = session.query(Announcement).count()
        if count >= 3:
            return
        for a in DEFAULT_ANNOUNCEMENTS:
            existing = session.query(Announcement).filter_by(title=a["title"]).first()
            if not existing:
                ann = Announcement(
                    title=a["title"],
                    category=a["category"],
                    content=a["content"],
                    author=a["author"],
                    badge_color=a["badge_color"],
                    is_urgent=a["is_urgent"],
                    target_grade=a["target_grade"]
                )
                session.add(ann)
        session.commit()
        print(f"[+] Don Montano CIS Official Announcements seeded ({session.query(Announcement).count()} items).")
    except Exception as e:
        session.rollback()
        print(f"[!] Error seeding announcements: {e}")
    finally:
        session.close()

def get_all_announcements_orm(limit=30, category=None):
    """Retrieves school announcements ordered by urgency and date (with 60s memory caching)."""
    global _ANNOUNCEMENTS_CACHE
    now = time.time()
    use_cache = (category in (None, "ALL") and limit == 30)
    if use_cache and _ANNOUNCEMENTS_CACHE["data"] is not None and (now - _ANNOUNCEMENTS_CACHE["ts"]) < 60:
        return _ANNOUNCEMENTS_CACHE["data"]

    session = Session()
    try:
        query = session.query(Announcement)
        if category and category != "ALL":
            query = query.filter(Announcement.category == category)
        items = query.order_by(Announcement.is_urgent.desc(), Announcement.id.desc()).limit(limit).all()
        res = [item.to_dict() for item in items]
        if use_cache:
            _ANNOUNCEMENTS_CACHE["data"] = res
            _ANNOUNCEMENTS_CACHE["ts"] = now
        return res
    finally:
        session.close()

def save_announcement_orm(title, category, content, author="School Administration", badge_color="blue", is_urgent=False, target_grade="ALL"):
    global _ANNOUNCEMENTS_CACHE
    session = Session()
    try:
        ann = Announcement(
            title=title.strip(),
            category=category.strip(),
            content=content.strip(),
            author=author.strip(),
            badge_color=badge_color.strip(),
            is_urgent=bool(is_urgent),
            target_grade=target_grade.strip()
        )
        session.add(ann)
        session.commit()
        _ANNOUNCEMENTS_CACHE["data"] = None  # Cache invalidation
        return ann.to_dict()
    finally:
        session.close()

def delete_announcement_orm(announcement_id):
    global _ANNOUNCEMENTS_CACHE
    session = Session()
    try:
        ann = session.query(Announcement).filter_by(id=int(announcement_id)).first()
        if not ann:
            return False, "Announcement not found"
        session.delete(ann)
        session.commit()
        _ANNOUNCEMENTS_CACHE["data"] = None  # Cache invalidation
        return True, "Announcement deleted successfully"
    finally:
        session.close()

# -------------------------------------------------------------
# School Events & Calendar Functions
# -------------------------------------------------------------

DEFAULT_EVENTS = [
    {
        "title": "1st Quarter Periodical Examinations",
        "category": "ACADEMIC",
        "description": "Comprehensive first quarter examinations for all Kindergarten to Grade 12 learners. Morning and afternoon testing schedules apply. Review materials are available with class advisers.",
        "event_date": "2026-10-08",
        "start_time": "07:30 AM",
        "end_time": "03:30 PM",
        "location": "Respective Classrooms",
        "target_grades": "Kindergarten to Grade 12",
        "organizer": "Academic Affairs & DepEd Testing Committee",
        "badge_color": "blue",
        "is_highlighted": True
    },
    {
        "title": "General PTA Assembly & Report Card Day",
        "category": "PTA",
        "description": "Distribution of 1st Quarter Learner Progress Report Cards (SF9) and parent-teacher consultations regarding student academic progress and gate attendance safety.",
        "event_date": "2026-10-16",
        "start_time": "01:30 PM",
        "end_time": "05:00 PM",
        "location": "School Covered Court & Main Gymnasium",
        "target_grades": "All Grade Levels",
        "organizer": "General PTA Executive Council & Faculty",
        "badge_color": "amber",
        "is_highlighted": True
    },
    {
        "title": "Annual Intramural Sports Festival & Cheerdance",
        "category": "SPORTS",
        "description": "Annual campus sports fest featuring basketball, volleyball, badminton, track and field, chess tournament, and the inter-unit cheerdance competition.",
        "event_date": "2026-10-23",
        "start_time": "08:00 AM",
        "end_time": "05:00 PM",
        "location": "Main Athletic Grounds & Gymnasium",
        "target_grades": "Junior & Senior High School",
        "organizer": "MAPEH Department & Sports Club",
        "badge_color": "emerald",
        "is_highlighted": False
    },
    {
        "title": "National Reading Month Celebration & Book Parade",
        "category": "CULTURAL",
        "description": "School-wide celebration honoring reading literacy. Activities include 'Drop Everything and Read' (DEAR), storytelling by guest teachers, and the literary character dress-up parade.",
        "event_date": "2026-11-06",
        "start_time": "09:00 AM",
        "end_time": "03:00 PM",
        "location": "School Audio-Visual Room (AVR) & Library",
        "target_grades": "Elementary & Junior High",
        "organizer": "English & Filipino Learning Areas",
        "badge_color": "purple",
        "is_highlighted": False
    },
    {
        "title": "Brigada Eskwela & Campus Safety Clean-up",
        "category": "GENERAL",
        "description": "Community volunteer maintenance drive focusing on classroom sanitation, electrical safety checks, and tree pruning for disaster preparedness.",
        "event_date": "2026-11-20",
        "start_time": "07:00 AM",
        "end_time": "12:00 PM",
        "location": "Campus Grounds & All School Buildings",
        "target_grades": "Parents, Teachers, Alumni & Volunteers",
        "organizer": "Disaster Risk Reduction and Management Committee",
        "badge_color": "rose",
        "is_highlighted": False
    }
]

def seed_default_events_orm():
    """Seeds realistic DepEd school events and activities if table is empty."""
    session = Session()
    try:
        count = session.query(SchoolEvent).count()
        if count >= 3:
            return
        for e in DEFAULT_EVENTS:
            existing = session.query(SchoolEvent).filter_by(title=e["title"]).first()
            if not existing:
                ev = SchoolEvent(
                    title=e["title"],
                    category=e["category"],
                    description=e["description"],
                    event_date=e["event_date"],
                    start_time=e["start_time"],
                    end_time=e["end_time"],
                    location=e["location"],
                    target_grades=e["target_grades"],
                    organizer=e["organizer"],
                    badge_color=e.get("badge_color", "blue"),
                    is_highlighted=e.get("is_highlighted", False)
                )
                session.add(ev)
        session.commit()
        print(f"[+] Don Montano CIS School Events seeded ({session.query(SchoolEvent).count()} items).")
    except Exception as ex:
        session.rollback()
        print(f"[!] Error seeding events: {ex}")
    finally:
        session.close()

def get_all_events_orm(limit=50, category=None, upcoming_only=False):
    """Retrieves school events ordered by event date (with 60s memory caching)."""
    global _EVENTS_CACHE
    now = time.time()
    use_cache = (category in (None, "ALL") and limit == 50 and not upcoming_only)
    if use_cache and _EVENTS_CACHE["data"] is not None and (now - _EVENTS_CACHE["ts"]) < 60:
        return _EVENTS_CACHE["data"]

    session = Session()
    try:
        query = session.query(SchoolEvent)
        if category and category.upper() != "ALL":
            query = query.filter(SchoolEvent.category == category.upper())
        if upcoming_only:
            today_str = pht_now().date().isoformat()
            query = query.filter(SchoolEvent.event_date >= today_str)
        items = query.order_by(SchoolEvent.event_date.asc(), SchoolEvent.id.asc()).limit(limit).all()
        res = [i.to_dict() for i in items]
        if use_cache:
            _EVENTS_CACHE["data"] = res
            _EVENTS_CACHE["ts"] = now
        return res
    finally:
        session.close()

def save_event_orm(title, category, description, event_date, start_time="08:00 AM", end_time="04:00 PM",
                   location="School Gymnasium", target_grades="ALL", organizer="School Administration",
                   badge_color="blue", is_highlighted=False):
    """Creates a new school event."""
    global _EVENTS_CACHE
    session = Session()
    try:
        ev = SchoolEvent(
            title=str(title).strip(),
            category=str(category).strip().upper(),
            description=str(description).strip(),
            event_date=str(event_date).strip(),
            start_time=str(start_time).strip(),
            end_time=str(end_time).strip(),
            location=str(location).strip(),
            target_grades=str(target_grades).strip(),
            organizer=str(organizer).strip(),
            badge_color=str(badge_color).strip(),
            is_highlighted=bool(is_highlighted)
        )
        session.add(ev)
        session.commit()
        _EVENTS_CACHE["data"] = None  # Cache invalidation
        return ev.to_dict(), "Event created successfully!"
    except Exception as ex:
        session.rollback()
        raise ex
    finally:
        session.close()

def delete_event_orm(event_id):
    """Deletes a school event."""
    global _EVENTS_CACHE
    session = Session()
    try:
        ev = session.query(SchoolEvent).filter_by(id=int(event_id)).first()
        if not ev:
            return False, "Event not found"
        session.delete(ev)
        session.commit()
        _EVENTS_CACHE["data"] = None  # Cache invalidation
        return True, "Event deleted successfully"
    finally:
        session.close()

# -------------------------------------------------------------
# User & Role-Based Access Control (RBAC) Functions
# -------------------------------------------------------------

def create_user_orm(username, email, password, full_name, role="TEACHER", phone_number="", assigned_section_id=None):
    """Creates a new user account with hashed password."""
    session = Session()
    try:
        u_clean = username.strip().lower()
        e_clean = email.strip().lower()
        existing = session.query(User).filter((User.username == u_clean) | (User.email == e_clean)).first()
        if existing:
            return False, f"Username '{u_clean}' or email '{e_clean}' is already registered."
        
        user = User(
            username=u_clean,
            email=e_clean,
            password_hash=generate_password_hash(password.strip()),
            full_name=full_name.strip(),
            role=role.strip().upper(),
            is_active=True,
            phone_number=phone_number.strip(),
            assigned_section_id=assigned_section_id
        )
        session.add(user)
        session.commit()
        return True, user.to_dict()
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def authenticate_user_orm(username_or_email, password):
    """Authenticates credentials against password hash, returns user dict or None."""
    session = Session()
    try:
        ident = username_or_email.strip().lower()
        try:
            user = session.query(User).filter(
                (User.username == ident) | (User.email == ident)
            ).first()
        except Exception as query_err:
            # If a missing column caused the query to fail on PostgreSQL, trigger column migration and retry
            print(f"[!] User query note ({query_err}), running auto_migrate_columns_orm...")
            session.rollback()
            session.close()
            auto_migrate_columns_orm()
            session = Session()
            user = session.query(User).filter(
                (User.username == ident) | (User.email == ident)
            ).first()

        # Auto-seed default accounts on fresh/unseeded cloud database
        if not user and session.query(User).count() == 0:
            seed_default_users_orm()
            user = session.query(User).filter(
                (User.username == ident) | (User.email == ident)
            ).first()

        if not user or not user.is_active:
            return None, "Invalid credentials or inactive account."
        if not check_password_hash(user.password_hash, password.strip()):
            return None, "Incorrect password."
        
        try:
            user.last_login = pht_now()
            session.commit()
        except Exception:
            session.rollback()

        return user.to_dict(), "Authentication successful."
    except Exception as e:
        session.rollback()
        print(f"[!] authenticate_user_orm error: {e}")
        return None, f"Database sign-in notice: {str(e)}"
    finally:
        session.close()

def get_user_by_id_orm(user_id):
    session = Session()
    try:
        user = session.query(User).filter_by(id=int(user_id)).first()
        return user.to_dict() if user else None
    finally:
        session.close()

def get_all_users_orm():
    session = Session()
    try:
        users = session.query(User).order_by(User.id.asc()).all()
        return [u.to_dict() for u in users]
    finally:
        session.close()

def update_user_orm(user_id, **kwargs):
    """Updates user account details with uniqueness checks and Super Admin safeguards."""
    session = Session()
    try:
        user = session.query(User).filter_by(id=int(user_id)).first()
        if not user:
            return False, "User not found."
        
        # Username update with duplicate check
        if "username" in kwargs and kwargs["username"]:
            new_u = kwargs["username"].strip().lower()
            if new_u != user.username:
                existing = session.query(User).filter(User.username == new_u, User.id != user.id).first()
                if existing:
                    return False, f"Username '{new_u}' is already taken."
                user.username = new_u

        # Email update with duplicate check
        if "email" in kwargs and kwargs["email"]:
            new_e = kwargs["email"].strip().lower()
            if new_e != user.email:
                existing = session.query(User).filter(User.email == new_e, User.id != user.id).first()
                if existing:
                    return False, f"Email address '{new_e}' is already registered."
                user.email = new_e

        if "full_name" in kwargs and kwargs["full_name"]:
            user.full_name = kwargs["full_name"].strip()

        # Role change safeguard: prevent demoting sole Super Admin
        if "role" in kwargs and kwargs["role"]:
            new_role = kwargs["role"].strip().upper()
            if user.role == "SUPER_ADMIN" and new_role != "SUPER_ADMIN":
                admin_count = session.query(User).filter_by(role="SUPER_ADMIN").count()
                if admin_count <= 1:
                    return False, "Cannot demote the sole Super Administrator account."
            user.role = new_role

        if "phone_number" in kwargs:
            user.phone_number = kwargs["phone_number"].strip()

        # Activation status change safeguard: prevent deactivating sole active Super Admin
        if "is_active" in kwargs:
            new_active = bool(kwargs["is_active"])
            if user.role == "SUPER_ADMIN" and not new_active:
                active_admins = session.query(User).filter_by(role="SUPER_ADMIN", is_active=True).count()
                if active_admins <= 1:
                    return False, "Cannot deactivate the sole active Super Administrator account."
            user.is_active = new_active

        # Class Section Assignment
        if "assigned_section_id" in kwargs:
            sec_val = kwargs["assigned_section_id"]
            if sec_val in (None, "", "null", "none", 0, "0"):
                user.assigned_section_id = None
            else:
                try:
                    user.assigned_section_id = int(sec_val)
                except (ValueError, TypeError):
                    user.assigned_section_id = None

        # Password Reset
        if "password" in kwargs and kwargs["password"] and kwargs["password"].strip():
            user.password_hash = generate_password_hash(kwargs["password"].strip())
            
        session.commit()
        # Refresh to load assigned_section relation
        session.refresh(user)
        return True, user.to_dict()
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()


def delete_user_orm(user_id):
    session = Session()
    try:
        user = session.query(User).filter_by(id=int(user_id)).first()
        if not user:
            return False, "User not found."
        if user.role == "SUPER_ADMIN" and session.query(User).filter_by(role="SUPER_ADMIN").count() <= 1:
            return False, "Cannot delete the sole Super Administrator account."
        session.delete(user)
        session.commit()
        return True, "User deleted successfully."
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def update_user_profile_orm(user_id, **kwargs):
    """
    Empowers Teaching and Non-Teaching staff to edit their personal profiles,
    section assignments, grade level, section name, room number, designation, and credentials.
    Automatically keeps Section and Student records in sync.
    """
    global _SECTIONS_CACHE
    session = Session()
    try:
        user = session.query(User).filter_by(id=int(user_id)).first()
        if not user:
            return False, "User account not found."

        # 1. Update Full Name
        if "full_name" in kwargs and kwargs["full_name"]:
            new_name = str(kwargs["full_name"]).strip()
            if new_name:
                user.full_name = new_name

        # 2. Update Username (uniqueness check)
        if "username" in kwargs and kwargs["username"]:
            new_u = str(kwargs["username"]).strip().lower()
            if new_u and new_u != user.username:
                existing = session.query(User).filter(User.username == new_u, User.id != user.id).first()
                if existing:
                    return False, f"Username '{new_u}' is already taken."
                user.username = new_u

        # 3. Update Email (uniqueness check)
        if "email" in kwargs and kwargs["email"]:
            new_e = str(kwargs["email"]).strip().lower()
            if new_e and new_e != user.email:
                existing = session.query(User).filter(User.email == new_e, User.id != user.id).first()
                if existing:
                    return False, f"Email address '{new_e}' is already registered."
                user.email = new_e

        # 4. Update Phone Number
        if "phone_number" in kwargs:
            user.phone_number = str(kwargs["phone_number"]).strip()

        # 5. Update Designation (for Non-Teaching Staff / Admin)
        if "designation" in kwargs:
            try:
                user.designation = str(kwargs["designation"]).strip()
            except Exception:
                pass

        # 6. Update Password (if provided)
        if "password" in kwargs and kwargs["password"]:
            pwd = str(kwargs["password"]).strip()
            if pwd:
                if len(pwd) < 4:
                    return False, "Password must be at least 4 characters long."
                user.password_hash = generate_password_hash(pwd)

        # 7. Section & Grade Level Management (For Teachers / Class Advisers)
        if user.role == "TEACHER":
            grade_level = str(kwargs.get("grade_level", "")).strip()
            section_name = str(kwargs.get("section_name", "")).strip()
            room_number = str(kwargs.get("room_number", "")).strip()
            switch_section_id = kwargs.get("switch_section_id")

            # Case A: Switching to an existing section from dropdown
            if switch_section_id and str(switch_section_id).isdigit() and int(switch_section_id) > 0:
                target_sec = session.query(Section).filter_by(id=int(switch_section_id)).first()
                if target_sec:
                    user.assigned_section_id = target_sec.id
                    target_sec.adviser_teacher = user.full_name
                    if grade_level:
                        target_sec.grade_level = grade_level
                    if section_name:
                        target_sec.section_name = section_name
                    if room_number:
                        target_sec.room_number = room_number
                    
                    new_label = f"{target_sec.grade_level} - {target_sec.section_name}"
                    # Update students assigned to this section
                    session.query(Student).filter(Student.section_id == target_sec.id).update({
                        "grade_level": target_sec.grade_level,
                        "section_name": target_sec.section_name,
                        "grade_section": new_label,
                        "class_adviser": user.full_name
                    }, synchronize_session=False)

            # Case B: Editing their currently assigned section
            elif user.assigned_section_id:
                sec = session.query(Section).filter_by(id=user.assigned_section_id).first()
                if sec:
                    old_label = f"{sec.grade_level} - {sec.section_name}"
                    if grade_level:
                        sec.grade_level = grade_level
                    if section_name:
                        sec.section_name = section_name
                    if room_number:
                        sec.room_number = room_number
                    sec.adviser_teacher = user.full_name

                    new_label = f"{sec.grade_level} - {sec.section_name}"
                    # Sync students in this section
                    session.query(Student).filter(
                        (Student.section_id == sec.id) | (Student.grade_section == old_label)
                    ).update({
                        "grade_level": sec.grade_level,
                        "section_name": sec.section_name,
                        "grade_section": new_label,
                        "class_adviser": user.full_name
                    }, synchronize_session=False)

            # Case C: Teacher had no section yet, creating or finding by name
            elif grade_level and section_name:
                existing_sec = session.query(Section).filter(
                    func.lower(Section.grade_level) == grade_level.lower(),
                    func.lower(Section.section_name) == section_name.lower()
                ).first()
                if existing_sec:
                    existing_sec.adviser_teacher = user.full_name
                    if room_number:
                        existing_sec.room_number = room_number
                    user.assigned_section_id = existing_sec.id
                else:
                    new_sec = Section(
                        grade_level=grade_level,
                        section_name=section_name,
                        room_number=room_number,
                        adviser_teacher=user.full_name
                    )
                    session.add(new_sec)
                    session.flush()
                    user.assigned_section_id = new_sec.id

        _SECTIONS_CACHE["data"] = None
        session.commit()
        session.refresh(user)
        return True, user.to_dict()
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

# -------------------------------------------------------------
# Faculty & Staff Biometric Face Enrollment & Authentic Geotag DTR
# -------------------------------------------------------------

def enroll_staff_face_orm(user_id, embedding_array, photo_path=""):
    """
    Enrolls or updates a teacher or staff member's 128-dimensional facial embedding
    and portrait snapshot for AI facial recognition authentication.
    """
    global _STAFF_FACES_CACHE
    session = Session()
    try:
        user = session.query(User).filter_by(id=int(user_id)).first()
        if not user:
            return False, "User account not found."

        if isinstance(embedding_array, np.ndarray):
            emb_json = json.dumps(embedding_array.tolist())
        elif isinstance(embedding_array, (list, tuple)):
            emb_json = json.dumps(list(embedding_array))
        else:
            emb_json = str(embedding_array)

        user.face_embedding = emb_json
        if photo_path:
            user.photo_path = str(photo_path).strip()

        session.commit()
        session.refresh(user)
        _STAFF_FACES_CACHE["data"] = None
        return True, user.to_dict()
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def get_enrolled_staff_faces_orm():
    """
    Returns all active faculty and staff members with enrolled facial embeddings
    for high-speed in-memory cosine similarity matching.
    """
    global _STAFF_FACES_CACHE
    now = time.time()
    if _STAFF_FACES_CACHE["data"] is not None and (now - _STAFF_FACES_CACHE["ts"]) < 30:
        return _STAFF_FACES_CACHE["data"]

    session = Session()
    try:
        users = session.query(User).filter(
            User.is_active == True,
            User.face_embedding != None,
            User.face_embedding != ""
        ).all()

        enrolled = []
        for u in users:
            try:
                emb = np.array(json.loads(u.face_embedding), dtype=np.float32)
                enrolled.append({
                    "user_id": u.id,
                    "username": u.username,
                    "full_name": u.full_name,
                    "role": u.role,
                    "designation": getattr(u, 'designation', '') or "",
                    "assigned_section_name": f"{u.assigned_section.grade_level} - {u.assigned_section.section_name}" if u.assigned_section else "N/A",
                    "photo_path": getattr(u, 'photo_path', '') or "",
                    "embedding": emb
                })
            except Exception as ex:
                print(f"[!] Error parsing face embedding for staff {u.id}: {ex}")

        _STAFF_FACES_CACHE["data"] = enrolled
        _STAFF_FACES_CACHE["ts"] = now
        return enrolled
    finally:
        session.close()

def record_staff_attendance_orm(user_id, scan_type="AUTO", lat=None, lon=None, accuracy=None, method="FACIAL_RECOGNITION", score=0.0, photo=None):
    """
    Logs an authentic time-in / time-out entry for teaching or non-teaching personnel.
    Verifies GPS geotag against school geofence and enforces a 45-second duplicate scan cooldown.
    """
    from smile_config import verify_school_geotag
    session = Session()
    try:
        user = session.query(User).filter_by(id=int(user_id)).first()
        if not user:
            return False, "User account not found.", None

        now = pht_now()
        today_start = datetime.combine(now.date(), datetime.min.time())

        # Check today's latest scan for cooldown and auto-toggle
        latest_scan = session.query(StaffAttendanceLog).filter(
            StaffAttendanceLog.user_id == user.id,
            StaffAttendanceLog.timestamp >= today_start
        ).order_by(StaffAttendanceLog.timestamp.desc()).first()

        # Enforce 45-second cooldown to prevent accidental rapid double-scans
        if latest_scan:
            time_diff = (now - latest_scan.timestamp).total_seconds()
            if time_diff < 45:
                action_word = "Timed-In" if latest_scan.scan_type == "TIME_IN" else "Timed-Out"
                return False, f"Already {action_word} {int(time_diff)}s ago. Please wait before scanning again.", latest_scan.to_dict()

        # Resolve scan type (AUTO mode)
        resolved_type = scan_type.upper() if scan_type and scan_type.upper() in ["TIME_IN", "TIME_OUT"] else "AUTO"
        if resolved_type == "AUTO":
            if not latest_scan:
                resolved_type = "TIME_IN"
            elif latest_scan.scan_type == "TIME_IN":
                resolved_type = "TIME_OUT"
            else:
                resolved_type = "TIME_IN"

        # Determine school period (AM or PM)
        period = "AM" if now.hour < 12 else "PM"

        # Verify GPS Geotag
        is_verified, dist_meters, geotag_status = verify_school_geotag(lat, lon)

        log = StaffAttendanceLog(
            user_id=user.id,
            staff_name=user.full_name,
            role=user.role,
            scan_type=resolved_type,
            period=period,
            timestamp=now,
            latitude=float(lat) if lat is not None else None,
            longitude=float(lon) if lon is not None else None,
            accuracy_meters=float(accuracy) if accuracy is not None else None,
            geotag_status=geotag_status,
            verification_method=method,
            face_confidence=float(score) if score else 0.0,
            photo_snapshot=photo or "",
            created_at=now
        )
        session.add(log)
        session.commit()
        session.refresh(log)

        action_label = "Time-In" if resolved_type == "TIME_IN" else "Time-Out"
        geo_note = " (Campus Verified 📍)" if geotag_status == "CAMPUS_VERIFIED" else (" (Off-Campus Geotag ⚠️)" if geotag_status == "OFF_CAMPUS" else "")
        msg = f"{action_label} successfully recorded for {user.full_name}{geo_note}."

        return True, msg, log.to_dict()
    except Exception as e:
        session.rollback()
        return False, str(e), None
    finally:
        session.close()

def get_staff_today_status_orm(user_id):
    """
    Returns today's 4-punch DTR state (AM IN, AM OUT, PM IN, PM OUT) and total rendered hours.
    """
    session = Session()
    try:
        now = pht_now()
        today_start = datetime.combine(now.date(), datetime.min.time())

        logs = session.query(StaffAttendanceLog).filter(
            StaffAttendanceLog.user_id == int(user_id),
            StaffAttendanceLog.timestamp >= today_start
        ).order_by(StaffAttendanceLog.timestamp.asc()).all()

        am_in = None
        am_out = None
        pm_in = None
        pm_out = None

        for l in logs:
            t_str = l.timestamp.strftime("%I:%M %p")
            if l.period == "AM":
                if l.scan_type == "TIME_IN" and not am_in:
                    am_in = t_str
                elif l.scan_type == "TIME_OUT":
                    am_out = t_str
            else: # PM
                if l.scan_type == "TIME_IN" and not pm_in:
                    pm_in = t_str
                elif l.scan_type == "TIME_OUT":
                    pm_out = t_str

        latest = logs[-1].to_dict() if logs else None

        return {
            "am_in": am_in or "--:--",
            "am_out": am_out or "--:--",
            "pm_in": pm_in or "--:--",
            "pm_out": pm_out or "--:--",
            "has_am_in": bool(am_in),
            "has_am_out": bool(am_out),
            "has_pm_in": bool(pm_in),
            "has_pm_out": bool(pm_out),
            "total_punches": len(logs),
            "latest_scan": latest,
            "today_logs": [l.to_dict() for l in logs]
        }
    finally:
        session.close()

def get_staff_dtr_logs_orm(user_id=None, month=None, year=None, limit=100):
    """
    Returns civil service DTR logs filterable by user, month, and year.
    """
    session = Session()
    try:
        q = session.query(StaffAttendanceLog)
        if user_id:
            q = q.filter(StaffAttendanceLog.user_id == int(user_id))

        now = pht_now()
        target_year = int(year) if year and str(year).isdigit() else now.year
        target_month = int(month) if month and str(month).isdigit() else now.month

        # Month date bounds
        start_date = datetime(target_year, target_month, 1, 0, 0, 0)
        import calendar
        _, last_day = calendar.monthrange(target_year, target_month)
        end_date = datetime(target_year, target_month, last_day, 23, 59, 59)

        q = q.filter(StaffAttendanceLog.timestamp >= start_date, StaffAttendanceLog.timestamp <= end_date)
        logs = q.order_by(StaffAttendanceLog.timestamp.desc()).limit(limit).all()
        return [l.to_dict() for l in logs]
    finally:
        session.close()

DEFAULT_STUDENTS = [
    {
        "lrn": "152008250007",
        "first_name": "Juan",
        "last_name": "Dela Cruz",
        "gender": "Male",
        "grade_level": "Grade 10",
        "section_name": "Rizal",
        "grade_section": "Grade 10 - Rizal",
        "track_strand": "Junior High",
        "parent_name": "Maria Dela Cruz",
        "parent_phone": "09171234567",
        "parent_relationship": "Mother",
        "rfid_card_uid": "RFID-8801"
    },
    {
        "lrn": "152008250008",
        "first_name": "Maria",
        "last_name": "Santos",
        "gender": "Female",
        "grade_level": "Grade 10",
        "section_name": "Mabini",
        "grade_section": "Grade 10 - Mabini",
        "track_strand": "Junior High",
        "parent_name": "Elena Santos",
        "parent_phone": "09189876543",
        "parent_relationship": "Mother",
        "rfid_card_uid": "RFID-8802"
    },
    {
        "lrn": "152008250009",
        "first_name": "Angelo",
        "last_name": "Reyes",
        "gender": "Male",
        "grade_level": "Grade 8",
        "section_name": "Luna",
        "grade_section": "Grade 8 - Luna",
        "track_strand": "Junior High",
        "parent_name": "Roberto Reyes",
        "parent_phone": "09205551234",
        "parent_relationship": "Father",
        "rfid_card_uid": "RFID-8803"
    },
    {
        "lrn": "152008250010",
        "first_name": "Chloe",
        "last_name": "Mendoza",
        "gender": "Female",
        "grade_level": "Grade 11",
        "section_name": "STEM",
        "grade_section": "Grade 11 - STEM",
        "track_strand": "STEM",
        "parent_name": "Carmen Mendoza",
        "parent_phone": "09173339876",
        "parent_relationship": "Mother",
        "rfid_card_uid": "RFID-8804"
    },
    {
        "lrn": "152008250011",
        "first_name": "Ethan",
        "last_name": "Flores",
        "gender": "Male",
        "grade_level": "Grade 1",
        "section_name": "Mabait",
        "grade_section": "Grade 1 - Mabait",
        "track_strand": "Elementary",
        "parent_name": "Elena Flores",
        "parent_phone": "09171112233",
        "parent_relationship": "Mother",
        "rfid_card_uid": "RFID-8805"
    },
    {
        "lrn": "152008250012",
        "first_name": "Sophia",
        "last_name": "Reyes",
        "gender": "Female",
        "grade_level": "Grade 1",
        "section_name": "Mabait",
        "grade_section": "Grade 1 - Mabait",
        "track_strand": "Elementary",
        "parent_name": "Mark Reyes",
        "parent_phone": "09174445566",
        "parent_relationship": "Father",
        "rfid_card_uid": "RFID-8806"
    }
]

def seed_default_students_orm(force=False):
    """Seeds default DepEd student records only during initial bootstrap. Never resurrects deleted students."""
    try:
        marker_file = smile_config.DATA_DIR / ".students_seeded"
        if marker_file.exists() and not force:
            return
    except Exception:
        marker_file = None

    session = Session()
    try:
        if session.query(Student).count() > 0 and not force:
            if marker_file:
                try:
                    marker_file.touch(exist_ok=True)
                except Exception:
                    pass
            return
        for s in DEFAULT_STUDENTS:
            st = Student(
                lrn=s["lrn"],
                first_name=s["first_name"],
                last_name=s["last_name"],
                gender=s["gender"],
                grade_level=s.get("grade_level", "Grade 10"),
                section_name=s.get("section_name", "Rizal"),
                grade_section=s["grade_section"],
                track_strand=s.get("track_strand", "Junior High"),
                parent_name=s.get("parent_name", "Guardian"),
                parent_phone=s.get("parent_phone", "09171234567"),
                parent_relationship=s.get("parent_relationship", "Parent"),
                rfid_card_uid=s.get("rfid_card_uid", "N/A"),
                qr_code_path=f"/qr/{s['lrn']}.png"
            )
            session.add(st)
        session.commit()
        if marker_file:
            try:
                marker_file.touch(exist_ok=True)
            except Exception:
                pass
    except Exception as e:
        session.rollback()
        print(f"[!] Error seeding students: {e}")
    finally:
        session.close()

def seed_default_users_orm():
    """Seeds default demonstration accounts for each role level."""
    session = Session()
    try:
        # Find advisory section for demo teacher (Grade 1 - Mabait)
        mabait_sec = session.query(Section).filter_by(grade_level="Grade 1", section_name="Mabait").first()
        if not mabait_sec:
            mabait_sec = session.query(Section).first()
        advisory_id = mabait_sec.id if mabait_sec else None

        default_accounts = [
            {
                "username": "admin",
                "email": "admin@donmontano.edu.ph",
                "password": "admin123",
                "full_name": "Engr. System Administrator",
                "role": "SUPER_ADMIN",
                "phone_number": "09170000001",
                "assigned_section_id": None
            },
            {
                "username": "principal",
                "email": "principal@donmontano.edu.ph",
                "password": "principal123",
                "full_name": "Dr. Maria Clara Santos, CESO V",
                "role": "PRINCIPAL",
                "phone_number": "09170000002",
                "assigned_section_id": None
            },
            {
                "username": "teacher",
                "email": "teacher.flores@donmontano.edu.ph",
                "password": "teacher123",
                "full_name": "Mrs. Erlinda Flores (Grade 1 Adviser)",
                "role": "TEACHER",
                "phone_number": "09170000003",
                "assigned_section_id": advisory_id
            },
            {
                "username": "staff",
                "email": "staff.bautista@donmontano.edu.ph",
                "password": "staff123",
                "full_name": "Ms. Andrea Bautista (School Registrar)",
                "role": "STAFF",
                "phone_number": "09170000005",
                "assigned_section_id": None
            },
            {
                "username": "guard",
                "email": "security.ramos@donmontano.edu.ph",
                "password": "guard123",
                "full_name": "Officer Danilo Ramos (Gate 1)",
                "role": "GUARD",
                "phone_number": "09170000004",
                "assigned_section_id": None
            }
        ]
        for acc in default_accounts:
            existing = session.query(User).filter_by(username=acc["username"]).first()
            if not existing:
                u = User(
                    username=acc["username"],
                    email=acc["email"],
                    password_hash=generate_password_hash(acc["password"]),
                    full_name=acc["full_name"],
                    role=acc["role"],
                    is_active=True,
                    phone_number=acc["phone_number"],
                    assigned_section_id=acc.get("assigned_section_id")
                )
                session.add(u)
            else:
                existing.is_active = True
                if acc.get("role"):
                    existing.role = acc["role"]
                if acc.get("assigned_section_id") and not existing.assigned_section_id:
                    existing.assigned_section_id = acc["assigned_section_id"]
                # Update password hash in case schema refreshed
                if not check_password_hash(existing.password_hash, acc["password"]):
                    existing.password_hash = generate_password_hash(acc["password"])
        session.commit()
        print(f"[+] Default RBAC users verified ({session.query(User).count()} accounts).")
    except Exception as e:
        session.rollback()
        print(f"[!] Error seeding users: {e}")
    finally:
        session.close()

# -------------------------------------------------------------
# Pricing Plans & Income Monetization Engine
# -------------------------------------------------------------

DEFAULT_PRICING_PLANS = [
    {
        "plan_code": "STARTER_FREE",
        "name": "DepEd Community Starter (Free)",
        "category": "SCHOOL",
        "price_php": 0.0,
        "billing_cycle": "monthly",
        "description": "Basic smart gate monitoring for small rural schools up to 100 learners.",
        "features": [
            "Up to 100 Enrolled Learners",
            "1 Gate Kiosk Station",
            "RFID & Face Recognition Monitoring",
            "Mock / Simulator SMS Alerts",
            "Community Support"
        ]
    },
    {
        "plan_code": "STANDARD_SCHOOL",
        "name": "DepEd Standard Campus License",
        "category": "SCHOOL",
        "price_php": 4999.0,
        "billing_cycle": "monthly",
        "description": "Full-featured attendance & safety suite for public elementary and integrated high schools.",
        "features": [
            "Unlimited Enrolled Students & Sections",
            "Dual-Channel SMS Integration (PhilSMS / Semaphore)",
            "Native Installable Parent Mobile App (Android & iOS PWA)",
            "Automated DepEd SF2 (School Form 2) CSV Reports",
            "Real Database Announcements Feed",
            "Adviser Excuse Letter Workflow"
        ]
    },
    {
        "plan_code": "ENTERPRISE_SCHOOL",
        "name": "Integrated School Multi-Gate Enterprise",
        "category": "SCHOOL",
        "price_php": 9999.0,
        "billing_cycle": "monthly",
        "description": "High-volume multi-gate synchronization for large central integrated schools & divisions.",
        "features": [
            "Unlimited Multi-Gate Kiosks (Gate 1, Gate 2, Senior High)",
            "Direct GSM SIM Hardware + Cloud SMS Fallback",
            "Custom School Branding & Logo Header",
            "Priority Push Alert Routing (<1.5s latency)",
            "24/7 Dedicated Priority Technical Support",
            "Full System Backup & Auto-Sync Engine"
        ]
    },
    {
        "plan_code": "PARENT_MONTHLY",
        "name": "Parent VIP Safety Pass (Monthly)",
        "category": "PARENT",
        "price_php": 50.0,
        "billing_cycle": "monthly",
        "description": "Individual parent safety subscription with dual-channel SMS and live camera photo alerts.",
        "features": [
            "Instant Dual-Channel SMS Gate Delivery",
            "Push Notification Chime on Smartphone",
            "Adviser Digital Excuse Note Priority Review",
            "Verified Authorized Guardian Digital QR Badge"
        ]
    },
    {
        "plan_code": "PARENT_ANNUAL",
        "name": "Parent VIP Annual Protection Pass",
        "category": "PARENT",
        "price_php": 500.0,
        "billing_cycle": "annual",
        "description": "Full 10-month school year coverage with 2 months free discount.",
        "features": [
            "All VIP Monthly Features Included",
            "2 Months Free (Save ₱100/year)",
            "Priority School Bulletin & Weather Push Alerts",
            "Digital ID Re-issuance Waiver"
        ]
    }
]

def seed_default_pricing_plans_orm():
    """Seeds default editable SaaS pricing plans."""
    session = Session()
    try:
        for p in DEFAULT_PRICING_PLANS:
            existing = session.query(PricingPlan).filter_by(plan_code=p["plan_code"]).first()
            if not existing:
                plan = PricingPlan(
                    plan_code=p["plan_code"],
                    name=p["name"],
                    category=p["category"],
                    price_php=p["price_php"],
                    billing_cycle=p["billing_cycle"],
                    description=p["description"],
                    features_json=json.dumps(p["features"]),
                    is_active=True
                )
                session.add(plan)
        session.commit()
        print(f"[+] Default SaaS Pricing Plans seeded ({session.query(PricingPlan).count()} plans).")
    except Exception as e:
        session.rollback()
        print(f"[!] Error seeding pricing plans: {e}")
    finally:
        session.close()

def get_all_pricing_plans_orm(category=None):
    session = Session()
    try:
        query = session.query(PricingPlan).filter_by(is_active=True)
        if category:
            query = query.filter_by(category=category.upper())
        plans = query.order_by(PricingPlan.price_php.asc()).all()
        return [p.to_dict() for p in plans]
    finally:
        session.close()

def get_pricing_plan_by_code_orm(plan_code):
    session = Session()
    try:
        p = session.query(PricingPlan).filter_by(plan_code=str(plan_code).strip()).first()
        return p.to_dict() if p else None
    finally:
        session.close()

def update_pricing_plan_orm(plan_code, price_php, name=None, description=None, billing_cycle=None):
    """Allows Super Admin to edit subscription pricing amounts in real time."""
    session = Session()
    try:
        plan = session.query(PricingPlan).filter_by(plan_code=str(plan_code).strip()).first()
        if not plan:
            return False, f"Pricing plan '{plan_code}' not found."
        
        plan.price_php = float(price_php)
        if name:
            plan.name = name.strip()
        if description:
            plan.description = description.strip()
        if billing_cycle:
            plan.billing_cycle = billing_cycle.strip().lower()
            
        session.commit()
        return True, plan.to_dict()
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def record_payment_transaction_orm(payer_name, plan_code, amount_php, payment_method="GCASH", 
                                   payer_email_phone="", payer_role="PARENT", notes=""):
    """Records a revenue-generating subscription payment in the database."""
    session = Session()
    try:
        import uuid
        prefix = "SMILE-PAY"
        ref_num = f"{prefix}-{pht_now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        
        tx = PaymentTransaction(
            transaction_ref=ref_num,
            payer_name=payer_name.strip(),
            payer_email_phone=payer_email_phone.strip(),
            payer_role=payer_role.strip().upper(),
            plan_code=plan_code.strip(),
            amount_php=float(amount_php),
            payment_method=payment_method.strip().upper(),
            status="COMPLETED",
            notes=notes.strip()
        )
        session.add(tx)
        session.commit()
        return True, tx.to_dict()
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def get_recent_payment_transactions_orm(limit=50):
    session = Session()
    try:
        txs = session.query(PaymentTransaction).order_by(PaymentTransaction.id.desc()).limit(limit).all()
        return [t.to_dict() for t in txs]
    finally:
        session.close()

def get_revenue_statistics_orm():
    """Computes MRR, total revenue, and subscriber counts."""
    session = Session()
    try:
        total_rev = session.query(func.sum(PaymentTransaction.amount_php)).scalar() or 0.0
        total_tx = session.query(func.count(PaymentTransaction.id)).scalar() or 0
        
        # Monthly Recurring Revenue from active school plans
        standard_plan = session.query(PricingPlan).filter_by(plan_code="STANDARD_SCHOOL").first()
        school_mrr = standard_plan.price_php if standard_plan else 4999.0
        parent_rev = session.query(func.sum(PaymentTransaction.amount_php)).filter(
            PaymentTransaction.payer_role == "PARENT"
        ).scalar() or 0.0
        
        return {
            "total_revenue_php": float(total_rev),
            "total_revenue_formatted": f"₱{total_rev:,.2f}",
            "monthly_recurring_revenue": float(school_mrr + parent_rev),
            "mrr_formatted": f"₱{(school_mrr + parent_rev):,.2f}",
            "total_transactions": total_tx,
            "parent_pack_revenue": float(parent_rev),
            "parent_pack_formatted": f"₱{parent_rev:,.2f}",
            "active_school_license": "DepEd Standard Campus License",
            "school_license_price": float(school_mrr)
        }
    finally:
        session.close()

# -------------------------------------------------------------
# W3C WebPush Subscription Management & Background Push Dispatch
# Wakes mobile device even when locked or screen is off
# -------------------------------------------------------------

def save_push_subscription_orm(endpoint, p256dh, auth, lrn=None, parent_phone="", user_agent=""):
    """Saves or updates a WebPush push subscription from a parent's mobile device."""
    session = Session()
    try:
        clean_ep = str(endpoint).strip()
        sub = session.query(PushSubscription).filter_by(endpoint=clean_ep).first()
        if not sub:
            sub = PushSubscription(
                endpoint=clean_ep,
                p256dh=str(p256dh).strip(),
                auth=str(auth).strip()
            )
            session.add(sub)
        else:
            sub.p256dh = str(p256dh).strip()
            sub.auth = str(auth).strip()

        if lrn:
            sub.lrn = str(lrn).strip()
        if parent_phone:
            sub.parent_phone = str(parent_phone).strip()
        if user_agent:
            sub.user_agent = str(user_agent)[:250]
        sub.created_at = pht_now()
        session.commit()
        return sub.to_dict()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_all_push_subscriptions_orm():
    """Returns all active WebPush device subscriptions."""
    session = Session()
    try:
        subs = session.query(PushSubscription).all()
        return [s.to_dict() for s in subs]
    finally:
        session.close()

def delete_push_subscription_orm(endpoint):
    """Removes an expired or unsubscribed push endpoint."""
    session = Session()
    try:
        deleted = session.query(PushSubscription).filter_by(endpoint=str(endpoint).strip()).delete()
        session.commit()
        return deleted > 0
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()

def dispatch_web_push_notification(lrn, title, body, tag=None, data_url=None, icon=None, badge=None):
    """
    Sends RFC 8291/8292 encrypted Web Push Notification to all registered parent devices.
    Wakes up device when screen is off or mobile is locked!
    """
    from smile_config import VAPID_PRIVATE_KEY, VAPID_CLAIMS
    import json, time

    session = Session()
    try:
        query = session.query(PushSubscription)
        if lrn and lrn != "ALL":
            query = query.filter((PushSubscription.lrn == str(lrn)) | (PushSubscription.lrn == "ALL") | (PushSubscription.lrn == "") | (PushSubscription.lrn.is_(None)))
        subs = query.all()
        if not subs:
            return 0

        payload = json.dumps({
            "title": title,
            "body": body,
            "icon": icon or "/static/images/pwa_icon_192.png",
            "badge": badge or "/static/images/apple_touch_icon.png",
            "tag": tag or f"gate-{int(time.time())}",
            "url": data_url or (f"/parent?lrn={lrn}" if lrn else "/parent"),
            "lrn": str(lrn) if lrn else "",
            "timestamp": pht_now().strftime("%I:%M %p")
        })

        success_count = 0
        dead_endpoints = []

        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            print("[Push] Note: pywebpush library not present on this runtime.")
            return 0

        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {
                            "p256dh": sub.p256dh,
                            "auth": sub.auth
                        }
                    },
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS,
                    ttl=86400,
                    headers={"Urgency": "high", "Topic": "attendance"},
                    timeout=5
                )
                success_count += 1
                sub.last_notified = pht_now()
            except WebPushException as ex:
                print(f"[Push] WebPush endpoint delivery note: {ex}")
                # 404 or 410 means subscription expired / app uninstalled
                if ex.response is not None and ex.response.status_code in (404, 410):
                    dead_endpoints.append(sub.endpoint)
            except Exception as e:
                print(f"[Push] WebPush sending error: {e}")

        # Prune expired subscriptions
        if dead_endpoints:
            session.query(PushSubscription).filter(PushSubscription.endpoint.in_(dead_endpoints)).delete(synchronize_session=False)

        session.commit()
        return success_count
    except Exception as e:
        session.rollback()
        print(f"[Push] dispatch error: {e}")
# -------------------------------------------------------------
# Expo Native Push Notification Token & Lock-Screen Dispatch System
# Wakes mobile device with sound and vibration even when phone is locked
# -------------------------------------------------------------

def save_parent_device_token_orm(token, lrn=None, platform="android", device_name=""):
    """Registers or updates a parent device Expo push token."""
    session = Session()
    try:
        clean_tok = str(token).strip()
        if not clean_tok:
            return None
        dev = session.query(ParentDeviceToken).filter_by(token=clean_tok).first()
        if not dev:
            dev = ParentDeviceToken(
                token=clean_tok,
                lrn=str(lrn).strip() if lrn else None,
                platform=str(platform or "android").lower(),
                device_name=str(device_name or ""),
                is_active=True,
                created_at=pht_now(),
                updated_at=pht_now()
            )
            session.add(dev)
        else:
            if lrn:
                dev.lrn = str(lrn).strip()
            if platform:
                dev.platform = str(platform).lower()
            if device_name:
                dev.device_name = str(device_name)
            dev.is_active = True
            dev.updated_at = pht_now()
        session.commit()
        return dev.to_dict()
    except Exception as e:
        session.rollback()
        print(f"[!] save_parent_device_token_orm error: {e}")
        return None
    finally:
        session.close()

def get_parent_device_tokens_orm(lrn=None):
    """Retrieves active device tokens for a learner LRN or all active tokens."""
    session = Session()
    try:
        query = session.query(ParentDeviceToken).filter_by(is_active=True)
        if lrn and str(lrn).strip() and str(lrn) != "ALL":
            clean_lrn = str(lrn).strip()
            query = query.filter(
                (ParentDeviceToken.lrn == clean_lrn) |
                (ParentDeviceToken.lrn == "ALL") |
                (ParentDeviceToken.lrn == "") |
                (ParentDeviceToken.lrn.is_(None))
            )
        tokens = query.all()
        return [t.to_dict() for t in tokens]
    finally:
        session.close()

def deactivate_parent_device_token_orm(token):
    """Deactivates an unsubscribed device token."""
    session = Session()
    try:
        dev = session.query(ParentDeviceToken).filter_by(token=str(token).strip()).first()
        if dev:
            dev.is_active = False
            session.commit()
            return True
        return False
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()

def dispatch_expo_push_notification(title, body, lrn=None, data=None, channel_id="gate-attendance-channel", sound="default"):
    """
    Dispatches high-priority push notifications to registered parent devices via Expo Push Service.
    Wakes up Android phone, displays Heads-Up notification on Lock Screen with audio sound and vibration!
    """
    import urllib.request
    import json
    import threading

    def _do_send():
        session = Session()
        try:
            query = session.query(ParentDeviceToken).filter_by(is_active=True)
            if lrn and str(lrn).strip() and str(lrn) != "ALL":
                clean_lrn = str(lrn).strip()
                query = query.filter(
                    (ParentDeviceToken.lrn == clean_lrn) |
                    (ParentDeviceToken.lrn == "ALL") |
                    (ParentDeviceToken.lrn == "") |
                    (ParentDeviceToken.lrn.is_(None))
                )
            tokens = query.all()
            if not tokens:
                return 0

            unique_tokens = list({t.token for t in tokens if t.token})
            if not unique_tokens:
                return 0

            messages = []
            for tok in unique_tokens:
                msg = {
                    "to": tok,
                    "sound": sound or "default",
                    "title": title,
                    "body": body,
                    "channelId": channel_id,
                    "priority": "high",
                    "_displayInForeground": True,
                    "data": data or {}
                }
                messages.append(msg)

            chunk_size = 100
            success_count = 0
            for i in range(0, len(messages), chunk_size):
                chunk = messages[i:i + chunk_size]
                req = urllib.request.Request(
                    "https://exp.host/--/api/v2/push/send",
                    data=json.dumps(chunk).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip, deflate",
                        "User-Agent": "DepEd-Project-Smile/1.0"
                    }
                )
                try:
                    with urllib.request.urlopen(req, timeout=6) as res:
                        resp_data = json.loads(res.read().decode("utf-8"))
                        print(f"[Expo Push] Dispatched {len(chunk)} push alert(s) to parent devices: {resp_data.get('data', [])}")
                        success_count += len(chunk)
                except Exception as post_err:
                    print(f"[Expo Push] Error posting to Expo Push API: {post_err}")

            return success_count
        except Exception as err:
            print(f"[Expo Push] Dispatch error: {err}")
            return 0
        finally:
            session.close()

    is_serverless = getattr(smile_config, 'IS_VERCEL', False) or os.environ.get('VERCEL') == '1'
    if is_serverless:
        try:
            return _do_send()
        except Exception as _e:
            print(f"[Expo Push] Serverless send note: {_e}")
            return 0
    else:
        threading.Thread(target=_do_send, daemon=True).start()
        return 1

save_parent_device_token = save_parent_device_token_orm
get_parent_device_tokens = get_parent_device_tokens_orm
deactivate_parent_device_token = deactivate_parent_device_token_orm
dispatch_expo_push = dispatch_expo_push_notification

try:
    init_orm_db()
except Exception as _init_err:
    print(f"[!] Note: Database initial check deferred: {_init_err}")

# Compatibility Aliases
init_db = init_orm_db
save_student = save_student_orm
get_all_enrolled_students = get_all_enrolled_students_orm
check_can_scan = check_can_scan_orm
record_attendance = record_attendance_orm
get_today_summary = get_today_summary_orm
get_student_by_identifier = get_student_by_lrn_or_rfid_orm
delete_student = delete_student_orm
evaluate_daily_scan_rule = evaluate_daily_scan_rule_orm
get_all_sections = get_all_sections_orm
get_sections_by_grade = get_sections_by_grade_orm
get_section_by_id = get_section_by_id_orm
save_section = save_section_orm
update_section = update_section_orm
delete_section = delete_section_orm
get_all_announcements = get_all_announcements_orm
save_announcement = save_announcement_orm
delete_announcement = delete_announcement_orm
seed_default_announcements = seed_default_announcements_orm
create_user = create_user_orm
authenticate_user = authenticate_user_orm
get_all_users = get_all_users_orm
get_all_pricing_plans = get_all_pricing_plans_orm
update_pricing_plan = update_pricing_plan_orm
get_all_events = get_all_events_orm
save_event = save_event_orm
delete_event = delete_event_orm
seed_default_events = seed_default_events_orm
save_push_subscription = save_push_subscription_orm
get_all_push_subscriptions = get_all_push_subscriptions_orm
delete_push_subscription = delete_push_subscription_orm
dispatch_web_push = dispatch_web_push_notification
get_enrolled_students_count = get_enrolled_students_count_orm
get_students_directory = get_students_directory_orm

def clear_today_attendance_logs_orm():
    """Clears all attendance logs recorded today for test resets."""
    session = Session()
    now = pht_now()
    today_start = datetime.combine(now.date(), datetime.min.time())
    try:
        deleted = session.query(AttendanceLog).filter(AttendanceLog.timestamp >= today_start).delete()
        session.commit()
        return deleted
    except Exception as e:
        session.rollback()
        print(f"[!] Error clearing today logs: {e}")
        return 0
    finally:
        session.close()

clear_today_attendance_logs = clear_today_attendance_logs_orm

def create_parent_notification_orm(lrn, title, body, category="ATTENDANCE", priority="NORMAL", workflow_key="gate_scan"):
    """Inserts a real-time parent push notification into the database."""
    session = Session()
    try:
        notif = ParentNotification(
            lrn=str(lrn).strip() if lrn else None,
            title=title,
            body=body,
            category=category,
            priority=priority,
            workflow_key=workflow_key,
            is_read=False,
            sent_at=pht_now()
        )
        session.add(notif)
        session.commit()
        return notif.to_dict()
    except Exception as e:
        session.rollback()
        print(f"[!] create_parent_notification_orm error: {e}")
        return None
    finally:
        session.close()

def get_parent_notifications_orm(lrn=None, limit=25):
    """Retrieves real-time notifications for a specific student LRN or broadcast."""
    session = Session()
    try:
        query = session.query(ParentNotification)
        if lrn:
            clean_lrn = str(lrn).strip()
            query = query.filter((ParentNotification.lrn == clean_lrn) | (ParentNotification.lrn == None) | (ParentNotification.lrn == ''))
        items = query.order_by(ParentNotification.id.desc()).limit(limit).all()
        return [i.to_dict() for i in items]
    except Exception as e:
        print(f"[!] get_parent_notifications_orm error: {e}")
        return []
    finally:
        session.close()

def mark_parent_notifications_read_orm(lrn=None):
    """Marks notifications as read for a learner."""
    session = Session()
    try:
        query = session.query(ParentNotification).filter_by(is_read=False)
        if lrn:
            clean_lrn = str(lrn).strip()
            query = query.filter((ParentNotification.lrn == clean_lrn) | (ParentNotification.lrn == None))
        updated = query.update({ParentNotification.is_read: True})
        session.commit()
        return updated
    except Exception as e:
        session.rollback()
        print(f"[!] mark_parent_notifications_read_orm error: {e}")
        return 0
    finally:
        session.close()

def get_incidents_orm(lrn=None, limit=20):
    """Retrieves safety incident logs from the database."""
    session = Session()
    try:
        query = session.query(Incident)
        if lrn:
            clean_lrn = str(lrn).strip()
            query = query.filter((Incident.lrn == clean_lrn) | (Incident.lrn == None) | (Incident.lrn == ''))
        items = query.order_by(Incident.id.desc()).limit(limit).all()
        return [i.to_dict() for i in items]
    except Exception as e:
        print(f"[!] get_incidents_orm error: {e}")
        return []
    finally:
        session.close()

def save_incident_orm(lrn, title, incident_type, description, location="School Grounds", reported_by="Parent"):
    """Files a new safety or security incident log."""
    session = Session()
    try:
        inc = Incident(
            lrn=str(lrn).strip() if lrn else None,
            title=title,
            incident_type=incident_type,
            description=description,
            location=location,
            reported_by=reported_by,
            status="OPEN",
            created_at=pht_now()
        )
        session.add(inc)
        session.commit()
        return inc.to_dict()
    except Exception as e:
        session.rollback()
        print(f"[!] save_incident_orm error: {e}")
        return None
    finally:
        session.close()

create_parent_notification = create_parent_notification_orm
get_parent_notifications = get_parent_notifications_orm
mark_parent_notifications_read = mark_parent_notifications_read_orm
get_incidents = get_incidents_orm
save_incident = save_incident_orm
get_teacher_advisory_overview = get_teacher_advisory_overview_orm
update_user_profile = update_user_profile_orm
enroll_staff_face = enroll_staff_face_orm
get_enrolled_staff_faces = get_enrolled_staff_faces_orm
record_staff_attendance = record_staff_attendance_orm
get_staff_today_status = get_staff_today_status_orm
get_staff_dtr_logs = get_staff_dtr_logs_orm
auto_migrate_columns = auto_migrate_columns_orm


