# ==============================================
# AuraCare — Live Aggression Detection Module
# ==============================================
# Real-time aggression detection from camera feed.
# Adapted from SilverGuard's live_demo.py.
#
# This module:
#   1. Captures frames from a camera (or RTSP stream)
#   2. Extracts pose keypoints via MediaPipe
#   3. Computes kinetic features (velocity, acceleration, jerk, etc.)
#   4. Runs the AggressionLSTM model per-person
#   5. When aggression is detected, auto-reports to the AuraCare webhook
#   6. Overlays an alert HUD on the live feed
#
# Usage:
#   cd D:\app\Auracare\AuraCare\backend
#   python live_aggression.py --camera 0 --device-id CAM_01
#
# Arguments:
#   --camera 0            Camera index or RTSP URL (default 0)
#   --device-id CAM_01    Device ID registered in AuraCare (required)
#   --threshold 0.7       Fight confidence threshold (default 0.7)
#   --api-key <key>       AuraCare API key (default: default-secret-key)
#   --api-url <url>       AuraCare webhook URL
#   --no-skeleton         Disable skeleton overlay
#   --cooldown 30         Seconds between repeated alerts (default 30)

import os
import sys
import time
import argparse
import collections
import threading
import numpy as np
import cv2
import torch
import torch.nn as nn
import torch.nn.functional as F
import pickle
import requests

# ══════════════════════════════════════════════
# CONFIG (embedded from SilverGuard config.py)
# ══════════════════════════════════════════════
WINDOW_SIZE = 30
NUM_KEYPOINTS = 33
KEYPOINT_DIMS = 3
AGGRESSION_THRESHOLD = 0.7
VISION_HIDDEN_SIZE = 128
VISION_NUM_LAYERS = 2
MAX_PERSONS = 3

# ══════════════════════════════════════════════
# MODEL (embedded from SilverGuard src/models.py)
# ══════════════════════════════════════════════
class AggressionLSTM(nn.Module):
    """LSTM-based classifier for detecting aggression from skeleton sequences."""
    def __init__(self, input_size, hidden_size=VISION_HIDDEN_SIZE,
                 num_layers=VISION_NUM_LAYERS, dropout=0.0, num_classes=2):
        super(AggressionLSTM, self).__init__()
        self.lstm = nn.LSTM(
            input_size=input_size, hidden_size=hidden_size,
            num_layers=num_layers, batch_first=True, bidirectional=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size * 2, num_classes)

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        last_output = self.dropout(lstm_out[:, -1, :])
        return self.fc(last_output)


# ══════════════════════════════════════════════
# KINETIC FEATURES (embedded from SilverGuard)
# ══════════════════════════════════════════════
def _compute_velocity(kps):
    return kps[1:, :, :2] - kps[:-1, :, :2]

def _compute_kinetic_energy(vel):
    return np.sum(vel ** 2, axis=(1, 2))

def _compute_acceleration(vel):
    return vel[1:] - vel[:-1]

def _compute_jerk(acc):
    return acc[1:] - acc[:-1]

def _compute_inter_hand_distance(kps):
    return np.linalg.norm(kps[:, 15, :2] - kps[:, 16, :2], axis=1)

def _compute_hand_to_face_distance(kps):
    nose = kps[:, 0, :2]
    d_l = np.linalg.norm(kps[:, 15, :2] - nose, axis=1)
    d_r = np.linalg.norm(kps[:, 16, :2] - nose, axis=1)
    return np.minimum(d_l, d_r)

def _compute_body_part_velocities(kps):
    pos = kps[:, :, :2]
    vel = pos[1:] - pos[:-1]
    speed = np.sqrt((vel ** 2).sum(axis=2))
    return np.column_stack([
        speed[:, [15, 16, 17, 18, 19, 20]].mean(axis=1),
        speed[:, [27, 28, 29, 30, 31, 32]].mean(axis=1),
        speed[:, [11, 12, 23, 24]].mean(axis=1),
    ])

def _compute_pose_spread(kps):
    x, y = kps[:, :, 0], kps[:, :, 1]
    return (x.max(axis=1) - x.min(axis=1)) * (y.max(axis=1) - y.min(axis=1))

def _compute_limb_angles(kps):
    triplets = [(11, 13, 15), (12, 14, 16), (23, 25, 27), (24, 26, 28)]
    def _angle(a, b, c):
        ba, bc = a - b, c - b
        cos_a = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
        return np.degrees(np.arccos(np.clip(cos_a, -1, 1)))
    angles = np.zeros((len(kps), 4))
    for i in range(len(kps)):
        for j, (p1, p2, p3) in enumerate(triplets):
            angles[i, j] = _angle(kps[i, p1, :2], kps[i, p2, :2], kps[i, p3, :2])
    return angles

def extract_all_features(keypoints):
    """Compute 15 kinetic features per frame from raw (N, 33, 3) keypoints."""
    vel = _compute_velocity(keypoints)
    ke = _compute_kinetic_energy(vel)
    mean_vel = np.mean(np.abs(vel), axis=(1, 2))
    max_vel = np.max(np.abs(vel), axis=(1, 2))
    acc = _compute_acceleration(vel)
    mean_acc = np.concatenate(([0], np.mean(np.abs(acc), axis=(1, 2))))
    jerk = _compute_jerk(acc)
    mean_jerk = np.concatenate(([0, 0], np.mean(np.abs(jerk), axis=(1, 2))))
    inter_hand = _compute_inter_hand_distance(keypoints)[1:]
    hand_face = _compute_hand_to_face_distance(keypoints)[1:]
    bp_vel = _compute_body_part_velocities(keypoints)
    spread = _compute_pose_spread(keypoints)[1:]
    angles = _compute_limb_angles(keypoints)[1:]
    return np.column_stack([
        ke, mean_vel, max_vel, mean_acc, mean_jerk,
        inter_hand, hand_face, bp_vel, spread, angles,
    ])


# ══════════════════════════════════════════════
# MEDIAPIPE POSE
# ══════════════════════════════════════════════
from mediapipe.tasks.python.vision import pose_landmarker as _pl
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode
from mediapipe.tasks.python.vision.core.image import Image as _MpImage
from mediapipe.tasks.python.vision.core.image import ImageFormat as _MpImageFormat

def init_pose_model(model_path):
    """Initialize MediaPipe PoseLandmarker in VIDEO mode."""
    options = _pl.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=model_path),
        running_mode=VisionTaskRunningMode.VIDEO,
        num_poses=MAX_PERSONS,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return _pl.PoseLandmarker.create_from_options(options)

def extract_keypoints_multi(pose_model, frame, timestamp_ms):
    """Extract keypoints for all detected persons from a BGR frame."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_img = _MpImage(image_format=_MpImageFormat.SRGB, data=rgb)
    result = pose_model.detect_for_video(mp_img, timestamp_ms)
    if not result.pose_landmarks:
        return []
    all_kps = []
    for person_landmarks in result.pose_landmarks:
        kps = np.array(
            [[lm.x, lm.y, lm.visibility] for lm in person_landmarks],
            dtype=np.float32,
        )
        all_kps.append(kps)
    return all_kps


# ══════════════════════════════════════════════
# VISUAL OVERLAY
# ══════════════════════════════════════════════
COLOR_SAFE = (0, 200, 0)
COLOR_WARNING = (0, 200, 255)
COLOR_CRITICAL = (0, 0, 255)
COLOR_BG = (40, 40, 40)

PERSON_COLORS = [(255, 200, 0), (0, 255, 200), (200, 100, 255)]
PERSON_COLORS_FIGHT = [(0, 0, 255), (0, 80, 255), (0, 50, 200)]

POSE_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (24, 26), (26, 28),
    (15, 17), (15, 19), (15, 21), (16, 18), (16, 20), (16, 22),
    (27, 29), (27, 31), (28, 30), (28, 32),
]

def draw_skeleton(frame, keypoints, color, person_label=None):
    h, w = frame.shape[:2]
    for i in range(NUM_KEYPOINTS):
        x, y, vis = int(keypoints[i, 0] * w), int(keypoints[i, 1] * h), keypoints[i, 2]
        if vis > 0.3:
            cv2.circle(frame, (x, y), 3, color, -1)
    for p1, p2 in POSE_CONNECTIONS:
        if keypoints[p1, 2] > 0.3 and keypoints[p2, 2] > 0.3:
            x1, y1 = int(keypoints[p1, 0] * w), int(keypoints[p1, 1] * h)
            x2, y2 = int(keypoints[p2, 0] * w), int(keypoints[p2, 1] * h)
            cv2.line(frame, (x1, y1), (x2, y2), color, 2)
    if person_label and keypoints[0, 2] > 0.3:
        lx, ly = int(keypoints[0, 0] * w), int(keypoints[0, 1] * h) - 15
        cv2.putText(frame, person_label, (lx - 5, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

def draw_hud(frame, alert_level, confidence, fps, num_persons, per_person_conf, threshold):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    
    if alert_level == "FIGHT":
        color, label = COLOR_CRITICAL, "⚠ AGGRESSION DETECTED"
    elif alert_level == "CAUTION":
        color, label = COLOR_WARNING, "CAUTION"
    else:
        color, label = COLOR_SAFE, "SAFE"

    # Top bar background with transparency
    cv2.rectangle(overlay, (0, 0), (w, 60), (15, 20, 25), -1)
    
    # AuraCare LIVE logo area
    cv2.putText(overlay, "AuraCare", (15, 40), cv2.FONT_HERSHEY_DUPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(overlay, "LIVE", (180, 40), cv2.FONT_HERSHEY_DUPLEX, 1.1, (50, 205, 50), 2, cv2.LINE_AA)

    # Status label background
    badge_w = 360
    cv2.rectangle(overlay, (w - badge_w - 15, 10), (w - 15, 50), color, -1)
    cv2.putText(overlay, label, (w - badge_w + 10, 38), cv2.FONT_HERSHEY_DUPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)

    # Bottom bar background
    cv2.rectangle(overlay, (0, h - 45), (w, h), (15, 20, 25), -1)
    
    # Blend overlay with frame
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
    
    # Bottom details (drawn directly on frame for sharpness)
    info = f"Confidence: {confidence:.0%}    |    FPS: {fps:.0f}    |    Persons Tracked: {num_persons}"
    cv2.putText(frame, info, (15, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)

    # Confidence bar area
    bar_x, bar_y, bar_w, bar_h = 15, 75, 220, 18
    # Background for bar
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (40, 40, 40), -1)
    
    # Fill gradient-like effect based on confidence
    fill = int(bar_w * min(confidence, 1.0))
    if fill > 0:
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill, bar_y + bar_h), color, -1)
        
    # Bar border
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (150, 150, 150), 1)
    
    # Threshold indicator
    thresh_x = bar_x + int(bar_w * threshold)
    cv2.line(frame, (thresh_x, bar_y - 4), (thresh_x, bar_y + bar_h + 4), (255, 255, 255), 2)
    cv2.putText(frame, "THRESH", (thresh_x - 20, bar_y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)

    # Per-person mini bars
    for pid, pconf in enumerate(per_person_conf):
        mini_y = bar_y + bar_h + 12 + pid * 22
        p_color = PERSON_COLORS[pid % len(PERSON_COLORS)]
        
        # Draw subject text
        cv2.putText(frame, f"SUBJ {pid+1}", (bar_x, mini_y + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, p_color, 1, cv2.LINE_AA)
        
        mini_bx, mini_bw = bar_x + 65, bar_w - 65
        # Individual background
        cv2.rectangle(frame, (mini_bx, mini_y), (mini_bx + mini_bw, mini_y + 14), (50, 50, 50), -1)
        
        mini_fill = int(mini_bw * min(pconf, 1.0))
        bar_color = COLOR_CRITICAL if pconf >= threshold else p_color
        if mini_fill > 0:
            cv2.rectangle(frame, (mini_bx, mini_y), (mini_bx + mini_fill, mini_y + 14), bar_color, -1)
            
        cv2.putText(frame, f"{pconf:.0%}", (mini_bx + mini_bw + 8, mini_y + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)


# ══════════════════════════════════════════════
# PERSON MATCHING
# ══════════════════════════════════════════════
def _match_persons(prev_kps_list, curr_kps_list):
    """Match detected persons across frames using torso center distance."""
    def _torso_center(kps):
        pts = kps[[11, 12, 23, 24], :2]
        vis = kps[[11, 12, 23, 24], 2]
        if vis.max() < 0.2:
            return None
        return pts[vis > 0.2].mean(axis=0)

    if not prev_kps_list:
        return {i: i for i in range(len(curr_kps_list))}
    prev_centers = [_torso_center(k) for k in prev_kps_list]
    curr_centers = [_torso_center(k) for k in curr_kps_list]
    used_prev, mapping = set(), {}
    for ci, cc in enumerate(curr_centers):
        if cc is None:
            continue
        best_dist, best_pi = float('inf'), None
        for pi, pc in enumerate(prev_centers):
            if pc is None or pi in used_prev:
                continue
            d = np.linalg.norm(cc - pc)
            if d < best_dist:
                best_dist, best_pi = d, pi
        if best_pi is not None and best_dist < 0.3:
            mapping[ci] = best_pi
            used_prev.add(best_pi)
    next_slot = max(list(mapping.values()) + [-1]) + 1 if mapping else 0
    if prev_kps_list:
        next_slot = max(next_slot, len(prev_kps_list))
    for ci in range(len(curr_kps_list)):
        if ci not in mapping:
            mapping[ci] = next_slot
            next_slot += 1
    return mapping


# ══════════════════════════════════════════════
# WEBHOOK REPORTER
# ══════════════════════════════════════════════
def _report_aggression(api_url, api_key, device_id, confidence):
    """Send aggression incident to AuraCare webhook (non-blocking)."""
    def _post():
        try:
            resp = requests.post(
                api_url,
                json={
                    "device_id": device_id,
                    "description": f"Live aggression detected — confidence {confidence:.0%}"
                },
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                timeout=5,
            )
            if resp.status_code == 201:
                print(f"  [WEBHOOK] ✅ Incident reported (id={resp.json()['data']['id']})")
            else:
                print(f"  [WEBHOOK] ⚠ Server replied {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"  [WEBHOOK] ❌ Failed to report: {e}")
    threading.Thread(target=_post, daemon=True).start()


# ══════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════
def run_live(camera_idx, device_id, threshold, api_url, api_key,
             show_skeleton=True, cooldown=30):
    """Main live camera loop with multi-person tracking and auto-reporting."""

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  Device: {device}")

    # ── Resolve model paths relative to this file ──
    core_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "core")

    # ── Load LSTM model ──
    print("  Loading aggression LSTM model...")
    ckpt_path = os.path.join(core_dir, "aggression_lstm.pt")
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    if "model_state_dict" in ckpt:
        state = ckpt["model_state_dict"]
        input_size = ckpt.get("input_size", 15)
    else:
        state = ckpt
        input_size = state["lstm.weight_ih_l0"].shape[1]

    model = AggressionLSTM(input_size=input_size)
    model.load_state_dict(state)
    model.to(device).eval()
    print(f"  Loaded: {input_size} features")

    # ── Load scaler ──
    scaler_path = os.path.join(core_dir, "feature_scaler.pkl")
    scaler = None
    if os.path.isfile(scaler_path):
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)
    else:
        print("  WARNING: feature_scaler.pkl not found — predictions may be inaccurate")

    # ── Init pose model ──
    print(f"  Initializing pose model (up to {MAX_PERSONS} persons)...")
    pose_path = os.path.join(core_dir, "pose_landmarker_lite.task")
    pose = init_pose_model(pose_path)
    print("  Ready!")

    # ── Open camera ──
    try:
        cam = int(camera_idx)
    except ValueError:
        cam = camera_idx  # RTSP URL string
    cap = cv2.VideoCapture(cam)
    if not cap.isOpened():
        print(f"  ERROR: Cannot open camera {camera_idx}")
        sys.exit(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print(f"\n{'=' * 55}")
    print(f"  AuraCare LIVE — Aggression Detection")
    print(f"  Camera: {camera_idx}  |  Device ID: {device_id}")
    print(f"  Multi-person tracking: up to {MAX_PERSONS}")
    print(f"  Threshold: {threshold}  |  Cooldown: {cooldown}s")
    print(f"  Webhook: {api_url}")
    print(f"  Press 'Q' to quit")
    print(f"{'=' * 55}\n")

    # ── Per-person state ──
    person_buffers = {}
    person_confs = {}
    person_last_seen = {}
    prev_frame_kps = []

    frame_count = 0
    start_time = time.time()
    alert_level = "SAFE"
    confidence = 0.0
    fps = 0.0
    last_inference_time = 0
    last_alert_time = 0
    inference_interval = 0.5
    person_timeout = 2.0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("  Camera read failed")
            break

        frame_count += 1
        now = time.time()
        elapsed = now - start_time
        if elapsed > 0:
            fps = frame_count / elapsed
        if elapsed > 2.0:
            frame_count = 0
            start_time = now

        # ── Extract keypoints ──
        timestamp_ms = int(now * 1000) % (2**31)
        all_kps = extract_keypoints_multi(pose, frame, timestamp_ms)
        num_detected = len(all_kps)

        # ── Match persons ──
        if all_kps:
            mapping = _match_persons(prev_frame_kps, all_kps)
            for ci, kps in enumerate(all_kps):
                slot = mapping.get(ci, ci)
                if slot >= MAX_PERSONS:
                    continue
                if slot not in person_buffers:
                    person_buffers[slot] = collections.deque(maxlen=WINDOW_SIZE + 5)
                    person_confs[slot] = 0.0
                person_buffers[slot].append(kps)
                person_last_seen[slot] = now
                if show_skeleton:
                    skel_color = (PERSON_COLORS_FIGHT if alert_level == "FIGHT"
                                  else PERSON_COLORS)[slot % len(PERSON_COLORS)]
                    draw_skeleton(frame, kps, color=skel_color, person_label=f"P{slot+1}")
            prev_frame_kps = all_kps
        else:
            for slot in list(person_buffers.keys()):
                person_buffers[slot].append(np.zeros((NUM_KEYPOINTS, KEYPOINT_DIMS), dtype=np.float32))

        # ── Expire stale persons ──
        for slot in list(person_buffers.keys()):
            if now - person_last_seen.get(slot, 0) > person_timeout:
                del person_buffers[slot]
                person_confs.pop(slot, None)
                person_last_seen.pop(slot, None)

        # ── Inference ──
        if (now - last_inference_time) >= inference_interval:
            last_inference_time = now
            for slot, buf in person_buffers.items():
                if len(buf) < WINDOW_SIZE + 1:
                    continue
                kp_array = np.array(list(buf))
                features = extract_all_features(kp_array)
                if len(features) < WINDOW_SIZE:
                    continue
                window = features[-WINDOW_SIZE:]
                if scaler is not None:
                    window = scaler.transform(window)
                with torch.no_grad():
                    x = torch.FloatTensor(window).unsqueeze(0).to(device)
                    logits = model(x)
                    probs = F.softmax(logits, dim=1)
                    fight_prob = float(probs[0, 1].cpu())
                person_confs[slot] = fight_prob

            confidence = max(person_confs.values()) if person_confs else 0.0
            if confidence >= threshold:
                alert_level = "FIGHT"
                # Auto-report with cooldown
                if (now - last_alert_time) > cooldown:
                    last_alert_time = now
                    print(f"  🚨 AGGRESSION DETECTED — confidence {confidence:.0%}")
                    _report_aggression(api_url, api_key, device_id, confidence)
            elif confidence >= threshold * 0.7:
                alert_level = "CAUTION"
            else:
                alert_level = "SAFE"

        # ── Draw HUD ──
        active_slots = sorted(person_buffers.keys())
        per_person_conf = [person_confs.get(s, 0.0) for s in active_slots]
        draw_hud(frame, alert_level, confidence, fps, num_detected, per_person_conf, threshold)

        # ── Show ──
        cv2.imshow("AuraCare LIVE — Aggression Detection", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == ord('Q') or key == 27:
            break

    pose.close()
    cap.release()
    cv2.destroyAllWindows()
    print("\nAuraCare LIVE stopped.")


# ══════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AuraCare — Live Aggression Detection")
    parser.add_argument("--camera", default="0",
                        help="Camera index or RTSP URL (default: 0)")
    parser.add_argument("--device-id", required=True,
                        help="Device ID registered in AuraCare (e.g. CAM_01)")
    parser.add_argument("--threshold", type=float, default=AGGRESSION_THRESHOLD,
                        help=f"Fight confidence threshold (default: {AGGRESSION_THRESHOLD})")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/api/ingest/aggression/",
                        help="AuraCare webhook URL")
    parser.add_argument("--api-key", default="default-secret-key",
                        help="AuraCare API key")
    parser.add_argument("--no-skeleton", action="store_true",
                        help="Disable skeleton overlay")
    parser.add_argument("--cooldown", type=int, default=30,
                        help="Seconds between repeated alerts (default: 30)")
    args = parser.parse_args()

    print("=" * 55)
    print("  AuraCare — Live Aggression Detection Module")
    print("=" * 55)

    run_live(
        camera_idx=args.camera,
        device_id=args.device_id,
        threshold=args.threshold,
        api_url=args.api_url,
        api_key=args.api_key,
        show_skeleton=not args.no_skeleton,
        cooldown=args.cooldown,
    )
