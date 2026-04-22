import cv2
import json
import joblib
import argparse
import numpy as np
import os
import sys
from datetime import datetime
from scipy.signal import find_peaks
from scipy.spatial.distance import euclidean
##gaitmodel
import requests

# ── Backend API ────────────────────────────────────────────────────────
BACKEND_URL = 'http://127.0.0.1:8000/api/gait/ingest/'
API_KEY     = 'default-secret-key'

def send_to_backend(patient_name, label, confidence, features, zone='East Wing Corridor'):
    """Send gait analysis result to AuraCare backend."""
    try:
        requests.post(
            BACKEND_URL,
            json={
                'patient_id': patient_name,
                'label':      label,
                'confidence': confidence,
                'zone':       zone,
                'features':   features,
            },
            headers={'X-API-KEY': API_KEY},
            timeout=2
        )
    except Exception:
        pass



# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(BASE_DIR, 'data')
MODEL_PATH   = os.path.join(DATA_DIR, 'pose_landmarker.task')
LOCAL_MODEL  = os.path.join(DATA_DIR, 'gait_model_local.pkl')
DB_PATH      = os.path.join(DATA_DIR, 'patient_database.json')
HISTORY_PATH = os.path.join(DATA_DIR, 'patient_history.json')
os.makedirs(DATA_DIR, exist_ok=True)

FEATURE_COLS = [
    'stride_length', 'walking_speed', 'arm_swing',
    'step_variability', 'cadence', 'height_ratio'
]

# ── Config ─────────────────────────────────────────────────────────────
FRAME_SKIP   = 3
MAX_PERSONS  = 5
MIN_FRAMES   = 20
WINDOW_SEC   = 3.0
CONF_THRESH  = 0.3
MATCH_THRESH = 120

PERSON_COLORS = [
    (0,   230, 120),
    (255, 100, 0  ),
    (0,   200, 255),
    (200, 0,   255),
    (0,   140, 255),
]

# ── MediaPipe ──────────────────────────────────────────────────────────
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import (
    PoseLandmarker, PoseLandmarkerOptions, RunningMode
)

print('✅ MediaPipe Tasks API loaded')

LM = {
    'left_shoulder':  11, 'right_shoulder': 12,
    'left_elbow':     13, 'right_elbow':    14,
    'left_wrist':     15, 'right_wrist':    16,
    'left_hip':       23, 'right_hip':      24,
    'left_knee':      25, 'right_knee':     26,
    'left_ankle':     27, 'right_ankle':    28,
    'nose':            0,
}


# ══════════════════════════════════════════════════════════════════════
# LOAD MODEL
# ══════════════════════════════════════════════════════════════════════
def load_model():
    if not os.path.exists(LOCAL_MODEL):
        print(f'❌ Model not found: {LOCAL_MODEL}')
        return None, None, None
    meta = joblib.load(LOCAL_MODEL)
    print(f'✅ Gait model loaded')
    return meta['model'], meta['feature_cols'], meta['label_map']


# ══════════════════════════════════════════════════════════════════════
# KEYPOINT EXTRACTION
# ══════════════════════════════════════════════════════════════════════
def extract_keypoints(landmarks, width, height):
    kps = {}
    for name, idx in LM.items():
        if idx < len(landmarks):
            lm = landmarks[idx]
            if lm.visibility > CONF_THRESH:
                kps[name] = (lm.x * width, lm.y * height)
            else:
                kps[name] = None
        else:
            kps[name] = None
    return kps


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════
def dist(p1, p2):
    return float(np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2))

def angle_deg(p_ref, p_end):
    return float(np.degrees(np.arctan2(
        p_end[1]-p_ref[1], p_end[0]-p_ref[0]
    )))


# ══════════════════════════════════════════════════════════════════════
# GAIT FEATURES (exact same as v3)
# ══════════════════════════════════════════════════════════════════════
def compute_gait_features(kp_sequence):
    valid = [
        kp for kp in kp_sequence
        if kp and kp.get('left_ankle') and kp.get('right_ankle')
        and kp.get('left_hip') and kp.get('right_hip')
    ]
    if len(valid) < 10:
        return None

    ankle_dists = [dist(kp['left_ankle'], kp['right_ankle']) for kp in valid]
    hip_x       = [(kp['left_hip'][0] + kp['right_hip'][0]) / 2 for kp in valid]
    hip_dx      = np.abs(np.diff(hip_x))

    arm_angles = []
    for kp in valid:
        if kp.get('left_shoulder') and kp.get('left_wrist'):
            arm_angles.append(abs(angle_deg(kp['left_shoulder'], kp['left_wrist'])))
        if kp.get('right_shoulder') and kp.get('right_wrist'):
            arm_angles.append(abs(angle_deg(kp['right_shoulder'], kp['right_wrist'])))

    peaks, _ = find_peaks(
        ankle_dists,
        height=np.mean(ankle_dists) * 0.5,
        distance=3
    )

    height_ratios = []
    for kp in valid:
        if kp.get('left_shoulder') and kp.get('right_shoulder') \
                and kp.get('left_ankle'):
            sw = dist(kp['left_shoulder'], kp['right_shoulder'])
            bh = abs(kp['left_shoulder'][1] - kp['left_ankle'][1])
            if sw > 0:
                height_ratios.append(bh / sw)

    return {
        'stride_length':    float(np.mean(ankle_dists)),
        'walking_speed':    float(np.mean(hip_dx)) if len(hip_dx) > 0 else 0.0,
        'arm_swing':        float(np.mean(arm_angles)) if arm_angles else 0.0,
        'step_variability': float(np.std(ankle_dists)),
        'cadence':          float(len(peaks) / len(valid)),
        'height_ratio':     float(np.mean(height_ratios)) if height_ratios else 0.0,
    }


# ══════════════════════════════════════════════════════════════════════
# BODY SHAPE FOR RE-ID (exact same as v3)
# ══════════════════════════════════════════════════════════════════════
def extract_body_shape(kps, width, height):
    if not kps:
        return None

    shoulder_w = dist(kps['left_shoulder'], kps['right_shoulder']) \
        if kps.get('left_shoulder') and kps.get('right_shoulder') else 0.0
    hip_w = dist(kps['left_hip'], kps['right_hip']) \
        if kps.get('left_hip') and kps.get('right_hip') else 0.0
    body_h = dist(kps['nose'], kps['left_ankle']) \
        if kps.get('nose') and kps.get('left_ankle') else 0.0

    if kps.get('left_wrist') and kps.get('right_wrist') and kps.get('left_hip'):
        left_arm  = dist(kps['left_wrist'], kps['left_hip'])
        right_arm = dist(kps['right_wrist'], kps['right_hip']) \
            if kps.get('right_hip') else left_arm
        asym = abs(left_arm - right_arm) / max(left_arm + right_arm, 1)
    else:
        asym = 0.0

    return {
        'shoulder_w': shoulder_w / width,
        'hip_w':      hip_w / width,
        'body_h':     body_h / height,
        'h_w_ratio':  body_h / max(shoulder_w, 1),
        'asym':       asym,
    }


def sig_to_vec(sig):
    keys = ['shoulder_w', 'hip_w', 'body_h', 'h_w_ratio', 'asym',
            'stride_length', 'walking_speed', 'arm_swing',
            'step_variability', 'cadence', 'height_ratio']
    return np.array([sig.get(k, 0.0) for k in keys], dtype=float)


# ══════════════════════════════════════════════════════════════════════
# DATABASE (exact same as v3)
# ══════════════════════════════════════════════════════════════════════
def load_db():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, 'r') as f:
            return json.load(f)
    return {'patients': {}}

def save_db(db):
    with open(DB_PATH, 'w') as f:
        json.dump(db, f, indent=2)

def load_history():
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, 'r') as f:
            return json.load(f)
    return {'patients': {}}

def save_history(h):
    with open(HISTORY_PATH, 'w') as f:
        json.dump(h, f, indent=2)


def identify_person(sig, threshold=0.5):
    db = load_db()
    if not db['patients'] or sig is None:
        return 'unknown', 'Unknown', 0.0

    new_vec  = sig_to_vec(sig)
    new_norm = new_vec / (np.linalg.norm(new_vec) + 1e-8)

    best_id, best_name, best_dist = None, None, float('inf')
    for pid, info in db['patients'].items():
        reg_vec  = sig_to_vec(info['signature'])
        reg_norm = reg_vec / (np.linalg.norm(reg_vec) + 1e-8)
        d        = float(euclidean(new_norm, reg_norm))
        if d < best_dist:
            best_dist, best_id, best_name = d, pid, info['name']

    confidence = max(0.0, (1 - best_dist) * 100)
    if best_dist > threshold:
        return 'unknown', 'Unknown', confidence
    return best_id, best_name, confidence


def register_patient(name, sig):
    db  = load_db()
    pid = f'P{len(db["patients"])+1:03d}'
    db['patients'][pid] = {
        'name':      name,
        'signature': sig,
        'sessions':  []
    }
    save_db(db)
    return pid


def log_session(pid, name, features, label, confidence):
    h = load_history()
    if pid not in h['patients']:
        h['patients'][pid] = {'name': name, 'sessions': []}
    h['patients'][pid]['sessions'].append({
        'date':       datetime.now().strftime('%Y-%m-%d'),
        'time':       datetime.now().strftime('%H:%M:%S'),
        'label':      label,
        'confidence': round(confidence, 1),
        'features':   {k: round(v, 4) for k, v in features.items()},
    })
    save_history(h)


# ══════════════════════════════════════════════════════════════════════
# DRAWING (same style as v3)
# ══════════════════════════════════════════════════════════════════════
def draw_skeleton(frame, kps, color):
    connections = [
        ('left_shoulder',  'right_shoulder'),
        ('left_shoulder',  'left_elbow'),
        ('left_elbow',     'left_wrist'),
        ('right_shoulder', 'right_elbow'),
        ('right_elbow',    'right_wrist'),
        ('left_hip',       'right_hip'),
        ('left_shoulder',  'left_hip'),
        ('right_shoulder', 'right_hip'),
        ('left_hip',       'left_knee'),
        ('left_knee',      'left_ankle'),
        ('right_hip',      'right_knee'),
        ('right_knee',     'right_ankle'),
    ]
    for a, b in connections:
        if kps.get(a) and kps.get(b):
            cv2.line(frame,
                     (int(kps[a][0]), int(kps[a][1])),
                     (int(kps[b][0]), int(kps[b][1])),
                     color, 2)
    for pt in kps.values():
        if pt:
            cv2.circle(frame, (int(pt[0]), int(pt[1])), 5, (255, 100, 0), -1)


def draw_person_ui(frame, kps, label, confidence, features, patient_name, tid):
    h_frame, w_frame = frame.shape[:2]
    ref = kps.get('nose') or kps.get('left_shoulder') or kps.get('right_shoulder')
    if not ref:
        return

    x, y = int(ref[0]), max(int(ref[1]) - 15, 50)

    if label == 'normal':
        color = (0, 200, 80)
        text  = f'P{tid} {patient_name} | NORMAL ({confidence:.0f}%)'
    elif label == 'abnormal':
        color = (0, 60, 220)
        text  = f'P{tid} {patient_name} | ABNORMAL ({confidence:.0f}%)'
    else:
        color = (180, 180, 180)
        text  = f'P{tid} {patient_name} | Collecting...'

    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
    cv2.rectangle(frame, (x-4, y-th-6), (x+tw+4, y+4), (25, 25, 25), -1)
    cv2.putText(frame, text, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


def draw_hud(frame, n_persons, frame_idx, total_frames=None):
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 35), (25, 25, 25), -1)
    info = f'Gait Monitor v4  |  Persons: {n_persons}'
    if total_frames:
        info += f'  |  Frame: {frame_idx}/{total_frames}'
    cv2.putText(frame, info, (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1)
    cv2.putText(frame, 'Q:quit  R:register  C:clear',
                (10, h - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 120), 1)


# ══════════════════════════════════════════════════════════════════════
# PERSON TRACKER
# ══════════════════════════════════════════════════════════════════════
class PersonTracker:
    def __init__(self, max_persons=5, max_lost=30):
        self.tracks      = {}
        self.next_id     = 0
        self.max_persons = max_persons
        self.max_lost    = max_lost

    def _hip_center(self, kps):
        if kps.get('left_hip') and kps.get('right_hip'):
            lh, rh = kps['left_hip'], kps['right_hip']
            return ((lh[0]+rh[0])/2, (lh[1]+rh[1])/2)
        return None

    def update(self, kps_list, fps):
        centers = [self._hip_center(k) for k in kps_list]

        for tid in list(self.tracks.keys()):
            self.tracks[tid]['lost'] += 1
            if self.tracks[tid]['lost'] > self.max_lost:
                del self.tracks[tid]

        assigned = set()
        result   = []

        for i, kps in enumerate(kps_list):
            c = centers[i]
            best_tid, best_d = None, float('inf')

            if c:
                for tid, tr in self.tracks.items():
                    if tid in assigned:
                        continue
                    if tr.get('last_center'):
                        d = dist(c, tr['last_center'])
                        if d < best_d:
                            best_d, best_tid = d, tid

            if best_tid is not None and best_d < MATCH_THRESH:
                tid = best_tid
            else:
                if len(self.tracks) >= self.max_persons:
                    continue
                tid = self.next_id
                self.next_id += 1
                self.tracks[tid] = {
                    'kp_seq':       [],
                    'shape_list':   [],
                    'label':        '',
                    'confidence':   0.0,
                    'features':     {},
                    'patient_id':   'unknown',
                    'patient_name': 'Unknown',
                    'last_center':  None,
                    'last_analyzed':0,
                    'lost':         0,
                    'color':        PERSON_COLORS[tid % len(PERSON_COLORS)],
                }

            tr = self.tracks[tid]
            tr['lost']        = 0
            tr['last_center'] = c
            tr['kp_seq'].append(kps)
            if len(tr['kp_seq']) > 150:
                tr['kp_seq'].pop(0)

            assigned.add(tid)
            result.append((tid, kps))

        return result


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
def run(source=0, output_path=None):
    model, feat_cols, label_map = load_model()
    if model is None:
        return

    if not os.path.exists(MODEL_PATH):
        print(f'❌ Pose model not found: {MODEL_PATH}')
        return

    db = load_db()
    print(f'✅ Database: {len(db["patients"])} registered patients')

    print('\n=== Gait Monitor v4 — Multi-Person ===')
    print('Controls:')
    print('  Q     — quit')
    print('  R     — register current person')
    print('  C     — clear session')
    print()

    options = PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=RunningMode.VIDEO,
        num_poses=MAX_PERSONS,
        min_pose_detection_confidence=CONF_THRESH,
        min_pose_presence_confidence=CONF_THRESH,
        min_tracking_confidence=CONF_THRESH,
    )

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f'❌ Cannot open: {source}')
        return

    fps    = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f'✅ Source: {width}x{height} @ {fps:.0f}fps')

    writer = None
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        print(f'✅ Recording to: {output_path}')

    tracker       = PersonTracker(max_persons=MAX_PERSONS)
    frame_idx     = 0
    window_frames = int(fps * WINDOW_SEC)

    with PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ret, frame = cap.read()
            if not ret:
                print('End of stream.')
                break

            frame_idx += 1
            timestamp_ms = int((frame_idx / fps) * 1000)

            if frame_idx % FRAME_SKIP != 0:
                if writer:
                    writer.write(frame)
                cv2.imshow('Gait Monitor v4', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result   = landmarker.detect_for_video(mp_image, timestamp_ms)

            kps_list = []
            for person_landmarks in result.pose_landmarks:
                kps = extract_keypoints(person_landmarks, width, height)
                kps_list.append(kps)

            tracked = tracker.update(kps_list, fps)

            for track_idx, (tid, kps) in enumerate(tracked):
                tr    = tracker.tracks[tid]
                color = tr['color']

                # Body shape for re-ID
                shape = extract_body_shape(kps, width, height)
                if shape:
                    tr['shape_list'].append(shape)
                    if len(tr['shape_list']) > 30:
                        tr['shape_list'].pop(0)

                # Auto-identify
                if (len(tr['shape_list']) >= 10 and
                        tr['patient_id'] == 'unknown'):
                    shape_keys = list(tr['shape_list'][0].keys())
                    avg_shape  = {
                        k: float(np.mean([s[k] for s in tr['shape_list']]))
                        for k in shape_keys
                    }
                    feats_so_far = compute_gait_features(tr['kp_seq'])
                    sig = {**avg_shape, **feats_so_far} if feats_so_far else avg_shape
                    pid, pname, conf_id = identify_person(sig)
                    if pid != 'unknown':
                        tr['patient_id']   = pid
                        tr['patient_name'] = pname
                        print(f'  👤 Identified: {pname} (Track {tid})')

                # Gait analysis
                if (len(tr['kp_seq']) >= MIN_FRAMES and
                        frame_idx - tr['last_analyzed'] >= window_frames):

                    tr['last_analyzed'] = frame_idx
                    feats = compute_gait_features(tr['kp_seq'])

                    if feats:
                        X    = np.array([[feats[c] for c in feat_cols]])
                        pred = model.predict(X)[0]
                        prob = model.predict_proba(X)[0]
                        tr['label']      = label_map[pred]
                        tr['confidence'] = float(prob[pred] * 100)
                        tr['features']   = feats
                        send_to_backend(
                            tr['patient_name'],
                            tr['label'],
                            tr['confidence'],
                            feats
                        )

                        print(f'\n👤 {tr["patient_name"]} | {tr["label"]} ({tr["confidence"]:.0f}%)')
                        for k, v in feats.items():
                            print(f'   {k:<22s}: {v:.4f}')

                        if tr['patient_id'] != 'unknown':
                            log_session(tr['patient_id'], tr['patient_name'],
                                        feats, tr['label'], tr['confidence'])
                            print(f'  💾 Logged: {tr["patient_name"]} — {tr["label"]}')

                draw_skeleton(frame, kps, color)
                draw_person_ui(frame, kps,
                               tr['label'], tr['confidence'],
                               tr['features'], tr['patient_name'], tid)

            draw_hud(frame, len(tracked), frame_idx,
                     total if total > 0 else None)

            if writer:
                writer.write(frame)

            cv2.imshow('Gait Monitor v4', frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                break

            elif key == ord('r'):
                if tracked:
                    tid0, _ = tracked[0]
                    tr0 = tracker.tracks[tid0]
                    feats0 = compute_gait_features(tr0['kp_seq'])
                    if feats0 and tr0['shape_list']:
                        shape_keys = list(tr0['shape_list'][0].keys())
                        avg_shape  = {
                            k: float(np.mean([s[k] for s in tr0['shape_list']]))
                            for k in shape_keys
                        }
                        sig = {**avg_shape, **feats0}
                        cv2.destroyAllWindows()
                        name = input(f'\nRegister Track {tid0} — Enter patient name: ').strip()
                        if name:
                            pid = register_patient(name, sig)
                            tr0['patient_id']   = pid
                            tr0['patient_name'] = name
                            print(f'✅ {name} registered as {pid}')
                        cap = cv2.VideoCapture(source)
                    else:
                        print('⚠️  Not enough frames to register.')

            elif key == ord('c'):
                for tr in tracker.tracks.values():
                    tr['kp_seq']    = []
                    tr['shape_list']= []
                    tr['label']     = ''
                    tr['features']  = {}
                print('✅ Session cleared.')

    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()
    print('\n✅ Session ended.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gait Monitor v4 — Multi-Person')
    parser.add_argument('--mode',   choices=['live', 'video'], default='live')
    parser.add_argument('--path',   type=str, default=None)
    parser.add_argument('--output', type=str, default=None)
    parser.add_argument('--camera', type=int, default=0)
    args = parser.parse_args()

    if args.mode == 'video':
        if not args.path:
            print('❌ Provide --path for video mode')
        else:
            run(source=args.path, output_path=args.output)
    else:
        run(source=args.camera, output_path=args.output)
