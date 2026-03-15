import sys
import time
import os
import cv2
import numpy as np
from PyQt6 import QtWidgets, QtGui, QtCore
from face_engine import FaceEngine
from config import (
    LOCK_DELAY_SECONDS,
    LOCK_COOLDOWN_SECONDS,
    ANALYZE_SCALE,
    RECOGNITION_EVERY_N_FRAMES,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    MIN_CONFIDENCE_PERCENT,
    WEAK_CONFIDENCE_PERCENT,
)

class SentinelGUI(QtWidgets.QWidget):
    def __init__(self, show_camera_preview=False):
        super().__init__()
        self.show_camera_preview = show_camera_preview
        self.setWindowTitle("Sentinel Face Lock")
        self.resize(800, 600)

        self.video_label = QtWidgets.QLabel()
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.video_label)
        self.setLayout(layout)

        self.face_engine = FaceEngine()
        warning_message = self.face_engine.get_startup_warning()
        if warning_message:
            QtWidgets.QMessageBox.warning(
                self,
                "Face Source Setup Required",
                warning_message,
            )

        self.camera_index = None
        self.cap = None
        self.last_camera_retry = 0.0
        self.camera_retry_interval = 2.0
        self.last_lock_time = 0.0
        self.lock_cooldown_seconds = LOCK_COOLDOWN_SECONDS
        self.awaiting_camera_verification = True
        self.open_camera(preferred_index=0)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

        self.last_time = time.time()
        self.fps = 0
        self.last_seen_authorized = time.time()
        self.frame_count = 0
        self.cached_faces = []

    def _draw_status_frame(self, message):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            frame,
            message,
            (20, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 180, 255),
            2,
        )
        h, w, _ = frame.shape
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qt_image = QtGui.QImage(frame_rgb.data, w, h, 3 * w, QtGui.QImage.Format.Format_RGB888)
        self.video_label.setPixmap(QtGui.QPixmap.fromImage(qt_image))

    def open_camera(self, preferred_index=0):
        candidate_indices = [preferred_index, 0, 1, 2, 3]
        tried = set()

        for index in candidate_indices:
            if index in tried:
                continue
            tried.add(index)

            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                continue

            ok, _ = cap.read()
            if ok:
                if self.cap is not None:
                    self.cap.release()
                self.cap = cap
                self.camera_index = index
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                self.awaiting_camera_verification = True
                print(f"Active camera index: {index}")
                return True

            cap.release()

        if self.cap is not None:
            self.cap.release()
        self.cap = None
        self.camera_index = None
        print("No camera is currently available.")
        return False

    def _ensure_camera_available(self):
        now = time.time()
        if self.cap is not None and self.cap.isOpened():
            return True

        if now - self.last_camera_retry < self.camera_retry_interval:
            return False

        self.last_camera_retry = now
        return self.open_camera(preferred_index=0)

    def update_frame(self):
        if not self._ensure_camera_available():
            self.awaiting_camera_verification = True
            if self.show_camera_preview:
                self._draw_status_frame("Camera unavailable - retrying...")
            return

        if self.cap is None:
            return

        ret, frame = self.cap.read()
        if not ret:
            # Camera may have disconnected: force reconnection on next timer tick.
            if self.cap is not None:
                self.cap.release()
            self.cap = None
            self.awaiting_camera_verification = True
            if self.show_camera_preview:
                self._draw_status_frame("Camera stream lost - reconnecting...")
            return

        frame = cv2.flip(frame, 1)  # horizontal mirror
        h, w, _ = frame.shape

        min_confidence = max(0, min(100, MIN_CONFIDENCE_PERCENT))
        weak_confidence = max(0, min(min_confidence, WEAK_CONFIDENCE_PERCENT))
        match_threshold = 1.0 - (min_confidence / 100.0)
        weak_match_threshold = 1.0 - (weak_confidence / 100.0)

        self.frame_count += 1
        should_analyze = self.awaiting_camera_verification or (
            self.frame_count % max(1, RECOGNITION_EVERY_N_FRAMES) == 0
        )
        analyzed_this_frame = False
        if should_analyze:
            try:
                self.cached_faces = self.face_engine.analyze(
                    frame,
                    scale=ANALYZE_SCALE,
                    match_threshold=match_threshold,
                    weak_match_threshold=weak_match_threshold,
                )
                analyzed_this_frame = True
            except KeyboardInterrupt:
                print("Interrupted during face analysis. Exiting cleanly...")
                QtWidgets.QApplication.quit()
                return
            except Exception as exc:
                # Keep the app alive if face analysis fails on a single frame.
                print(f"Face analysis error: {exc}")
                self.cached_faces = []
                self.awaiting_camera_verification = True

        faces = self.cached_faces
        authorized_seen = False

        for (x, y, width, height, name, confidence, is_authorized) in faces:
            if self.show_camera_preview:
                color = (0, 255, 0) if is_authorized else (0, 0, 255)
                cv2.rectangle(frame, (x, y), (x + width, y + height), color, 2)
                cv2.putText(frame, f"{name} {confidence}%", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            if is_authorized:
                authorized_seen = True

        # Compute FPS.
        current_time = time.time()
        self.fps = 0.9 * self.fps + 0.1 * (1 / max(current_time - self.last_time, 0.001))
        self.last_time = current_time
        if self.show_camera_preview:
            cv2.putText(frame, f"FPS: {int(self.fps)}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        # Automatic lock with countdown.
        if analyzed_this_frame and self.awaiting_camera_verification:
            # Require one real verification cycle after camera recovery before locking.
            if authorized_seen:
                self.last_seen_authorized = current_time
            else:
                self.last_seen_authorized = current_time - LOCK_DELAY_SECONDS
            self.awaiting_camera_verification = False

        if authorized_seen:
            self.last_seen_authorized = current_time
        else:
            elapsed = int(current_time - self.last_seen_authorized)
            remaining = max(0, LOCK_DELAY_SECONDS - elapsed)
            if self.show_camera_preview:
                cv2.putText(frame, f"LOCK IN: {remaining}s", (w//2 - 70, h//2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
            if remaining <= 0:
                if current_time - self.last_lock_time >= self.lock_cooldown_seconds:
                    os.system("rundll32.exe user32.dll,LockWorkStation")
                    self.last_lock_time = current_time
                    self.last_seen_authorized = current_time
                    self.awaiting_camera_verification = True
                    self.cached_faces = []

        if self.show_camera_preview:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            qt_image = QtGui.QImage(frame_rgb.data, w, h, 3 * w, QtGui.QImage.Format.Format_RGB888)
            self.video_label.setPixmap(QtGui.QPixmap.fromImage(qt_image))

    def closeEvent(self, a0):
        self.cleanup()
        super().closeEvent(a0)

    def cleanup(self):
        if self.timer.isActive():
            self.timer.stop()
        if self.cap is not None:
            self.cap.release()
            self.cap = None


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = SentinelGUI(show_camera_preview=True)
    window.show()
    sys.exit(app.exec())
