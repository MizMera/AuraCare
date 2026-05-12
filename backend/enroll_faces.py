"""
AuraCare — Face Enrollment Script
===================================
Run this from your backend folder:
    cd AuraCare-mainfinalYomna/backend
    py enroll_faces.py

This script:
1. Extracts face encodings from the 3 video frames
2. Creates test residents in the DB (Person 1, 2, 3)
3. Stores face encodings in the Resident model
4. Tests identification to confirm it works
"""

import os
import sys
import json
import numpy as np



os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# ── Django setup ──────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from core.models import Resident , FaceEncoding
from deepface import DeepFace

print("=" * 55)
print("  AuraCare — Face Enrollment")
print("=" * 55)

# ── Paths to your enrollment photos ──────────────────────────
# Copy your 3 video frames to backend/enrollment_photos/
ENROLLMENT_DIR = os.path.join(os.path.dirname(__file__), 'enrollment_photos')
os.makedirs(ENROLLMENT_DIR, exist_ok=True)

PERSONS = [
    {
        'name':       'Person Normal Walk',
        'room':       'TEST-01',
        'age':        25,
        'photo_file': 'person1_normal.jpg',
    },
    {
        'name':       'Person Older Walk',
        'room':       'TEST-02',
        'age':        70,
        'photo_file': 'person2_older.jpg',
    },
    {
        'name':       'Person Parkinson Gait',
        'room':       'TEST-03',
        'age':        60,
        'photo_file': 'person3_parkinson.jpg',
    },
]

enrolled = []

print(f"\n[1/3] Enrolling faces from {ENROLLMENT_DIR}")
print(f"      Make sure you placed the 3 photos there!\n")

for person in PERSONS:
    photo_path = os.path.join(ENROLLMENT_DIR, person['photo_file'])

    if not os.path.exists(photo_path):
        print(f"  ⚠️  {person['name']}: photo not found at {photo_path}")
        print(f"       Please place the photo there and re-run.")
        continue

    print(f"  Processing: {person['name']}...")

    try:
        # Extract face encoding using ArcFace
        result = DeepFace.represent(
            img_path=photo_path,
            model_name='ArcFace',
            enforce_detection=False,
            detector_backend='opencv',
        )
        encoding = result[0]['embedding']
        print(f"  ✅ Encoding extracted ({len(encoding)} dimensions)")

        # Create or update resident in DB
        

        resident, created = Resident.objects.update_or_create(
            name=person['name'],
            defaults={
                'room_number': person['room'],
                'age':         person['age'],
                'risk_level':  'LOW',
            }
        )

        FaceEncoding.objects.update_or_create(
            resident=resident,
            defaults={'encoding_json': json.dumps(encoding)}
        )

        action = 'Created' if created else 'Updated'
        print(f"  ✅ {action} resident: {resident.name} (ID={resident.id})")
        enrolled.append({'id': resident.id, 'name': resident.name, 'encoding': encoding})

    except Exception as e:
        print(f"  ❌ Failed: {e}")

print(f"\n[2/3] Enrolled {len(enrolled)}/3 persons")

# ── Test identification ───────────────────────────────────────
print(f"\n[3/3] Testing identification...")

if len(enrolled) >= 2:
    # Try to identify person 1 against all enrolled
    test = enrolled[0]
    print(f"\n  Testing: who is '{test['name']}'?")

    best_match = None
    best_distance = float('inf')

    for candidate in enrolled:
        a = np.array(test['encoding'])
        b = np.array(candidate['encoding'])
        cosine_sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        distance = round(1 - cosine_sim, 4)
        match_label = "✅ MATCH" if distance < 0.68 else "❌"
        print(f"  vs {candidate['name']}: distance={distance} {match_label}")

        if distance < best_distance:
            best_distance = distance
            best_match = candidate['name']

    print(f"\n  → Best match: {best_match} (distance={best_distance})")
else:
    print("  Not enough enrolled persons to test identification.")

print("\n" + "=" * 55)
print("  ✅ Enrollment complete!")
print(f"  Enrolled residents: {[e['name'] for e in enrolled]}")
print("  Next: run identify_from_video.py to test on videos")
print("=" * 55)
