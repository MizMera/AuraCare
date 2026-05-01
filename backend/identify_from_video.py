"""
AuraCare — Identify Residents from Video
=========================================
Run after enroll_faces.py:
    py identify_from_video.py

This script:
1. Loads all face encodings from DB
2. Processes each video frame by frame
3. Detects faces and identifies which resident it is
4. Auto-tags GaitObservation with the identified resident
"""

import os
import sys
import json
import numpy as np
import cv2

os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# ── Django setup ──────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from core.models import Resident, GaitObservation
from deepface import DeepFace

print("=" * 55)
print("  AuraCare — Video Face Identification")
print("=" * 55)

# ── Load enrolled residents from DB ──────────────────────────
print("\n[1/3] Loading enrolled residents from DB...")
residents = Resident.objects.exclude(face_encoding__isnull=True).exclude(face_encoding='')
enrolled = []

for r in residents:
    try:
        encoding = json.loads(r.face_encoding)
        enrolled.append({'id': r.id, 'name': r.name, 'encoding': encoding})
        print(f"  ✅ Loaded: {r.name} (ID={r.id})")
    except Exception as e:
        print(f"  ❌ {r.name}: bad encoding — {e}")

print(f"  Total enrolled: {len(enrolled)}")

if len(enrolled) == 0:
    print("  No enrolled residents found. Run enroll_faces.py first!")
    sys.exit(1)

# ── Videos to process ────────────────────────────────────────
VIDEOS = [
    'normalwalk.mp4',
    'OlderPersonWalking.mp4',
    'parkinsonGait.mp4',
]

VIDEO_DIR = r'C:\Users\yomna\Downloads\AuraCare-main\gait_model\test_videos'
def identify_face(frame, enrolled, threshold=0.68):
    """
    Given a frame, detect and identify the face.
    Returns (resident_id, resident_name, confidence) or None
    """
    try:
        result = DeepFace.represent(
            img_path=frame,
            model_name='ArcFace',
            enforce_detection=False,
            detector_backend='opencv',
        )
        if not result:
            return None

        face_encoding = np.array(result[0]['embedding'])
        best_match = None
        best_distance = float('inf')

        for candidate in enrolled:
            stored = np.array(candidate['encoding'])
            cosine_sim = np.dot(face_encoding, stored) / (
                np.linalg.norm(face_encoding) * np.linalg.norm(stored)
            )
            distance = 1 - cosine_sim
            if distance < best_distance:
                best_distance = distance
                best_match = candidate

        if best_distance < threshold:
            confidence = round((1 - best_distance) * 100, 1)
            return best_match['id'], best_match['name'], confidence
        return None

    except Exception:
        return None


print("\n[2/3] Processing videos...")

results_summary = []

for video_file in VIDEOS:
    video_path = os.path.join(VIDEO_DIR, video_file)

    if not os.path.exists(video_path):
        print(f"\n  ⚠️  {video_file} not found in {VIDEO_DIR}")
        print(f"      Place your videos there and re-run.")
        continue

    print(f"\n  📹 Processing: {video_file}")
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    identification_counts = {}
    frames_checked = 0
    SAMPLE_EVERY = 30  # check every 30 frames (1 per second at 30fps)

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % SAMPLE_EVERY == 0:
            result = identify_face(frame, enrolled)
            if result:
                res_id, res_name, confidence = result
                if res_name not in identification_counts:
                    identification_counts[res_name] = []
                identification_counts[res_name].append(confidence)
                print(f"    Frame {frame_idx}: identified {res_name} ({confidence}%)")
            frames_checked += 1

        frame_idx += 1

    cap.release()

    # Determine dominant identity
    if identification_counts:
        dominant = max(identification_counts, key=lambda k: len(identification_counts[k]))
        avg_conf = round(np.mean(identification_counts[dominant]), 1)
        print(f"  → Dominant identity: {dominant} (avg confidence: {avg_conf}%)")
        results_summary.append({
            'video': video_file,
            'identified_as': dominant,
            'confidence': avg_conf,
            'counts': {k: len(v) for k, v in identification_counts.items()}
        })

        # ── Auto-tag untagged GaitObservations ────────────────
        resident_obj = Resident.objects.filter(name=dominant).first()
        if resident_obj:
            untagged = GaitObservation.objects.filter(resident__isnull=True)
            count = untagged.count()
            if count > 0:
                untagged.update(resident=resident_obj)
                print(f"  ✅ Auto-tagged {count} GaitObservations → {dominant}")
    else:
        print(f"  ❌ Could not identify anyone in {video_file}")

# ── Summary ───────────────────────────────────────────────────
print("\n[3/3] Summary")
print("=" * 55)
for r in results_summary:
    print(f"  {r['video']}")
    print(f"  → Identified as: {r['identified_as']} ({r['confidence']}% confidence)")
    print()
print("✅ Done! Check your DB for updated GaitObservations.")
