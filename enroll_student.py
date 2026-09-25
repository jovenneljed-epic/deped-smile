import cv2
import sys
import argparse
from pathlib import Path
from smile_config import CAMERA_INDEX, PHOTOS_DIR
from smile_db import save_student
from smile_face_engine import SmileFaceEngine

def capture_face_from_webcam(camera_idx=CAMERA_INDEX):
    """
    Opens interactive webcam window to capture a clear student portrait.
    Press SPACE to capture, or ESC / 'q' to cancel.
    """
    print(f"[*] Opening camera index {camera_idx} for enrollment...")
    cap = cv2.VideoCapture(camera_idx)
    if not cap.isOpened():
        print(f"[!] Error: Could not open camera {camera_idx}.")
        return None

    captured_frame = None
    print("\n" + "="*50)
    print(" ENROLLMENT CAMERA GUIDE:")
    print(" - Look straight at the camera.")
    print(" - Make sure lighting is bright.")
    print(" - Press [SPACE] to capture the photo.")
    print(" - Press [ESC] or [Q] to cancel.")
    print("="*50 + "\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[!] Failed to read frame from camera.")
            break

        display = frame.copy()
        h, w, _ = display.shape

        # Draw an oval/box guide for positioning face
        center_x, center_y = w // 2, h // 2
        box_w, box_h = int(w * 0.45), int(h * 0.65)
        top_left = (center_x - box_w // 2, center_y - box_h // 2)
        bottom_right = (center_x + box_w // 2, center_y + box_h // 2)

        cv2.rectangle(display, top_left, bottom_right, (0, 255, 128), 2)
        cv2.putText(display, "Position face in box, then press SPACE", (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 128), 2)

        cv2.imshow("Project S.M.I.L.E. - Student Face Enrollment", display)
        key = cv2.waitKey(1) & 0xFF

        if key == 32:  # SPACEBAR pressed
            captured_frame = frame.copy()
            break
        elif key in (27, ord('q'), ord('Q')):  # ESC or Q
            print("[*] Enrollment cancelled by user.")
            break

    cap.release()
    cv2.destroyAllWindows()
    return captured_frame

def enroll_student(lrn, first_name, last_name, grade_section, parent_name, parent_phone, image_path=None):
    """
    Enrolls a student, extracts face embedding using YuNet + SFace, and saves to database.
    """
    engine = SmileFaceEngine()

    if image_path:
        img_p = Path(image_path)
        if not img_p.exists():
            print(f"[!] Error: Photo file not found: {image_path}")
            return False
        frame = cv2.imread(str(img_p))
        if frame is None:
            print(f"[!] Error: Could not read image at {image_path}")
            return False
    else:
        frame = capture_face_from_webcam()
        if frame is None:
            return False

    # Detect faces
    faces = engine.detect_faces(frame)
    if len(faces) == 0:
        print("[!] No face detected in the photo. Please try again in better lighting.")
        return False
    elif len(faces) > 1:
        print(f"[!] Warning: {len(faces)} faces detected. Only one face must be visible during enrollment.")
        return False

    # Extract 128-d biometric embedding
    face = faces[0]
    embedding = engine.extract_face_embedding(frame, face)

    # Save student photo for records
    photo_save_path = PHOTOS_DIR / f"{lrn}_{last_name.lower()}.jpg"
    x, y, w, h = int(face[0]), int(face[1]), int(face[2]), int(face[3])
    # Add modest padding around face
    pad_y, pad_x = int(h * 0.2), int(w * 0.2)
    img_h, img_w, _ = frame.shape
    y1, y2 = max(0, y - pad_y), min(img_h, y + h + pad_y)
    x1, x2 = max(0, x - pad_x), min(img_w, x + w + pad_x)
    cropped_face = frame[y1:y2, x1:x2]
    
    cv2.imwrite(str(photo_save_path), cropped_face if cropped_face.size > 0 else frame)

    # Save to SQLite
    save_student(
        lrn=lrn,
        first_name=first_name,
        last_name=last_name,
        grade_section=grade_section,
        parent_name=parent_name,
        parent_phone=parent_phone,
        photo_path=str(photo_save_path),
        embedding_array=embedding
    )

    print("\n" + "="*50)
    print(" [SUCCESS] STUDENT ENROLLED SUCCESSFULLY!")
    print(f" Name:           {first_name} {last_name}")
    print(f" LRN:            {lrn}")
    print(f" Grade/Section:  {grade_section}")
    print(f" Parent:         {parent_name} ({parent_phone})")
    print(f" Photo Saved:    {photo_save_path}")
    print("="*50 + "\n")
    return True

def interactive_cli():
    print("="*60)
    print("      PROJECT S.M.I.L.E. - STUDENT ENROLLMENT UTILITY")
    print("="*60)
    
    lrn = input("Enter 12-Digit LRN (Learner Reference Number): ").strip()
    if not lrn:
        print("[!] LRN cannot be empty.")
        return

    first_name = input("Enter Student First Name: ").strip()
    last_name = input("Enter Student Last Name: ").strip()
    grade_section = input("Enter Grade & Section (e.g., Gr. 10 - Rizal): ").strip()
    parent_name = input("Enter Parent / Guardian Name: ").strip()
    parent_phone = input("Enter Parent Mobile Number (e.g., 09171234567): ").strip()

    photo_choice = input("Capture from Webcam [W] or Load File [F]? (default: W): ").strip().upper()
    image_path = None
    if photo_choice == "F":
        image_path = input("Enter path to student image file (.jpg/.png): ").strip()

    enroll_student(
        lrn=lrn,
        first_name=first_name,
        last_name=last_name,
        grade_section=grade_section,
        parent_name=parent_name,
        parent_phone=parent_phone,
        image_path=image_path
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enroll student into Project S.M.I.L.E.")
    parser.add_argument("--lrn", help="12-digit Learner Reference Number")
    parser.add_argument("--first-name", help="Student first name")
    parser.add_argument("--last-name", help="Student last name")
    parser.add_argument("--grade", help="Grade and Section")
    parser.add_argument("--parent-name", help="Parent / Guardian Name")
    parser.add_argument("--phone", help="Parent mobile number")
    parser.add_argument("--image", help="Optional path to student photo image file")

    args = parser.parse_args()

    if args.lrn and args.first_name and args.last_name and args.phone:
        enroll_student(
            lrn=args.lrn,
            first_name=args.first_name,
            last_name=args.last_name,
            grade_section=args.grade or "Unassigned",
            parent_name=args.parent_name or "",
            parent_phone=args.phone,
            image_path=args.image
        )
    else:
        interactive_cli()
