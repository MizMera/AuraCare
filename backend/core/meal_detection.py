import os
from functools import lru_cache

import cv2

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover - optional runtime dependency
    YOLO = None


class PeopleDetector:
    def __init__(self):
        self.model = None
        self.model_name = 'hog'
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self._load_optional_model()

    def _load_optional_model(self):
        if YOLO is None:
            return
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bestt.pt')
        if not os.path.exists(model_path):
            return
        try:
            self.model = YOLO(model_path)
            self.model_name = 'yolo-bestt'
        except Exception:
            self.model = None
            self.model_name = 'hog'

    def process(self, frame):
        if self.model is not None:
            return self._process_yolo(frame)
        return self._process_hog(frame)

    def _process_yolo(self, frame):
        results = self.model(frame, verbose=False)
        boxes = []
        count = 0
        for box in results[0].boxes:
            cls = int(box.cls[0]) if hasattr(box.cls, '__len__') else int(box.cls)
            if cls != 0:
                continue
            count += 1
            coords = box.xyxy[0].tolist()
            x1, y1, x2, y2 = [int(value) for value in coords]
            boxes.append((x1, y1, x2 - x1, y2 - y1))
        annotated = results[0].plot()
        return annotated, count, boxes

    def _process_hog(self, frame):
        boxes, _ = self.hog.detectMultiScale(
            frame,
            winStride=(8, 8),
            padding=(8, 8),
            scale=1.05,
        )
        annotated = frame.copy()
        for (x, y, w, h) in boxes:
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (68, 166, 181), 2)
        return annotated, len(boxes), boxes


@lru_cache(maxsize=1)
def get_people_detector():
    return PeopleDetector()
