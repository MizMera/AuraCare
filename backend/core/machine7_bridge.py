from __future__ import annotations

import importlib
import os
import sys
import threading
import time
from pathlib import Path


_DEFAULT_MACHINE7_ROOT = Path(
    os.environ.get(
        'AURACARE_MACHINE7_ROOT',
        r'C:\Users\5anzour\Desktop\pi - Copy\elderly-care-monitoring-system',
    )
)

_runtime_modules = None
_runtime_error = None
_pipeline_thread = None
_pipeline_lock = threading.Lock()
_preview_frame_jpeg = None
_preview_lock = threading.Lock()
_stop_requested = False
_stop_lock = threading.Lock()


def machine7_bridge_enabled():
    explicit = os.environ.get('AURACARE_ENABLE_MACHINE7_BRIDGE')
    if explicit is not None:
        return explicit == '1'
    return 'test' not in sys.argv


def get_machine7_root():
    return _DEFAULT_MACHINE7_ROOT


def _normalise_source(source):
    if source is None:
        return None
    if isinstance(source, str):
        source = source.strip()
        if not source:
            return None
        if source.isdigit():
            return int(source)
        return source
    return source


def _load_runtime_modules():
    global _runtime_modules, _runtime_error

    if _runtime_modules is not None or _runtime_error is not None:
        return _runtime_modules

    if not machine7_bridge_enabled():
        _runtime_error = 'Machine7 bridge disabled.'
        return None

    root = get_machine7_root()
    if not root.exists():
        _runtime_error = f'Machine7 project not found at {root}'
        return None

    os.environ.setdefault('MACHINE7_DISABLE_AUTOPIPELINE', '1')

    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    try:
        _runtime_modules = {
            'config': importlib.import_module('config'),
            'state': importlib.import_module('machine7.dashboard.state'),
            'pipeline': importlib.import_module('machine7.pipeline'),
            'enrollment': importlib.import_module('machine7.enrollment.enroll'),
        }
        _runtime_error = None
    except Exception as exc:
        _runtime_error = f'{type(exc).__name__}: {exc}'
        _runtime_modules = None

    return _runtime_modules


def get_machine7_error():
    _load_runtime_modules()
    return _runtime_error


def get_machine7_state():
    runtime = _load_runtime_modules()
    if not runtime:
        return None
    return runtime['state']


def get_machine7_status():
    state = get_machine7_state()
    heartbeat = getattr(state, 'pipeline_last_heartbeat', None) if state else None
    active_sources = set(getattr(state, 'active_camera_sources', set()) or []) if state else set()
    thread_alive = bool(_pipeline_thread and _pipeline_thread.is_alive())
    healthy = bool(active_sources) or bool(
        state
        and getattr(state, 'pipeline_running', False)
        and heartbeat
        and (time.time() - float(heartbeat)) < 300.0
    )
    return {
        'available': bool(state),
        'healthy': healthy,
        'thread_alive': thread_alive,
        'state': state,
        'error': _runtime_error,
    }


def get_machine7_preview_jpeg():
    with _preview_lock:
        return _preview_frame_jpeg


def _configure_runtime_for_camera(camera, source_override=None):
    runtime = _load_runtime_modules()
    if not runtime:
        return None

    config = runtime['config']
    source = _normalise_source(source_override)
    if source is None:
        source = _normalise_source(getattr(camera, 'source', None)) if camera is not None else None
    if source is not None:
        config.CAMERA_SOURCE = source

    location = ''
    if camera is not None and getattr(camera, 'zone_id', None):
        location = camera.zone.name or ''

    if location:
        config.AREA_INFERENCE_MODE = 'camera'
        config.CAMERA_FIXED_AREA = location
        source_map = dict(getattr(config, 'CAMERA_SOURCE_AREA_MAP', {}) or {})
        source_key = source if source is not None else getattr(config, 'CAMERA_SOURCE', None)
        if source_key is not None:
            source_map[source_key] = location
            source_map[str(source_key)] = location
            config.CAMERA_SOURCE_AREA_MAP = source_map

    return config


def start_machine7_pipeline(camera=None, source_override=None):
    global _pipeline_thread, _stop_requested

    runtime = _load_runtime_modules()
    if not runtime:
        return {
            'started': False,
            'available': False,
            'already_running': False,
            'error': _runtime_error,
        }

    with _pipeline_lock:
        with _stop_lock:
            _stop_requested = False

        status = get_machine7_status()
        if status['healthy'] or status['thread_alive']:
            return {
                'started': True,
                'available': True,
                'already_running': True,
                'error': None,
            }

        _configure_runtime_for_camera(camera, source_override=source_override)

        # Enroll all Django residents into machine7 before starting, so only
        # residents from this project are recognised in the activity log.
        sync_all_django_residents_to_machine7()

        def _run_pipeline_runtime():
            # Mirror processed frames for web preview while optionally keeping the Python window.
            try:
                import cv2

                original_imshow = cv2.imshow
                original_waitkey = cv2.waitKey
                headless = os.environ.get('AURACARE_PIPELINE_HEADLESS') == '1'

                def _capture_preview(window_name, frame):
                    global _preview_frame_jpeg
                    try:
                        ok, encoded = cv2.imencode('.jpg', frame)
                        if ok:
                            with _preview_lock:
                                _preview_frame_jpeg = encoded.tobytes()
                    except Exception:
                        pass

                    if not headless:
                        try:
                            original_imshow(window_name, frame)
                        except Exception:
                            pass

                cv2.imshow = _capture_preview

                def _waitkey_with_stop(*args, **kwargs):
                    with _stop_lock:
                        if _stop_requested:
                            return ord('q')
                    if headless:
                        return -1
                    try:
                        return original_waitkey(*args, **kwargs)
                    except Exception:
                        return -1

                cv2.waitKey = _waitkey_with_stop

                if headless:
                    cv2.destroyAllWindows = lambda *args, **kwargs: None
                    cv2.namedWindow = lambda *args, **kwargs: None
            except Exception:
                pass

            runtime['pipeline'].run_monitoring_system()

        _pipeline_thread = threading.Thread(
            target=_run_pipeline_runtime,
            daemon=True,
            name='machine7-pipeline-bridge',
        )
        _pipeline_thread.start()

    for _ in range(10):
        time.sleep(0.5)
        status = get_machine7_status()
        if status['healthy']:
            return {
                'started': True,
                'available': True,
                'already_running': False,
                'error': None,
            }
        if not (_pipeline_thread and _pipeline_thread.is_alive()):
            return {
                'started': False,
                'available': True,
                'already_running': False,
                'error': 'Machine7 pipeline stopped immediately. Close the browser camera preview or any other app using the webcam, then try again.',
            }

    return {
        'started': bool(_pipeline_thread and _pipeline_thread.is_alive()),
        'available': True,
        'already_running': False,
        'error': None if _pipeline_thread and _pipeline_thread.is_alive() else 'Machine7 pipeline did not stay active.',
    }


def stop_machine7_pipeline(timeout_seconds=5.0):
    global _stop_requested, _preview_frame_jpeg

    with _stop_lock:
        _stop_requested = True

    with _preview_lock:
        _preview_frame_jpeg = None

    thread = _pipeline_thread
    if thread and thread.is_alive():
        thread.join(timeout=max(0.0, float(timeout_seconds)))

    return {
        'stopped': not (thread and thread.is_alive()),
        'thread_alive': bool(thread and thread.is_alive()),
    }


def sync_machine7_resident_enrollment(resident):
    runtime = _load_runtime_modules()
    if not runtime:
        return {'synced': False, 'error': _runtime_error}

    person_id = getattr(resident, 'resident_id', None) or getattr(resident, 'id', None)
    if person_id is None:
        return {'synced': False, 'error': 'Resident has no stable id.'}

    try:
        import cv2
        import numpy as np
    except Exception as exc:
        return {'synced': False, 'error': f'{type(exc).__name__}: {exc}'}

    decoded_images = []
    for enrollment_image in resident.enrollment_images.order_by('created_at')[:5]:
        image_field = getattr(enrollment_image, 'image', None)
        if not image_field:
            continue
        try:
            with image_field.open('rb') as handle:
                payload = handle.read()
            image_array = np.frombuffer(payload, dtype=np.uint8)
            frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            if frame is not None and getattr(frame, 'size', 0) > 0:
                decoded_images.append(frame)
        except Exception:
            continue

    if not decoded_images:
        return {'synced': False, 'error': 'No decodable enrollment images were found.'}

    state = runtime['state']
    enroll_fn = getattr(state, 'enroll_images_fn', None)
    if enroll_fn is None:
        manager = runtime['enrollment'].EnrollmentManager()
        enroll_fn = manager.enroll_from_images

    result = enroll_fn(resident.name, decoded_images, person_id=int(person_id))
    if not result:
        return {'synced': False, 'error': 'Second-project enrollment failed.'}

    return {'synced': True, 'result': result}


def sync_all_django_residents_to_machine7():
    """Enroll every Django resident that has enrollment photos into machine7.
    Called automatically when the pipeline starts so that only residents from
    THIS project are used for face recognition in the activity log."""
    runtime = _load_runtime_modules()
    if not runtime:
        return {'synced': 0, 'skipped': 0, 'error': _runtime_error}

    try:
        import django
        from django.apps import apps
        Resident = apps.get_model('core', 'Resident')
    except Exception as exc:
        return {'synced': 0, 'skipped': 0, 'error': str(exc)}

    residents = Resident.objects.prefetch_related('enrollment_images').all()
    valid_ids = {int(r.id) for r in residents}
    valid_names = {int(r.id): (r.name or '').strip().lower() for r in residents}

    # First remove stale/mismatched entries from machine7 enrollment storage.
    try:
        manager = runtime['enrollment'].EnrollmentManager()
        for entry in manager.list_residents():
            try:
                person_id = int(entry.get('person_id'))
            except Exception:
                continue
            entry_name = (entry.get('name') or '').strip().lower()
            if person_id not in valid_ids or valid_names.get(person_id) != entry_name:
                manager.delete_resident(person_id)
    except Exception:
        # Best-effort cleanup: keep pipeline startup resilient.
        pass

    synced, skipped = 0, 0
    for resident in residents:
        if not resident.enrollment_images.exists():
            skipped += 1
            continue
        result = sync_machine7_resident_enrollment(resident)
        if result.get('synced'):
            synced += 1
        else:
            skipped += 1
    return {'synced': synced, 'skipped': skipped, 'error': None}


def update_machine7_resident_name(person_id, name):
    runtime = _load_runtime_modules()
    if not runtime or person_id is None:
        return False

    state = runtime['state']
    update_fn = getattr(state, 'update_resident_fn', None)
    if update_fn is None:
        update_fn = runtime['enrollment'].EnrollmentManager().update_resident_name
    return bool(update_fn(int(person_id), name))


def delete_machine7_resident(person_id):
    runtime = _load_runtime_modules()
    if not runtime or person_id is None:
        return False

    state = runtime['state']
    delete_fn = getattr(state, 'delete_resident_fn', None)
    if delete_fn is None:
        delete_fn = runtime['enrollment'].EnrollmentManager().delete_resident
    return bool(delete_fn(int(person_id)))