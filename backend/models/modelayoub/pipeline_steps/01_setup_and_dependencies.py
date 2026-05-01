# Auto-generated from notebook code cells, grouped by pipeline step.

# ===== From cell_01.py =====
# Dependency installation is handled via requirements/requirements.txt.

# ===== From cell_02.py =====
import numpy as np
import cv2
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import torch
from ultralytics import YOLO
import json
import csv
import logging
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

print("All imports successful!")
print(f"PyTorch Version: {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")

