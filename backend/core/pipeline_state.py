import time

# Shared in-process state compatible with the second project's pipeline module.
state_store = {}
pipeline_running = False
pipeline_started_at = None
pipeline_last_heartbeat = None
active_camera_sources = set()


def touch_pipeline(source=None):
    global pipeline_running, pipeline_started_at, pipeline_last_heartbeat

    now = time.time()
    pipeline_running = True
    if pipeline_started_at is None:
        pipeline_started_at = now
    pipeline_last_heartbeat = now
    if source:
        active_camera_sources.add(str(source))
    return now


def update_resident_state(person_id, *, name=None, area=None, activity=None, last_seen=None, match_debug=None):
    entry = state_store.setdefault(str(person_id), {})
    if name is not None:
        entry['name'] = name
    if area is not None:
        entry['area'] = area
    if activity is not None:
        entry['activity'] = activity
    entry['last_seen'] = last_seen if last_seen is not None else time.time()
    if match_debug is not None:
        entry['match_debug'] = match_debug
    return entry


def remove_resident_state(*person_ids):
    """Evict one or more person_ids from the in-memory state_store."""
    for pid in person_ids:
        state_store.pop(str(pid), None)
