# ==============================================
# AuraCare — Aggression Detection MJPEG Streamer
# ==============================================
# Provides a Django StreamingHttpResponse that serves
# annotated camera frames as an MJPEG stream for the
# browser dashboard.

import os
import time
import collections
import threading
import numpy as np
import cv2
import torch
import torch.nn as nn
import torch.nn.functional as torchF
import pickle
import requests

# ══════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════
WINDOW_SIZE = 30
NUM_KEYPOINTS = 33
KEYPOINT_DIMS = 3
AGGRESSION_THRESHOLD = 0.7
VISION_HIDDEN_SIZE = 128
VISION_NUM_LAYERS = 2
MAX_PERSONS = 3

CORE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

# ══════════════════════════════════════════════
# MODEL
# ══════════════════════════════════════════════
class AggressionLSTM(nn.Module):
    def __init__(self, input_size, hidden_size=VISION_HIDDEN_SIZE,
                 num_layers=VISION_NUM_LAYERS, dropout=0.0, num_classes=2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size, hidden_size=hidden_size,
            num_layers=num_layers, batch_first=True, bidirectional=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size * 2, num_classes)

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        return self.fc(self.dropout(lstm_out[:, -1, :]))


# ══════════════════════════════════════════════
# KINETIC FEATURES
# ══════════════════════════════════════════════
def _vel(kps):
    return kps[1:, :, :2] - kps[:-1, :, :2]

def _ke(vel):
    return np.sum(vel ** 2, axis=(1, 2))

def _acc(vel):
    return vel[1:] - vel[:-1]

def _jerk(acc):
    return acc[1:] - acc[:-1]

def _inter_hand(kps):
    return np.linalg.norm(kps[:, 15, :2] - kps[:, 16, :2], axis=1)

def _hand_face(kps):
    nose = kps[:, 0, :2]
    return np.minimum(
        np.linalg.norm(kps[:, 15, :2] - nose, axis=1),
        np.linalg.norm(kps[:, 16, :2] - nose, axis=1),
    )

def _bp_vel(kps):
    pos = kps[:, :, :2]
    vel = pos[1:] - pos[:-1]
    speed = np.sqrt((vel ** 2).sum(axis=2))
    return np.column_stack([
        speed[:, [15, 16, 17, 18, 19, 20]].mean(axis=1),
        speed[:, [27, 28, 29, 30, 31, 32]].mean(axis=1),
        speed[:, [11, 12, 23, 24]].mean(axis=1),
    ])

def _spread(kps):
    x, y = kps[:, :, 0], kps[:, :, 1]
    return (x.max(axis=1) - x.min(axis=1)) * (y.max(axis=1) - y.min(axis=1))

def _angles(kps):
    trips = [(11, 13, 15), (12, 14, 16), (23, 25, 27), (24, 26, 28)]
    def _a(a, b, c):
        ba, bc = a - b, c - b
        cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
        return np.degrees(np.arccos(np.clip(cos, -1, 1)))
    out = np.zeros((len(kps), 4))
    for i in range(len(kps)):
        for j, (p1, p2, p3) in enumerate(trips):
            out[i, j] = _a(kps[i, p1, :2], kps[i, p2, :2], kps[i, p3, :2])
    return out

def extract_features(kps):
    v = _vel(kps)
    ke = _ke(v)
    mv = np.mean(np.abs(v), axis=(1, 2))
    xv = np.max(np.abs(v), axis=(1, 2))
    a = _acc(v)
    ma = np.concatenate(([0], np.mean(np.abs(a), axis=(1, 2))))
    j = _jerk(a)
    mj = np.concatenate(([0, 0], np.mean(np.abs(j), axis=(1, 2))))
    return np.column_stack([
        ke, mv, xv, ma, mj,
        _inter_hand(kps)[1:], _hand_face(kps)[1:],
        _bp_vel(kps), _spread(kps)[1:], _angles(kps)[1:],
    ])


# ══════════════════════════════════════════════
# MEDIAPIPE
# ══════════════════════════════════════════════
from mediapipe.tasks.python.vision import pose_landmarker as _pl
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode
from mediapipe.tasks.python.vision.core.image import Image as _MpImage
from mediapipe.tasks.python.vision.core.image import ImageFormat as _MpFmt

def _init_pose():
    path = os.path.join(CORE_DIR, "pose_landmarker_lite.task")
    opts = _pl.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=path),
        running_mode=VisionTaskRunningMode.VIDEO,
        num_poses=MAX_PERSONS,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return _pl.PoseLandmarker.create_from_options(opts)

def _extract_kps(pose, frame, ts_ms):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    res = pose.detect_for_video(_MpImage(image_format=_MpFmt.SRGB, data=rgb), ts_ms)
    if not res.pose_landmarks:
        return []
    return [
        np.array([[lm.x, lm.y, lm.visibility] for lm in pl], dtype=np.float32)
        for pl in res.pose_landmarks
    ]


# ══════════════════════════════════════════════
# DRAW HELPERS
# ══════════════════════════════════════════════
_SAFE = (0, 200, 0)
_WARN = (0, 200, 255)
_CRIT = (0, 0, 255)
_BG   = (40, 40, 40)
_PCOL = [(255, 200, 0), (0, 255, 200), (200, 100, 255)]
_PCOL_F = [(0, 0, 255), (0, 80, 255), (0, 50, 200)]

POSE_CONNS = [
    (0,1),(1,2),(2,3),(3,7),(0,4),(4,5),(5,6),(6,8),
    (9,10),(11,12),(11,13),(13,15),(12,14),(14,16),
    (11,23),(12,24),(23,24),(23,25),(25,27),(24,26),(26,28),
    (15,17),(15,19),(15,21),(16,18),(16,20),(16,22),
    (27,29),(27,31),(28,30),(28,32),
]

def _draw_skel(f, kps, color, label=None):
    h, w = f.shape[:2]
    for i in range(NUM_KEYPOINTS):
        x, y, vis = int(kps[i, 0]*w), int(kps[i, 1]*h), kps[i, 2]
        if vis > 0.3:
            cv2.circle(f, (x, y), 3, color, -1)
    for p1, p2 in POSE_CONNS:
        if kps[p1, 2] > 0.3 and kps[p2, 2] > 0.3:
            cv2.line(f,
                (int(kps[p1,0]*w), int(kps[p1,1]*h)),
                (int(kps[p2,0]*w), int(kps[p2,1]*h)), color, 2)
    if label and kps[0, 2] > 0.3:
        cv2.putText(f, label, (int(kps[0,0]*w)-5, int(kps[0,1]*h)-15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

def _draw_hud(f, alert, conf, fps, n_pers, pp_conf, thresh):
    h, w = f.shape[:2]
    if alert == "FIGHT":
        color, label = _CRIT, "AGGRESSION DETECTED"
    elif alert == "CAUTION":
        color, label = _WARN, "CAUTION"
    else:
        color, label = _SAFE, "SAFE"
    # top bar
    cv2.rectangle(f, (0, 0), (w, 50), _BG, -1)
    cv2.putText(f, "AuraCare LIVE", (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)
    bw = 350
    cv2.rectangle(f, (w-bw-10, 5), (w-10, 45), color, -1)
    cv2.putText(f, label, (w-bw+5, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,255,255), 2)
    # bottom bar
    cv2.rectangle(f, (0, h-40), (w, h), _BG, -1)
    cv2.putText(f, f"Conf: {conf:.0%}  |  FPS: {fps:.0f}  |  Persons: {n_pers}",
                (10, h-12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200,200,200), 1)
    # confidence bar
    bx, by, bw2, bh = 10, 60, 200, 20
    cv2.rectangle(f, (bx, by), (bx+bw2, by+bh), (80,80,80), -1)
    fill = int(bw2 * min(conf, 1.0))
    cv2.rectangle(f, (bx, by), (bx+fill, by+bh), color, -1)
    cv2.rectangle(f, (bx, by), (bx+bw2, by+bh), (200,200,200), 1)
    tx = bx + int(bw2 * thresh)
    cv2.line(f, (tx, by-3), (tx, by+bh+3), (255,255,255), 2)
    # per-person bars
    for pid, pc in enumerate(pp_conf):
        my = by + bh + 8 + pid * 18
        pcol = _PCOL[pid % 3]
        cv2.putText(f, f"P{pid+1}", (bx, my+12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, pcol, 1)
        mbx, mbw = bx+25, bw2-25
        cv2.rectangle(f, (mbx, my), (mbx+mbw, my+12), (60,60,60), -1)
        mf = int(mbw * min(pc, 1.0))
        bc = _CRIT if pc >= thresh else pcol
        cv2.rectangle(f, (mbx, my), (mbx+mf, my+12), bc, -1)
        cv2.putText(f, f"{pc:.0%}", (mbx+mbw+5, my+11),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180,180,180), 1)


# ══════════════════════════════════════════════
# PERSON MATCHING
# ══════════════════════════════════════════════
def _match(prev, curr):
    def _tc(k):
        pts = k[[11,12,23,24], :2]; vis = k[[11,12,23,24], 2]
        return pts[vis > 0.2].mean(axis=0) if vis.max() >= 0.2 else None
    if not prev:
        return {i: i for i in range(len(curr))}
    pc = [_tc(k) for k in prev]; cc = [_tc(k) for k in curr]
    used, m = set(), {}
    for ci, c in enumerate(cc):
        if c is None: continue
        bd, bp = float('inf'), None
        for pi, p in enumerate(pc):
            if p is None or pi in used: continue
            d = np.linalg.norm(c - p)
            if d < bd: bd, bp = d, pi
        if bp is not None and bd < 0.3:
            m[ci] = bp; used.add(bp)
    ns = max(list(m.values()) + [-1]) + 1 if m else 0
    if prev: ns = max(ns, len(prev))
    for ci in range(len(curr)):
        if ci not in m: m[ci] = ns; ns += 1
    return m


# ══════════════════════════════════════════════
# WEBHOOK REPORTER
# ══════════════════════════════════════════════
def _report(api_url, api_key, device_id, conf):
    def _p():
        try:
            r = requests.post(api_url, json={
                "device_id": device_id,
                "description": f"Live aggression detected - confidence {conf:.0%}",
            }, headers={"X-API-KEY": api_key, "Content-Type": "application/json"}, timeout=5)
            print(f"  [WEBHOOK] {'OK' if r.status_code == 201 else r.status_code}")
        except Exception as e:
            print(f"  [WEBHOOK] ERROR: {e}")
    threading.Thread(target=_p, daemon=True).start()


# ══════════════════════════════════════════════
# SINGLETON STREAM ENGINE
# ══════════════════════════════════════════════
class AggressionStreamEngine:
    """Singleton engine that captures camera, runs detection, yields JPEG frames."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, camera_idx=0, device_id="CAM_01", threshold=AGGRESSION_THRESHOLD,
                 api_url="http://127.0.0.1:8000/api/ingest/aggression/",
                 api_key="default-secret-key", cooldown=30):
        if self._initialized:
            return
        self._initialized = True

        self.camera_idx = camera_idx
        self.device_id = device_id
        self.threshold = threshold
        self.api_url = api_url
        self.api_key = api_key
        self.cooldown = cooldown

        self._running = False
        self._frame_lock = threading.Lock()
        self._latest_jpeg = None
        self._alert_level = "SAFE"
        self._confidence = 0.0
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("  [STREAM] Engine started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("  [STREAM] Engine stopped")

    @property
    def status(self):
        return {
            "running": self._running,
            "alert_level": self._alert_level,
            "confidence": round(self._confidence, 2),
            "device_id": self.device_id,
        }

    def _loop(self):
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"  [STREAM] Device: {device}")

        # Load LSTM
        ckpt = torch.load(os.path.join(CORE_DIR, "aggression_lstm.pt"),
                          map_location="cpu", weights_only=True)
        state = ckpt.get("model_state_dict", ckpt)
        inp_size = ckpt.get("input_size", state["lstm.weight_ih_l0"].shape[1])
        model = AggressionLSTM(input_size=inp_size)
        model.load_state_dict(state)
        model.to(device).eval()

        # Load scaler
        sp = os.path.join(CORE_DIR, "feature_scaler.pkl")
        scaler = pickle.load(open(sp, "rb")) if os.path.isfile(sp) else None

        # Init pose
        pose = _init_pose()

        # Open camera
        try:
            cam = int(self.camera_idx)
        except ValueError:
            cam = self.camera_idx
        cap = cv2.VideoCapture(cam)
        if not cap.isOpened():
            print(f"  [STREAM] ERROR: Cannot open camera {self.camera_idx}")
            self._running = False
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # State
        pbufs, pconfs, plast = {}, {}, {}
        prev_kps = []
        fc, st = 0, time.time()
        fps = 0.0
        last_inf, last_alert = 0, 0

        fail_count = 0
        while self._running:
            ret, frame = cap.read()
            if not ret:
                fail_count += 1
                if fail_count > 50:
                    print("  [STREAM] Camera failed to capture 50 consecutive frames. Stopping.")
                    self._running = False
                    break
                time.sleep(0.01)
                continue
            fail_count = 0

            fc += 1
            now = time.time()
            el = now - st
            if el > 0:
                fps = fc / el
            if el > 2.0:
                fc, st = 0, now

            ts_ms = int(now * 1000) % (2**31)
            all_kps = _extract_kps(pose, frame, ts_ms)
            n_det = len(all_kps)

            if all_kps:
                mapping = _match(prev_kps, all_kps)
                for ci, kps in enumerate(all_kps):
                    slot = mapping.get(ci, ci)
                    if slot >= MAX_PERSONS:
                        continue
                    if slot not in pbufs:
                        pbufs[slot] = collections.deque(maxlen=WINDOW_SIZE + 5)
                        pconfs[slot] = 0.0
                    pbufs[slot].append(kps)
                    plast[slot] = now
                    scol = (_PCOL_F if self._alert_level == "FIGHT" else _PCOL)[slot % 3]
                    _draw_skel(frame, kps, scol, f"P{slot+1}")
                prev_kps = all_kps
            else:
                for s in list(pbufs.keys()):
                    pbufs[s].append(np.zeros((NUM_KEYPOINTS, KEYPOINT_DIMS), dtype=np.float32))

            for s in list(pbufs.keys()):
                if now - plast.get(s, 0) > 2.0:
                    del pbufs[s]; pconfs.pop(s, None); plast.pop(s, None)

            if (now - last_inf) >= 0.5:
                last_inf = now
                for slot, buf in pbufs.items():
                    if len(buf) < WINDOW_SIZE + 1:
                        continue
                    feats = extract_features(np.array(list(buf)))
                    if len(feats) < WINDOW_SIZE:
                        continue
                    w = feats[-WINDOW_SIZE:]
                    if scaler is not None:
                        w = scaler.transform(w)
                    with torch.no_grad():
                        x = torch.FloatTensor(w).unsqueeze(0).to(device)
                        probs = torchF.softmax(model(x), dim=1)
                        pconfs[slot] = float(probs[0, 1].cpu())

                self._confidence = max(pconfs.values()) if pconfs else 0.0
                if self._confidence >= self.threshold:
                    self._alert_level = "FIGHT"
                    if (now - last_alert) > self.cooldown:
                        last_alert = now
                        _report(self.api_url, self.api_key, self.device_id, self._confidence)
                elif self._confidence >= self.threshold * 0.7:
                    self._alert_level = "CAUTION"
                else:
                    self._alert_level = "SAFE"

            active = sorted(pbufs.keys())
            pp = [pconfs.get(s, 0.0) for s in active]
            _draw_hud(frame, self._alert_level, self._confidence, fps, n_det, pp, self.threshold)

            ok, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                with self._frame_lock:
                    self._latest_jpeg = jpeg.tobytes()

            # ~30 FPS cap
            time.sleep(0.01)

        pose.close()
        cap.release()
        self._running = False

    def generate_mjpeg(self):
        """Yield MJPEG multipart frames for StreamingHttpResponse."""
        while self._running:
            with self._frame_lock:
                frame = self._latest_jpeg
            if frame:
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                )
            time.sleep(0.033)  # ~30fps


# Module-level singleton reference
_engine = None

def get_engine(**kwargs):
    global _engine
    if _engine is None:
        _engine = AggressionStreamEngine(**kwargs)
    return _engine
