# Auto-generated from notebook code cells, grouped by pipeline step.

# ===== From cell_12.py =====
print("\n" + "=" * 70)
print("GENERATED OUTPUT FILES")
print("=" * 70)

output_files = sorted(OUTPUT_DIR.glob('*'))
for f in output_files:
    if f.is_file():
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"Ã¢Å“â€œ {f.name} ({size_mb:.2f} MB)")

print("=" * 70)

# ===== From cell_13.py =====
trajectories_file = OUTPUT_DIR / 'trajectories.json'

tracking_data = None
if trajectories_file.exists():
    with open(trajectories_file, 'r') as f:
        tracking_data = json.load(f)
    
    print("\nTracking Results Summary:")
    print(f"Total Tracks: {tracking_data['metadata']['total_tracks']}")
    print(f"Total Frames: {tracking_data['metadata']['total_frames']}")
    print(f"FPS: {tracking_data['metadata']['fps']}")
    print(f"Resolution: {tracking_data['metadata']['width']}x{tracking_data['metadata']['height']}")
    print(f"Timestamp: {tracking_data['metadata']['timestamp']}")
    
    # Analyze first few tracks
    print("\nSample Track Data (first 3 tracks):")
    for i, (track_id, trajectory) in enumerate(list(tracking_data['tracks'].items())[:3]):
        print(f"\n  Track ID: {track_id}")
        print(f"  Length: {len(trajectory)} frames")
        print(f"  Start: Frame {trajectory[0]['frame_id']}")
        print(f"  End: Frame {trajectory[-1]['frame_id']}")
        print(f"  Avg Confidence: {np.mean([t['confidence'] for t in trajectory]):.3f}")

# ===== From cell_14.py =====
from IPython.display import Image, display

# Display statistics plot
stats_plot = OUTPUT_DIR / 'tracking_statistics.png'
if stats_plot.exists():
    print("Tracking Statistics Visualization:")
    display(Image(str(stats_plot)))

# Display trajectories plot
traj_plot = OUTPUT_DIR / 'trajectories_visualization.png'
if traj_plot.exists():
    print("\nTrajectories Visualization:")
    display(Image(str(traj_plot)))

# ===== From cell_15.py =====
if tracking_data and tracking_data['metadata']['width'] > 0:
    heatmap = np.zeros((tracking_data['metadata']['height'], tracking_data['metadata']['width']))
    
    for track_id, trajectory in tracking_data['tracks'].items():
        for entry in trajectory:
            cx, cy = int(entry['center'][0]), int(entry['center'][1])
            if 0 <= cy < heatmap.shape[0] and 0 <= cx < heatmap.shape[1]:
                heatmap[cy, cx] += 1

    # Smooth and normalize sparse webcam trajectories for clearer visualization.
    heatmap_smooth = cv2.GaussianBlur(heatmap.astype(np.float32), (0, 0), sigmaX=6, sigmaY=6)
    non_zero = heatmap_smooth[heatmap_smooth > 0]
    if non_zero.size > 0:
        vmax = float(np.percentile(non_zero, 99))
        if vmax <= 0:
            vmax = float(np.max(heatmap_smooth)) if np.max(heatmap_smooth) > 0 else 1.0
    else:
        vmax = 1.0
    
    fig, ax = plt.subplots(figsize=(14, 10))
    im = ax.imshow(heatmap_smooth, cmap='hot', origin='upper', vmin=0, vmax=vmax)
    ax.set_title('Human Presence Heatmap')
    ax.set_xlabel('X (pixels)')
    ax.set_ylabel('Y (pixels)')
    plt.colorbar(im, ax=ax, label='Detection Density (smoothed)')
    
    heatmap_file = OUTPUT_DIR / 'detection_heatmap.png'
    plt.savefig(heatmap_file, dpi=150, bbox_inches='tight')
    plt.show()
    
    logger.info(f"Heatmap saved to: {heatmap_file}")
    logger.info(f"Heatmap non-zero points: {int(np.count_nonzero(heatmap))}")

# ===== From cell_16.py =====
if tracking_data:
    tracks_data = []
    
    for track_id, trajectory in tracking_data['tracks'].items():
        positions = np.array([t['center'] for t in trajectory])
        distances = np.linalg.norm(np.diff(positions, axis=0), axis=1) if len(positions) > 1 else []
        
        track_info = {
            'Track ID': track_id,
            'Length (frames)': len(trajectory),
            'Duration (s)': (trajectory[-1]['frame_id'] - trajectory[0]['frame_id']) / tracking_data['metadata']['fps'],
            'Total Distance (px)': np.sum(distances),
            'Avg Velocity (px/f)': np.mean(distances) if len(distances) > 0 else 0,
            'Avg Confidence': np.mean([t['confidence'] for t in trajectory]),
            'Start Frame': trajectory[0]['frame_id'],
            'End Frame': trajectory[-1]['frame_id']
        }
        tracks_data.append(track_info)
    
    df_tracks = pd.DataFrame(tracks_data)
    
    print("\nTrack Statistics Summary:")
    print(df_tracks.to_string())
    
    # Save to CSV
    stats_csv = OUTPUT_DIR / 'track_details.csv'
    df_tracks.to_csv(stats_csv, index=False)
    print(f"\nDetailed statistics saved to: {stats_csv}")

# ===== From cell_17.py =====
print("\n" + "=" * 70)
print("MULTI-HUMAN TRACKING PIPELINE - COMPLETE!")
print("=" * 70)
print(f"\nÃ¢Å“â€œ All results saved to: {OUTPUT_DIR}")
print("\nGenerated Files:")
print("  - tracking_output.mp4 (annotated video)")
print("  - trajectories.json (detailed trajectories)")
print("  - trajectories.csv (trajectories in CSV format)")
print("  - tracking_statistics.png (statistical plots)")
print("  - trajectories_visualization.png (visual trajectories)")
print("  - detection_heatmap.png (detection density)")
print("  - tracking_summary.json (summary report)")
print("  - track_details.csv (detailed track info)")
print("\n" + "=" * 70)
print("SYSTEM READY FOR VIDEO ANALYSIS!")
print("=" * 70)

