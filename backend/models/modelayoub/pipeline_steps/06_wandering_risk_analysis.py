# CV-only wandering risk analysis from extracted trajectories.

import math
import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

if globals().get("OUTPUT_DIR") is None:
    OUTPUT_DIR = Path(__file__).resolve().parents[1] / "tracking_results"

if globals().get("logger") is None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _compute_track_features(track_id, trajectory, fps):
    positions = np.array([entry["center"] for entry in trajectory], dtype=np.float32)
    frame_ids = np.array([entry["frame_id"] for entry in trajectory], dtype=np.float32)
    confidences = np.array([entry.get("confidence", 0.0) for entry in trajectory], dtype=np.float32)

    if len(positions) < 2:
        return {
            "track_id": track_id,
            "num_points": len(positions),
            "duration_s": 0.0,
            "avg_confidence": _safe_float(np.mean(confidences) if len(confidences) else 0.0),
            "total_distance_px": 0.0,
            "mean_speed_px_per_s": 0.0,
            "speed_std_px_per_s": 0.0,
            "max_speed_px_per_s": 0.0,
            "displacement_px": 0.0,
            "tortuosity": 1.0,
            "turn_rate_per_min": 0.0,
            "revisit_ratio": 0.0,
            "idle_ratio": 1.0,
        }

    deltas = np.diff(positions, axis=0)
    step_dist = np.linalg.norm(deltas, axis=1)

    frame_dt = np.diff(frame_ids)
    frame_dt[frame_dt <= 0] = 1.0
    time_dt = frame_dt / max(fps, 1e-6)
    speeds = step_dist / np.maximum(time_dt, 1e-6)

    total_distance = float(np.sum(step_dist))
    displacement = float(np.linalg.norm(positions[-1] - positions[0]))
    duration_s = float(max(frame_ids[-1] - frame_ids[0], 1.0) / max(fps, 1e-6))

    # Tortuosity >1 means less direct movement (more wandering-like motion patterns).
    tortuosity = total_distance / max(displacement, 1.0)

    headings = np.arctan2(deltas[:, 1], deltas[:, 0])
    heading_diff = np.diff(headings)
    heading_diff = np.arctan2(np.sin(heading_diff), np.cos(heading_diff))
    turn_events = np.sum(np.abs(heading_diff) > (math.pi / 4.0))
    turn_rate_per_min = float((turn_events / max(duration_s, 1e-6)) * 60.0)

    # Grid revisit ratio captures repeated traversals of the same area.
    cell_size = 32.0
    grid_cells = np.floor(positions / cell_size).astype(np.int32)
    unique_cells = len({(int(c[0]), int(c[1])) for c in grid_cells})
    revisit_ratio = float(1.0 - (unique_cells / max(len(grid_cells), 1)))

    speed_thresh = 15.0
    idle_ratio = float(np.mean(speeds < speed_thresh)) if len(speeds) else 1.0

    return {
        "track_id": track_id,
        "num_points": int(len(positions)),
        "duration_s": duration_s,
        "avg_confidence": _safe_float(np.mean(confidences)),
        "total_distance_px": total_distance,
        "mean_speed_px_per_s": _safe_float(np.mean(speeds)),
        "speed_std_px_per_s": _safe_float(np.std(speeds)),
        "max_speed_px_per_s": _safe_float(np.max(speeds)),
        "displacement_px": displacement,
        "tortuosity": float(tortuosity),
        "turn_rate_per_min": turn_rate_per_min,
        "revisit_ratio": revisit_ratio,
        "idle_ratio": idle_ratio,
    }


def _wandering_risk_score(features):
    # Weighted interpretable score in [0, 100].
    norm_tortuosity = min(max((features["tortuosity"] - 1.0) / 5.0, 0.0), 1.0)
    norm_turn_rate = min(features["turn_rate_per_min"] / 80.0, 1.0)
    norm_revisit = min(max(features["revisit_ratio"], 0.0), 1.0)
    norm_duration = min(features["duration_s"] / (5.0 * 60.0), 1.0)
    norm_speed_var = min(features["speed_std_px_per_s"] / 120.0, 1.0)

    score = (
        0.30 * norm_tortuosity
        + 0.20 * norm_turn_rate
        + 0.20 * norm_revisit
        + 0.15 * norm_duration
        + 0.15 * norm_speed_var
    ) * 100.0

    if score >= 65.0:
        level = "high"
    elif score >= 35.0:
        level = "medium"
    else:
        level = "low"

    return float(score), level


def run_wandering_risk_analysis():
    trajectories_file = OUTPUT_DIR / "trajectories.json"
    print("\n" + "=" * 70)
    print("WANDERING RISK ANALYSIS")
    print("=" * 70)
    print(f"Input trajectories file: {trajectories_file}")

    if not trajectories_file.exists():
        logger.warning("No trajectories.json found; skipping wandering risk analysis.")
        print("No trajectories file found. Nothing to analyze.")
        print("=" * 70)
        return

    with open(trajectories_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    fps = _safe_float(data.get("metadata", {}).get("fps", 30.0), 30.0)
    tracks = data.get("tracks", {}) or {}

    rows = []
    for track_id, trajectory in tracks.items():
        if not trajectory:
            continue
        features = _compute_track_features(track_id, trajectory, fps)
        score, level = _wandering_risk_score(features)
        features["risk_score"] = score
        features["risk_level"] = level
        rows.append(features)

    if not rows:
        csv_path = OUTPUT_DIR / "wandering_risk_tracks.csv"
        json_path = OUTPUT_DIR / "wandering_risk_report.json"
        pd.DataFrame(columns=[
            "track_id", "num_points", "duration_s", "avg_confidence", "total_distance_px",
            "mean_speed_px_per_s", "speed_std_px_per_s", "max_speed_px_per_s", "displacement_px",
            "tortuosity", "turn_rate_per_min", "revisit_ratio", "idle_ratio", "risk_score", "risk_level"
        ]).to_csv(csv_path, index=False)

        empty_report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_tracks": 0,
                "high_risk_tracks": 0,
                "medium_risk_tracks": 0,
                "low_risk_tracks": 0,
                "note": "No valid tracks available for analysis.",
            },
            "tracks": [],
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(empty_report, f, indent=2)
        logger.info(f"Wandering risk report written: {json_path}")
        print("No valid tracks were found in trajectories. Generated empty risk outputs.")
        print(f"Saved: {csv_path}")
        print(f"Saved: {json_path}")
        print("=" * 70)
        return

    df_risk = pd.DataFrame(rows).sort_values("risk_score", ascending=False)

    high_count = int((df_risk["risk_level"] == "high").sum())
    med_count = int((df_risk["risk_level"] == "medium").sum())
    low_count = int((df_risk["risk_level"] == "low").sum())

    summary = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_tracks": int(len(df_risk)),
            "high_risk_tracks": high_count,
            "medium_risk_tracks": med_count,
            "low_risk_tracks": low_count,
            "thresholds": {
                "low": "score < 35",
                "medium": "35 <= score < 65",
                "high": "score >= 65",
            },
        },
        "tracks": df_risk.to_dict(orient="records"),
    }

    csv_path = OUTPUT_DIR / "wandering_risk_tracks.csv"
    json_path = OUTPUT_DIR / "wandering_risk_report.json"

    df_risk.to_csv(csv_path, index=False)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Total tracks analyzed: {len(df_risk)}")
    print(f"High risk: {high_count} | Medium risk: {med_count} | Low risk: {low_count}")
    print("Top tracks by risk score:")
    for _, row in df_risk.head(5).iterrows():
        print(
            f"  Track {row['track_id']}: score={row['risk_score']:.1f} "
            f"level={row['risk_level']} duration={row['duration_s']:.1f}s "
            f"tortuosity={row['tortuosity']:.2f}"
        )
    print(f"Saved: {csv_path}")
    print(f"Saved: {json_path}")
    print("=" * 70)


run_wandering_risk_analysis()
