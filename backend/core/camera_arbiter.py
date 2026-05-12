import threading


class CameraArbiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._owner = None
        self._count = 0

    def acquire(self, owner):
        with self._lock:
            if self._owner in (None, owner):
                self._owner = owner
                self._count += 1
                return True, None
            return False, self._owner

    def release(self, owner):
        with self._lock:
            if self._owner != owner:
                return
            self._count = max(0, self._count - 1)
            if self._count == 0:
                self._owner = None

    def current_owner(self):
        with self._lock:
            return self._owner


camera_arbiter = CameraArbiter()
