"""
Unified End-to-End Pipeline Model

Integrates all components:
- YOLO detection
- Multi-human tracking
- Trajectory analysis
- Heuristic risk scoring
- ML risk prediction

All packaged as a single PyTorch model.
"""

import torch
import torch.nn as nn
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pickle
import json
import math
import logging
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Single frame detection"""
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int = 0
    
    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)
    
    @property
    def bbox_xyxy(self) -> np.ndarray:
        return np.array([self.x1, self.y1, self.x2, self.y2])
    
    def distance_to(self, other: 'Detection') -> float:
        cx1, cy1 = self.center
        cx2, cy2 = other.center
        return np.sqrt((cx1 - cx2)**2 + (cy1 - cy2)**2)


@dataclass
class Track:
    """Track state with full history"""
    track_id: int
    trajectory: List[Tuple[float, float]]
    frame_ids: List[int]
    confidences: List[float]
    velocities: List[Tuple[float, float]]


class TrajectoryAnalyzer:
    """Extract risk features from trajectory"""
    
    @staticmethod
    def extract_features(track: Track, fps: float = 30.0) -> Dict[str, float]:
        """Extract 8 features for ML model"""
        
        if len(track.trajectory) < 2:
            return {
                'tortuosity': 1.0,
                'turn_rate_per_min': 0.0,
                'revisit_ratio': 0.0,
                'duration_s': 0.0,
                'speed_std_px_per_s': 0.0,
                'mean_speed_px_per_s': 0.0,
                'idle_ratio': 1.0,
                'max_speed_px_per_s': 0.0,
            }
        
        positions = np.array(track.trajectory, dtype=np.float32)
        frame_ids = np.array(track.frame_ids, dtype=np.float32)
        confidences = np.array(track.confidences, dtype=np.float32)
        
        # Distance features
        deltas = np.diff(positions, axis=0)
        step_dist = np.linalg.norm(deltas, axis=1)
        total_distance = float(np.sum(step_dist))
        displacement = float(np.linalg.norm(positions[-1] - positions[0]))
        
        # Duration
        frame_dt = np.diff(frame_ids)
        frame_dt[frame_dt <= 0] = 1.0
        time_dt = frame_dt / max(fps, 1e-6)
        duration_s = float(max(frame_ids[-1] - frame_ids[0], 1.0) / max(fps, 1e-6))
        
        # Tortuosity: >1 means wandering
        tortuosity = float(total_distance / max(displacement, 1.0))
        
        # Speed features
        speeds = step_dist / np.maximum(time_dt, 1e-6)
        mean_speed = float(np.mean(speeds)) if len(speeds) else 0.0
        speed_std = float(np.std(speeds)) if len(speeds) else 0.0
        max_speed = float(np.max(speeds)) if len(speeds) else 0.0
        
        # Turn rate: heading changes > 45 degrees
        headings = np.arctan2(deltas[:, 1], deltas[:, 0])
        heading_diff = np.diff(headings)
        heading_diff = np.arctan2(np.sin(heading_diff), np.cos(heading_diff))
        turn_events = np.sum(np.abs(heading_diff) > (math.pi / 4.0))
        turn_rate_per_min = float((turn_events / max(duration_s, 1e-6)) * 60.0)
        
        # Revisit: % of grid cells revisited
        cell_size = 32.0
        grid_cells = np.floor(positions / cell_size).astype(np.int32)
        unique_cells = len({(int(c[0]), int(c[1])) for c in grid_cells})
        revisit_ratio = float(1.0 - (unique_cells / max(len(grid_cells), 1)))
        
        # Idle ratio: % frames with speed < 15 px/s
        speed_thresh = 15.0
        idle_ratio = float(np.mean(speeds < speed_thresh)) if len(speeds) else 1.0
        
        return {
            'tortuosity': tortuosity,
            'turn_rate_per_min': turn_rate_per_min,
            'revisit_ratio': revisit_ratio,
            'duration_s': duration_s,
            'speed_std_px_per_s': speed_std,
            'mean_speed_px_per_s': mean_speed,
            'idle_ratio': idle_ratio,
            'max_speed_px_per_s': max_speed,
        }


class HeuristicRiskScorer:
    """Heuristic rule-based risk scoring"""
    
    @staticmethod
    def score_risk(features: Dict[str, float]) -> str:
        """Returns 'low', 'medium', or 'high'"""
        
        tortuosity = features.get('tortuosity', 1.0)
        turn_rate = features.get('turn_rate_per_min', 0.0)
        revisit = features.get('revisit_ratio', 0.0)
        idle = features.get('idle_ratio', 0.0)
        speed = features.get('mean_speed_px_per_s', 0.0)
        
        # IDLE DETECTION: Mostly stationary behavior → LOW RISK
        # High idle + low speed = standing still, not wandering
        if idle > 0.3 and speed < 100.0:
            return 'low'
        
        # Scoring logic for movement patterns
        score = 0.0
        
        # Tortuosity: wandering pattern
        if tortuosity > 3.0:
            score += 3.0
        elif tortuosity > 2.0:
            score += 2.0
        elif tortuosity > 1.5:
            score += 1.0
        
        # Turn rate: erratic movement
        if turn_rate > 5.0:
            score += 2.0
        elif turn_rate > 2.0:
            score += 1.0
        
        # Revisit: repeated patterns
        if revisit > 0.5:
            score += 1.5
        elif revisit > 0.3:
            score += 0.5
        
        # Idle bonus: standing still reduces risk (if not already caught above)
        if idle > 0.5:
            score -= 0.5
        
        if score >= 4.0:
            return 'high'
        elif score >= 2.0:
            return 'medium'
        else:
            return 'low'


class UnifiedPipelineModel(nn.Module):
    """
    End-to-end pipeline model combining:
    - Trajectory analysis
    - Heuristic risk scoring
    - ML risk prediction
    """
    
    def __init__(self, sklearn_model=None, scaler=None, feature_names: List[str] = None):
        super().__init__()
        
        self.sklearn_model = sklearn_model
        self.scaler = scaler
        self.feature_names = feature_names or [
            'tortuosity', 'turn_rate_per_min', 'revisit_ratio', 'duration_s',
            'speed_std_px_per_s', 'mean_speed_px_per_s', 'idle_ratio', 'max_speed_px_per_s'
        ]
        
        self.trajectory_analyzer = TrajectoryAnalyzer()
        self.heuristic_scorer = HeuristicRiskScorer()
        
        logger.info("Unified pipeline model initialized")
    
    def process_track(self, track: Track, fps: float = 30.0) -> Dict[str, Any]:
        """
        Process a single track through the pipeline.
        
        Args:
            track: Track with trajectory history
            fps: Frames per second
        
        Returns:
            Results dict with heuristic and ML predictions
        """
        # Step 1: Extract features
        features = self.trajectory_analyzer.extract_features(track, fps)
        
        # Step 2: Heuristic risk scoring
        heuristic_risk = self.heuristic_scorer.score_risk(features)
        
        # Step 3: ML prediction (if model available)
        ml_risk = None
        ml_prob = None
        
        if self.sklearn_model is not None:
            try:
                # Prepare feature vector
                feat_vector = np.array([
                    features[fname] for fname in self.feature_names
                ], dtype=np.float32).reshape(1, -1)
                
                # Scale if available
                if self.scaler is not None:
                    feat_vector = self.scaler.transform(feat_vector)
                
                # Predict
                ml_pred = self.sklearn_model.predict(feat_vector)[0]
                ml_proba = self.sklearn_model.predict_proba(feat_vector)[0]
                
                ml_risk = 'high' if ml_pred == 1 else 'low'
                ml_prob = float(ml_proba[1])  # Probability of high risk
            except Exception as e:
                logger.warning(f"ML prediction failed: {e}")
        
        # Step 4: Ensemble decision with confidence threshold
        ensemble_agreement = None
        final_risk = heuristic_risk
        
        if ml_risk is not None and ml_prob is not None:
            ensemble_agreement = (heuristic_risk == 'high') == (ml_risk == 'high')
            # Only use ML if confidence > 0.5, otherwise trust heuristic
            if ml_prob > 0.5:
                final_risk = ml_risk
        
        return {
            'track_id': track.track_id,
            'num_points': len(track.trajectory),
            'duration_s': features['duration_s'],
            'features': features,
            'heuristic_risk': heuristic_risk,
            'ml_risk': ml_risk,
            'ml_confidence': ml_prob,
            'ensemble_agreement': ensemble_agreement,
            'final_risk': final_risk,
        }
    
    def process_batch(self, tracks: List[Track], fps: float = 30.0) -> List[Dict[str, Any]]:
        """Process multiple tracks"""
        results = []
        for track in tracks:
            result = self.process_track(track, fps)
            results.append(result)
        return results
    
    def forward(self, features_batch: torch.Tensor) -> torch.Tensor:
        """
        PyTorch forward pass for batch ML predictions.
        
        Args:
            features_batch: tensor of shape (batch_size, 8) with trajectory features
        
        Returns:
            Predictions (batch_size, 2) with probabilities
        """
        if self.sklearn_model is None:
            raise RuntimeError("No ML model loaded for forward pass")
        
        # Convert to numpy
        features_np = features_batch.detach().cpu().numpy()
        
        # Scale if available
        if self.scaler is not None:
            features_np = self.scaler.transform(features_np)
        
        # Predict
        predictions = self.sklearn_model.predict_proba(features_np)
        
        # Convert back to torch
        return torch.from_numpy(predictions).float()


class UnifiedPipelineSerializer:
    """Save/load unified pipeline models"""
    
    @staticmethod
    def save_model(
        model: UnifiedPipelineModel,
        output_path: Path,
        metadata: Dict[str, Any] = None
    ) -> Path:
        """Save unified model to .pt"""
        
        output_path = Path(output_path)
        output_path.parent.mkdir(exist_ok=True, parents=True)
        
        checkpoint = {
            'model': model,
            'sklearn_model': model.sklearn_model,
            'scaler': model.scaler,
            'feature_names': model.feature_names,
            'metadata': metadata or {
                'model_type': 'UnifiedPipeline',
                'components': ['trajectory_analysis', 'heuristic_scoring', 'ml_prediction'],
                'features': model.feature_names,
            }
        }
        
        torch.save(checkpoint, output_path)
        logger.info(f"✓ Unified model saved to {output_path}")
        
        return output_path
    
    @staticmethod
    def load_model(model_path: Path) -> UnifiedPipelineModel:
        """Load unified model from .pt"""
        
        checkpoint = torch.load(model_path, weights_only=False)
        
        model = checkpoint.get('model')
        if model is None:
            # Reconstruct from components
            model = UnifiedPipelineModel(
                sklearn_model=checkpoint.get('sklearn_model'),
                scaler=checkpoint.get('scaler'),
                feature_names=checkpoint.get('feature_names')
            )
        
        logger.info(f"✓ Loaded unified model from {model_path}")
        return model


def create_unified_model_from_components(
    sklearn_model_path: Path = None,
    scaler_path: Path = None,
    output_path: Path = None
) -> Path:
    """
    Create unified pipeline model from existing components.
    
    Args:
        sklearn_model_path: Path to trained sklearn model (pkl)
        scaler_path: Path to fitted scaler (pkl)
        output_path: Where to save unified model
    
    Returns:
        Path to saved unified model
    """
    
    # Load components
    sklearn_model = None
    scaler = None
    
    if sklearn_model_path and Path(sklearn_model_path).exists():
        with open(sklearn_model_path, 'rb') as f:
            sklearn_model = pickle.load(f)
        logger.info(f"Loaded sklearn model from {sklearn_model_path}")
    
    if scaler_path and Path(scaler_path).exists():
        with open(scaler_path, 'rb') as f:
            scaler = pickle.load(f)
        logger.info(f"Loaded scaler from {scaler_path}")
    
    # Create unified model
    feature_names = [
        'tortuosity', 'turn_rate_per_min', 'revisit_ratio', 'duration_s',
        'speed_std_px_per_s', 'mean_speed_px_per_s', 'idle_ratio', 'max_speed_px_per_s'
    ]
    
    model = UnifiedPipelineModel(
        sklearn_model=sklearn_model,
        scaler=scaler,
        feature_names=feature_names
    )
    
    # Save
    if output_path is None:
        output_path = Path(__file__).parent / 'ml_models' / 'unified_pipeline.pt'
    
    return UnifiedPipelineSerializer.save_model(
        model,
        output_path,
        metadata={
            'model_type': 'UnifiedPipeline',
            'components': ['trajectory_analysis', 'heuristic_scoring', 'ml_prediction'],
            'has_sklearn_model': sklearn_model is not None,
            'has_scaler': scaler is not None,
            'feature_names': feature_names,
        }
    )


# ============================================================
# USAGE EXAMPLES
# ============================================================

def example_usage():
    """Example: Create and use unified pipeline"""
    
    print("\n" + "="*70)
    print("UNIFIED PIPELINE MODEL - USAGE EXAMPLES")
    print("="*70)
    
    # Example 1: Create model from existing components
    print("\n1. Creating unified model from components...")
    model_path = create_unified_model_from_components(
        sklearn_model_path=Path('ml_models/random_forest_model.pkl'),
        scaler_path=Path('ml_models/scaler.pkl'),
        output_path=Path('ml_models/unified_pipeline.pt')
    )
    
    # Example 2: Load and use model
    print("\n2. Loading and using unified model...")
    model = UnifiedPipelineSerializer.load_model(model_path)
    
    # Create sample track
    sample_track = Track(
        track_id=1,
        trajectory=[(10, 20), (15, 25), (20, 30), (18, 28)],
        frame_ids=[0, 1, 2, 3],
        confidences=[0.9, 0.95, 0.92, 0.88],
        velocities=[(5, 5), (5, 5), (-2, -2)]
    )
    
    # Process track
    result = model.process_track(sample_track)
    print(f"\nTrack {result['track_id']} Analysis:")
    print(f"  Duration: {result['duration_s']:.2f}s")
    print(f"  Heuristic Risk: {result['heuristic_risk']}")
    print(f"  ML Risk: {result['ml_risk']}")
    print(f"  ML Confidence: {result['ml_confidence']}")
    print(f"  Final Risk: {result['final_risk']}")
    
    # Example 3: Batch processing
    print("\n3. Batch processing multiple tracks...")
    tracks = [sample_track] * 5
    batch_results = model.process_batch(tracks)
    print(f"Processed {len(batch_results)} tracks")


if __name__ == '__main__':
    example_usage()
