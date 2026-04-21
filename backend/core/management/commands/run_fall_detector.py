import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.fall_detection import FallDetector
from core.fall_incident import record_fall_incident
from core.models import Device


class Command(BaseCommand):
    help = (
        'Run YOLO pose + LSTM fall detection on a webcam and record Incident rows '
        '(zone from Device.zone, type=FALL, severity=CRITICAL).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--device-id',
            type=str,
            required=True,
            help='Registered Device.device_id for this camera (must exist in DB).',
        )
        parser.add_argument(
            '--camera',
            type=int,
            default=0,
            help='OpenCV camera index (default 0).',
        )
        parser.add_argument(
            '--cooldown',
            type=float,
            default=60.0,
            help='Minimum seconds between fall records for this run (default 60).',
        )
        parser.add_argument(
            '--display',
            action='store_true',
            help='Show OpenCV preview window.',
        )
        parser.add_argument(
            '--opencv-backend',
            type=str,
            choices=['auto', 'msmf', 'dshow'],
            default='auto',
            help='Camera backend on Windows (default: auto fallback).',
        )

    def _open_capture(self, cv2, camera_index: int, backend: str):
        backend_map = {
            'msmf': ('MSMF', cv2.CAP_MSMF),
            'dshow': ('DSHOW', cv2.CAP_DSHOW),
        }
        if backend in backend_map:
            name, api = backend_map[backend]
            cap = cv2.VideoCapture(camera_index, api)
            return cap, name

        # Auto mode: try DirectShow first on Windows, then MSMF, then default.
        candidates = [
            ('DSHOW', cv2.CAP_DSHOW),
            ('MSMF', cv2.CAP_MSMF),
            ('DEFAULT', None),
        ]
        for name, api in candidates:
            cap = cv2.VideoCapture(camera_index) if api is None else cv2.VideoCapture(camera_index, api)
            if cap.isOpened():
                return cap, name
            cap.release()
        return cv2.VideoCapture(camera_index), 'DEFAULT'

    def _configure_capture(self, cv2, cap, backend_name: str, frame_w: int, frame_h: int):
        # These hints improve stability on many Windows webcams.
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_h)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if backend_name in {'DSHOW', 'DEFAULT'}:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

    def _warmup_capture(self, cap, warmup_frames: int = 20):
        # First frames can be black/garbled while the camera stream stabilizes.
        for _ in range(warmup_frames):
            ok, _frame = cap.read()
            if not ok:
                break
            time.sleep(0.01)

    def handle(self, *args, **options):
        device_id = options['device_id']
        if not Device.objects.filter(device_id=device_id).exists():
            raise CommandError(f'No Device with device_id={device_id!r}')

        try:
            import cv2
        except ImportError as e:
            raise CommandError('opencv-python is required. pip install opencv-python') from e

        try:
            detector = FallDetector()
        except Exception as e:
            raise CommandError(f'Failed to load fall models: {e}') from e

        cap, backend_name = self._open_capture(cv2, options['camera'], options['opencv_backend'])
        if not cap.isOpened():
            raise CommandError(f'Could not open camera index {options["camera"]}')
        self._configure_capture(cv2, cap, backend_name, detector.frame_w, detector.frame_h)
        self._warmup_capture(cap)

        cooldown = max(0.0, options['cooldown'])
        last_fall_at = 0.0
        self.stdout.write(
            self.style.SUCCESS(
                f'Fall detector running for device_id={device_id!r}. Press q in the window to quit.'
                if options['display']
                else f'Fall detector running for device_id={device_id!r}. Ctrl+C to stop.'
            )
        )
        self.stdout.write(f'Camera source={options["camera"]} backend={backend_name}')

        try:
            while cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    raise CommandError(
                        'Camera opened but frame read failed. Try: '
                        '--opencv-backend dshow or a different --camera index.'
                    )
                if frame is None or frame.size == 0:
                    continue
                display = frame.copy()
                detector.push_frame(frame)
                pred_result = detector.predict_if_ready()
                if pred_result is not None:
                    pred, conf = pred_result
                    if detector.is_fall(pred):
                        now = time.monotonic()
                        if now - last_fall_at >= cooldown:
                            record_fall_incident(device_id)
                            last_fall_at = now
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Fall recorded at {timezone.now().isoformat()} '
                                    f'(confidence={conf:.2f})'
                                )
                            )
                        label = f'FALL ({conf:.2f})'
                        color = (0, 0, 255)
                    else:
                        label = f'OK ({conf:.2f})'
                        color = (0, 255, 0)
                    if options['display']:
                        cv2.putText(
                            display,
                            label,
                            (30, 40),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.0,
                            color,
                            2,
                        )

                if options['display']:
                    cv2.imshow('Fall detection', display)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
        finally:
            cap.release()
            if options['display']:
                cv2.destroyAllWindows()
