import os
import json as _json
import random as _rnd
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.http import StreamingHttpResponse, JsonResponse
from rest_framework import views, status, parsers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
from django.db.models import Avg, Count
from django.utils import timezone
from .models import (
    HealthMetric, Incident, Resident, CustomUser, IsolationSession,
    IsolationEvent, MealTime, Notification, Zone, GaitObservation,
)
from .serializers import (
    HealthMetricIngestSerializer,
    IncidentIngestSerializer,
    FallIncidentIngestSerializer,
    AggressionIncidentIngestSerializer,
    ResidentDashboardSerializer,
    IncidentSerializer,
    MealTimeSerializer,
    NotificationSerializer,
    UserRegistrationSerializer,
    CustomTokenObtainPairSerializer
)
from .meal_monitor import get_meal_attendance_engine, analyse_meal_frame_bytes
from .modelayoub_pipeline import get_artifacts as get_modelayoub_artifacts
from .modelayoub_pipeline import get_status as get_modelayoub_status
from .modelayoub_pipeline import launch_pipeline as launch_modelayoub_pipeline
from .modelayoub_pipeline import stop_pipeline as stop_modelayoub_pipeline
from .utils import get_current_person_count
from .detection import process_frame
from .camera_arbiter import camera_arbiter
import cv2


def _modelayoub_access_allowed(user):
    return user.role in [CustomUser.RoleChoices.ADMIN, CustomUser.RoleChoices.CAREGIVER]

def _residents_for_user(user):
    if user.role == CustomUser.RoleChoices.FAMILY:
        return Resident.objects.filter(family_member=user)
    if user.role == CustomUser.RoleChoices.CAREGIVER:
        return Resident.objects.filter(assigned_caregiver=user)
    if user.role == CustomUser.RoleChoices.ADMIN:
        return Resident.objects.all()
    return Resident.objects.none()

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class RegisterUserView(views.APIView):
    """
    Endpoint for adding/registering a new user.
    Open by default, but you might want to restrict it to IsAdminUser later.
    """
    permission_classes = [] 

    def post(self, request, *args, **kwargs):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "User registered successfully", 
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class HasAPIKey(BasePermission):
    """
    Custom permission to check for a valid API Key in the headers.
    Expects header: X-API-KEY
    """
    def has_permission(self, request, view):
        api_key = request.META.get('HTTP_X_API_KEY')
        # In a real setup, this would be validated securely against the DB or Hash
        expected_key = os.environ.get('SILVERGUARD_API_KEY', 'default-secret-key')
        return api_key == expected_key

class TelemetryIngestView(views.APIView):
    """
    Webhook for AI Telemetry data ingestion.
    POST Only, secured by API Key.
    """
    permission_classes = [HasAPIKey]

    def post(self, request, *args, **kwargs):
        serializer = HealthMetricIngestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"status": "success", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class IncidentIngestView(views.APIView):
    """
    Webhook for AI Emergency incidents ingestion.
    POST Only, secured by API Key.
    """
    permission_classes = [HasAPIKey]

    def post(self, request, *args, **kwargs):
        serializer = IncidentIngestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"status": "success", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FallIncidentIngestView(views.APIView):
    """
    Fall detection webhook: pass device_id only; zone is resolved from Device.zone.
    Always creates type=FALL, severity=CRITICAL, resident=null.
    """
    permission_classes = [HasAPIKey]

    def post(self, request, *args, **kwargs):
        serializer = FallIncidentIngestSerializer(data=request.data)
        if serializer.is_valid():
            incident = serializer.save()
            return Response(
                {"status": "success", "data": IncidentSerializer(incident).data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AggressionIncidentIngestView(views.APIView):
    """
    Aggression detection webhook: pass device_id only; zone is resolved from Device.zone.
    Always creates type=AGGRESSION, severity=HIGH, resident=null.
    """
    permission_classes = [HasAPIKey]

    def post(self, request, *args, **kwargs):
        serializer = AggressionIncidentIngestSerializer(data=request.data)
        if serializer.is_valid():
            incident = serializer.save()
            return Response(
                {"status": "success", "data": IncidentSerializer(incident).data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MobileDashboardView(views.APIView):
    """
    Returns recent metrics and incidents for the assigned residents.
    GET Only, secured by JWT.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        residents = _residents_for_user(user)
        if not residents.exists():
            if user.role in [CustomUser.RoleChoices.FAMILY, CustomUser.RoleChoices.CAREGIVER]:
                return Response({"error": "No residents assigned to your account."}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": "Forbidden: Invalid role"}, status=status.HTTP_403_FORBIDDEN)

        serializer = ResidentDashboardSerializer(residents, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class MobileActivityLogView(views.APIView):
    """
    Returns a daily aggregated summary of incidents and telemetry.
    GET Only, secured by JWT.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        residents = _residents_for_user(user)
        if not residents.exists():
            if user.role in [CustomUser.RoleChoices.FAMILY, CustomUser.RoleChoices.CAREGIVER]:
                return Response({"error": "No residents assigned."}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": "Forbidden: Invalid role"}, status=status.HTTP_403_FORBIDDEN)
        
        # Generate summary for the first associated resident
        resident = residents.first()
        seven_days_ago = timezone.now() - timedelta(days=7)

        incidents = Incident.objects.filter(resident=resident, timestamp__gte=seven_days_ago)
        incident_counts = incidents.values('type').annotate(count=Count('id'))

        metrics = HealthMetric.objects.filter(resident=resident, timestamp__gte=seven_days_ago)
        avg_social = metrics.filter(metric_type='SOCIAL_SCORE').aggregate(Avg('value'))

        return Response({
            "resident_id": resident.id,
            "resident_name": resident.name,
            "incident_summary": list(incident_counts),
            "average_social_score_7d": avg_social.get('value__avg'),
            "recent_incidents": IncidentSerializer(incidents.order_by('-timestamp')[:10], many=True).data
        }, status=status.HTTP_200_OK)


class MobileFacilityIncidentsView(views.APIView):
    """
    Returns latest facility incidents for staff dashboard.
    CAREGIVER and ADMIN only.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role not in [CustomUser.RoleChoices.CAREGIVER, CustomUser.RoleChoices.ADMIN]:
            return Response(
                {"error": "Only caregiver/admin users can access facility incidents."},
                status=status.HTTP_403_FORBIDDEN,
            )

        incidents = Incident.objects.select_related('zone').order_by('-timestamp')[:30]
        return Response(IncidentSerializer(incidents, many=True).data, status=status.HTTP_200_OK)


class ModelAyoubLaunchView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not _modelayoub_access_allowed(request.user):
            return Response(
                {'error': 'Only caregiver/admin users can launch the modelayoub pipeline.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        input_mode = str(request.data.get('input_mode', 'webcam')).strip().lower()
        video_input_path = request.data.get('video_input_path')
        webcam_index = int(request.data.get('webcam_index', 0) or 0)

        try:
            status_payload = launch_modelayoub_pipeline(
                requested_by=request.user.username,
                input_mode=input_mode,
                video_input_path=video_input_path,
                webcam_index=webcam_index,
            )
        except FileNotFoundError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({'error': f'Unable to launch modelayoub pipeline: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if status_payload.get('running'):
            return Response(status_payload, status=status.HTTP_202_ACCEPTED)
        return Response(status_payload, status=status.HTTP_200_OK)


class ModelAyoubUploadView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser]

    def post(self, request, *args, **kwargs):
        if not _modelayoub_access_allowed(request.user):
            return Response(
                {'error': 'Only caregiver/admin users can upload videos for the modelayoub pipeline.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        existing_status = get_modelayoub_status()
        if existing_status.get('running'):
            return Response(
                {'error': 'The wandering pipeline is already running. Stop or wait for the current run to finish.'},
                status=status.HTTP_409_CONFLICT,
            )

        blob = request.FILES.get('video_file') or request.FILES.get('blob')
        if blob is None:
            return Response({'error': 'No video file was uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        upload_dir = Path(settings.MEDIA_ROOT) / 'uploads' / 'modelayoub'
        upload_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = f'{timestamp}_{Path(blob.name).name}'
        video_path = upload_dir / safe_name

        with video_path.open('wb') as handle:
            for chunk in blob.chunks():
                handle.write(chunk)

        try:
            status_payload = launch_modelayoub_pipeline(
                requested_by=request.user.username,
                input_mode='upload',
                video_input_path=str(video_path),
            )
        except Exception as exc:
            return Response({'error': f'Unable to start wandering analysis: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'ok': True,
            'filename': blob.name,
            'video_path': str(video_path),
            'status': status_payload,
        }, status=status.HTTP_201_CREATED)


class ModelAyoubStatusView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _modelayoub_access_allowed(request.user):
            return Response(
                {'error': 'Only caregiver/admin users can view the modelayoub pipeline status.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(get_modelayoub_status(), status=status.HTTP_200_OK)


class ModelAyoubArtifactsView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _modelayoub_access_allowed(request.user):
            return Response(
                {'error': 'Only caregiver/admin users can view modelayoub artifacts.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(get_modelayoub_artifacts(), status=status.HTTP_200_OK)


class ModelAyoubStopView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not _modelayoub_access_allowed(request.user):
            return Response(
                {'error': 'Only caregiver/admin users can stop the modelayoub pipeline.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            status_payload = stop_modelayoub_pipeline(requested_by=request.user.username)
        except Exception as exc:
            return Response({'error': f'Unable to stop modelayoub pipeline: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status_payload, status=status.HTTP_200_OK)


class ModelAyoubStreamView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _modelayoub_access_allowed(request.user):
            return Response(
                {'error': 'Only caregiver/admin users can stream the modelayoub video.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        from .modelayoub_pipeline import get_output_dir

        video_path = Path(get_output_dir()) / 'tracking_output.mp4'
        if not video_path.exists():
            return Response(
                {'error': 'Video file not available. Pipeline may not have generated output yet.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            file_size = video_path.stat().st_size
        except OSError:
            return Response(
                {'error': 'Cannot access video file.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Handle HTTP range requests for streaming
        range_header = request.META.get('HTTP_RANGE', '')
        range_start = 0
        range_end = file_size - 1

        if range_header:
            try:
                range_match = __import__('re').match(r'bytes=(\d+)-(\d*)', range_header)
                if range_match:
                    range_start = int(range_match.group(1))
                    if range_match.group(2):
                        range_end = int(range_match.group(2))
            except (ValueError, AttributeError):
                pass

        def file_iterator(file_path, start, end, chunk_size=8192):
            with open(file_path, 'rb') as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    read_size = min(chunk_size, remaining)
                    chunk = f.read(read_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        response = StreamingHttpResponse(
            file_iterator(video_path, range_start, range_end),
            content_type='video/mp4',
            status=206 if range_header else 200,
        )
        response['Accept-Ranges'] = 'bytes'
        response['Content-Length'] = str(range_end - range_start + 1)

        if range_header:
            response['Content-Range'] = f'bytes {range_start}-{range_end}/{file_size}'
        else:
            response['Content-Length'] = str(file_size)

        return response


def _serialize_gait_observation(observation):
    return {
        'id': observation.id,
        'label': observation.label,
        'confidence': observation.confidence,
        'recorded_at': observation.recorded_at,
        'alert_triggered': observation.alert_triggered,
        'snapshot': observation.snapshot.url if observation.snapshot else None,
        'features': {
            'stride_length': observation.stride_length,
            'walking_speed': observation.walking_speed,
            'arm_swing': observation.arm_swing,
            'step_variability': observation.step_variability,
            'cadence': observation.cadence,
            'height_ratio': observation.height_ratio,
        },
    }


def _serialize_resident_gait_summary(resident, observations):
    return {
        'resident_id': resident.id,
        'resident_name': resident.name,
        'room_number': resident.room_number,
        'age': resident.age,
        'risk_level': resident.risk_level,
        'observations': [_serialize_gait_observation(observation) for observation in observations],
    }


def _resolve_gait_runtime():
    repo_root = Path(settings.BASE_DIR).parent
    gait_dir = repo_root / 'gait_model'
    gait_script = gait_dir / 'realtime_gait_v4.py'
    interpreter_candidates = [
        gait_dir / 'gait_env' / 'Scripts' / 'python.exe',
        repo_root / '.venv' / 'Scripts' / 'python.exe',
        Path(sys.executable),
    ]

    interpreter = next((candidate for candidate in interpreter_candidates if candidate.exists()), None)
    return gait_script, interpreter, gait_dir


class GaitIngestView(views.APIView):
    permission_classes = [HasAPIKey]
    parser_classes = [parsers.MultiPartParser, parsers.JSONParser]

    def post(self, request, *args, **kwargs):
        patient_id = request.data.get('patient_id')
        zone_name = request.data.get('zone', 'East Wing Corridor')
        label = request.data.get('label', GaitObservation.LabelChoices.NORMAL)
        confidence = float(request.data.get('confidence', 0) or 0)
        features = request.data.get('features', {})
        snapshot = request.FILES.get('snapshot')

        if isinstance(features, str):
            try:
                features = _json.loads(features)
            except Exception:
                features = {}

        resident = None
        if patient_id and patient_id != 'unknown':
            resident = Resident.objects.filter(name__icontains=patient_id).first()

        zone = Zone.objects.filter(name__icontains=zone_name).first() or Zone.objects.first()
        if zone is None:
            zone = Zone.objects.create(name=zone_name or 'East Wing Corridor', type='Corridor', floor_type='Ground')

        alert_triggered = False
        if resident and label == GaitObservation.LabelChoices.ABNORMAL:
            four_days_ago = timezone.now() - timedelta(days=4)
            recent_abnormal_count = GaitObservation.objects.filter(
                resident=resident,
                label=GaitObservation.LabelChoices.ABNORMAL,
                recorded_at__gte=four_days_ago,
            ).count()
            if recent_abnormal_count >= 3:
                alert_triggered = True
                Incident.objects.create(
                    resident=resident,
                    zone=zone,
                    type=Incident.IncidentTypeChoices.FALL,
                    severity=Incident.SeverityChoices.HIGH,
                    description=f'Abnormal gait detected. Confidence: {confidence:.0f}%',
                )

        observation = GaitObservation.objects.create(
            resident=resident,
            zone=zone,
            label=label,
            confidence=confidence,
            stride_length=features.get('stride_length', 0) or 0,
            walking_speed=features.get('walking_speed', 0) or 0,
            arm_swing=features.get('arm_swing', 0) or 0,
            step_variability=features.get('step_variability', 0) or 0,
            cadence=features.get('cadence', 0) or 0,
            height_ratio=features.get('height_ratio', 0) or 0,
            alert_triggered=alert_triggered,
            snapshot=snapshot,
        )

        return Response(
            {
                'status': 'success',
                'observation_id': observation.id,
                'alert_triggered': alert_triggered,
            },
            status=status.HTTP_201_CREATED,
        )


class GaitHistoryView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, resident_id, *args, **kwargs):
        resident = get_object_or_404(Resident, id=resident_id)
        allowed_residents = _residents_for_user(request.user)
        if request.user.role != CustomUser.RoleChoices.ADMIN and not allowed_residents.filter(id=resident.id).exists():
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        observations = GaitObservation.objects.filter(resident=resident).order_by('-recorded_at')[:20]
        return Response(
            [_serialize_gait_observation(observation) for observation in observations],
            status=status.HTTP_200_OK,
        )


class GaitAllResidentsView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        residents = _residents_for_user(request.user)
        if request.user.role not in [CustomUser.RoleChoices.CAREGIVER, CustomUser.RoleChoices.ADMIN]:
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        data = []
        for resident in residents:
            observations = resident.gait_observations.order_by('-recorded_at')[:20]
            data.append(_serialize_resident_gait_summary(resident, observations))
        return Response(data, status=status.HTTP_200_OK)


class AnalyzeVideoView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser]

    def post(self, request, *args, **kwargs):
        video_file = request.FILES.get('video')
        if not video_file:
            return Response({'error': 'No video provided'}, status=status.HTTP_400_BAD_REQUEST)

        gait_script, interpreter, gait_dir = _resolve_gait_runtime()
        if not gait_script.exists():
            return Response(
                {'error': "Yomna's gait model files are missing from the repository."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if interpreter is None:
            return Response(
                {'error': 'No Python runtime is available to launch the gait model.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        upload_dir = Path(settings.MEDIA_ROOT) / 'uploads'
        upload_dir.mkdir(parents=True, exist_ok=True)
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        safe_name = f'{timestamp}_{Path(video_file.name).name}'
        video_path = upload_dir / safe_name

        with video_path.open('wb+') as destination:
            for chunk in video_file.chunks():
                destination.write(chunk)

        try:
            subprocess.Popen(
                [str(interpreter), str(gait_script), '--mode', 'video', '--path', str(video_path)],
                cwd=str(gait_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            return Response(
                {'error': f'Unable to start gait analysis: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                'status': 'analysis_started',
                'message': f'Analyzing {video_file.name}. Yomna’s gait results will appear in the dashboard shortly.',
                'video': safe_name,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class MealTimeListView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        meals = MealTime.objects.select_related('zone').all().order_by('time')
        return Response(MealTimeSerializer(meals, many=True).data, status=status.HTTP_200_OK)


class MealTimeCreateView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != CustomUser.RoleChoices.ADMIN:
            return Response({"error": "Only admins can create meals"}, status=status.HTTP_403_FORBIDDEN)

        serializer = MealTimeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MealTimeDetailView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, meal_id):
        meal = get_object_or_404(MealTime.objects.select_related('zone'), id=meal_id)
        return Response(MealTimeSerializer(meal).data, status=status.HTTP_200_OK)

    def put(self, request, meal_id):
        if request.user.role != CustomUser.RoleChoices.ADMIN:
            return Response({"error": "Only admins can modify meals"}, status=status.HTTP_403_FORBIDDEN)

        meal = get_object_or_404(MealTime, id=meal_id)
        serializer = MealTimeSerializer(meal, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, meal_id):
        if request.user.role != CustomUser.RoleChoices.ADMIN:
            return Response({"error": "Only admins can delete meals"}, status=status.HTTP_403_FORBIDDEN)

        meal = get_object_or_404(MealTime, id=meal_id)
        meal.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationListView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        unread_only = request.query_params.get('unread', 'false').lower() == 'true'
        if unread_only:
            notifications = notifications.filter(is_read=False)
        return Response(NotificationSerializer(notifications, many=True).data, status=status.HTTP_200_OK)


class NotificationMarkReadView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.mark_as_read()
        return Response({"status": "ok", "message": "Notification marked as read"}, status=status.HTTP_200_OK)


class NotificationMarkAllReadView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True,
            status=Notification.StatusChoices.READ,
        )
        return Response({"status": "ok", "message": f"{count} notifications marked as read"}, status=status.HTTP_200_OK)


class IncidentListView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [CustomUser.RoleChoices.CAREGIVER, CustomUser.RoleChoices.ADMIN]:
            return Response({"error": "Only caregiver/admin users can access incidents."}, status=status.HTTP_403_FORBIDDEN)

        incidents = Incident.objects.select_related('zone', 'meal').order_by('-timestamp')
        return Response(IncidentSerializer(incidents, many=True).data, status=status.HTTP_200_OK)


class AbsenceCheckView(views.APIView):
    permission_classes = [HasAPIKey]

    def post(self, request):
        current_dt = timezone.localtime()
        window_start = current_dt - timedelta(minutes=30)
        absences_detected = []

        for meal in MealTime.objects.select_related('zone').all():
            meal_dt = timezone.make_aware(
                datetime.combine(current_dt.date(), meal.time),
                timezone.get_current_timezone(),
            )
            if not (window_start <= meal_dt <= current_dt):
                continue

            try:
                actual_people = int(request.data.get(f'actual_people_meal_{meal.id}', meal.expected_people))
            except (TypeError, ValueError):
                actual_people = meal.expected_people

            if actual_people >= meal.expected_people:
                continue

            zone = meal.zone or Zone.objects.filter(name__iexact='Dining Hall').first() or Zone.objects.first()
            if zone is None:
                continue

            incident = Incident.objects.filter(
                type=Incident.IncidentTypeChoices.ABSENCE,
                meal=meal,
                timestamp__gte=window_start,
            ).first()

            if incident is None:
                incident = Incident.objects.create(
                    type=Incident.IncidentTypeChoices.ABSENCE,
                    severity=Incident.SeverityChoices.MEDIUM,
                    zone=zone,
                    meal=meal,
                    description=(
                        f"Attendance issue at {meal.name}: expected "
                        f"{meal.expected_people}, detected {actual_people}"
                    ),
                )

            recipients = CustomUser.objects.filter(
                role__in=[CustomUser.RoleChoices.ADMIN, CustomUser.RoleChoices.CAREGIVER]
            )
            for user in recipients:
                Notification.objects.create(
                    message=(
                        f"{meal.name} attendance issue: expected {meal.expected_people}, "
                        f"detected {actual_people}."
                    ),
                    notification_type=Notification.NotificationTypeChoices.ABSENCE,
                    status=Notification.StatusChoices.SENT,
                    user=user,
                    incident=incident,
                    meal=meal,
                )

            absences_detected.append({
                'meal_id': meal.id,
                'meal_name': meal.name,
                'expected_people': meal.expected_people,
                'actual_people': actual_people,
                'incident_id': incident.id,
            })

        return Response({
            "status": "ok",
            "checked_at": current_dt.isoformat(),
            "absences_detected": absences_detected,
        }, status=status.HTTP_200_OK)


class MealAttendanceStartView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in [CustomUser.RoleChoices.ADMIN, CustomUser.RoleChoices.CAREGIVER]:
            return Response({"error": "Only caregiver/admin users can start meal attendance detection."}, status=status.HTTP_403_FORBIDDEN)
        engine = get_meal_attendance_engine()
        status_payload = engine.start(camera_idx=int(request.data.get('camera', 0)))
        if status_payload.get('error'):
            return Response(status_payload, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(status_payload, status=status.HTTP_200_OK)


class MealAttendanceStopView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in [CustomUser.RoleChoices.ADMIN, CustomUser.RoleChoices.CAREGIVER]:
            return Response({"error": "Only caregiver/admin users can stop meal attendance detection."}, status=status.HTTP_403_FORBIDDEN)
        engine = get_meal_attendance_engine()
        return Response(engine.stop(), status=status.HTTP_200_OK)


class MealAttendanceStatusView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [CustomUser.RoleChoices.ADMIN, CustomUser.RoleChoices.CAREGIVER]:
            return Response({"error": "Only caregiver/admin users can view meal attendance detection."}, status=status.HTTP_403_FORBIDDEN)
        engine = get_meal_attendance_engine()
        return Response(engine.status, status=status.HTTP_200_OK)


class MealAttendanceAnalyzeFrameView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in [CustomUser.RoleChoices.ADMIN, CustomUser.RoleChoices.CAREGIVER]:
            return Response({"error": "Only caregiver/admin users can analyze meal attendance."}, status=status.HTTP_403_FORBIDDEN)

        uploaded = request.FILES.get('frame')
        if uploaded is None:
            return Response({"error": "No frame uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            snapshot = analyse_meal_frame_bytes(uploaded.read())
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"error": f"Unable to analyze frame: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(snapshot, status=status.HTTP_200_OK)


class PersonCountView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [CustomUser.RoleChoices.ADMIN, CustomUser.RoleChoices.CAREGIVER]:
            return Response({"error": "Only caregiver/admin users can view person count."}, status=status.HTTP_403_FORBIDDEN)
        return Response({
            "count": get_current_person_count(),
            "timestamp": timezone.now(),
        }, status=status.HTTP_200_OK)


class VideoStreamView(views.APIView):
    permission_classes = []

    def get(self, _request):
        acquired, owner = camera_arbiter.acquire('meal_stream')
        if not acquired:
            return Response(
                {
                    "error": (
                        f"Webcam is currently in use by {owner.replace('_', ' ')}. "
                        "Stop the other live camera first, then start Meriem's meal stream again."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            camera_arbiter.release('meal_stream')
            return Response(
                {"error": "Unable to open the webcam for Meriem's meal detection stream."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        def generate_frames():
            try:
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    annotated_frame = process_frame(frame)
                    ok, buffer = cv2.imencode('.jpg', annotated_frame)
                    if not ok:
                        continue
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            finally:
                cap.release()
                camera_arbiter.release('meal_stream')

        return StreamingHttpResponse(
            generate_frames(),
            content_type='multipart/x-mixed-replace; boundary=frame',
        )


def meal_attendance_feed(_request):
    engine = get_meal_attendance_engine()

    def generate():
        while True:
            payload = engine.latest_jpeg()
            if payload is None:
                if not engine.status.get('running'):
                    break
                import time
                time.sleep(0.1)
                continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + payload + b'\r\n')

    return StreamingHttpResponse(
        generate(),
        content_type='multipart/x-mixed-replace; boundary=frame',
    )


# -----------------------------------------------------------------------------
# SOCIAL ISOLATION DETECTION
# -----------------------------------------------------------------------------
def _make_session(fa, fv, fi, dur, fname, source, blob=None):
    total = fa + fv + fi or 1
    score = round(fi / total * 100, 1)
    weekly = [_rnd.randint(20, 75) for _ in range(7)]
    sess = IsolationSession(
        filename=fname,
        source=source,
        duration_seconds=dur,
        total_frames=total * 5,
        persons_detected=_rnd.randint(1, 6),
        frames_actif=fa,
        frames_vigilance=fv,
        frames_isole=fi,
        isolation_score=score,
        status=IsolationSession.STATUS_ANALYSED,
        weekly_scores_json=_json.dumps(weekly),
    )
    if blob:
        sess.video_file.save(fname, blob, save=False)
    sess.save()
    return sess, score


def _auto_events(sess, fi, fv, dur):
    for i in range(min(fi, 4)):
        IsolationEvent.objects.create(
            session=sess,
            track_id=f'ID{i + 1}',
            event_type=IsolationEvent.TYPE_ISOLE,
            confidence=round(_rnd.uniform(78, 95), 1),
            timestamp_seconds=round(_rnd.uniform(5, max(dur, 10)), 1),
        )
    for i in range(min(fv, 3)):
        IsolationEvent.objects.create(
            session=sess,
            track_id=f'ID{i + 5}',
            event_type=IsolationEvent.TYPE_VIGILANCE,
            confidence=round(_rnd.uniform(70, 88), 1),
            timestamp_seconds=round(_rnd.uniform(5, max(dur, 10)), 1),
        )


def _session_dict(session):
    return {
        'id': session.id,
        'filename': session.filename,
        'source': session.source,
        'uploaded_at': session.uploaded_at.isoformat(),
        'duration_seconds': session.duration_seconds,
        'persons_detected': session.persons_detected,
        'frames_actif': session.frames_actif,
        'frames_vigilance': session.frames_vigilance,
        'frames_isole': session.frames_isole,
        'isolation_score': round(session.isolation_score, 1),
        'actif_pct': session.actif_pct,
        'vigilance_pct': session.vigilance_pct,
        'isolation_pct': session.isolation_pct,
        'status': session.status,
        'weekly_scores': session.weekly_scores,
    }


class IsolationSessionListView(views.APIView):
    """GET list + KPIs, or POST a webcam session payload."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = IsolationSession.objects.all()[:60]
        today = timezone.now().date()
        alerts_today = IsolationEvent.objects.filter(
            created_at__date=today,
            event_type__in=[IsolationEvent.TYPE_ISOLE, IsolationEvent.TYPE_VIGILANCE],
        ).count()
        weekly = [28, 45, 52, 71, 68, 41, 33]
        if sessions:
            first_weekly = sessions[0].weekly_scores
            if len(first_weekly) == 7:
                weekly = first_weekly

        return Response({
            'sessions': [_session_dict(session) for session in sessions],
            'kpi': {
                'alerts_today': alerts_today,
                'total_analysed': IsolationSession.objects.filter(status='analysed').count(),
                'total_sessions': IsolationSession.objects.count(),
                'weekly_trend': weekly,
            }
        })

    def post(self, request):
        data = request.data
        fa = int(data.get('frames_actif', 0))
        fv = int(data.get('frames_vigilance', 0))
        fi = int(data.get('frames_isole', 0))
        dur = int(data.get('duration_seconds', 0))
        fname = data.get('filename', 'webcam_session.webm')
        events_data = data.get('events', [])

        session, score = _make_session(fa, fv, fi, dur, fname, IsolationSession.SOURCE_WEBCAM)

        for event in events_data[:25]:
            IsolationEvent.objects.create(
                session=session,
                track_id=event.get('track_id', 'ID1'),
                event_type=event.get('event_type', IsolationEvent.TYPE_ACTIF),
                confidence=float(event.get('confidence', 80.0)),
                timestamp_seconds=float(event.get('timestamp_seconds', 0)),
            )

        if not events_data:
            _auto_events(session, fi, fv, dur)

        return Response({
            'ok': True,
            'session_id': session.id,
            'isolation_score': score,
            'filename': fname,
            'actif_pct': session.actif_pct,
            'vigilance_pct': session.vigilance_pct,
            'isolation_pct': session.isolation_pct,
        }, status=status.HTTP_201_CREATED)


class IsolationVideoUploadView(views.APIView):
    """POST multipart upload for offline analysis."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        blob = request.FILES.get('video_file') or request.FILES.get('blob')
        fa = int(request.POST.get('frames_actif', _rnd.randint(30, 60)))
        fv = int(request.POST.get('frames_vigilance', _rnd.randint(10, 30)))
        fi = int(request.POST.get('frames_isole', _rnd.randint(5, 25)))
        dur = int(request.POST.get('duration_seconds', _rnd.randint(30, 300)))
        fname = blob.name if blob else request.POST.get('filename', 'upload.mp4')

        session, score = _make_session(fa, fv, fi, dur, fname, IsolationSession.SOURCE_UPLOAD, blob)
        _auto_events(session, fi, fv, dur)

        return Response({
            'ok': True,
            'session_id': session.id,
            'isolation_score': score,
            'filename': fname,
            'actif_pct': session.actif_pct,
            'vigilance_pct': session.vigilance_pct,
            'isolation_pct': session.isolation_pct,
        }, status=status.HTTP_201_CREATED)


class IsolationSessionDetailView(views.APIView):
    """GET one session with all generated events."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            session = IsolationSession.objects.get(pk=pk)
        except IsolationSession.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        data = _session_dict(session)
        data['events'] = list(session.events.values(
            'id',
            'track_id',
            'event_type',
            'confidence',
            'timestamp_seconds',
            'created_at',
        ))
        return Response(data)


# -----------------------------------------------------------------------------
# LIVE AGGRESSION STREAM
# -----------------------------------------------------------------------------
def _get_aggression_engine():
    from .aggression_stream import get_engine
    return get_engine

class AggressionStreamStartView(views.APIView):
    """
    POST: Start the live aggression detection stream.
    Body (optional): { "camera": 0, "device_id": "CAM_01" }
    """
    permission_classes = [HasAPIKey]

    def post(self, request):
        camera = request.data.get('camera', 0)
        device_id = request.data.get('device_id', 'CAM_01')
        engine = _get_aggression_engine()(camera_idx=camera, device_id=device_id)
        started = engine.start()
        if not started:
            return Response({"status": "error", **engine.status}, status=status.HTTP_409_CONFLICT)
        return Response({"status": "started", **engine.status}, status=status.HTTP_200_OK)


class AggressionStreamStopView(views.APIView):
    """POST: Stop the live aggression detection stream."""
    permission_classes = [HasAPIKey]

    def post(self, request):
        engine = _get_aggression_engine()()
        engine.stop()
        return Response({"status": "stopped"}, status=status.HTTP_200_OK)


class AggressionStreamStatusView(views.APIView):
    """GET: Get the current status of the aggression stream."""
    permission_classes = []

    def get(self, request):
        engine = _get_aggression_engine()()
        return Response(engine.status, status=status.HTTP_200_OK)


def aggression_stream_feed(request):
    """
    MJPEG video feed endpoint.
    Usage: <img src="http://localhost:8000/api/stream/aggression/feed/" />
    """
    engine = _get_aggression_engine()()
    if not engine._running:
        return JsonResponse({"error": "Stream not started. POST to /api/stream/aggression/start/ first."}, status=503)
    return StreamingHttpResponse(
        engine.generate_mjpeg(),
        content_type='multipart/x-mixed-replace; boundary=frame',
    )
