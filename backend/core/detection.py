import os

from ultralytics import YOLO

from .utils import check_absence_alert, update_person_count

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "bestt.pt")
model = YOLO(MODEL_PATH)


def process_frame(frame):
    results = model(frame, verbose=False)
    nb_personnes = sum(1 for box in results[0].boxes if int(box.cls) == 0)
    update_person_count(nb_personnes)
    check_absence_alert(nb_personnes, frame)
    return results[0].plot()
