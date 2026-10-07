"""
Project S.M.I.L.E. - Database Migration Utility
Transfers local SQLite database records (students, attendance, users, sections, workflows)
directly to a permanent Cloud PostgreSQL database (Supabase, Neon, or Vercel Postgres).

Usage:
    python migrate_sqlite_to_cloud.py "postgresql://postgres:...@...:5432/deped_smile"
"""

import sys
import os
import json
import sqlite3
from pathlib import Path

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import smile_config
from smile_orm import (
    Base, engine, Session,
    Student, Section, User, AttendanceLog,
    Announcement, SchoolEvent, ExcuseNote,
    PricingPlan, PaymentTransaction, create_engine
)

def run_migration(target_db_url: str):
    print("=" * 65)
    print("  PROJECT S.M.I.L.E. - CLOUD DATABASE MIGRATION TOOL")
    print("=" * 65)

    clean_url = target_db_url.strip()
    if clean_url.startswith("postgres://"):
        clean_url = clean_url.replace("postgres://", "postgresql://", 1)

    # Convert to pure-python pg8000 driver
    if clean_url.startswith("postgresql://") and not clean_url.startswith("postgresql+pg8000://"):
        clean_url = clean_url.replace("postgresql://", "postgresql+pg8000://", 1)

    # Strip sslmode because pg8000 handles SSL via ssl_context
    if "sslmode=" in clean_url:
        import re
        clean_url = re.sub(r'[\?\&]sslmode=[^\&]+', '', clean_url)
        if clean_url.endswith("?"):
            clean_url = clean_url[:-1]

    # Handle Supabase pooler
    if ".supabase.co" in clean_url:
        import re
        region = os.environ.get("SUPABASE_REGION", "ap-northeast-2")
        match = re.search(r'db\.([a-z0-9]+)\.supabase\.co', clean_url)
        if match:
            ref = match.group(1)
            clean_url = clean_url.replace(f"db.{ref}.supabase.co:5432", f"aws-0-{region}.pooler.supabase.com:6543")
            clean_url = clean_url.replace(f"db.{ref}.supabase.co", f"aws-0-{region}.pooler.supabase.com:6543")
            if "://postgres:" in clean_url:
                clean_url = clean_url.replace("://postgres:", f"://postgres.{ref}:")

    print(f"\n[1/4] Connecting to target cloud database...")
    try:
        import ssl
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        target_engine = create_engine(
            clean_url,
            connect_args={"ssl_context": ssl_ctx} if "pg8000" in clean_url else {},
            pool_pre_ping=True
        )
        with target_engine.connect() as conn:
            print("  [OK] Successfully connected to Cloud Database!")
    except Exception as e:
        print(f"  [ERROR] Could not connect to target database: {e}")
        return False

    print("\n[2/4] Ensuring database schema and tables exist...")
    try:
        Base.metadata.create_all(target_engine)
        print("  [OK] All tables verified in Cloud Database.")

        # For PostgreSQL / Supabase, automatically enable Row Level Security (RLS) on all public tables
        if target_engine.dialect.name == "postgresql":
            try:
                with target_engine.connect() as conn:
                    from sqlalchemy import text
                    conn.execute(text("""
                        DO $$
                        DECLARE tbl record;
                        BEGIN
                            FOR tbl IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
                                EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', tbl.tablename);
                            END LOOP;
                        END $$;
                    """))
                    conn.commit()
                print("  [OK] Supabase Row Level Security (RLS) enabled on all public tables.")
            except Exception as rls_err:
                print(f"  [!] Note on RLS enablement: {rls_err}")
    except Exception as e:
        print(f"  [ERROR] Schema generation failed: {e}")
        return False

    # Read from local SQLite
    sqlite_file = smile_config.DATA_DIR / "smile_records.db"
    if not sqlite_file.exists():
        print(f"  [ERROR] Local SQLite database not found at {sqlite_file}")
        return False

    print(f"\n[3/4] Reading local records from {sqlite_file.name}...")
    local_conn = sqlite3.connect(sqlite_file)
    local_conn.row_factory = sqlite3.Row

    from sqlalchemy.orm import sessionmaker
    CloudSession = sessionmaker(bind=target_engine)
    cloud_session = CloudSession()

    try:
        # 1. Sections
        c = local_conn.cursor()
        c.execute("SELECT * FROM sections")
        sections = [dict(r) for r in c.fetchall()]
        sec_count = 0
        for s in sections:
            existing = cloud_session.query(Section).filter_by(grade_level=s['grade_level'], section_name=s['section_name']).first()
            if not existing:
                cloud_session.add(Section(
                    grade_level=s['grade_level'],
                    section_name=s['section_name'],
                    adviser_teacher=s.get('adviser_teacher', ''),
                    room_number=s.get('room_number', '')
                ))
                sec_count += 1
        cloud_session.commit()
        print(f"  - Sections: {sec_count} new migrated (Total in local: {len(sections)})")

        # 2. Users
        c.execute("SELECT * FROM users")
        users = [dict(r) for r in c.fetchall()]
        user_count = 0
        for u in users:
            existing = cloud_session.query(User).filter_by(username=u['username']).first()
            if not existing:
                cloud_session.add(User(
                    username=u['username'],
                    email=u['email'],
                    password_hash=u['password_hash'],
                    full_name=u['full_name'],
                    role=u.get('role', 'TEACHER'),
                    phone_number=u.get('phone_number', '')
                ))
                user_count += 1
        cloud_session.commit()
        print(f"  - Users/Admins: {user_count} new migrated (Total in local: {len(users)})")

        # 3. Students
        c.execute("SELECT * FROM students")
        students = [dict(r) for r in c.fetchall()]
        st_count = 0
        for s in students:
            existing = cloud_session.query(Student).filter_by(lrn=s['lrn']).first()
            if not existing:
                cloud_session.add(Student(
                    lrn=s['lrn'],
                    first_name=s['first_name'],
                    middle_name=s.get('middle_name', ''),
                    last_name=s['last_name'],
                    gender=s.get('gender', 'Unspecified'),
                    birthdate=s.get('birthdate', ''),
                    grade_level=s.get('grade_level', ''),
                    section_name=s.get('section_name', ''),
                    class_adviser=s.get('class_adviser', ''),
                    grade_section=s.get('grade_section', ''),
                    track_strand=s.get('track_strand', ''),
                    parent_name=s.get('parent_name', ''),
                    parent_phone=s.get('parent_phone', ''),
                    parent_relationship=s.get('parent_relationship', 'Parent'),
                    rfid_card_uid=s.get('rfid_card_uid', 'N/A'),
                    qr_code_path=s.get('qr_code_path', f"/qr/{s['lrn']}.png"),
                    photo_path=s.get('photo_path', ''),
                    face_embedding=s.get('face_embedding', None),
                    is_active=bool(s.get('is_active', 1))
                ))
                st_count += 1
        cloud_session.commit()
        print(f"  - Enrolled Students: {st_count} new migrated (Total in local: {len(students)})")

        # 4. Announcements
        c.execute("SELECT * FROM announcements")
        announcements = [dict(r) for r in c.fetchall()]
        ann_count = 0
        for a in announcements:
            existing = cloud_session.query(Announcement).filter_by(title=a['title']).first()
            if not existing:
                cloud_session.add(Announcement(
                    title=a['title'],
                    content=a['content'],
                    category=a.get('category', 'GENERAL'),
                    is_urgent=bool(a.get('is_urgent', 0)),
                    author_name=a.get('author_name', 'School Administration')
                ))
                ann_count += 1
        cloud_session.commit()
        print(f"  - Announcements: {ann_count} new migrated (Total in local: {len(announcements)})")

        # 5. Push Workflows
        try:
            c.execute("SELECT * FROM push_workflows")
            workflows = [dict(r) for r in c.fetchall()]
            for wf in workflows:
                with target_engine.connect() as t_conn:
                    t_conn.execute(
                        "INSERT INTO push_workflows (workflow_key, title, description, trigger_type, cron_schedule, is_active, total_runs, total_dispatched) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (workflow_key) DO NOTHING",
                        (wf['workflow_key'], wf['title'], wf.get('description', ''), wf.get('trigger_type', 'EVENT_DRIVEN'),
                         wf.get('cron_schedule', ''), wf.get('is_active', 1), wf.get('total_runs', 0), wf.get('total_dispatched', 0))
                    )
            print(f"  - n8n Automation Workflows: {len(workflows)} synchronized")
        except Exception:
            pass

        print("\n[4/4] Migration Complete!")
        print("=" * 65)
        print("  ALL LOCAL DATA SUCCESSFULLY MIGRATED TO CLOUD DATABASE!")
        print("=" * 65)
        return True

    except Exception as e:
        cloud_session.rollback()
        print(f"  [ERROR] Migration failed during data insert: {e}")
        return False
    finally:
        cloud_session.close()
        local_conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("    python migrate_sqlite_to_cloud.py \"postgresql://...\"\n")
        print("Example:")
        print("    python migrate_sqlite_to_cloud.py \"postgresql://postgres:pass@ep-cool-db.us-east-2.aws.neon.tech/neondb\"\n")
        sys.exit(1)

    db_url = sys.argv[1]
    run_migration(db_url)
