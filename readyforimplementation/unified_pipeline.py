"""
Unified Webcam Tracking & Risk Analysis Pipeline

Captures live video from webcam, detects humans with YOLO,
tracks trajectories with centroid-based tracking,
and processes through unified risk analysis model.

Usage:
  python unified_pipeline.py [--duration 60] [--no-display]
"""

import sys
import cv2
import json
import logging
import argparse
import shutil
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import components
try:
    from unified_pipeline_model import Track, UnifiedPipelineModel, UnifiedPipelineSerializer
    logger.info("✓ Imported unified pipeline model")
except ImportError as e:
    logger.error(f"Failed to import unified pipeline: {e}")
    sys.exit(1)

try:
    from ultralytics import YOLO
    logger.info("✓ YOLO imported")
except ImportError:
    logger.error("YOLO not installed. Install with: pip install ultralytics")
    sys.exit(1)


class SORTTracker:
    """Simple Online and Realtime Tracking (SORT) - Same as working pipeline"""
    
    def __init__(self, max_age: int = 30, min_hits: int = 1, iou_threshold: float = 0.3):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.tracks: Dict[int, Dict] = {}
        self.next_id = 1
        self.frame_count = 0
    
    def update(self, detections: List[Tuple[float, float, float, float, float]], frame_id: int):
        """Update tracks with new detections (detections: list of (x1,y1,x2,y2,conf))"""
        
        self.frame_count = frame_id
        
        if not detections:
            detections = []
        
        # Assign detections to tracks by IoU
        matched = {}
        unmatched_dets = set(range(len(detections)))
        
        for track_id in list(self.tracks.keys()):
            track = self.tracks[track_id]
            track_box = track['bbox']
            best_iou = self.iou_threshold
            best_det_idx = -1
            
            for det_idx, (x1, y1, x2, y2, conf) in enumerate(detections):
                if det_idx not in unmatched_dets:
                    continue
                iou = self._compute_iou(track_box, (x1, y1, x2, y2))
                if iou > best_iou:
                    best_iou = iou
                    best_det_idx = det_idx
            
            if best_det_idx >= 0:
                x1, y1, x2, y2, conf = detections[best_det_idx]
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                
                track['bbox'] = (x1, y1, x2, y2)
                track['centroid'] = (cx, cy)
                track['trajectory'].append((cx, cy))
                track['frame_ids'].append(frame_id)
                track['confidences'].append(conf)
                track['age'] += 1
                track['consecutive_misses'] = 0
                
                matched[track_id] = True
                unmatched_dets.discard(best_det_idx)
        
        # Increment misses for unmatched tracks
        for track_id in self.tracks:
            if track_id not in matched:
                self.tracks[track_id]['consecutive_misses'] += 1
        
        # Create new tracks
        for det_idx in unmatched_dets:
            x1, y1, x2, y2, conf = detections[det_idx]
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            
            self.tracks[self.next_id] = {
                'bbox': (x1, y1, x2, y2),
                'centroid': (cx, cy),
                'trajectory': [(cx, cy)],
                'frame_ids': [frame_id],
                'confidences': [conf],
                'velocities': [],
                'age': 1,
                'consecutive_misses': 0
            }
            self.next_id += 1
        
        # Remove old tracks
        to_remove = [
            tid for tid, track in self.tracks.items()
            if track['consecutive_misses'] > self.max_age
        ]
        for tid in to_remove:
            del self.tracks[tid]
    
    def _compute_iou(self, box1, box2):
        """Compute IoU between two boxes"""
        x1_inter = max(box1[0], box2[0])
        y1_inter = max(box1[1], box2[1])
        x2_inter = min(box1[2], box2[2])
        y2_inter = min(box1[3], box2[3])
        
        if x2_inter < x1_inter or y2_inter < y1_inter:
            return 0.0
        
        inter_area = (x2_inter - x1_inter) * (y2_inter - y1_inter)
        box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union_area = box1_area + box2_area - inter_area
        
        return inter_area / union_area if union_area > 0 else 0.0
    
    def get_active_tracks(self, min_age: int = 3) -> List[Track]:
        """Return active tracks with enough history"""
        tracks = []
        for track_id, track_data in self.tracks.items():
            if len(track_data['trajectory']) >= min_age and track_data['consecutive_misses'] == 0:
                track = Track(
                    track_id=track_id,
                    trajectory=track_data['trajectory'],
                    frame_ids=track_data['frame_ids'],
                    confidences=track_data['confidences'],
                    velocities=track_data['velocities']
                )
                tracks.append(track)
        return tracks


class UnifiedPipeline:
    """Webcam tracking and risk analysis pipeline"""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.models_dir = self.project_root / 'models'
        self.results_dir = self.project_root / 'pipeline_test_results'
        self.stop_request_file = self.results_dir / 'wandering_stop_request.json'
        
        self.results_dir.mkdir(exist_ok=True, parents=True)
        
        # Load unified model
        self.model_path = self.models_dir / 'unified_pipeline.pt'
        if not self.model_path.exists():
            logger.error(f"Unified model not found at {self.model_path}")
            sys.exit(1)
        
        logger.info(f"Loading unified model from {self.model_path}")
        self.model = UnifiedPipelineSerializer.load_model(self.model_path)
        logger.info("✓ Unified model loaded successfully")

    def _clear_stop_request(self) -> None:
        if self.stop_request_file.exists():
            self.stop_request_file.unlink()

    def _stop_requested(self) -> bool:
        return self.stop_request_file.exists()

    def _build_trajectory_export(
        self,
        tracker: SORTTracker,
        fps: float,
        width: int,
        height: int,
        frame_count: int,
        source_path: str | None,
    ) -> dict[str, Any]:
        tracks: dict[str, list[dict[str, Any]]] = {}

        for track_id, track_data in tracker.tracks.items():
            trajectory: list[dict[str, Any]] = []
            points = track_data.get('trajectory', [])
            frame_ids = track_data.get('frame_ids', [])
            confidences = track_data.get('confidences', [])

            for index, (x, y) in enumerate(points):
                trajectory.append({
                    'frame_id': frame_ids[index] if index < len(frame_ids) else index,
                    'center': [float(x), float(y)],
                    'confidence': float(confidences[index]) if index < len(confidences) else 0.0,
                })

            tracks[str(track_id)] = trajectory

        return {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_tracks': len(tracks),
                'total_frames': frame_count,
                'fps': fps,
                'width': width,
                'height': height,
                'video_path': source_path,
            },
            'tracks': tracks,
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # WEBCAM MODE
    # ═══════════════════════════════════════════════════════════════════════════

    def _open_video_capture(self, video_input_path: Optional[str], webcam_index: int):
        if video_input_path:
            cap = cv2.VideoCapture(video_input_path)
            return cap, f"video file: {video_input_path}"

        # On Windows, CAP_MSMF can fail with -1072875772 on some webcams.
        backend_candidates = [
            (cv2.CAP_DSHOW, 'CAP_DSHOW'),
            (cv2.CAP_MSMF, 'CAP_MSMF'),
            (cv2.CAP_ANY, 'CAP_ANY'),
        ]

        last_cap = None
        for backend, backend_name in backend_candidates:
            try:
                cap = cv2.VideoCapture(webcam_index, backend)
            except TypeError:
                cap = cv2.VideoCapture(webcam_index)

            if cap is not None and cap.isOpened():
                logger.info(f"Opened webcam {webcam_index} using {backend_name}")
                return cap, f"webcam {webcam_index} ({backend_name})"

            if cap is not None:
                cap.release()
            last_cap = cap

        return last_cap, f"webcam {webcam_index}"
    
    def run_webcam_mode(
        self,
        duration_seconds: Optional[int] = 60,
        show_display: bool = True,
        video_input_path: Optional[str] = None,
        webcam_index: int = 0,
    ):
        """Capture from webcam or video file, track, and analyze"""
        
        logger.info("="*70)
        logger.info("WEBCAM TRACKING WITH UNIFIED PIPELINE")
        logger.info("="*70)
        
        # Initialize YOLO and tracker
        yolo_model_path = self.project_root / 'yolov8n.pt'
        if not yolo_model_path.exists():
            logger.error(f"YOLO model not found at {yolo_model_path}")
            return False
        
        logger.info(f"Loading YOLO model: {yolo_model_path}")
        yolo_model = YOLO(str(yolo_model_path))
        tracker = SORTTracker(max_age=30, min_hits=1, iou_threshold=0.3)
        
        # Open video source (with webcam backend fallbacks on Windows)
        video_source = video_input_path if video_input_path else webcam_index
        cap, source_desc = self._open_video_capture(video_input_path, webcam_index)
        if not cap.isOpened():
            logger.error(f"Failed to open video source: {source_desc}")
            return False
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if video_input_path:
            logger.info(f"Video file properties: {width}x{height} @ {fps} FPS")
            logger.info(f"Capturing uploaded video: {video_input_path}")
        else:
            logger.info(f"Webcam properties: {width}x{height} @ {fps} FPS")
            logger.info(f"Webcam source: {source_desc}")
            logger.info(f"Capturing for {duration_seconds} seconds...")
        
        # Video writer
        video_path = self.results_dir / 'tracking_output.mp4'
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))

        self._clear_stop_request()
        
        frame_count = 0
        start_time = datetime.now()
        last_frame_time = start_time
        frame_timeout_seconds = 10  # Max time to wait for a frame
        
        logger.info(f"Starting capture loop with {frame_timeout_seconds}s frame timeout...")
        
        try:
            while True:
                # CHECK STOP REQUEST FIRST - before blocking on frame read
                if self._stop_requested():
                    logger.info("✓ Stop requested; breaking capture loop")
                    break
                
                # Check for timeout safety (prevent infinite waits)
                elapsed_total = (datetime.now() - start_time).total_seconds()
                elapsed_since_frame = (datetime.now() - last_frame_time).total_seconds()
                
                if elapsed_since_frame > frame_timeout_seconds:
                    logger.warning(f"Frame timeout ({elapsed_since_frame:.1f}s > {frame_timeout_seconds}s) - breaking")
                    break
                
                # Check duration for live webcam runs
                if duration_seconds is not None and not video_input_path and elapsed_total >= duration_seconds:
                    logger.info(f"✓ Capture duration reached ({elapsed_total:.1f}s >= {duration_seconds}s)")
                    break
                
                # Read frame
                ret, frame = cap.read()
                if not ret:
                    logger.info("✓ No more frames (end of stream)")
                    break
                
                last_frame_time = datetime.now()
                
                # CHECK STOP REQUEST AGAIN after frame read
                if self._stop_requested():
                    logger.info("✓ Stop requested (after frame read); breaking capture loop")
                    break
                
                # Run YOLO detection
                logger.debug(f"Frame {frame_count}: Running YOLO detection...")
                results = yolo_model(frame, conf=0.4, verbose=False)
                detections = []
                
                for result in results:
                    boxes = result.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = float(box.conf[0])
                        
                        # Only detect people (class 0)
                        if int(box.cls[0]) == 0:
                            # Clamp to frame bounds
                            x1 = max(0, min(x1, width))
                            y1 = max(0, min(y1, height))
                            x2 = max(0, min(x2, width))
                            y2 = max(0, min(y2, height))
                            
                            if x2 > x1 and y2 > y1:
                                detections.append((float(x1), float(y1), float(x2), float(y2), conf))
                
                # Update tracker
                tracker.update(detections, frame_count)
                
                # Draw on frame
                frame_with_boxes = frame.copy()
                
                # Draw detections
                for x1, y1, x2, y2, conf in detections:
                    cv2.rectangle(frame_with_boxes, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    cv2.putText(frame_with_boxes, f'{conf:.2f}', (int(x1), int(y1)-5),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                
                # Draw tracks
                for track_id, track_data in tracker.tracks.items():
                    if track_data['consecutive_misses'] > 0:
                        continue
                    
                    trajectory = track_data['trajectory']
                    
                    # Draw trajectory line
                    for i in range(1, len(trajectory)):
                        pt1 = (int(trajectory[i-1][0]), int(trajectory[i-1][1]))
                        pt2 = (int(trajectory[i][0]), int(trajectory[i][1]))
                        cv2.line(frame_with_boxes, pt1, pt2, (255, 0, 0), 2)
                    
                    # Draw track ID
                    if trajectory:
                        cx, cy = trajectory[-1]
                        cv2.putText(frame_with_boxes, f'ID:{track_id}', (int(cx), int(cy)-10),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                
                # Add text
                cv2.putText(frame_with_boxes, f'Frame: {frame_count}', (10, 30),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame_with_boxes, f'Tracks: {len([t for t in tracker.tracks.values() if t["consecutive_misses"] == 0])}', (10, 70),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame_with_boxes, f'Time: {elapsed_total:.1f}s', (10, 110),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # Write to video
                out.write(frame_with_boxes)
                
                # Show display
                if show_display:
                    cv2.imshow('Webcam Tracking', frame_with_boxes)
                    
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        logger.info("User quit early")
                        break
                
                frame_count += 1
                
                if frame_count % 30 == 0:
                    active = len([t for t in tracker.tracks.values() if t['consecutive_misses'] == 0])
                    logger.info(f"[{elapsed_total:.1f}s] Processed {frame_count} frames, {active} active tracks, {len(detections)} detections")
        
        finally:
            cap.release()
            out.release()
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                pass
            
            elapsed_total = (datetime.now() - start_time).total_seconds()
            logger.info(f"✓ Capture loop completed after {elapsed_total:.1f}s, {frame_count} frames written")
        
        # Process and save results
        logger.info("\n" + "="*70)
        logger.info("PROCESSING TRAJECTORIES")
        logger.info("="*70)
        
        active_tracks = tracker.get_active_tracks(min_age=3)
        
        if not active_tracks:
            logger.info("No active tracks found (no people detected)")
            self.save_results([], tracker, fps=fps, width=width, height=height, frame_count=frame_count, source_video_path=str(video_path), input_video_path=video_input_path)
            logger.info("✓ Webcam capture completed successfully")
            return True
        
        # Filter out short tracks (< 3 seconds)
        min_duration_frames = int(3 * 30)  # 3 seconds at 30 FPS
        filtered_tracks = []
        for track in active_tracks:
            if len(track.trajectory) >= min_duration_frames:
                filtered_tracks.append(track)
        
        if not filtered_tracks:
            logger.info(f"All {len(active_tracks)} tracks too short (< 3 seconds)")
            self.save_results([], tracker, fps=fps, width=width, height=height, frame_count=frame_count, source_video_path=str(video_path), input_video_path=video_input_path)
            logger.info("✓ Webcam capture completed successfully")
            return True
        
        logger.info(f"Processing {len(filtered_tracks)} tracks (filtered from {len(active_tracks)})...")
        results = self.model.process_batch(filtered_tracks, fps=30)
        
        # Save and print results
        self.print_summary(results)
        self.save_results(results, tracker, fps=fps, width=width, height=height, frame_count=frame_count, source_video_path=str(video_path), input_video_path=video_input_path)
        
        return True
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RESULTS & SAVING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def print_summary(self, results: List[Dict[str, Any]]) -> None:
        """Print results summary"""
        
        high_risk = sum(1 for r in results if r['final_risk'] == 'high')
        medium_risk = sum(1 for r in results if r['final_risk'] == 'medium')
        low_risk = sum(1 for r in results if r['final_risk'] == 'low')
        
        logger.info("\n" + "="*70)
        logger.info("RESULTS SUMMARY")
        logger.info("="*70)
        logger.info(f"Total Tracks: {len(results)}")
        logger.info(f"High Risk:    {high_risk} ({high_risk/len(results)*100:.1f}%)")
        logger.info(f"Medium Risk:  {medium_risk} ({medium_risk/len(results)*100:.1f}%)")
        logger.info(f"Low Risk:     {low_risk} ({low_risk/len(results)*100:.1f}%)")
        
        logger.info(f"\n{'Track ID':>8} | {'Duration':>10} | {'Points':>6} | {'Heuristic':>10} | {'Final Risk':>10}")
        logger.info("-" * 70)
        
        for result in sorted(results, key=lambda x: x['track_id']):
            logger.info(
                f"{result['track_id']:>8} | "
                f"{result['duration_s']:>9.2f}s | "
                f"{result['num_points']:>6} | "
                f"{result['heuristic_risk']:>10} | "
                f"{result['final_risk']:>10}"
            )
    
    def save_results(
        self,
        results: List[Dict[str, Any]],
        tracker: SORTTracker,
        fps: float,
        width: int,
        height: int,
        frame_count: int,
        source_video_path: str,
        input_video_path: Optional[str] = None,
    ) -> None:
        """Save processing results"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info("\n" + "="*70)
        logger.info("SAVING RESULTS")
        logger.info("="*70)

        result_rows = [
            {
                'track_id': r['track_id'],
                'duration_s': r['duration_s'],
                'num_points': r['num_points'],
                'tortuosity': r['features']['tortuosity'],
                'turn_rate_per_min': r['features']['turn_rate_per_min'],
                'revisit_ratio': r['features']['revisit_ratio'],
                'mean_speed_px_per_s': r['features']['mean_speed_px_per_s'],
                'idle_ratio': r['features']['idle_ratio'],
                'heuristic_risk': r['heuristic_risk'],
                'ml_risk': r['ml_risk'],
                'ml_confidence': r['ml_confidence'],
                'final_risk': r['final_risk'],
            }
            for r in results
        ]
        
        # JSON results
        json_file = self.results_dir / f"webcam_results_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"✓ Saved JSON: {json_file}")
        
        # CSV results
        df_columns = [
            'track_id',
            'duration_s',
            'num_points',
            'tortuosity',
            'turn_rate_per_min',
            'revisit_ratio',
            'mean_speed_px_per_s',
            'idle_ratio',
            'heuristic_risk',
            'ml_risk',
            'ml_confidence',
            'final_risk',
        ]
        df = pd.DataFrame(result_rows, columns=df_columns)
        
        csv_file = self.results_dir / f"webcam_results_{timestamp}.csv"
        df.to_csv(csv_file, index=False)
        logger.info(f"✓ Saved CSV: {csv_file}")

        # Legacy-compatible artifact files for the Django dashboard
        trajectories = self._build_trajectory_export(
            tracker=tracker,
            fps=fps,
            width=width,
            height=height,
            frame_count=frame_count,
            source_path=input_video_path or source_video_path,
        )

        trajectories_file = self.results_dir / 'trajectories.json'
        with open(trajectories_file, 'w', encoding='utf-8') as handle:
            json.dump(trajectories, handle, indent=2)
        logger.info(f"✓ Saved trajectories: {trajectories_file}")

        trajectories_csv = self.results_dir / 'trajectories.csv'
        trajectory_rows = []
        for track_id, points in trajectories['tracks'].items():
            for point in points:
                trajectory_rows.append({
                    'track_id': track_id,
                    'frame_id': point['frame_id'],
                    'center_x': point['center'][0],
                    'center_y': point['center'][1],
                    'confidence': point['confidence'],
                })
        pd.DataFrame(trajectory_rows, columns=['track_id', 'frame_id', 'center_x', 'center_y', 'confidence']).to_csv(trajectories_csv, index=False)
        logger.info(f"✓ Saved trajectories CSV: {trajectories_csv}")

        track_details = self.results_dir / 'track_details.csv'
        pd.DataFrame(result_rows, columns=df_columns).to_csv(track_details, index=False)
        logger.info(f"✓ Saved track details: {track_details}")

        total_tracks = len(results)
        tracking_summary = {
            'timestamp': datetime.now().isoformat(),
            'configuration': {
                'video_input': input_video_path or 'webcam',
                'fps': fps,
                'width': width,
                'height': height,
            },
            'processing_stats': {
                'total_tracks': total_tracks,
                'unique_tracks': total_tracks,
                'frames_processed': frame_count,
                'frames_with_detections': frame_count if total_tracks else 0,
                'avg_track_length': float(np.mean([row['num_points'] for row in results])) if results else 0.0,
            },
            'trajectory_stats': {
                'total_unique_tracks': len(trajectories['tracks']),
                'fps': fps,
                'width': width,
                'height': height,
                'total_frames': frame_count,
            },
            'output_files': {
                'video': str(self.results_dir / 'tracking_output.mp4'),
                'trajectories_json': str(trajectories_file),
                'trajectories_csv': str(trajectories_csv),
                'statistics_plot': str(self.results_dir / 'tracking_statistics.png'),
                'trajectories_plot': str(self.results_dir / 'trajectories_visualization.png'),
            },
        }

        tracking_summary_file = self.results_dir / 'tracking_summary.json'
        with open(tracking_summary_file, 'w', encoding='utf-8') as handle:
            json.dump(tracking_summary, handle, indent=2)
        logger.info(f"✓ Saved tracking summary: {tracking_summary_file}")

        wandering_report = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_tracks': total_tracks,
                'high_risk_tracks': sum(1 for row in results if row['final_risk'] == 'high'),
                'medium_risk_tracks': sum(1 for row in results if row['final_risk'] == 'medium'),
                'low_risk_tracks': sum(1 for row in results if row['final_risk'] == 'low'),
                'thresholds': {
                    'low': 'score < 35',
                    'medium': '35 <= score < 65',
                    'high': 'score >= 65',
                },
            },
            'tracks': [
                {
                    'track_id': row['track_id'],
                    'num_points': row['num_points'],
                    'duration_s': row['duration_s'],
                    'tortuosity': row['features']['tortuosity'],
                    'turn_rate_per_min': row['features']['turn_rate_per_min'],
                    'revisit_ratio': row['features']['revisit_ratio'],
                    'idle_ratio': row['features']['idle_ratio'],
                    'mean_speed_px_per_s': row['features']['mean_speed_px_per_s'],
                    'speed_std_px_per_s': row['features']['speed_std_px_per_s'],
                    'max_speed_px_per_s': row['features']['max_speed_px_per_s'],
                    'risk_score': 100.0 if row['final_risk'] == 'high' else 50.0 if row['final_risk'] == 'medium' else 10.0,
                    'risk_level': row['final_risk'],
                }
                for row in results
            ],
        }
        wandering_report_file = self.results_dir / 'wandering_risk_report.json'
        with open(wandering_report_file, 'w', encoding='utf-8') as handle:
            json.dump(wandering_report, handle, indent=2)
        logger.info(f"✓ Saved wandering risk report: {wandering_report_file}")

        latest_video = self.results_dir / 'tracking_output.mp4'
        if frame_count > 0 and Path(source_video_path).resolve() != latest_video.resolve():
            shutil.copy(source_video_path, latest_video)
            logger.info(f"✓ Saved tracking video: {latest_video}")
        else:
            logger.info(f"✓ Preserving existing tracking video: {latest_video}")
        
        # Text summary
        high_risk = sum(1 for r in results if r['final_risk'] == 'high')
        medium_risk = sum(1 for r in results if r['final_risk'] == 'medium')
        low_risk = sum(1 for r in results if r['final_risk'] == 'low')
        total_for_summary = len(results) or 1
        
        summary_file = self.results_dir / f"webcam_summary_{timestamp}.txt"
        with open(summary_file, 'w') as f:
            f.write("="*70 + "\n")
            f.write("WEBCAM TRACKING & RISK ANALYSIS - RESULTS\n")
            f.write("="*70 + "\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Model: unified_pipeline.pt\n")
            f.write(f"\nSUMMARY:\n")
            f.write(f"  Total Tracks: {len(results)}\n")
            f.write(f"  High Risk:    {high_risk} ({high_risk/total_for_summary*100:.1f}%)\n")
            f.write(f"  Medium Risk:  {medium_risk} ({medium_risk/total_for_summary*100:.1f}%)\n")
            f.write(f"  Low Risk:     {low_risk} ({low_risk/total_for_summary*100:.1f}%)\n")
            f.write(f"\nDETAILED RESULTS:\n")
            f.write(df.to_string())
        
        logger.info(f"✓ Saved summary: {summary_file}")
        
        # Update latest files
        shutil.copy(json_file, self.results_dir / "latest_webcam_results.json")
        shutil.copy(csv_file, self.results_dir / "latest_webcam_results.csv")
        shutil.copy(summary_file, self.results_dir / "latest_webcam_summary.txt")
        logger.info(f"✓ Updated latest files")
        logger.info(f"\n✓ All results saved to: {self.results_dir}")


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(description='Unified Webcam Tracking & Risk Analysis Pipeline')
    parser.add_argument('--duration', type=int, default=60, help='Webcam capture duration (seconds)')
    parser.add_argument('--video-input-path', type=str, default=None, help='Optional video file to analyze instead of webcam')
    parser.add_argument('--webcam-index', type=int, default=0, help='Webcam index to open when no video file is provided')
    parser.add_argument('--no-display', action='store_true', help='Hide live display (default: show display)')
    
    args = parser.parse_args()
    
    try:
        pipeline = UnifiedPipeline()
        
        success = pipeline.run_webcam_mode(
            duration_seconds=args.duration,
            show_display=not args.no_display,
            video_input_path=args.video_input_path,
            webcam_index=args.webcam_index,
        )
        
        if success:
            logger.info("\n" + "="*70)
            logger.info("✓ EXECUTION COMPLETE")
            logger.info("="*70)
            logger.info(f"Results saved to: {pipeline.results_dir}")
            return 0
        else:
            logger.error("Pipeline execution failed")
            return 1
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
