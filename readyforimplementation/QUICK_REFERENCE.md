# Quick Reference Card

## Installation (One-Time)
```bash
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## Common Commands

### Run Webcam Pipeline
```bash
# Basic (60 seconds with display)
python unified_pipeline.py

# Custom duration
python unified_pipeline.py --duration 120

# No display (faster)
python unified_pipeline.py --duration 60 --no-display

# Help
python unified_pipeline.py --help
```

### Check Results
```bash
# Linux/Mac
cat pipeline_test_results/latest_webcam_summary.txt

# Windows PowerShell
Get-Content pipeline_test_results/latest_webcam_summary.txt

# Python
import pandas as pd
df = pd.read_csv('pipeline_test_results/latest_webcam_results.csv')
print(df)
```

### Retrain Model
```bash
# 1. Generate synthetic data
python generate_synthetic_training_data.py

# 2. Retrain
python retrain_ml_combined.py

# 3. Pipeline uses new model automatically on next run
python unified_pipeline.py --duration 60
```

---

## Python API

### Load Model
```python
from unified_pipeline_model import UnifiedPipelineModel, UnifiedPipelineSerializer

model = UnifiedPipelineSerializer.load_model('models/unified_pipeline.pt')
```

### Process Single Track
```python
from unified_pipeline_model import Track

track = Track(
    track_id=1,
    trajectory=[(10,20), (15,25), (20,30)],
    frame_ids=[0, 1, 2],
    confidences=[0.9, 0.92, 0.95],
    velocities=[]
)

result = model.process_track(track, fps=30)
print(result['final_risk'])  # 'high', 'medium', or 'low'
print(result['ml_confidence'])  # confidence score
```

### Process Multiple Tracks
```python
results = model.process_batch(tracks_list, fps=30)
# Returns list of result dicts
```

---

## Output Files

| File | Content | Format |
|------|---------|--------|
| `latest_webcam_results.csv` | Track results | CSV table |
| `latest_webcam_results.json` | Detailed results | JSON |
| `latest_webcam_summary.txt` | Human-readable summary | Text |
| `webcam_capture_*.mp4` | Video with trajectories | MP4 video |

---

## Configuration Changes

### Edit YOLO Settings
**File**: `unified_pipeline_config.json`
```json
{
  "yolo": {
    "confidence_threshold": 0.3,  // Lower for more detections
    "resolution": [640, 480],     // Video resolution
    "fps": 30                      // Video framerate
  }
}
```

### Edit Tracker Settings
```json
{
  "tracker": {
    "max_age": 50,           // Higher = tracks last longer
    "min_hits": 1,           // Lower = confirm faster
    "iou_threshold": 0.2     // Lower = easier matching
  }
}
```

### Edit Risk Thresholds
**File**: `unified_pipeline_model.py` (HeuristicRiskScorer)
```python
# Line ~155
if tortuosity > 3.0:      # Increase for stricter
    score += 3.0
if turn_rate > 5.0:       # Increase for stricter
    score += 2.0
```

---

## Troubleshooting

### No Detections
```bash
# Lower confidence threshold
# Edit unified_pipeline_config.json:
"confidence_threshold": 0.3  # was 0.4
```

### Tracks Ending Too Soon
```bash
# Increase max_age in config
"max_age": 60  # was 30
```

### Poor Risk Classifications
```bash
# Retrain on your data
python generate_synthetic_training_data.py
python retrain_ml_combined.py
```

### Model Load Error
```bash
# Verify model files exist
ls models/
ls ml_models/

# Reinstall torch
pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cpu
```

---

## Performance Tips

| Goal | Action |
|------|--------|
| **Faster** | Use `--no-display` flag |
| **Better tracking** | Increase `iou_threshold` to 0.5 |
| **More detections** | Lower `confidence_threshold` to 0.3 |
| **More accurate risk** | Retrain model on your data |
| **Longer tracks** | Increase `max_age` to 60 |

---

## Output Interpretation

### Risk Levels
- **HIGH**: Wandering behavior, erratic movement, frequent revisits
- **MEDIUM**: Mixed patterns, some concern
- **LOW**: Linear movement, purposeful motion, stationary

### Key Metrics
- **tortuosity** > 3: Indicates wandering
- **turn_rate** > 500/min: Erratic movement
- **revisit_ratio** > 0.8: Returning to same areas
- **idle_ratio** > 30%: Mostly standing still

### Confidence Score
- **0.9-1.0**: Model highly confident
- **0.6-0.9**: Model moderately confident
- **< 0.6**: Use heuristic prediction instead

---

## Directory Structure

```
readyforimplementation/
├── unified_pipeline.py
├── unified_pipeline_model.py
├── ml_risk_predictor.py
├── generate_synthetic_training_data.py
├── retrain_ml_combined.py
├── requirements.txt
├── unified_pipeline_config.json
├── INTEGRATION_README.md
├── SETUP_GUIDE.md
├── DELIVERY_MANIFEST.md
├── models/
│   └── unified_pipeline.pt
├── ml_models/
│   ├── risk_predictor_v1.pkl
│   └── risk_predictor_v1_scaler.pkl
└── yolov8n.pt
```

**After first run:**
- `pipeline_test_results/` - Results from latest run
- `tracking_results/` - Training data (if retraining)

---

## Key Files at a Glance

| File | What to do |
|------|-----------|
| **unified_pipeline.py** | Run this to capture and analyze |
| **unified_pipeline_model.py** | Don't edit unless customizing |
| **ml_risk_predictor.py** | Don't edit unless retraining |
| **requirements.txt** | Run once: `pip install -r requirements.txt` |
| **retrain_ml_combined.py** | Run to improve model on your data |
| **INTEGRATION_README.md** | Read for detailed understanding |
| **SETUP_GUIDE.md** | Follow for initial setup |

---

## One-Liner Commands

```bash
# Install all dependencies
pip install -r requirements.txt && pip install torch --index-url https://download.pytorch.org/whl/cpu

# Run pipeline and show results
python unified_pipeline.py --duration 60 && cat pipeline_test_results/latest_webcam_summary.txt

# Retrain and test
python generate_synthetic_training_data.py && python retrain_ml_combined.py && python unified_pipeline.py --duration 30

# Check model loads correctly
python -c "from unified_pipeline_model import UnifiedPipelineSerializer; m = UnifiedPipelineSerializer.load_model('models/unified_pipeline.pt'); print('✓ Ready')"
```

---

## Next Steps

1. **Setup**: Follow SETUP_GUIDE.md
2. **First Run**: `python unified_pipeline.py --duration 10`
3. **Check Results**: Open `latest_webcam_summary.txt`
4. **Integrate**: Use Python API from INTEGRATION_README.md
5. **Customize**: Adjust config or retrain as needed

---

**Version**: 1.0 | **Status**: Ready for Production | **Last Updated**: 2026-05-12
