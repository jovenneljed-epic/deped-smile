"""
Bridge module ensuring backward compatibility with all existing scripts
while directing all queries to the SQLAlchemy Enterprise ORM Engine.
"""
from smile_orm import (
    init_orm_db as init_db,
    save_student_orm as save_student,
    get_all_enrolled_students_orm as get_all_enrolled_students,
    check_can_scan_orm as check_can_scan,
    record_attendance_orm as record_attendance,
    update_attendance_sms_status_orm as update_attendance_sms_status,
    record_sms_orm as record_sms,
    get_today_summary_orm as get_today_summary,
    get_database_stats_orm as get_database_stats,
    get_student_by_lrn_or_rfid_orm as get_student_by_lrn,
    delete_student_orm as delete_student,
    evaluate_daily_scan_rule_orm as evaluate_daily_scan_rule,
    Session
)
from smile_config import MIDDAY_SPLIT_HOUR
from datetime import datetime

def determine_scan_type(lrn=None, student_name=None):
    """
    Determines TIME_IN vs TIME_OUT based on daily scan quota:
    - 1 Time-In, 1 Time-Out in Morning
    - 1 Time-In, 2 Time-Outs in Afternoon
    """
    if lrn:
        res = evaluate_daily_scan_rule(lrn, student_name=student_name)
        if res.get("scan_type"):
            return res["scan_type"]
    now = datetime.now()
    return "TIME_IN" if now.hour < MIDDAY_SPLIT_HOUR else "TIME_OUT"

def get_connection():
    """Returns raw connection for backwards compatibility."""
    import sqlite3
    from smile_config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

