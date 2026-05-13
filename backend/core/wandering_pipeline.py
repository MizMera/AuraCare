import json
import os
import signal
import subprocess
import sys
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings


_PROCESS_LOCK = threading.Lock()
_PROCESS = None

_ARTIFACT_FILES = [
    'tracking_output.mp4',
    'trajectories.json',
    'trajectories.csv',
    'track_details.csv',
    'tracking_summary.json',
    'wandering_risk_report.json',
    'tracking_statistics.png',
    'trajectories_visualization.png',
    'detection_heatmap.png',
    'latest_webcam_results.json',
    'latest_webcam_results.csv',
    'latest_webcam_summary.txt',
]


def get_repo_root() -> Path:
    return Path(settings.BASE_DIR).parent


def get_pipeline_root() -> Path:
    return get_repo_root() / 'readyforimplementation'


def get_runner_path() -> Path:
    return get_pipeline_root() / 'unified_pipeline.py'


def get_output_dir() -> Path:
    return get_pipeline_root() / 'pipeline_test_results'


def get_stop_request_path() -> Path:
    return get_output_dir() / 'wandering_stop_request.json'


def get_log_dir() -> Path:
    return Path(settings.BASE_DIR) / 'logs'


def get_status_file() -> Path:
    return get_log_dir() / 'wandering_status.json'


def get_log_file() -> Path:
    return get_log_dir() / 'wandering_run.log'


def _ensure_paths() -> None:
    get_log_dir().mkdir(parents=True, exist_ok=True)
    get_output_dir().mkdir(parents=True, exist_ok=True)


def _clear_stop_request() -> None:
    stop_request = get_stop_request_path()
    if stop_request.exists():
        stop_request.unlink()


def _write_stop_request(requested_by: str | None = None) -> None:
    payload = {
        'requested_at': datetime.now().isoformat(),
        'requested_by': requested_by,
        'reason': 'Stop requested from dashboard',
    }
    _write_json(get_stop_request_path(), payload)


def _pid_is_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def _write_status(payload: dict[str, Any]) -> None:
    _write_json(get_status_file(), payload)


def _read_log_tail(limit: int = 50) -> list[str]:
    log_file = get_log_file()
    if not log_file.exists():
        return []

    with log_file.open('r', encoding='utf-8', errors='replace') as handle:
        return list(deque((line.rstrip('\n') for line in handle), maxlen=limit))


def _extract_failure_message(log_tail: list[str]) -> str:
    for line in reversed(log_tail):
        text = line.strip()
        if not text or text == 'Traceback (most recent call last):':
            continue
        if text.startswith('File "'):
            continue
        return f'Pipeline failed to start: {text}'
    return 'Pipeline failed to start. Check the pipeline log for details.'


def _artifact_listing() -> list[dict[str, Any]]:
    output_dir = get_output_dir()
    items: list[dict[str, Any]] = []

    for name in _ARTIFACT_FILES:
        path = output_dir / name
        if not path.exists():
            continue
        items.append({
            'name': name,
            'path': str(path),
            'size_bytes': path.stat().st_size,
        })

    return items


def get_video_artifact_path() -> Path | None:
    preferred = get_output_dir() / 'tracking_output.mp4'
    if preferred.exists():
        return preferred

    captures = sorted(get_output_dir().glob('webcam_capture_*.mp4'), key=lambda path: path.stat().st_mtime, reverse=True)
    if captures:
        return captures[0]

    return None


def _load_trajectories() -> dict[str, Any]:
    trajectories = _read_json(get_output_dir() / 'trajectories.json', {})
    if not isinstance(trajectories, dict):
        return {}
    return trajectories


def _load_latest_results() -> list[dict[str, Any]]:
    results = _read_json(get_output_dir() / 'latest_webcam_results.json', [])
    if isinstance(results, list):
        return results
    return []


def _build_legacy_summary_from_latest_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_tracks = len(results)
    total_points = sum(int(row.get('num_points', 0) or 0) for row in results)

    return {
        'timestamp': datetime.now().isoformat(),
        'configuration': {
            'video_input': 'webcam',
        },
        'processing_stats': {
            'total_tracks': total_tracks,
            'unique_tracks': total_tracks,
            'frames_processed': total_points,
            'frames_with_detections': total_points,
            'avg_track_length': float(total_points / total_tracks) if total_tracks else 0.0,
        },
        'trajectory_stats': {
            'total_unique_tracks': total_tracks,
        },
        'output_files': {},
    }


def _build_legacy_risk_report_from_latest_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_tracks = len(results)
    high = sum(1 for row in results if row.get('final_risk') == 'high')
    medium = sum(1 for row in results if row.get('final_risk') == 'medium')
    low = sum(1 for row in results if row.get('final_risk') == 'low')

    return {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'total_tracks': total_tracks,
            'high_risk_tracks': high,
            'medium_risk_tracks': medium,
            'low_risk_tracks': low,
        },
        'tracks': [
            {
                'track_id': row.get('track_id'),
                'num_points': row.get('num_points'),
                'duration_s': row.get('duration_s'),
                'tortuosity': row.get('features', {}).get('tortuosity'),
                'turn_rate_per_min': row.get('features', {}).get('turn_rate_per_min'),
                'revisit_ratio': row.get('features', {}).get('revisit_ratio'),
                'idle_ratio': row.get('features', {}).get('idle_ratio'),
                'mean_speed_px_per_s': row.get('features', {}).get('mean_speed_px_per_s'),
                'speed_std_px_per_s': row.get('features', {}).get('speed_std_px_per_s'),
                'max_speed_px_per_s': row.get('features', {}).get('max_speed_px_per_s'),
                'risk_score': 100.0 if row.get('final_risk') == 'high' else 50.0 if row.get('final_risk') == 'medium' else 10.0,
                'risk_level': row.get('final_risk'),
            }
            for row in results
        ],
    }


def _sample_trajectories() -> list[dict[str, Any]]:
    trajectories = _load_trajectories()
    tracks = trajectories.get('tracks', {})
    sampled: list[dict[str, Any]] = []

    if not isinstance(tracks, dict):
        return sampled

    for track_id, points in list(tracks.items())[:5]:
        if not isinstance(points, list):
            continue
        sampled_points = []
        for point in points[:80]:
            center = point.get('center') or [None, None]
            sampled_points.append({
                'frame_id': point.get('frame_id'),
                'x': center[0],
                'y': center[1],
                'confidence': point.get('confidence'),
            })
        sampled.append({
            'track_id': track_id,
            'points': sampled_points,
        })

    return sampled


def get_artifacts() -> dict[str, Any]:
    output_dir = get_output_dir()
    results = _load_latest_results()
    summary = _read_json(output_dir / 'tracking_summary.json', {})
    if not summary and results:
        summary = _build_legacy_summary_from_latest_results(results)

    wandering = _read_json(output_dir / 'wandering_risk_report.json', {})
    if not wandering and results:
        wandering = _build_legacy_risk_report_from_latest_results(results)

    trajectories = _load_trajectories()

    return {
        'tracking_summary': summary,
        'wandering_risk_report': wandering,
        'trajectory_metadata': trajectories.get('metadata', {}),
        'sampled_trajectories': _sample_trajectories(),
        'report_files': _artifact_listing(),
    }


def _current_status() -> dict[str, Any]:
    payload = _read_json(get_status_file(), {
        'running': False,
        'pid': None,
        'requested_by': None,
        'started_at': None,
        'ended_at': None,
        'message': 'Idle',
        'input_mode': 'webcam',
        'video_input_path': None,
        'webcam_index': 0,
        'duration_seconds': 20,
    })

    pid = payload.get('pid')
    if payload.get('running') and not _pid_is_running(pid):
        payload['running'] = False
        payload['ended_at'] = payload.get('ended_at') or datetime.now().isoformat()
        if payload.get('message') == 'Wandering pipeline launched':
            payload['message'] = 'Completed'
        _write_status(payload)

    payload['log_tail'] = _read_log_tail()
    payload['artifacts'] = get_artifacts()
    return payload


def get_status() -> dict[str, Any]:
    with _PROCESS_LOCK:
        return _current_status()


def _build_command(input_mode: str, video_input_path: str | None, webcam_index: int, duration_seconds: int) -> list[str]:
    command = [
        sys.executable,
        str(get_runner_path()),
        '--duration',
        str(duration_seconds),
        '--no-display',
    ]

    mode = (input_mode or 'webcam').strip().lower()
    if mode == 'upload':
        if not video_input_path:
            raise ValueError('A video input path is required for upload mode.')
        if not Path(video_input_path).exists():
            raise FileNotFoundError(f'Uploaded video not found: {video_input_path}')
        command.extend(['--video-input-path', str(video_input_path)])
    else:
        command.extend(['--webcam-index', str(webcam_index)])

    return command


def launch_pipeline(
    requested_by: str | None = None,
    input_mode: str = 'webcam',
    video_input_path: str | None = None,
    webcam_index: int = 0,
    duration_seconds: int = 20,
) -> dict[str, Any]:
    global _PROCESS

    _ensure_paths()
    _clear_stop_request()
    runner = get_runner_path()
    if not runner.exists():
        raise FileNotFoundError(f'Unified pipeline not found: {runner}')

    with _PROCESS_LOCK:
        existing = _current_status()
        if existing.get('running') and _pid_is_running(existing.get('pid')):
            return existing

        command = _build_command(input_mode, video_input_path, webcam_index, duration_seconds)
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        log_handle = get_log_file().open('ab')

        try:
            _PROCESS = subprocess.Popen(
                command,
                cwd=str(get_pipeline_root()),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
                creationflags=creationflags,
            )
        except Exception:
            log_handle.close()
            raise
        else:
            log_handle.close()

        payload = {
            'running': True,
            'pid': _PROCESS.pid,
            'requested_by': requested_by,
            'started_at': datetime.now().isoformat(),
            'ended_at': None,
            'message': 'Wandering pipeline launched',
            'input_mode': input_mode,
            'video_input_path': video_input_path,
            'webcam_index': webcam_index,
            'duration_seconds': duration_seconds,
        }
        _write_status(payload)
        return _current_status()


def _stop_running_process(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        if os.name == 'nt':
            try:
                import subprocess as sp
                sp.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, timeout=5)
            except Exception:
                pass
        else:
            # Try SIGTERM first on POSIX systems.
            os.kill(pid, signal.SIGTERM)
        
        import time
        time.sleep(0.5)

        if _pid_is_running(pid):
            if os.name == 'nt':
                try:
                    import subprocess as sp
                    sp.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, timeout=5)
                except Exception:
                    pass
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
        
        return True
    except OSError:
        return False


def stop_pipeline(requested_by: str | None = None) -> dict[str, Any]:
    global _PROCESS
    import time

    with _PROCESS_LOCK:
        payload = _current_status()
        if payload.get('running'):
            _write_stop_request(requested_by=requested_by)
            payload['message'] = (
                f'Stop requested by {requested_by}; finalizing trajectory analysis'
                if requested_by
                else 'Stop requested; finalizing trajectory analysis'
            )
            payload['ended_at'] = None
            _write_status(payload)
            
            # Give the process a reasonable time to exit gracefully (10 seconds)
            if _PROCESS is not None:
                try:
                    _PROCESS.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Force kill if it didn't exit gracefully
                    _kill_process_tree(_PROCESS.pid)
                    try:
                        _PROCESS.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass  # Process still won't die, give up for now
        else:
            _clear_stop_request()

        _PROCESS = None
        return _current_status()