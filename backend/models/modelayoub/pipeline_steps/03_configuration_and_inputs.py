# Auto-generated from notebook code cells, grouped by pipeline step.

import os

# ===== From cell_09.py =====
# ===== CONFIGURATION =====

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DETECTOR_MODEL_PATH = str(PROJECT_ROOT / 'models' / 'yolo26n.pt')
VIDEO_INPUT_PATH = os.getenv('WANDER_VIDEO_INPUT_PATH', str(PROJECT_ROOT / 'input.mp4'))
OUTPUT_DIR = PROJECT_ROOT / 'tracking_results'
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

# Input source
USE_WEBCAM = os.getenv('WANDER_USE_WEBCAM', '1').lower() not in ('0', 'false', 'no')
WEBCAM_INDEX = int(os.getenv('WANDER_WEBCAM_INDEX', '0'))
MAX_FRAMES = 900  # ~30s at 30 FPS; set to None for continuous capture
SHOW_LIVE_FEED = os.getenv('WANDER_SHOW_LIVE_FEED', '1').lower() not in ('0', 'false', 'no')

# Tracking parameters
TRACKER_MAX_AGE = 30
TRACKER_MIN_HITS = 3
CONF_THRESHOLD = 0.5
DEVICE = '0' if torch.cuda.is_available() else 'cpu'

# Processing parameters
SHOW_PROGRESS = True
EXPORT_FORMATS = ['json', 'csv']
GENERATE_VISUALIZATIONS = True

print("=" * 70)
print("MULTI-HUMAN TRACKING PIPELINE CONFIGURATION")
print("=" * 70)
print(f"Detector Model: {DETECTOR_MODEL_PATH}")
print(f"Video Input: {VIDEO_INPUT_PATH}")
print(f"Output Directory: {OUTPUT_DIR}")
print(f"Device: {DEVICE}")
print(f"Confidence Threshold: {CONF_THRESHOLD}")
print(f"Max Track Age: {TRACKER_MAX_AGE} frames")
print("=" * 70)

# ===== From cell_10.py =====
def get_input_source():
    """Resolve detector and input source for local runs."""
    
    detector_path = Path(DETECTOR_MODEL_PATH)
    video_path = Path(VIDEO_INPUT_PATH)
    
    # Check if detector exists
    if not detector_path.exists():
        logger.warning(f"Detector model not found: {DETECTOR_MODEL_PATH}")
        logger.info("Will use pretrained YOLOv8m model instead...")
        detector_use = 'yolov8m.pt'
    else:
        detector_use = str(detector_path)
    
    # Prefer webcam for live input.
    if USE_WEBCAM:
        return detector_use, WEBCAM_INDEX

    # Fallback to file input if webcam is disabled.
    if not video_path.exists():
        raise FileNotFoundError(
            f"Video file not found: {VIDEO_INPUT_PATH}. Provide a valid local video or set USE_WEBCAM=True."
        )

    return detector_use, str(video_path)

detector_model, video_file = get_input_source()
print(f"\nUsing detector: {detector_model}")
print(f"Using video: {video_file}")

