# Quick Setup Guide

## 5-Minute Setup

### Step 1: Install Python Dependencies
```bash
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### Step 2: Run Pipeline
```bash
# First run - will create pipeline_test_results/ folder
python unified_pipeline.py --duration 60

# Results appear in pipeline_test_results/ folder
```

### Step 3: Check Results
```bash
# View summary
cat pipeline_test_results/latest_webcam_summary.txt

# Open video
# Windows: start pipeline_test_results/webcam_capture_*.mp4
# Linux: vlc pipeline_test_results/webcam_capture_*.mp4
```

---

## File Descriptions

| File | Size | Purpose |
|------|------|---------|
| **unified_pipeline.py** | ~400 lines | Main webcam tracking pipeline |
| **unified_pipeline_model.py** | ~450 lines | Core model with all analysis |
| **ml_risk_predictor.py** | ~400 lines | ML training utilities |
| **generate_synthetic_training_data.py** | ~250 lines | Synthetic data generator |
| **retrain_ml_combined.py** | ~120 lines | Retraining script |
| **models/unified_pipeline.pt** | ~50 MB | Pre-trained model (PyTorch) |
| **ml_models/risk_predictor_v1.pkl** | ~2 MB | RandomForest classifier |
| **ml_models/risk_predictor_v1_scaler.pkl** | ~5 KB | Feature scaler |
| **yolov8n.pt** | ~6 MB | YOLO detection model |
| **requirements.txt** | ~20 lines | Python dependencies |

**Total Size: ~60 MB**

---

## Command Reference

```bash
# Basic usage (60 seconds)
python unified_pipeline.py

# Custom duration
python unified_pipeline.py --duration 120

# No display (faster)
python unified_pipeline.py --no-display

# Help
python unified_pipeline.py --help
```

---

## Expected Output

```
✓ YOLO imported
✓ Loaded unified model
✓ Webcam properties: 640x480 @ 30.0 FPS
Capturing for 60 seconds...

Processed 30 frames, 2 active tracks
Processed 60 frames, 3 active tracks
...

✓ Captured 1800 frames to webcam_capture_*.mp4

RESULTS SUMMARY
Total Tracks: 3
High Risk:    1 (33.3%)
Medium Risk:  1 (33.3%)
Low Risk:     1 (33.3%)

Track ID | Duration | Points | Heuristic | Final Risk
    1    |  20.2s   |  608   |   high    |   high
    2    |  18.5s   |  555   |   medium  |   medium
    3    |  15.1s   |  453   |   low     |   low

✓ Saved results to pipeline_test_results/
```

---

## Folder Structure After First Run

```
readyforimplementation/
├── [Core Files - as listed above]
├── pipeline_test_results/          (created after first run)
│   ├── latest_webcam_results.csv
│   ├── latest_webcam_results.json
│   ├── latest_webcam_summary.txt
│   └── webcam_capture_*.mp4
└── tracking_results/               (created during retraining)
    └── training_data_combined.csv
```

---

## Retraining (Optional)

If you want to train on your own data:

```bash
# 1. Collect webcam data
python unified_pipeline.py --duration 60

# 2. Generate synthetic samples
python generate_synthetic_training_data.py

# 3. Retrain model
python retrain_ml_combined.py

# 4. New model automatically used on next run
```

---

## Integration Examples

### Python Integration
```python
from unified_pipeline_model import UnifiedPipelineModel, UnifiedPipelineSerializer, Track

# Load model
model = UnifiedPipelineSerializer.load_model('models/unified_pipeline.pt')

# Create track from your data
track = Track(
    track_id=1,
    trajectory=[(100, 200), (105, 205), (110, 210)],
    frame_ids=[0, 1, 2],
    confidences=[0.9, 0.92, 0.95],
    velocities=[]
)

# Get risk prediction
result = model.process_track(track, fps=30)
print(f"Risk: {result['final_risk']}")  # Output: 'high', 'medium', or 'low'
```

### CSV Import
```python
import pandas as pd

df = pd.read_csv('pipeline_test_results/latest_webcam_results.csv')
print(df[['track_id', 'duration_s', 'final_risk']])
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Webcam not detected | Check permissions, try `ls /dev/video*` (Linux) |
| No tracks found | Lower detection threshold, check lighting |
| Slow performance | Use `--no-display` flag, check CPU usage |
| Model load error | Ensure all model files present, reinstall torch |
| Wrong risk predictions | Retrain on your data: `python retrain_ml_combined.py` |

---

## System Requirements

- **Python**: 3.8 or higher
- **OS**: Windows, Linux, Mac
- **RAM**: 4GB minimum (8GB recommended)
- **GPU**: Optional (CPU works fine)
- **Webcam**: USB or built-in
- **Disk**: 200MB free space

---

## Contact & Support

For issues or questions about integration, refer to:
- INTEGRATION_README.md (detailed documentation)
- Code comments in unified_pipeline.py
- ml_risk_predictor.py for ML customization

---

**Ready for production deployment!** 🚀
