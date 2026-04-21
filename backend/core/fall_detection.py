"""
Pose + LSTM fall classifier (matches training notebook / camera_test.py).
Loaded only when running the detector (e.g. manage.py run_fall_detector).
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Deque, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from django.conf import settings
from ultralytics import YOLO


class AttentionLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_classes, dropout=0.3):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.attention = nn.Sequential(
            nn.Linear(hidden_size * 2, 128),
            nn.Tanh(),
            nn.Linear(128, 1),
        )
        self.fc1 = nn.Linear(hidden_size * 2, 128)
        self.bn1 = nn.BatchNorm1d(128)
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(128, num_classes)

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        attention_scores = self.attention(lstm_out)
        attention_weights = torch.softmax(attention_scores, dim=1)
        context_vector = torch.sum(attention_weights * lstm_out, dim=1)
        out = torch.relu(self.fc1(context_vector))
        out = self.bn1(out)
        out = self.dropout(out)
        logits = self.fc2(out)
        return logits, attention_weights


def extract_kinematic_features(keypoints: np.ndarray, frame_w: int, frame_h: int) -> np.ndarray:
    features = []
    try:
        nose, left_ankle, right_ankle = keypoints[0], keypoints[15], keypoints[16]
        if nose[2] > 0.3 and (left_ankle[2] > 0.3 or right_ankle[2] > 0.3):
            lowest_ankle = left_ankle[1] if left_ankle[2] > right_ankle[2] else right_ankle[1]
            vertical_extent = abs(nose[1] - lowest_ankle) / frame_h
        else:
            vertical_extent = 0.0
        features.append(vertical_extent)

        valid_points = keypoints[keypoints[:, 2] > 0.3]
        if len(valid_points) > 0:
            com_x = np.average(valid_points[:, 0], weights=valid_points[:, 2]) / frame_w
            com_y = np.average(valid_points[:, 1], weights=valid_points[:, 2]) / frame_h
        else:
            com_x, com_y = 0.5, 0.5
        features.extend([com_x, com_y])

        ls, rs, lh, rh = keypoints[5], keypoints[6], keypoints[11], keypoints[12]
        if all(kp[2] > 0.3 for kp in [ls, rs, lh, rh]):
            s_mid = [(ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2]
            h_mid = [(lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2]
            torso_angle = np.arctan2(abs(h_mid[0] - s_mid[0]), abs(h_mid[1] - s_mid[1]))
        else:
            torso_angle = 0.0
        features.append(min(torso_angle, np.pi / 2))

        if len(valid_points) > 3:
            width = (np.max(valid_points[:, 0]) - np.min(valid_points[:, 0])) / frame_w
            height = (np.max(valid_points[:, 1]) - np.min(valid_points[:, 1])) / frame_h
            aspect_ratio = width / (height + 1e-6)
        else:
            aspect_ratio = 0.5
        features.append(aspect_ratio)
        features.append(float(np.mean(keypoints[:, 2])))
    except Exception:
        features = [0.0] * 6
    return np.array(features, dtype=np.float32)


class FallDetector:
    """YOLO pose + AttentionLSTM sequence classifier."""

    FEATURE_DIM = 57  # 17 keypoints * 3 + 6 kinematic

    def __init__(
        self,
        lstm_weights: Optional[Path] = None,
        yolo_weights: Optional[str] = None,
    ):
        cfg = getattr(settings, "FALL_DETECTION", {})
        self.frame_w = int(cfg.get("FRAME_WIDTH", 640))
        self.frame_h = int(cfg.get("FRAME_HEIGHT", 480))
        self.sequence_length = int(cfg.get("SEQUENCE_LENGTH", 25))
        self.hidden_size = int(cfg.get("LSTM_HIDDEN_SIZE", 256))
        self.num_layers = int(cfg.get("LSTM_NUM_LAYERS", 2))
        self.num_classes = int(cfg.get("NUM_CLASSES", 2))
        self.fall_class_index = int(cfg.get("FALL_CLASS_INDEX", 1))

        default_weights = settings.BASE_DIR / "models" / "best_model.pth"
        path = lstm_weights or cfg.get("LSTM_WEIGHTS", default_weights)
        self._lstm_path = Path(path)
        yolo_name = yolo_weights or cfg.get("YOLO_POSE", "yolo11n-pose.pt")

        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.yolo = YOLO(yolo_name)
        self.model = AttentionLSTM(
            input_size=self.FEATURE_DIM,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            num_classes=self.num_classes,
        ).to(self._device)
        try:
            state = torch.load(self._lstm_path, map_location=self._device, weights_only=False)
        except TypeError:
            state = torch.load(self._lstm_path, map_location=self._device)
        self.model.load_state_dict(state)
        self.model.eval()

        self._buffer: Deque[np.ndarray] = deque(maxlen=self.sequence_length)

    def reset_buffer(self) -> None:
        self._buffer.clear()

    def frame_to_vector(self, frame_bgr: np.ndarray) -> np.ndarray:
        import cv2

        frame = cv2.resize(frame_bgr, (self.frame_w, self.frame_h))
        results = self.yolo(frame, verbose=False)
        if results[0].keypoints is not None and len(results[0].keypoints) > 0:
            kpts = results[0].keypoints.xy[0].cpu().numpy()
            conf = results[0].keypoints.conf[0].cpu().numpy().reshape(-1, 1)
            keypoints = np.concatenate([kpts, conf], axis=1)
            pose_feat = keypoints.flatten()
            kin_feat = extract_kinematic_features(keypoints, self.frame_w, self.frame_h)
            return np.concatenate([pose_feat, kin_feat]).astype(np.float32)
        return np.zeros(self.FEATURE_DIM, dtype=np.float32)

    def push_frame(self, frame_bgr: np.ndarray) -> None:
        self._buffer.append(self.frame_to_vector(frame_bgr))

    def predict_if_ready(self) -> Optional[Tuple[int, float]]:
        """
        If the sequence buffer is full, run LSTM and return (class_index, confidence).
        Otherwise return None.
        """
        if len(self._buffer) < self.sequence_length:
            return None
        seq = np.array(self._buffer, dtype=np.float32)
        x = torch.FloatTensor(seq).unsqueeze(0).to(self._device)
        with torch.no_grad():
            logits, _ = self.model(x)
            prob = torch.softmax(logits, dim=1)
            pred = int(torch.argmax(prob, dim=1).item())
            confidence = float(prob[0, pred].item())
        return pred, confidence

    def is_fall(self, pred: int) -> bool:
        return pred == self.fall_class_index
