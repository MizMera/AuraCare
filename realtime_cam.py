"""
Test en temps réel avec webcam
Social Isolation Detection — YOLOv8 + DeepSORT + LSTM
------------------------------------------------------
Prérequis:
  pip install ultralytics deep-sort-realtime opencv-python torch scikit-learn

Usage:
  python realtime_cam.py --model best_visual_model.pt --cam 0
"""

import argparse
import numpy as np
import cv2
import torch
import torch.nn as nn
from collections import deque
from sklearn.preprocessing import StandardScaler

from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

# ──────────────────────────────────────────────────────────
# CONFIG (doit correspondre à ton notebook)
# ──────────────────────────────────────────────────────────
WINDOW_SIZE   = 20
PROXIMITY_THR = 150   # pixels
DEVICE        = 'cuda' if torch.cuda.is_available() else 'cpu'

CLASS_LABELS = ['Actif', 'Vigilance', 'Isolé']
CLASS_COLORS = [(0, 200, 80), (0, 165, 255), (0, 0, 220)]   # BGR


# ──────────────────────────────────────────────────────────
# MODÈLE (copie exacte depuis ton notebook)
# ──────────────────────────────────────────────────────────
class VisualIsolationLSTM(nn.Module):
    def __init__(self, input_size=3, hidden_size=32, num_layers=2, dropout=0.4, num_classes=3):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers,
                            batch_first=True, dropout=dropout, bidirectional=True)
        self.bn1      = nn.BatchNorm1d(hidden_size * 2)
        self.dropout1 = nn.Dropout(dropout)
        self.attention = nn.Sequential(
            nn.Linear(hidden_size * 2, hidden_size),
            nn.Tanh(),
            nn.Linear(hidden_size, 1)
        )
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size * 2, 32),
            nn.ReLU(),
            nn.BatchNorm1d(32),
            nn.Dropout(dropout),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Dropout(dropout * 0.8),
            nn.Linear(16, num_classes)
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        out    = self.bn1(out.transpose(1, 2)).transpose(1, 2)
        attn   = torch.softmax(self.attention(out), dim=1)
        ctx    = (attn * out).sum(dim=1)
        ctx    = self.dropout1(ctx)
        return self.classifier(ctx)


# ──────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────
def load_model(model_path):
    model = VisualIsolationLSTM().to(DEVICE)
    model.load_state_dict(torch.load(model_path, map_location=DEVICE))
    model.eval()
    print(f"✅ Modèle chargé depuis {model_path}")
    return model


def detect_and_track(frame, yolo_model, tracker):
    results = yolo_model(frame, classes=[0], verbose=False)
    detections = []
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = box.conf[0].item()
            if conf > 0.4:
                detections.append(([x1, y1, x2 - x1, y2 - y1], conf, 0))

    if not detections:
        return {}

    tracks = tracker.update_tracks(detections, frame=frame)
    tracked_persons = {}
    for track in tracks:
        if not track.is_confirmed():
            continue
        tid = track.track_id
        l, t, r, b = track.to_ltrb()
        tracked_persons[tid] = {'bbox': (int(l), int(t), int(r), int(b)),
                                 'cx': (l + r) / 2, 'cy': (t + b) / 2}

    features_by_id = {}
    person_list = list(tracked_persons.items())
    for tid, p in person_list:
        distances = [
            np.sqrt((p['cx'] - o['cx']) ** 2 + (p['cy'] - o['cy']) ** 2)
            for other_tid, o in person_list if other_tid != tid
        ]
        dist_nearest = min(distances) if distances else 999
        neighbors    = sum(1 for d in distances if d <= PROXIMITY_THR)
        features_by_id[tid] = {
            'bbox':         p['bbox'],
            'cx':           p['cx'], 'cy': p['cy'],
            'dist_nearest': dist_nearest,
            'neighbors':    neighbors,
            'isolated':     1.0 if dist_nearest > PROXIMITY_THR else 0.0,
        }
    return features_by_id


def predict_class(seq_deque, model, scaler):
    """Prédit la classe sur la fenêtre glissante."""
    if len(seq_deque) < WINDOW_SIZE:
        return None, None
    seq = np.array([[f['dist_nearest'], f['neighbors'], f['isolated']]
                    for f in seq_deque], dtype=np.float32)
    seq_s  = scaler.transform(seq)
    tensor = torch.FloatTensor(seq_s).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        probs = torch.softmax(model(tensor), dim=1).cpu().numpy()[0]
    return int(np.argmax(probs)), probs


def draw_overlay(frame, tid, bbox, pred_class, probs, feat):
    """Dessine la bounding box et les infos sur la frame."""
    if pred_class is None:
        return
    x1, y1, x2, y2 = bbox
    color = CLASS_COLORS[pred_class]
    label = CLASS_LABELS[pred_class]
    conf  = probs[pred_class] * 100

    # Bounding box
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    # Badge en haut
    badge_text = f"ID{tid} | {label} {conf:.0f}%"
    (tw, th), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
    cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 6, y1), color, -1)
    cv2.putText(frame, badge_text, (x1 + 3, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

    # Mini stats sous le badge
    info = f"dist={feat['dist_nearest']:.0f}px  nb={feat['neighbors']}"
    cv2.putText(frame, info, (x1 + 3, y2 + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)


def draw_hud(frame, track_states):
    """HUD global en haut à gauche."""
    counts = [0, 0, 0]
    for state in track_states.values():
        if state is not None:
            counts[state] += 1
    icons = ["🟢 Actif", "🟡 Vigilance", "🔴 Isolé"]
    for i, (icon, cnt) in enumerate(zip(icons, counts)):
        text  = f"{icon}: {cnt}"
        color = CLASS_COLORS[i]
        cv2.putText(frame, text, (12, 30 + i * 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    cv2.putText(frame, "Q  quitter  |  S  screenshot", (12, frame.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)


# ──────────────────────────────────────────────────────────
# MAIN LOOP
# ──────────────────────────────────────────────────────────
def run(model_path, cam_index):
    # Charger modèles
    yolo    = YOLO('yolov8n.pt')
    model   = load_model(model_path)
    tracker = DeepSort(max_age=30, n_init=3, max_iou_distance=0.7)

    # Scaler : ajusté sur quelques valeurs typiques
    # (en production, sauvegarder le scaler avec joblib depuis le notebook)
    scaler = StandardScaler()
    scaler.mean_  = np.array([200.0, 2.0, 0.5])
    scaler.scale_ = np.array([100.0, 1.5, 0.4])
    scaler.var_   = scaler.scale_ ** 2
    scaler.n_features_in_ = 3

    cap = cv2.VideoCapture(cam_index)
    if not cap.isOpened():
        print(f"❌ Impossible d'ouvrir la caméra {cam_index}")
        return

    # Résolution conseillée pour la perf
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("🎥 Caméra ouverte. Appuyez sur Q pour quitter, S pour screenshot.")

    histories    = {}   # tid → deque(feat, maxlen=WINDOW_SIZE)
    pred_classes = {}   # tid → int ou None
    pred_probs   = {}   # tid → np.array
    last_feats   = {}   # tid → dict de la dernière frame
    frame_idx    = 0
    shot_count   = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Détection + tracking (toutes les frames)
        features_by_id = detect_and_track(frame, yolo, tracker)

        for tid, feat in features_by_id.items():
            if tid not in histories:
                histories[tid] = deque(maxlen=WINDOW_SIZE)
            histories[tid].append(feat)
            last_feats[tid] = feat

            # Prédiction toutes les 5 frames (équilibre perf/latence)
            if frame_idx % 5 == 0:
                pc, pp = predict_class(histories[tid], model, scaler)
                pred_classes[tid] = pc
                pred_probs[tid]   = pp

        # Dessin
        for tid in features_by_id:
            pc = pred_classes.get(tid)
            pp = pred_probs.get(tid, np.zeros(3))
            if pc is not None:
                draw_overlay(frame, tid, last_feats[tid]['bbox'], pc, pp, last_feats[tid])

        draw_hud(frame, pred_classes)

        cv2.imshow("Social Isolation Detection — Webcam (Q pour quitter)", frame)
        frame_idx += 1

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            shot_count += 1
            fname = f"screenshot_{shot_count:03d}.png"
            cv2.imwrite(fname, frame)
            print(f"📸 Screenshot sauvegardé : {fname}")

    cap.release()
    cv2.destroyAllWindows()
    print("✅ Session terminée.")


# ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Isolation sociale — webcam temps réel')
    parser.add_argument('--model', default='best_visual_model.pt',
                        help='Chemin vers best_visual_model.pt (défaut: ./best_visual_model.pt)')
    parser.add_argument('--cam',   type=int, default=0,
                        help='Index de la caméra (défaut: 0)')
    args = parser.parse_args()
    run(args.model, args.cam)
