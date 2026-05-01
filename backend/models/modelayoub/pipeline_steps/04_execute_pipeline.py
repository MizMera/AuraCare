# Auto-generated from notebook code cells, grouped by pipeline step.

# ===== From cell_11.py =====
def main():
    """Execute complete tracking pipeline"""
    
    # Create pipeline
    pipeline = MultiHumanTrackingPipeline(
        detector_path=detector_model,
        video_path=video_file,
        output_dir=OUTPUT_DIR,
        device=DEVICE,
        conf_threshold=CONF_THRESHOLD,
        max_track_age=TRACKER_MAX_AGE,
        max_frames=MAX_FRAMES,
        show_live=SHOW_LIVE_FEED
    )
    
    # Process video
    logger.info("Starting video processing...")
    stats = pipeline.process_video(show_progress=SHOW_PROGRESS)
    
    logger.info("\n" + "=" * 70)
    logger.info("PROCESSING STATISTICS")
    logger.info("=" * 70)
    for key, value in stats.items():
        logger.info(f"{key:.<40} {value}")
    logger.info("=" * 70)
    
    # Export trajectories
    for fmt in EXPORT_FORMATS:
        try:
            export_file = pipeline.export_trajectories(format=fmt)
            logger.info(f"Exported to: {export_file}")
        except Exception as e:
            logger.error(f"Export failed ({fmt}): {e}")
    
    # Get detailed statistics
    detailed_stats = pipeline.get_statistics()
    
    if detailed_stats['track_statistics']:
        logger.info("\n" + "=" * 70)
        logger.info("TRAJECTORY STATISTICS")
        logger.info("=" * 70)
        logger.info(f"Total unique tracks: {detailed_stats['total_unique_tracks']}")
        logger.info(f"Total frames processed: {detailed_stats['total_frames_processed']}")
        
        track_lengths = [t['length'] for t in detailed_stats['track_statistics'].values()]
        track_distances = [t['total_distance'] for t in detailed_stats['track_statistics'].values()]
        
        logger.info(f"\nTrack Length Statistics:")
        logger.info(f"  Min: {min(track_lengths)} frames")
        logger.info(f"  Max: {max(track_lengths)} frames")
        logger.info(f"  Avg: {np.mean(track_lengths):.1f} frames")
        
        logger.info(f"\nDistance Statistics:")
        logger.info(f"  Min: {min(track_distances):.1f} pixels")
        logger.info(f"  Max: {max(track_distances):.1f} pixels")
        logger.info(f"  Avg: {np.mean(track_distances):.1f} pixels")
        logger.info("=" * 70)
    
    # Generate visualizations
    if GENERATE_VISUALIZATIONS:
        logger.info("Generating visualizations...")
        pipeline.visualize_statistics()
        pipeline.visualize_trajectories(sample_size=min(15, len(pipeline.tracks_history)))
    
    # Save summary report
    summary = {
        'timestamp': datetime.now().isoformat(),
        'configuration': {
            'detector_model': detector_model,
            'video_input': video_file,
            'device': str(DEVICE),
            'conf_threshold': CONF_THRESHOLD,
            'max_track_age': TRACKER_MAX_AGE
        },
        'processing_stats': stats,
        'trajectory_stats': detailed_stats,
        'output_files': {
            'video': str(OUTPUT_DIR / 'tracking_output.mp4'),
            'trajectories_json': str(OUTPUT_DIR / 'trajectories.json'),
            'trajectories_csv': str(OUTPUT_DIR / 'trajectories.csv'),
            'statistics_plot': str(OUTPUT_DIR / 'tracking_statistics.png'),
            'trajectories_plot': str(OUTPUT_DIR / 'trajectories_visualization.png')
        }
    }
    
    summary_file = OUTPUT_DIR / 'tracking_summary.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"\nSummary report saved to: {summary_file}")
    
    return summary, pipeline

# Execute pipeline
summary, pipeline = main()

