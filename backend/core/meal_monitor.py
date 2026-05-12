import os
import threading
import time
from datetime import datetime, timedelta

import cv2
import numpy as np
from django.utils import timezone

from .meal_detection import get_people_detector
from .models import CustomUser, Incident, MealTime, Notification, Zone
from .utils import get_current_meal, update_person_count, check_absence_alert

class MealAttendanceEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._capture = None
        self._running = False
        self._latest_frame = None
        self._latest_count = 0
        self._last_error = ''
        self._last_snapshot = {
            'count': 0,
            'active_meal': None,
            'expected_people': None,
            'mismatch': False,
            'missing_count': 0,
            'model': 'hog',
            'last_checked_at': None,
        }
        self._detector = get_people_detector()
        self._backend_name = 'uninitialized'

    @property
    def status(self):
        with self._lock:
            return {
                'running': self._running,
                'count': self._latest_count,
                'error': self._last_error,
                'camera_backend': self._backend_name,
                **self._last_snapshot,
            }

    def start(self, camera_idx=0):
        response = None
        with self._lock:
            if self._running:
                response = {
                    'running': self._running,
                    'count': self._latest_count,
                    'error': self._last_error,
                    'camera_backend': self._backend_name,
                    **self._last_snapshot,
                }
            else:
                self._capture, self._backend_name = self._open_capture(camera_idx)
                if not self._capture.isOpened():
                    if self._capture:
                        self._capture.release()
                    self._capture = None
                    self._last_error = 'Unable to access meal attendance camera. Close any app already using the webcam and try again.'
                    response = {
                        'running': self._running,
                        'count': self._latest_count,
                        'error': self._last_error,
                        'camera_backend': self._backend_name,
                        **self._last_snapshot,
                    }
                else:
                    self._running = True
                    self._last_error = ''
                    self._thread = threading.Thread(target=self._run, daemon=True)
                    self._thread.start()

        return response or self.status

    def stop(self):
        thread = None
        with self._lock:
            self._running = False
            thread = self._thread
            capture = self._capture
            self._thread = None
            self._capture = None
            self._latest_frame = None
            self._latest_count = 0
            self._last_snapshot = {
                'count': 0,
                'active_meal': None,
                'expected_people': None,
                'mismatch': False,
                'missing_count': 0,
                'model': self._detector.model_name,
                'last_checked_at': timezone.now().isoformat(),
            }
        if capture:
            capture.release()
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
            if thread.is_alive():
                thread.daemon = True
        return self.status

    def latest_jpeg(self):
        with self._lock:
            if self._latest_frame is None:
                return None
            ok, encoded = cv2.imencode('.jpg', self._latest_frame)
            if not ok:
                return None
            return encoded.tobytes()

    def _run(self):
        consecutive_failures = 0
        while self._running:
            with self._lock:
                if not self._running or self._capture is None:
                    break
                capture = self._capture

            ok, frame = capture.read()
            if not ok:
                consecutive_failures += 1
                with self._lock:
                    self._last_error = (
                        'Unable to read frames from meal attendance camera. '
                        'This often means Windows denied the current camera backend or another app is using it.'
                    )
                    if consecutive_failures >= 12:
                        self._running = False
                time.sleep(0.2)
                continue

            consecutive_failures = 0
            annotated, count, _boxes = self._detector.process(frame)
            snapshot = self._build_snapshot(count)
            #self._render_overlay(annotated, snapshot)

            with self._lock:
                self._latest_frame = annotated
                self._latest_count = count
                self._last_snapshot = snapshot
                self._last_error = ''

            # ✅ NOUVEAU : Mise à jour du compteur global
            update_person_count(count)
            
            # ✅ NOUVEAU : Alerte avec logique T+1 minute
            check_absence_alert(count, annotated)
            
            # ❌ ANCIEN : À commenter pour éviter les doublons
            # self._emit_alert_if_needed(snapshot)
            
            time.sleep(0.15)
        with self._lock:
            if self._capture:
                self._capture.release()
                self._capture = None

    def _open_capture(self, camera_idx):
        candidates = []
        if os.name == 'nt':
            candidates.extend([
                ('dshow', cv2.CAP_DSHOW),
                ('any', None),
                ('msmf', cv2.CAP_MSMF),
            ])
        else:
            candidates.append(('any', None))

        for backend_name, backend_flag in candidates:
            capture = cv2.VideoCapture(camera_idx, backend_flag) if backend_flag is not None else cv2.VideoCapture(camera_idx)
            if not capture or not capture.isOpened():
                if capture:
                    capture.release()
                continue
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return capture, backend_name

        fallback = cv2.VideoCapture(camera_idx)
        return fallback, 'fallback'

    def _build_snapshot(self, count):
        now = timezone.localtime()
        active_meal = get_current_meal() 
        expected = active_meal.expected_people if active_meal else None
        missing = max(0, (expected or 0) - count) if active_meal else 0
        mismatch = bool(active_meal and count < expected)
        return {
            'count': count,
            'active_meal': {
                'id': active_meal.id,
                'name': active_meal.name,
                'time': active_meal.time.strftime('%H:%M:%S'),
            } if active_meal else None,
            'expected_people': expected,
            'mismatch': mismatch,
            'missing_count': missing,
            'model': self._detector.model_name,
            'last_checked_at': now.isoformat(),
        }


    
    def _render_overlay(self, frame, snapshot):
        pass

_ENGINE = MealAttendanceEngine()


def get_meal_attendance_engine():
    return _ENGINE


def analyse_meal_frame_bytes(frame_bytes):
    if not frame_bytes:
        raise ValueError('No frame bytes received.')

    array = np.frombuffer(frame_bytes, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError('Unable to decode the uploaded frame.')

    detector = get_people_detector()
    _annotated, count, _boxes = detector.process(frame)
    snapshot = _ENGINE._build_snapshot(count)
    return snapshot
