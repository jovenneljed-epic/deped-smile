# PROJECT S.M.I.L.E.
### Security & Monitoring with Instant Logging & E-Notification
**DepEd School Smart ID (QR / RFID) Gate Attendance System & Automated Parent SMS Notifier**
*100% Data Privacy Act of 2012 (RA 10173) Compliant &bull; Non-Biometric Architecture*

---

## 🌟 Overview
**Project S.M.I.L.E.** is a modern school gate security and attendance monitoring system designed specifically for Philippine Department of Education (DepEd) public and private schools.

To uphold the highest data privacy standards for minors under Republic Act 10173, the system utilizes a **100% Non-Biometric Smart ID Architecture**:
- **DepEd Standard Smart QR Codes**: Students present their wallet-sized ID card to the gate optical camera.
- **Contactless USB RFID Tap Cards**: Students can tap their RFID card or badge at the gate sensor.
- **Barcode / 12-Digit LRN Manual Entry**: Gate guards can scan or enter a student's Learner Reference Number.

Whenever a student checks in or out, the system instantly logs their entry/exit and fires an automated SMS alert directly to their parent/guardian's mobile phone:

> *"DepEd Advisory: Good day! Your child Juan Dela Cruz (LRN: 109876543210, Grade 10 - Rizal) has successfully ENTERED the school gate (TIME-IN) at 07:15 AM, Sep 25, 2026. - DepEd Demonstration High School"*

---

## 🔒 100% Data Privacy Act of 2012 (RA 10173) Compliance
* **Zero Biometric Facial Data:** The system does NOT capture, process, or store facial feature vectors, facial geometry, or face embeddings.
* **DepEd Standard Identifiers:** Students are verified strictly through their official 12-digit Learner Reference Number (LRN) encoded into cryptographic QR codes and RFID tokens.
* **Offline-First Storage:** All records, sections, attendance logs, and SMS receipts are stored on the local school server or school intranet database (SQLite / MySQL / PostgreSQL) without exposing student records to third-party AI cloud services.

---

## 📁 Project Architecture

```
project_smile/
├── app.py                   # Central Flask Web Server & API Gate Controller
├── smile_config.py          # Central Config: School info, Database engine, SMS API keys
├── smile_orm.py             # SQLAlchemy Enterprise Models (Student, Section, Attendance, SMS)
├── smile_qr.py              # QR Code generator & decoder (DEPED-LRN:{lrn})
├── smile_sms.py             # Multi-mode SMS dispatcher (Semaphore API, Mock, GSM Serial)
├── web_streamer.py          # Real-time QR optical gate streamer & RFID tap processor
├── seed_deped_database.py   # Seeder for DepEd grade sections, demo learners, and QR badges
├── test_system.py           # Automated diagnostic & self-test suite
├── data/
│   └── smile_records.db     # Enterprise SQLite database file
├── static/
│   └── qrcodes/             # Auto-generated scannable QR codes for each student
└── templates/
    ├── base.html            # DepEd responsive navigation layout
    ├── dashboard.html       # School gate overview & real-time attendance stream
    ├── kiosk.html           # Fullscreen high-contrast gate kiosk with audio chime & RFID tap bar
    ├── id_card.html         # Printable wallet-sized DepEd Student Smart ID card
    ├── students.html        # Learner directory with direct QR ID printing & search
    ├── enroll.html          # Student registration with instant QR generation
    ├── database_admin.html  # SQL table explorer, record inspection & JSON backup
    ├── sections.html        # DepEd Grade 7–12 Section management & enrollment stats
    └── sms_logs.html        # Real-time carrier dispatch logs & delivery statuses
```

---

## 🚀 Quick Start Guide

### 1. Run the Diagnostic Self-Test
Verify all database tables, SMS dispatchers, and QR/RFID resolution engines:
```bash
python test_system.py
```

---

### 2. Populate / Re-seed DepEd School Records
Generates DepEd Grade 7–12 class sections and authentic demo learners with scannable QR codes:
```bash
python seed_deped_database.py
```

---

### 3. Start the Web Suite & Gate Kiosk
Launch the main application server:
```bash
python app.py
```
Open your web browser at:
* **Admin Dashboard:** `http://localhost:5000/`
* **Gate Kiosk Display:** `http://localhost:5000/kiosk` (Press `F11` for full screen)
* **Print Student Smart IDs:** `http://localhost:5000/students` -> click **Print Smart ID**
* **Database & SQL Explorer:** `http://localhost:5000/database`

---

## 💳 Testing Student Check-Ins at the Gate

You can test check-ins using any of the following 3 methods:

### Method 1: RFID Tap Bar or LRN Manual Entry (Recommended for Instant Testing)
1. Open `http://localhost:5000/kiosk`.
2. In the input box below the camera view, type any 12-digit LRN (e.g. `109876543210`) or RFID card UID (e.g. `RFID-098765`) and press **Enter** (or click **TAP ID CARD**).
3. The kiosk plays a high-fidelity confirmation chime, pops up the student's verified profile badge, and logs an automated SMS dispatch.

### Method 2: Test Scan Button (Simulated Gate Entry)
Click the green **"Test Scan"** button on the top right of the kiosk header or on the dashboard.

### Method 3: Physical Camera QR Scanning
Hold a printed DepEd Smart ID card or smartphone displaying the student's QR code up to the camera. The optical scanner will decode the `DEPED-LRN` payload and trigger attendance automatically.

---

## 🖨️ Printing DepEd Student Smart ID Cards
1. Navigate to `http://localhost:5000/students`.
2. Click **"Print Smart ID"** next to any student (or open `http://localhost:5000/id-card/109876543210`).
3. Press `Ctrl + P` to print. The layout is pre-formatted to DepEd standard portrait wallet-size badge dimensions (3.375" x 2.125") complete with official DepEd headers, student details, parent contact, and the scannable QR badge.

---

## 📱 Configuring Parent SMS Notifications

Configure your preferred SMS provider in `smile_config.py`:

### Option A: Semaphore SMS API (Recommended for Philippine Telcos: Globe / Smart / DITO)
1. Register for an account at [semaphore.co](https://semaphore.co).
2. Set your credentials in `smile_config.py`:
   ```python
   SMS_MODE = "SEMAPHORE"
   SEMAPHORE_API_KEY = "your_actual_api_key_here"
   SEMAPHORE_SENDER_NAME = "SEMAPHORE"  # Or your approved DepEd school sender ID
   ```

### Option B: Local Mock Gateway (Default - For Testing & Demonstrations)
```python
SMS_MODE = "MOCK"
```
Logs all dispatched SMS alerts to the console and records them into the database table viewable at `http://localhost:5000/sms-logs`.

### Option C: USB Hardware GSM Modem
```python
SMS_MODE = "GSM"
GSM_PORT = "COM3"
```

---

## 🗄️ Relational Database Configuration

The system uses SQLAlchemy ORM and supports three database backends in `smile_config.py`:

```python
# Select database: "SQLITE", "MYSQL", or "POSTGRESQL"
DATABASE_TYPE = "SQLITE"
```

* **SQLite (Default):** Zero configuration required; data stored locally in `data/smile_records.db`.
* **MySQL / MariaDB (XAMPP / WampServer):** Ideal for school computer laboratory local networks. Configure `MYSQL_CONFIG` in `smile_config.py`.
* **PostgreSQL:** Supported for division-wide or enterprise school deployments. Configure `POSTGRES_CONFIG` in `smile_config.py`.
