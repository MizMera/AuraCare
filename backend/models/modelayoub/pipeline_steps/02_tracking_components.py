# Auto-generated from notebook code cells, grouped by pipeline step.

# ===== From cell_03.py =====
@dataclass
class Detection:
    """Single frame detection result"""
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
    
    @property
    def bbox_xywh(self) -> Tuple:
        w = self.x2 - self.x1
        h = self.y2 - self.y1
        cx, cy = self.center
        return (cx, cy, w, h)
    
    @property
    def area(self) -> float:
        return (self.x2 - self.x1) * (self.y2 - self.y1)
    
    def iou(self, other: 'Detection') -> float:
        """Calculate Intersection over Union"""
        x1_inter = max(self.x1, other.x1)
        y1_inter = max(self.y1, other.y1)
        x2_inter = min(self.x2, other.x2)
        y2_inter = min(self.y2, other.y2)
        
        if x2_inter < x1_inter or y2_inter < y1_inter:
            return 0.0
        
        inter_area = (x2_inter - x1_inter) * (y2_inter - y1_inter)
        union_area = self.area + other.area - inter_area
        return inter_area / union_area if union_area > 0 else 0.0
    
    def distance_to(self, other: 'Detection') -> float:
        """Euclidean distance between centers"""
        cx1, cy1 = self.center
        cx2, cy2 = other.center
        return np.sqrt((cx1 - cx2)**2 + (cy1 - cy2)**2)

print("Detection class defined!")

# ===== From cell_04.py =====
@dataclass
class TrackState:
    """Track state including motion history"""
    track_id: int
    bbox: Detection
    frame_id: int
    age: int = 1
    consecutive_misses: int = 0
    trajectory: List[Tuple[float, float]] = field(default_factory=list)
    bbox_history: List[Detection] = field(default_factory=list)
    velocity: Optional[Tuple[float, float]] = None
    velocities: List[Tuple[float, float]] = field(default_factory=list)
    
    def update(self, detection: Detection, frame_id: int):
        """Update track with new detection"""
        if self.trajectory:
            prev_center = self.trajectory[-1]
            curr_center = detection.center
            self.velocity = (
                curr_center[0] - prev_center[0],
                curr_center[1] - prev_center[1]
            )
            self.velocities.append(self.velocity)
        
        self.bbox = detection
        self.frame_id = frame_id
        self.age += 1
        self.consecutive_misses = 0
        self.trajectory.append(detection.center)
        self.bbox_history.append(detection)
    
    def predict(self, frame_id: int) -> Optional[Detection]:
        """Predict next position using velocity"""
        if self.velocity is None or len(self.trajectory) < 2:
            return self.bbox
        
        frames_missed = frame_id - self.frame_id
        pred_center_x = self.trajectory[-1][0] + self.velocity[0] * frames_missed
        pred_center_y = self.trajectory[-1][1] + self.velocity[1] * frames_missed
        
        w = self.bbox.x2 - self.bbox.x1
        h = self.bbox.y2 - self.bbox.y1
        
        return Detection(
            x1=pred_center_x - w / 2,
            y1=pred_center_y - h / 2,
            x2=pred_center_x + w / 2,
            y2=pred_center_y + h / 2,
            confidence=self.bbox.confidence
        )
    
    def get_statistics(self) -> Dict:
        """Get trajectory statistics"""
        if len(self.trajectory) < 2:
            return {}
        
        positions = np.array(self.trajectory)
        distances = np.linalg.norm(np.diff(positions, axis=0), axis=1)
        
        stats = {
            'track_id': self.track_id,
            'age': self.age,
            'frames_active': len(self.trajectory),
            'total_distance': float(np.sum(distances)),
            'avg_velocity': float(np.mean(distances)) if len(distances) > 0 else 0.0,
            'max_velocity': float(np.max(distances)) if len(distances) > 0 else 0.0,
            'avg_confidence': float(np.mean([b.confidence for b in self.bbox_history])),
            'trajectory_length': len(self.trajectory)
        }
        return stats

print("TrackState class defined!")

# ===== From cell_05.py =====
class KalmanFilterTracker:
    """Simple Kalman filter for motion estimation"""
    
    def __init__(self, dt: float = 1.0, process_noise: float = 0.01, measurement_noise: float = 1.0):
        """
        State: [x, y, vx, vy]
        """
        self.dt = dt
        self.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])
        self.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])
        self.Q = np.eye(4) * process_noise
        self.R = np.eye(2) * measurement_noise
        self.P = np.eye(4) * 1.0
        self.x = None
    
    def init(self, detection: Detection):
        """Initialize with first detection"""
        cx, cy = detection.center
        self.x = np.array([[cx], [cy], [0], [0]], dtype=np.float32)
    
    def predict(self) -> Optional[np.ndarray]:
        """Predict next state"""
        if self.x is None:
            return None
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x[:2].flatten()
    
    def update(self, detection: Detection):
        """Update with measurement"""
        if self.x is None:
            self.init(detection)
            return
        
        cx, cy = detection.center
        z = np.array([[cx], [cy]], dtype=np.float32)
        
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P

print("KalmanFilterTracker class defined!")

# ===== From cell_06.py =====
# %% [markdown]
# ## Cell 6-FIXED: Define SORT Tracker with Better Association

# %%
class SORTTracker:
    """Simple Online and Realtime Tracking (SORT) - FIXED"""
    
    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 3,
        iou_threshold: float = 0.3
    ):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.tracks: Dict[int, TrackState] = {}
        self.kalman_filters: Dict[int, KalmanFilterTracker] = {}
        self.next_id = 0
        self.frame_count = 0
    
    def _associate_detections(
        self,
        detections: List[Detection]
    ) -> Tuple[Dict[int, Detection], List[Detection]]:
        """Associate detections to existing tracks using Hungarian algorithm - FIXED"""
        
        # If no tracks or no detections, return empty match
        if not self.tracks:
            return {}, detections
        
        if not detections:
            return {}, []
        
        track_ids = list(self.tracks.keys())
        n_tracks = len(track_ids)
        n_dets = len(detections)
        
        # Initialize cost matrix with high values (not infinite)
        cost_matrix = np.full((n_tracks, n_dets), 1.0, dtype=np.float32)
        
        # Fill cost matrix with IoU-based costs
        for i, track_id in enumerate(track_ids):
            track = self.tracks[track_id]
            for j, det in enumerate(detections):
                iou = track.bbox.iou(det)
                # Only set cost if IoU is above threshold
                if iou > self.iou_threshold:
                    cost_matrix[i, j] = 1.0 - iou  # Cost = 1 - IoU (lower is better)
                else:
                    cost_matrix[i, j] = 1.0  # High cost for poor matches
        
        # Apply Hungarian algorithm
        try:
            from scipy.optimize import linear_sum_assignment
            track_indices, det_indices = linear_sum_assignment(cost_matrix)
        except ValueError as e:
            logger.warning(f"Association error: {e}, returning no matches")
            return {}, detections
        
        matched = {}
        unmatched_dets = set(range(n_dets))
        
        # Process matched pairs
        for ti, di in zip(track_indices, det_indices):
            # Only accept match if cost is below threshold
            if cost_matrix[ti, di] < 1.0:  # Match threshold
                matched[track_ids[ti]] = detections[di]
                unmatched_dets.discard(di)
        
        unmatched_detections = [detections[i] for i in unmatched_dets]
        return matched, unmatched_detections
    
    def update(self, detections: List[Detection]) -> Dict[int, TrackState]:
        """Update tracks with new detections"""
        self.frame_count += 1
        
        # Handle empty detections
        if not detections:
            detections = []
        
        matched, unmatched_dets = self._associate_detections(detections)
        
        # Update matched tracks
        for track_id, detection in matched.items():
            self.tracks[track_id].update(detection, self.frame_count)
            if track_id in self.kalman_filters:
                self.kalman_filters[track_id].update(detection)
        
        # Update unmatched tracks (increment misses)
        unmatched_track_ids = set(self.tracks.keys()) - set(matched.keys())
        for track_id in unmatched_track_ids:
            self.tracks[track_id].consecutive_misses += 1
        
        # Create new tracks from unmatched detections
        for detection in unmatched_dets:
            if detection.confidence > 0.3:  # Lower threshold for new track creation
                new_track = TrackState(
                    track_id=self.next_id,
                    bbox=detection,
                    frame_id=self.frame_count,
                    trajectory=[detection.center],
                    bbox_history=[detection]
                )
                self.tracks[self.next_id] = new_track
                self.kalman_filters[self.next_id] = KalmanFilterTracker()
                self.kalman_filters[self.next_id].init(detection)
                self.next_id += 1
        
        # Remove old/dead tracks
        to_remove = [
            tid for tid, track in self.tracks.items()
            if track.consecutive_misses > self.max_age
        ]
        for tid in to_remove:
            del self.tracks[tid]
            if tid in self.kalman_filters:
                del self.kalman_filters[tid]
        
        return self.tracks

print("âœ“ SORTTracker class FIXED with better association handling!")

# ===== From cell_07.py =====
# %% [markdown]
# ## Cell 7-UPDATED: Add Error Handling to Pipeline

# %%
class MultiHumanTrackingPipeline:
    """Complete multi-human tracking pipeline - UPDATED"""
    
    def __init__(
        self,
        detector_path: str,
        video_path,
        output_dir: Path = Path('/kaggle/working/tracking_results'),
        device: str = 'cpu',
        conf_threshold: float = 0.5,
        max_track_age: int = 30,
        max_frames: Optional[int] = None,
        show_live: bool = False
    ):
        """Initialize tracking pipeline"""
        
        try:
            self.detector = YOLO(detector_path)
        except Exception as e:
            logger.error(f"Failed to load detector: {e}")
            raise
        
        self.video_source = video_path
        self.video_path = Path(video_path) if isinstance(video_path, (str, Path)) else None
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.conf_threshold = conf_threshold
        self.device = device
        self.max_frames = max_frames
        self.show_live = show_live
        
        self.tracker = SORTTracker(max_age=max_track_age, min_hits=1)
        self.tracks_history = defaultdict(list)
        self.frame_count = 0
        self.fps = 30
        self.width = 640
        self.height = 480
        
        logger.info(f"Pipeline initialized with detector: {detector_path}")
    
    def detect_frame(self, frame: np.ndarray) -> List[Detection]:
        """Detect humans in frame with error handling"""
        try:
            results = self.detector(frame, conf=self.conf_threshold, device=self.device, verbose=False)
            detections = []
            
            for result in results:
                if result.boxes is None:
                    continue
                
                boxes = result.boxes.xyxy.detach().cpu().numpy()
                confs = result.boxes.conf.detach().cpu().numpy()
                classes = result.boxes.cls.detach().cpu().numpy().astype(int)
                
                for box, conf, cls_id in zip(boxes, confs, classes):
                    if cls_id == 0:  # Person class
                        x1, y1, x2, y2 = box.tolist()
                        # Clamp to frame bounds
                        x1 = max(0, min(x1, frame.shape[1]))
                        y1 = max(0, min(y1, frame.shape[0]))
                        x2 = max(0, min(x2, frame.shape[1]))
                        y2 = max(0, min(y2, frame.shape[0]))
                        
                        # Skip invalid boxes
                        if x2 > x1 and y2 > y1:
                            detections.append(Detection(
                                x1=x1, y1=y1, x2=x2, y2=y2,
                                confidence=float(conf),
                                class_id=int(cls_id)
                            ))
            
            return detections
        except Exception as e:
            logger.warning(f"Detection error in frame: {e}")
            return []
    
    def process_video(self, show_progress: bool = True) -> Dict:
        """Process entire video with better error handling"""

        source = self.video_source
        cap = cv2.VideoCapture(source if isinstance(source, int) else str(source))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {source}")
        
        self.fps = cap.get(cv2.CAP_PROP_FPS)
        if self.fps is None or self.fps <= 0:
            self.fps = 30.0
        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames < 0:
            total_frames = 0
        
        out_path = self.output_dir / 'tracking_output.mp4'
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_writer = cv2.VideoWriter(str(out_path), fourcc, self.fps, (self.width, self.height))
        
        frame_id = 0
        stats = {
            'total_frames': total_frames,
            'total_detections': 0,
            'unique_tracks': 0,
            'avg_track_length': 0,
            'frames_with_detections': 0,
            'frames_processed': 0
        }
        
        logger.info(f"Processing source: {source}")
        if total_frames > 0:
            logger.info(f"Video: {self.fps:.1f} FPS | {self.width}x{self.height} | {total_frames} frames")
        else:
            logger.info(f"Stream: {self.fps:.1f} FPS | {self.width}x{self.height} | live/unknown frame count")

        preview_enabled = bool(self.show_live and isinstance(source, int))
        preview_window = 'Live Tracking Preview'
        if preview_enabled:
            logger.info("Live preview enabled. Press 'q' to stop.")
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                current_frame_id = frame_id
                
                try:
                    detections = self.detect_frame(frame)
                    stats['total_detections'] += len(detections)
                    if len(detections) > 0:
                        stats['frames_with_detections'] += 1
                    
                    # Update tracker
                    tracks = self.tracker.update(detections)
                    
                    # Record trajectories
                    for track_id, track in tracks.items():
                        self.tracks_history[track_id].append({
                            'frame_id': current_frame_id,
                            'bbox': track.bbox.bbox_xyxy.tolist(),
                            'center': track.bbox.center,
                            'confidence': track.bbox.confidence,
                            'age': track.age
                        })
                    
                    # Annotate and write frame
                    frame_annotated = self._annotate_frame(frame, tracks, display_frame_id=current_frame_id + 1)
                    out_writer.write(frame_annotated)

                    frame_id += 1
                    self.frame_count = frame_id
                    stats['frames_processed'] += 1

                    if preview_enabled:
                        try:
                            cv2.imshow(preview_window, frame_annotated)
                            if (cv2.waitKey(1) & 0xFF) == ord('q'):
                                logger.info("Live preview interrupted by user (q).")
                                break
                        except Exception as preview_error:
                            logger.warning(f"Live preview disabled: {preview_error}")
                            preview_enabled = False

                    if self.max_frames is not None and frame_id >= self.max_frames:
                        logger.info(f"Reached max_frames={self.max_frames}; stopping capture loop.")
                        break
                    
                    if show_progress and frame_id % max(1, total_frames // 10) == 0:
                        logger.info(f"Progress: {frame_id}/{total_frames} | Active tracks: {len(tracks)} | Detections: {len(detections)}")
                    elif show_progress and total_frames == 0 and frame_id % 30 == 0:
                        logger.info(f"Progress: {frame_id} frames processed | Active tracks: {len(tracks)} | Detections: {len(detections)}")
                
                except Exception as e:
                    logger.error(f"Error processing frame {frame_id}: {e}")
                    frame_id += 1
                    continue
        
        finally:
            cap.release()
            out_writer.release()
            if preview_enabled:
                try:
                    cv2.destroyWindow(preview_window)
                except Exception:
                    pass
        
        stats['unique_tracks'] = len(self.tracks_history)
        if self.tracks_history:
            avg_length = np.mean([len(v) for v in self.tracks_history.values()])
            stats['avg_track_length'] = float(avg_length)
        
        logger.info(f"Tracking complete. Output: {out_path}")
        logger.info(f"Total detections: {stats['total_detections']}")
        logger.info(f"Frames with detections: {stats['frames_with_detections']}/{stats['frames_processed']}")
        return stats
    
    def _annotate_frame(self, frame: np.ndarray, tracks: Dict[int, TrackState], display_frame_id: Optional[int] = None) -> np.ndarray:
        """Draw tracking annotations on frame"""
        
        frame_copy = frame.copy()
        colors = {}
        
        for track_id, track in tracks.items():
            if track_id not in colors:
                np.random.seed(track_id)
                colors[track_id] = (
                    np.random.randint(50, 255),
                    np.random.randint(50, 255),
                    np.random.randint(50, 255)
                )
            
            color = colors[track_id]
            
            try:
                x1, y1, x2, y2 = [int(v) for v in track.bbox.bbox_xyxy]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(frame_copy.shape[1], x2), min(frame_copy.shape[0], y2)
                
                cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, 2)
                
                label = f"ID:{track_id} ({track.age}f)"
                cv2.putText(frame_copy, label, (x1, max(20, y1 - 10)),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                if len(track.trajectory) > 1:
                    points = np.array(track.trajectory[-20:], dtype=np.int32)
                    # Clamp points to frame bounds
                    points[:, 0] = np.clip(points[:, 0], 0, frame_copy.shape[1] - 1)
                    points[:, 1] = np.clip(points[:, 1], 0, frame_copy.shape[0] - 1)
                    cv2.polylines(frame_copy, [points], False, color, 2)
            except Exception as e:
                logger.debug(f"Error drawing track {track_id}: {e}")
                continue
        
        frame_label = self.frame_count if display_frame_id is None else display_frame_id
        cv2.putText(frame_copy, f"Frame: {frame_label} | Tracks: {len(tracks)}",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return frame_copy
    
    def export_trajectories(self, format: str = 'json') -> Path:
        """Export track trajectories"""
        
        output_file = self.output_dir / f'trajectories.{format}'
        
        if format == 'json':
            export_data = {
                'metadata': {
                    'video_path': str(self.video_source),
                    'fps': self.fps,
                    'width': self.width,
                    'height': self.height,
                    'total_frames': self.frame_count,
                    'total_tracks': len(self.tracks_history),
                    'timestamp': datetime.now().isoformat()
                },
                'tracks': {}
            }
            
            for track_id, trajectory in self.tracks_history.items():
                export_data['tracks'][str(track_id)] = trajectory
            
            with open(output_file, 'w') as f:
                json.dump(export_data, f, indent=2)
        
        elif format == 'csv':
            with open(output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['track_id', 'frame_id', 'x1', 'y1', 'x2', 'y2', 'center_x', 'center_y', 'confidence', 'age'])
                
                for track_id, trajectory in self.tracks_history.items():
                    for entry in trajectory:
                        bbox = entry['bbox']
                        center = entry['center']
                        writer.writerow([
                            track_id, entry['frame_id'],
                            bbox[0], bbox[1], bbox[2], bbox[3],
                            center[0], center[1],
                            entry['confidence'], entry['age']
                        ])
        
        logger.info(f"Trajectories exported to {output_file}")
        return output_file
    
    def get_statistics(self) -> Dict:
        """Get tracking statistics"""
        
        stats = {
            'total_unique_tracks': len(self.tracks_history),
            'total_frames_processed': self.frame_count,
            'avg_detections_per_frame': 0,
            'track_statistics': {}
        }
        
        for track_id, trajectory in self.tracks_history.items():
            track_len = len(trajectory)
            if track_len > 0:
                positions = np.array([t['center'] for t in trajectory])
                distances = np.linalg.norm(np.diff(positions, axis=0), axis=1) if len(positions) > 1 else []
                total_distance = float(np.sum(distances))
                avg_confidence = float(np.mean([t['confidence'] for t in trajectory]))
                
                stats['track_statistics'][track_id] = {
                    'length': track_len,
                    'total_distance': total_distance,
                    'avg_velocity': float(np.mean(distances)) if len(distances) > 0 else 0.0,
                    'max_velocity': float(np.max(distances)) if len(distances) > 0 else 0.0,
                    'avg_confidence': avg_confidence,
                    'start_frame': trajectory[0]['frame_id'],
                    'end_frame': trajectory[-1]['frame_id'],
                    'duration_seconds': (trajectory[-1]['frame_id'] - trajectory[0]['frame_id']) / max(self.fps, 1)
                }
        
        return stats
    
    def visualize_statistics(self):
        """Create comprehensive visualization of tracking statistics"""
        
        if not self.tracks_history:
            logger.warning("No tracks to visualize")
            return
        
        track_lengths = [len(v) for v in self.tracks_history.values()]
        track_distances = []
        track_velocities = []
        
        for track_id, trajectory in self.tracks_history.items():
            if len(trajectory) > 1:
                positions = np.array([t['center'] for t in trajectory])
                distances = np.linalg.norm(np.diff(positions, axis=0), axis=1)
                track_distances.append(np.sum(distances))
                track_velocities.extend(distances.tolist())
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        axes[0, 0].hist(track_lengths, bins=max(1, len(track_lengths)//2 + 1), color='steelblue', edgecolor='black')
        axes[0, 0].set_xlabel('Track Length (frames)')
        axes[0, 0].set_ylabel('Frequency')
        axes[0, 0].set_title('Distribution of Track Lengths')
        axes[0, 0].grid(True, alpha=0.3)
        
        if track_distances:
            axes[0, 1].hist(track_distances, bins=max(1, len(track_distances)//2 + 1), color='coral', edgecolor='black')
            axes[0, 1].set_xlabel('Distance Traveled (pixels)')
            axes[0, 1].set_ylabel('Frequency')
            axes[0, 1].set_title('Distribution of Track Distances')
            axes[0, 1].grid(True, alpha=0.3)
        
        if track_velocities:
            axes[1, 0].hist(track_velocities, bins=50, color='lightgreen', edgecolor='black')
            axes[1, 0].set_xlabel('Velocity (pixels/frame)')
            axes[1, 0].set_ylabel('Frequency')
            axes[1, 0].set_title('Distribution of Velocities')
            axes[1, 0].grid(True, alpha=0.3)
        
        axes[1, 1].text(0.1, 0.9, f'Total Tracks: {len(self.tracks_history)}', 
                       transform=axes[1, 1].transAxes, fontsize=12, verticalalignment='top')
        axes[1, 1].text(0.1, 0.8, f'Avg Track Length: {np.mean(track_lengths):.1f} frames',
                       transform=axes[1, 1].transAxes, fontsize=12, verticalalignment='top')
        if track_distances:
            axes[1, 1].text(0.1, 0.7, f'Avg Distance: {np.mean(track_distances):.1f} pixels',
                           transform=axes[1, 1].transAxes, fontsize=12, verticalalignment='top')
        if track_velocities:
            axes[1, 1].text(0.1, 0.6, f'Avg Velocity: {np.mean(track_velocities):.2f} px/frame',
                           transform=axes[1, 1].transAxes, fontsize=12, verticalalignment='top')
        axes[1, 1].axis('off')
        
        plt.tight_layout()
        fig.savefig(self.output_dir / 'tracking_statistics.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info("Statistics visualization saved")
    
    def visualize_trajectories(self, sample_size: int = 10):
        """Visualize trajectories on a blank canvas"""
        
        if not self.tracks_history:
            logger.warning("No tracks to visualize")
            return
        
        fig, ax = plt.subplots(figsize=(14, 10))
        
        canvas = np.ones((self.height, self.width, 3), dtype=np.uint8) * 255
        
        track_ids = sorted(self.tracks_history.keys())[:sample_size]
        
        for idx, track_id in enumerate(track_ids):
            trajectory = self.tracks_history[track_id]
            positions = np.array([t['center'] for t in trajectory], dtype=np.int32)
            
            color_val = int(255 * (idx / max(len(track_ids), 1)))
            color = (color_val, 100, 255 - color_val)
            
            if len(positions) > 1:
                # Clamp to canvas bounds
                positions[:, 0] = np.clip(positions[:, 0], 0, self.width - 1)
                positions[:, 1] = np.clip(positions[:, 1], 0, self.height - 1)
                cv2.polylines(canvas, [positions], False, color, 2)
            
            if len(positions) > 0:
                cv2.circle(canvas, tuple(positions[0]), 5, (0, 255, 0), -1)
                cv2.circle(canvas, tuple(positions[-1]), 5, (0, 0, 255), -1)
        
        canvas_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        ax.imshow(canvas_rgb)
        ax.set_title(f'Trajectories of {len(track_ids)} Tracked Humans')
        ax.axis('off')
        
        plt.tight_layout()
        fig.savefig(self.output_dir / 'trajectories_visualization.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info("Trajectories visualization saved")

print("âœ“ MultiHumanTrackingPipeline class FIXED with comprehensive error handling!")

# ===== From cell_08.py =====
class MOTMetrics:
    """Multi-Object Tracking Metrics"""
    
    @staticmethod
    def bbox_iou(box1: np.ndarray, box2: np.ndarray) -> float:
        """Calculate IoU between two boxes [x1, y1, x2, y2]"""
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
    
    @staticmethod
    def compute_metrics_from_trajectories(
        pred_trajectories: Dict,
        iou_threshold: float = 0.5
    ) -> Dict:
        """
        Compute basic tracking metrics from predicted trajectories
        """
        
        metrics = {
            'total_tracks': len(pred_trajectories),
            'total_track_points': sum(len(v) for v in pred_trajectories.values()),
            'avg_track_length': 0,
            'track_continuity_score': 0
        }
        
        if pred_trajectories:
            lengths = [len(v) for v in pred_trajectories.values()]
            metrics['avg_track_length'] = np.mean(lengths)
            
            continuities = []
            for track_id, trajectory in pred_trajectories.items():
                if len(trajectory) > 1:
                    frame_ids = [t['frame_id'] for t in trajectory]
                    expected_frames = frame_ids[-1] - frame_ids[0] + 1
                    continuity = len(trajectory) / expected_frames if expected_frames > 0 else 0
                    continuities.append(continuity)
            
            if continuities:
                metrics['track_continuity_score'] = np.mean(continuities)
        
        return metrics

print("MOTMetrics class defined!")

