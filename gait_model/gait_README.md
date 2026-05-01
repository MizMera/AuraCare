# Gait Analysis Model — AuraCare

## Overview
This module analyzes walking patterns using a camera and detects abnormal gait in real time.
It supports multiple persons simultaneously and identifies registered patients.

## Features
- Multi-person detection (up to 5 persons)
- Automatic patient identification
- Normal / Abnormal gait classification
- Snapshot capture on abnormal detection
- Automatic sync with AuraCare Django backend

## Requirements
- Python 3.10+
- Webcam or video file

## Setup

### 1. Create virtual environment
```bash
python -m venv gait_env
gait_env\Scripts\activate      # Windows
source gait_env/bin/activate   # Linux/Mac
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Download required model files
Place these files in the `data/` folder:
- `pose_landmarker.task` — MediaPipe pose model
  Download from: https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task
- `gait_model_local.pkl` — Trained gait classifier (provided in repo)

### 4. Configure backend URL
In `realtime_gait_v4.py`, set:
```python
BACKEND_URL = 'http://127.0.0.1:8000/api/gait/ingest/'
API_KEY     = 'default-secret-key'
```

## Usage

### Test with a video file
```bash
py realtime_gait_v4.py --mode video --path "path/to/video.mp4"
```

### Live webcam
```bash
py realtime_gait_v4.py --mode live
```

### Save annotated output
```bash
py realtime_gait_v4.py --mode video --path "video.mp4" --output "output.mp4"
```

## Controls (while running)
| Key | Action |
|-----|--------|
| Q   | Quit |
| R   | Register current person as patient |
| C   | Clear session |

## Patient Registration
1. Run the model with a video or webcam
2. When a person is visible, press **R**
3. Enter the patient's name (must match exactly the name in Django Residents)
4. The patient will be identified automatically in future sessions

## Output
Each analysis session sends results to the AuraCare backend:
- Label: `normal` or `abnormal`
- Confidence score
- 6 gait features (stride_length, walking_speed, arm_swing, step_variability, cadence, height_ratio)
- Snapshot image at moment of detection

## File Structure
```
gait_model/
├── realtime_gait_v4.py     # Main pipeline
├── requirements.txt        # Python dependencies
├── README.md               # This file
└── data/
    ├── gait_model_local.pkl      # Trained classifier
    ├── pose_landmarker.task      # MediaPipe model
    ├── patient_database.json     # Registered patients
    └── patient_history.json      # Session history
```
