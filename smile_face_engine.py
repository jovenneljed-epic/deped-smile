import cv2
import numpy as np
import requests
import sys
from pathlib import Path
from smile_config import (
    YUNET_PATH, SFACE_PATH, YUNET_MODEL_URL, SFACE_MODEL_URL,
    COSINE_SIMILARITY_THRESHOLD, DETECTION_CONFIDENCE
)

def ensure_model_downloaded(file_path: Path, url: str, model_name: str):
    """Downloads the required ONNX model file from OpenCV Zoo if not already present."""
    if file_path.exists() and file_path.stat().st_size > 10000:
        return

    import smile_config
    # On Vercel / serverless runtime, filesystem is read-only and functions have strict timeouts
    if getattr(smile_config, "IS_VERCEL", False):
        print(f"[!] Serverless runtime: {model_name} not pre-bundled; skipping auto-download to prevent cold-start timeout.")
        return
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[*] Downloading {model_name} model weights from OpenCV Zoo...")
    print(f"    URL: {url}")
    print(f"    Target: {file_path}")
    
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        sys.stdout.write(f"\r    Progress: {percent:.1f}% ({downloaded / (1024*1024):.1f} MB)")
                        sys.stdout.flush()
        print(f"\n[+] Successfully installed {model_name}!")
    except Exception as e:
        if file_path.exists():
            file_path.unlink()  # Remove partial download
        raise RuntimeError(f"Failed to download {model_name}: {e}\nPlease check your internet connection.")

class SmileFaceEngine:
    """
    Core Face Detection and Recognition Engine for Project S.M.I.L.E.
    Uses OpenCV YuNet (Real-time detection) and SFace (Biometric 128-d embeddings).
    Runs with high efficiency on standard CPUs without any C++ compilation needed.
    """
    def __init__(self):
        self.available = False
        self.detector = None
        self.recognizer = None
        self.current_input_size = (320, 320)

        try:
            import smile_config
            is_serverless = getattr(smile_config, "IS_VERCEL", False)

            # 1. Resolve YuNet Detector path (with /tmp download fallback)
            yunet_file = YUNET_PATH
            if not (yunet_file.exists() and yunet_file.stat().st_size > 10000):
                candidates = [
                    Path("models/face_detection_yunet_2023mar.onnx"),
                    Path(__file__).parent / "models" / "face_detection_yunet_2023mar.onnx",
                    Path("/tmp") / "face_detection_yunet_2023mar.onnx",
                    Path("/var/task/models/face_detection_yunet_2023mar.onnx")
                ]
                for c in candidates:
                    if c.exists() and c.stat().st_size > 10000:
                        yunet_file = c
                        break
                else:
                    try:
                        import requests
                        tmp_target = Path("/tmp") / "face_detection_yunet_2023mar.onnx"
                        resp = requests.get(YUNET_MODEL_URL, timeout=8)
                        if resp.status_code == 200 and len(resp.content) > 10000:
                            tmp_target.write_bytes(resp.content)
                            yunet_file = tmp_target
                    except Exception as _dl_e:
                        print(f"[!] YuNet auto-download note: {_dl_e}")

            # 2. Resolve SFace Recognizer path
            sface_file = SFACE_PATH
            if not (sface_file.exists() and sface_file.stat().st_size > 10000):
                candidates = [
                    Path("models/face_recognition_sface_2021dec.onnx"),
                    Path(__file__).parent / "models" / "face_recognition_sface_2021dec.onnx",
                    Path("/tmp") / "face_recognition_sface_2021dec.onnx",
                    Path("/var/task/models/face_recognition_sface_2021dec.onnx")
                ]
                for c in candidates:
                    if c.exists() and c.stat().st_size > 10000:
                        sface_file = c
                        break

            if not is_serverless:
                ensure_model_downloaded(YUNET_PATH, YUNET_MODEL_URL, "YuNet Face Detector")
                ensure_model_downloaded(SFACE_PATH, SFACE_MODEL_URL, "SFace Face Recognizer")

            # 3. Initialize YuNet Detector if available
            if yunet_file.exists() and yunet_file.stat().st_size > 10000:
                self.detector = cv2.FaceDetectorYN.create(
                    model=str(yunet_file),
                    config="",
                    input_size=(320, 320),
                    score_threshold=DETECTION_CONFIDENCE,
                    nms_threshold=0.3,
                    top_k=5000
                )

            # 4. Initialize SFace Recognizer if available
            if sface_file.exists() and sface_file.stat().st_size > 10000:
                self.recognizer = cv2.FaceRecognizerSF.create(
                    model=str(sface_file),
                    config=""
                )

            if self.detector is not None:
                self.available = True
        except Exception as e:
            print(f"[!] Note: SmileFaceEngine running in lightweight mode ({e}). Barcode/QR & Portal operational.")

    def detect_faces(self, frame):
        """
        Detects faces in an RGB/BGR image frame.
        Returns a list of face detections or empty list if no face found.
        Each face is an array: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rc, y_rc, x_lc, y_lc, score]
        """
        if not self.detector or frame is None:
            return []

        h, w, _ = frame.shape
        if (w, h) != self.current_input_size:
            self.detector.setInputSize((w, h))
            self.current_input_size = (w, h)

        _, faces = self.detector.detect(frame)
        if faces is not None and len(faces) > 0:
            return faces

        # CLAHE (Contrast Limited Adaptive Histogram Equalization) Fallback:
        # Handles low-light, shadows, or strong backlighting from school gates/windows
        try:
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            enhanced_lab = cv2.merge((cl, a, b))
            enhanced_frame = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
            _, faces_enhanced = self.detector.detect(enhanced_frame)
            if faces_enhanced is not None and len(faces_enhanced) > 0:
                return faces_enhanced
        except Exception:
            pass

        return []

    def extract_face_embedding(self, frame, face_box):
        """
        Aligns, crops, and extracts a 128-dimensional biometric embedding vector for a face.
        """
        if not self.recognizer or frame is None:
            return None
        # Align and crop face using facial landmarks
        aligned_face = self.recognizer.alignCrop(frame, face_box)
        # Extract 128-d feature vector
        feature = self.recognizer.feature(aligned_face)
        return feature.flatten()

    def match_against_enrolled(self, query_embedding, enrolled_students, threshold=COSINE_SIMILARITY_THRESHOLD):
        """
        Compares query face embedding against a list of enrolled student dictionaries.
        Uses Cosine Similarity.
        Returns: (best_match_student_dict, highest_score) or (None, 0.0) if below threshold.
        """
        if not enrolled_students or query_embedding is None:
            return None, 0.0

        best_student = None
        best_score = -1.0

        # SFace embeddings are normalized; cosine similarity is dot product or cv2.match
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)

        for student in enrolled_students:
            cand_emb = student.get("embedding")
            if cand_emb is None:
                continue
            if not isinstance(cand_emb, np.ndarray):
                try:
                    cand_emb = np.array(cand_emb, dtype=np.float32)
                except Exception:
                    continue
            cand_norm = cand_emb / (np.linalg.norm(cand_emb) + 1e-10)
            
            # Cosine similarity between -1.0 and 1.0
            similarity = float(np.dot(query_norm, cand_norm))

            if similarity > best_score:
                best_score = similarity
                best_student = student

        if best_score >= threshold:
            return best_student, best_score
        
        return None, best_score
