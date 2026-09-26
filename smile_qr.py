import io
import qrcode
from pathlib import Path
from smile_config import BASE_DIR, IS_VERCEL

if IS_VERCEL:
    QR_DIR = Path("/tmp/smile_data/qrcodes")
else:
    QR_DIR = BASE_DIR / "static" / "qrcodes"

try:
    QR_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

def generate_student_qr_bytes(lrn: str) -> bytes:
    """
    Generates high-contrast PNG QR code image bytes in-memory for a student's LRN.
    Zero-disk I/O dependency for 100% serverless / read-only environment stability.
    """
    lrn_clean = str(lrn).strip()
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(f"DEPED-LRN:{lrn_clean}")
    qr.make(fit=True)

    img = qr.make_image(fill_color="#072648", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def generate_student_qr(lrn: str) -> str:
    """
    Generates a high-contrast QR code image for a student's LRN.
    Saves to disk if writable; safely skips disk I/O on read-only serverless filesystems.
    Always returns the resilient web URL path /qr/{lrn}.png.
    """
    lrn_clean = str(lrn).strip()
    try:
        qr_bytes = generate_student_qr_bytes(lrn_clean)
        # Attempt to save to disk if directory is writable (e.g. local or /tmp)
        try:
            QR_DIR.mkdir(parents=True, exist_ok=True)
            qr_file = QR_DIR / f"{lrn_clean}.png"
            with open(qr_file, "wb") as f:
                f.write(qr_bytes)
        except (OSError, IOError):
            # Read-only serverless filesystem (e.g. Vercel /var/task); dynamic route will serve it seamlessly
            pass
    except Exception as e:
        print(f"[!] Note: QR disk write skipped: {e}")

    return f"/qr/{lrn_clean}.png"

def parse_scanned_code(scanned_data: str) -> str:
    """
    Extracts 12-digit LRN from scanned QR text or RFID card input.
    Supports formats like:
      - "DEPED-LRN:109876543210"
      - "109876543210"
      - "LRN:109876543210"
    """
    raw = str(scanned_data).strip()
    if "DEPED-LRN:" in raw:
        return raw.split("DEPED-LRN:")[1].strip()
    elif "LRN:" in raw:
        return raw.split("LRN:")[1].strip()
    return raw

# Compatibility Aliases
generate_student_qr_code = generate_student_qr
parse_qr_text = parse_scanned_code
