import json
import os
import signal
import subprocess
import sys
import threading
import time
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
]


def get_model_root() -> Path:
    return Path(settings.BASE_DIR) / 'models' / 'modelayoub'


def get_runner_path() -> Path:
    return get_model_root() / 'run_project_pipeline.py'


def get_output_dir() -> Path:
    return get_model_root() / 'tracking_results'


def get_log_dir() -> Path:
    return Path(settings.BASE_DIR) / 'logs'


def get_status_file() -> Path:
    return get_log_dir() / 'modelayoub_status.json'


def get_log_file() -> Path:
    return get_log_dir() / 'modelayoub_run.log'


def _ensure_paths() -> None:
    get_log_dir().mkdir(parents=True, exist_ok=True)
    get_output_dir().mkdir(parents=True, exist_ok=True)


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


def _build_launch_env(input_mode: str, video_input_path: str | None, webcam_index: int) -> dict[str, str]:
    env = os.environ.copy()
    mode = (input_mode or 'webcam').strip().lower()

    if mode == 'upload':
        if not video_input_path:
            raise ValueError('A video input path is required for upload mode.')
        if not Path(video_input_path).exists():
            raise FileNotFoundError(f'Uploaded video not found: {video_input_path}')
        env['WANDER_USE_WEBCAM'] = '0'
        env['WANDER_VIDEO_INPUT_PATH'] = str(video_input_path)
        env['WANDER_SHOW_LIVE_FEED'] = '0'
    else:
        env['WANDER_USE_WEBCAM'] = '1'
        env['WANDER_WEBCAM_INDEX'] = str(webcam_index)
        env['WANDER_SHOW_LIVE_FEED'] = '1'

    return env


def _write_status(payload: dict[str, Any]) -> None:
    _write_json(get_status_file(), payload)


def _stop_running_process(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except OSError:
        return False


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


def _load_trajectories() -> dict[str, Any]:
    trajectories = _read_json(get_output_dir() / 'trajectories.json', {})
    if not isinstance(trajectories, dict):
        return {}
    return trajectories


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
    summary = _read_json(output_dir / 'tracking_summary.json', {})
    wandering = _read_json(output_dir / 'wandering_risk_report.json', {})
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
    })

    pid = payload.get('pid')
    if payload.get('running') and not _pid_is_running(pid):
        payload['running'] = False
        payload['ended_at'] = payload.get('ended_at') or datetime.now().isoformat()
        if payload.get('message') == 'Modelayoub pipeline launched':
            payload['message'] = 'Completed'
        _write_status(payload)

    payload['log_tail'] = _read_log_tail()
    payload['artifacts'] = get_artifacts()
    return payload


def get_status() -> dict[str, Any]:
    with _PROCESS_LOCK:
        return _current_status()


def launch_pipeline(
    requested_by: str | None = None,
    input_mode: str = 'webcam',
    video_input_path: str | None = None,
    webcam_index: int = 0,
) -> dict[str, Any]:
    global _PROCESS

    _ensure_paths()
    runner = get_runner_path()
    if not runner.exists():
        raise FileNotFoundError(f'Model runner not found: {runner}')

    launch_env = _build_launch_env(input_mode, video_input_path, webcam_index)
    normalized_mode = (input_mode or 'webcam').strip().lower()

    with _PROCESS_LOCK:
        existing = _current_status()
        if existing.get('running') and _pid_is_running(existing.get('pid')):
            return existing

        log_handle = get_log_file().open('ab')
        command = [sys.executable, str(runner)]
        creationflags = 0
        if os.name == 'nt':
            creationflags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
            creationflags |= getattr(subprocess, 'DETACHED_PROCESS', 0)

        try:
            _PROCESS = subprocess.Popen(
                command,
                cwd=str(get_model_root()),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=launch_env,
                creationflags=creationflags,
            )
        finally:
            log_handle.close()

        payload = {
            'running': True,
            'pid': _PROCESS.pid,
            'requested_by': requested_by,
            'started_at': datetime.now().isoformat(),
            'ended_at': None,
            'message': 'Modelayoub pipeline launched',
            'input_mode': normalized_mode,
            'video_input_path': video_input_path,
            'webcam_index': webcam_index,
        }
        _write_status(payload)
        time.sleep(0.5)
        if _PROCESS.poll() is not None:
            failed_payload = {
                **payload,
                'running': False,
                'ended_at': datetime.now().isoformat(),
                'message': _extract_failure_message(_read_log_tail()),
            }
            _write_status(failed_payload)
            return _current_status()
        return _current_status()


def stop_pipeline(requested_by: str | None = None) -> dict[str, Any]:
    global _PROCESS

    with _PROCESS_LOCK:
        payload = _current_status()
        pid = payload.get('pid')
        running = bool(payload.get('running') and _pid_is_running(pid))

        if running:
            _stop_running_process(pid)
            if _PROCESS is not None:
                try:
                    _PROCESS.terminate()
                except Exception:
                    pass
                _PROCESS = None

        payload['running'] = False
        payload['ended_at'] = datetime.now().isoformat()
        payload['message'] = 'Modelayoub pipeline stopped' if running else 'Modelayoub pipeline already idle'
        if requested_by:
            payload['requested_by'] = requested_by
        _write_status(payload)
        return _current_status()