# detection/detection.py
import os
from ultralytics import YOLO
from .utils import check_absence_alert, update_person_count

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(BASE_DIR, "bestt.pt")
model = YOLO(model_path)

def process_frame(frame):
    """
    Traite un frame vidéo, détecte les personnes et vérifie les absences.
    """
    results = model(frame)
    nb_personnes = sum(1 for box in results[0].boxes if int(box.cls) == 0)
    # Mettre à jour le compteur global
    update_person_count(nb_personnes)

    # Vérifier les absences par rapport aux repas
    check_absence_alert(nb_personnes, frame)
    
    return results[0].plot()