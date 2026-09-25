import qrcode
from pathlib import Path
from smile_config import BASE_DIR

QR_DIR = BASE_DIR / "static" / "qrcodes"
QR_DIR.mkdir(parents=True, exist_ok=True)

def generate_student_qr(lrn: str) -> str:
    """
    Generates a high-contrast QR code image for a student's LRN.
    Saves to static/qrcodes/{lrn}.png and returns the web URL path.
    """
    lrn_clean = str(lrn).strip()
    qr_file = QR_DIR / f"{lrn_clean}.png"
    
    # Generate QR Code containing standard DepEd LRN identifier
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(f"DEPED-LRN:{lrn_clean}")
    qr.make(fit=True)

    img = qr.make_image(fill_color="#072648", back_color="#ffffff")
    img.save(str(qr_file))
    
    return f"/static/qrcodes/{lrn_clean}.png"

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
