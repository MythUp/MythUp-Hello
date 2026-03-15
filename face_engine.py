import os
import sys
import face_recognition
import numpy as np
import cv2

try:
    from build_config import FACES_SOURCE_MODE
except Exception:
    FACES_SOURCE_MODE = "both"


def _resource_base_dir():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _runtime_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _normalize_mode(mode):
    value = (mode or "both").strip().lower()
    if value not in {"external", "embedded", "both"}:
        return "both"
    return value


class FaceEngine:
    def __init__(self, faces_folder="faces", cache_file="encodings.npy"):
        self.is_frozen = getattr(sys, "frozen", False)
        self.faces_source_mode = _normalize_mode(FACES_SOURCE_MODE)
        self.sources = self._build_sources(faces_folder, cache_file)

        self.known_encodings = []
        self.known_names = []
        self.source_loaded_counts = {}
        self.source_has_faces_dir = {}
        self.source_has_cache = {}
        self.load_encodings()

    def _build_sources(self, faces_folder, cache_file):
        runtime_dir = _runtime_base_dir()
        bundled_dir = _resource_base_dir()

        if not self.is_frozen:
            return [
                {
                    "label": "project",
                    "faces": os.path.join(runtime_dir, faces_folder),
                    "cache": os.path.join(runtime_dir, cache_file),
                    "allow_cache_write": True,
                }
            ]

        if self.faces_source_mode == "embedded":
            return [
                {
                    "label": "embedded",
                    "faces": os.path.join(bundled_dir, "faces"),
                    "cache": os.path.join(bundled_dir, "encodings.npy"),
                    "allow_cache_write": False,
                }
            ]

        if self.faces_source_mode == "both":
            return [
                {
                    "label": "external",
                    "faces": os.path.join(runtime_dir, "faces"),
                    "cache": os.path.join(runtime_dir, "encodings.npy"),
                    "allow_cache_write": True,
                },
                {
                    "label": "embedded",
                    "faces": os.path.join(bundled_dir, "faces"),
                    "cache": os.path.join(bundled_dir, "encodings.npy"),
                    "allow_cache_write": False,
                },
            ]

        # Default frozen mode: external only.
        return [
            {
                "label": "external",
                "faces": os.path.join(runtime_dir, "faces"),
                "cache": os.path.join(runtime_dir, "encodings.npy"),
                "allow_cache_write": True,
            }
        ]

    def load_encodings(self):
        self.known_encodings = []
        self.known_names = []
        self.source_loaded_counts = {}
        self.source_has_faces_dir = {}
        self.source_has_cache = {}
        seen_names = set()

        for source in self.sources:
            source_encodings = []
            source_names = []

            cache_file = source["cache"]
            faces_folder = source["faces"]
            label = source["label"]
            self.source_has_faces_dir[label] = os.path.isdir(faces_folder)
            self.source_has_cache[label] = os.path.exists(cache_file)

            if os.path.exists(cache_file):
                try:
                    data = np.load(cache_file, allow_pickle=True).item()
                    source_encodings = list(data.get("encodings", []))
                    source_names = list(data.get("names", []))
                    print(f"Loaded face encodings from {label} cache ({len(source_encodings)} faces).")
                except Exception as exc:
                    print(f"Failed to load {label} cache ({cache_file}): {exc}")

            if len(source_encodings) == 0 and os.path.isdir(faces_folder):
                source_encodings, source_names = self.encode_faces(faces_folder)
                if len(source_encodings) > 0 and source["allow_cache_write"]:
                    self.save_cache(cache_file, source_encodings, source_names)

            for encoding, name in zip(source_encodings, source_names):
                if name in seen_names:
                    continue
                self.known_encodings.append(encoding)
                self.known_names.append(name)
                seen_names.add(name)

            self.source_loaded_counts[label] = len(source_encodings)

        if len(self.known_encodings) == 0:
            print("No authorized faces were loaded from configured sources.")
        else:
            print(f"Face database ready ({len(self.known_encodings)} unique faces).")

    def get_startup_warning(self):
        if not self.is_frozen:
            return None

        total = len(self.known_encodings)
        external_faces_dir = self.source_has_faces_dir.get("external", False)
        external_cache = self.source_has_cache.get("external", False)
        external_loaded = self.source_loaded_counts.get("external", 0)
        embedded_loaded = self.source_loaded_counts.get("embedded", 0)

        if self.faces_source_mode == "external":
            if not external_faces_dir and not external_cache:
                return (
                    "No external authorized faces were found next to this executable.\n\n"
                    "Create one of these next to the .exe:\n"
                    "- faces/ with one image per person\n"
                    "- encodings.npy generated from those images\n\n"
                    "Then restart the application."
                )
            if external_loaded == 0:
                return (
                    "External mode is enabled, but no valid authorized face could be loaded.\n\n"
                    "Check faces/ images or encodings.npy next to the executable."
                )

        if self.faces_source_mode == "both":
            if total == 0 and embedded_loaded == 0 and external_loaded == 0:
                return (
                    "No authorized faces are available in external or embedded sources.\n\n"
                    "Provide faces/ or encodings.npy next to the executable,\n"
                    "or rebuild with embedded face data."
                )

        return None

    def encode_faces(self, faces_folder):
        found_encodings = []
        found_names = []
        if not os.path.isdir(faces_folder):
            print(f"Faces folder not found: {faces_folder}")
            return found_encodings, found_names

        for filename in os.listdir(faces_folder):
            if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            path = os.path.join(faces_folder, filename)
            try:
                image = face_recognition.load_image_file(path)
                encodings = face_recognition.face_encodings(image, num_jitters=0)
            except Exception as exc:
                print(f"Failed to encode {filename}: {exc}")
                continue

            if len(encodings) == 0:
                print(f"No face found in {filename}")
                continue
            found_encodings.append(encodings[0])
            found_names.append(os.path.splitext(filename)[0])
            print(f"Encoded face: {filename}")

        return found_encodings, found_names

    def save_cache(self, cache_file, encodings, names):
        try:
            np.save(cache_file, {"encodings": encodings, "names": names})
            print(f"Saved encoding cache ({len(encodings)} faces) to {cache_file}.")
        except Exception as exc:
            print(f"Could not save encoding cache to {cache_file}: {exc}")

    def analyze(self, frame, scale=1.0, match_threshold=0.5, weak_match_threshold=0.62):
        if scale <= 0 or scale > 1:
            scale = 1.0

        if scale < 1.0:
            small_frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
        else:
            small_frame = frame

        # Use a contiguous buffer for dlib/face_recognition compatibility.
        rgb_frame = np.ascontiguousarray(small_frame[:, :, ::-1])  # BGR -> RGB
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")

        if len(face_locations) == 0:
            return []

        try:
            face_encodings = face_recognition.face_encodings(
                rgb_frame,
                known_face_locations=face_locations,
                num_jitters=0,
            )
        except TypeError:
            # Defensive fallback for some dlib/face_recognition version combinations.
            face_encodings = face_recognition.face_encodings(rgb_frame, num_jitters=0)

        results = []
        for encoding, loc in zip(face_encodings, face_locations):
            # Build OpenCV rectangle coordinates.
            if isinstance(loc, tuple):
                top, right, bottom, left = loc
            else:  # dlib.rectangle
                top, right, bottom, left = loc.top(), loc.right(), loc.bottom(), loc.left()

            if scale < 1.0:
                inv_scale = 1.0 / scale
                top = int(top * inv_scale)
                right = int(right * inv_scale)
                bottom = int(bottom * inv_scale)
                left = int(left * inv_scale)

            if len(self.known_encodings) > 0:
                distances = face_recognition.face_distance(self.known_encodings, encoding)
                best_index = np.argmin(distances)
                distance = distances[best_index]
                confidence_percent = int(max(0, min(1, 1 - distance)) * 100)
                candidate_name = self.known_names[best_index]

                if distance <= match_threshold:
                    display_name = candidate_name
                    is_authorized = True
                elif distance <= weak_match_threshold:
                    # Closest candidate, but similarity is still too low.
                    display_name = f"{candidate_name}?"
                    is_authorized = False
                else:
                    display_name = "Unknown"
                    is_authorized = False
            else:
                display_name = "Unknown"
                confidence_percent = 0
                is_authorized = False

            results.append((left, top, right - left, bottom - top, display_name, confidence_percent, is_authorized))

        return results
