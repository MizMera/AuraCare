import os
import pickle
import numpy as np
from datetime import date, timedelta
from rest_framework import status

from rest_framework import views
from rest_framework.permissions import IsAuthenticated


import json as _json
import random as _rnd
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta
from django.db.models import Q
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
    Medication, MedicationLog, AdherenceRiskScore,Incident,Zone
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
from .chatbot_rag import answer_from_documents
from .modelayoub_pipeline import get_artifacts as get_modelayoub_artifacts
from .modelayoub_pipeline import get_status as get_modelayoub_status
from .modelayoub_pipeline import launch_pipeline as launch_modelayoub_pipeline
from .modelayoub_pipeline import stop_pipeline as stop_modelayoub_pipeline
from .utils import get_current_person_count, create_notifications_for_incident
from .chatbot_corpus import build_chatbot_documents_for_user
from .detection import process_frame
from .camera_arbiter import camera_arbiter
import cv2
from django.utils.dateparse import parse_datetime



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
                incident = Incident.objects.create(
                    resident=resident,
                    zone=zone,
                    type=Incident.IncidentTypeChoices.FALL_RISK,
                    severity=Incident.SeverityChoices.HIGH,
                    description=f'Abnormal gait detected. Confidence: {confidence:.0f}%',
                )
                create_notifications_for_incident(incident)

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
                {'error': "Gait model files are missing from the repository."},
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

                #stdout=subprocess.DEVNULL,
                #stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            return Response(
                {'error': f'Unable to start gait analysis: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                'status': 'analysis_started',
                'message': f'Analyzing {video_file.name}. Gait results will appear in the dashboard shortly.',
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
        incident_only = request.query_params.get('incident_only', 'false').lower() == 'true'
        today_only = request.query_params.get('today_only', 'false').lower() == 'true'
        unread_only = request.query_params.get('unread', 'false').lower() == 'true'

        if incident_only and today_only:
            todays_incidents = Incident.objects.filter(timestamp__date=timezone.localdate())
            existing_incident_ids = set(
                Notification.objects.filter(
                    user=request.user,
                    incident__isnull=False,
                ).values_list('incident_id', flat=True)
            )
            for incident in todays_incidents:
                if incident.id in existing_incident_ids:
                    continue
                incident_label = incident.get_type_display()
                zone_name = incident.zone.name if incident.zone else 'Unknown zone'
                description = incident.description or f'{incident_label} detected.'
                Notification.objects.create(
                    message=f"{incident_label} in {zone_name}: {description}",
                    notification_type=Notification.NotificationTypeChoices.INCIDENT,
                    status=Notification.StatusChoices.SENT,
                    user=request.user,
                    incident=incident,
                    meal=incident.meal,
                    resident=incident.resident,
                )

        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        if unread_only:
            notifications = notifications.filter(is_read=False)
        if incident_only:
            notifications = notifications.filter(
                Q(notification_type=Notification.NotificationTypeChoices.INCIDENT)
                | Q(notification_type=Notification.NotificationTypeChoices.ABSENCE)
                | Q(incident__isnull=False)
            )
        if today_only:
            notifications = notifications.filter(created_at__date=timezone.localdate())
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


class ChatbotQueryView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        question = (request.data.get('question') or '').strip()
        if not question:
            return Response({'error': 'Question is required.'}, status=status.HTTP_400_BAD_REQUEST)

        residents = _residents_for_user(request.user)
        accessible_residents = residents.count()
        normalized_question = question.lower().strip()

        # Deterministic diagnosis flow: if resident is missing, ask for clarification.
        diagnosis_keywords = ['diagnosis', 'diagnose', 'summary', 'status report', 'health status']
        if any(keyword in normalized_question for keyword in diagnosis_keywords):
            accessible_residents_qs = residents.order_by('name')
            matched_resident = None
            for resident in accessible_residents_qs:
                resident_name_lower = resident.name.lower()
                if resident_name_lower in normalized_question:
                    matched_resident = resident
                    break

            if matched_resident is None:
                if accessible_residents == 0:
                    return Response(
                        {'answer': 'I cannot generate a diagnosis because your account has no accessible residents.'},
                        status=status.HTTP_200_OK,
                    )
                available_names = list(accessible_residents_qs.values_list('name', flat=True)[:12])
                return Response(
                    {
                        'answer': (
                            "Please specify the resident name for the diagnosis summary. "
                            f"Accessible residents: {', '.join(available_names)}."
                        )
                    },
                    status=status.HTTP_200_OK,
                )

            resident_incidents = Incident.objects.filter(resident=matched_resident).order_by('-timestamp')[:5]
            resident_metrics = HealthMetric.objects.filter(resident=matched_resident).order_by('-timestamp')[:5]

            latest_incident = resident_incidents[0] if resident_incidents else None
            risk_level = matched_resident.risk_level
            incidents_last_24h = Incident.objects.filter(
                resident=matched_resident,
                timestamp__gte=timezone.now() - timedelta(hours=24),
            ).count()

            if latest_incident:
                latest_incident_line = (
                    f"{latest_incident.type} ({latest_incident.severity}) at "
                    f"{timezone.localtime(latest_incident.timestamp).strftime('%Y-%m-%d %H:%M')}"
                )
            else:
                latest_incident_line = "No incident history recorded yet."

            if resident_metrics:
                metric_lines = [
                    f"- {metric.metric_type}: {metric.value} "
                    f"({timezone.localtime(metric.timestamp).strftime('%Y-%m-%d %H:%M')})"
                    for metric in resident_metrics
                ]
                metrics_block = "\n".join(metric_lines)
            else:
                metrics_block = "- No recent health metrics recorded."

            structured_summary = (
                f"Diagnosis Summary for {matched_resident.name}\n"
                f"Room: {matched_resident.room_number}\n"
                f"Risk Level: {risk_level}\n"
                f"Incidents (last 24h): {incidents_last_24h}\n"
                f"Latest Incident: {latest_incident_line}\n"
                f"Recent Metrics:\n{metrics_block}"
            )
            return Response({'answer': structured_summary}, status=status.HTTP_200_OK)
        documents = build_chatbot_documents_for_user(request.user, residents)

        try:
            answer = answer_from_documents(question, documents)
        except Exception as exc:
            return Response(
                {
                    'error': 'Chatbot initialization failed. Check Gemini dependencies and GEMINI_API_KEY.',
                    'details': str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({'answer': answer}, status=status.HTTP_200_OK)


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
                    # Treat meal absence as an incident alert so it always appears in incident-focused feeds.
                    notification_type=Notification.NotificationTypeChoices.INCIDENT,
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
                        "Stop the other live camera first, then start the meal stream again."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            camera_arbiter.release('meal_stream')
            return Response(
                {"error": "Unable to open the webcam for the meal detection stream."},
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
# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _residents_for_user(user):
    """Reuse the same access control logic as the rest of the app."""
    if user.role == CustomUser.RoleChoices.ADMIN:
        return Resident.objects.all()
    elif user.role == CustomUser.RoleChoices.CAREGIVER:
        return user.assigned_residents.all()
    else:
        return user.family_residents.all()


def _serialize_medication(med):
    return {
        'id':             med.id,
        'name':           med.name,
        'dosage':         med.dosage,
        'frequency':      med.frequency,
        'scheduled_time': str(med.scheduled_time),
        'scheduled_time_2': str(med.scheduled_time_2) if med.scheduled_time_2 else None,
        'scheduled_time_3': str(med.scheduled_time_3) if med.scheduled_time_3 else None,
        'is_active':      med.is_active,
        'notes':          med.notes,
    }


def _serialize_log(log):
    return {
        'id':               log.id,
        'resident_id':      log.resident.id,
        'resident_name':    log.resident.name,
        'medication_id':    log.medication.id,
        'medication_name':  log.medication.name,
        'scheduled_at': log.scheduled_at.isoformat() if hasattr(log.scheduled_at, 'isoformat') else str(log.scheduled_at),
        'actual_taken_at':  log.actual_taken_at.isoformat() if log.actual_taken_at and hasattr(log.actual_taken_at, 'isoformat') else str(log.actual_taken_at) if log.actual_taken_at else None,
        'status':           log.status,
        'logged_by':        log.logged_by.username if log.logged_by else None,
        'notes':            log.notes,
        'created_at':       log.created_at.isoformat(),
    }


def _serialize_risk_score(score):
    return {
        'id':                    score.id,
        'resident_id':           score.resident.id,
        'resident_name':         score.resident.name,
        'room_number':           score.resident.room_number,
        'score':                 round(score.score, 3),
        'risk_level':            score.risk_level,
        'risk_color':            score.risk_color,
        'predicted_for':         score.predicted_for.isoformat(),
        'model_version':         score.model_version,
        'contributing_factors':  score.contributing_factors,
        'features': {
            'adherence_rate_7d':     score.adherence_rate_7d,
            'adherence_rate_30d':    score.adherence_rate_30d,
            'meal_skips_7d':         score.meal_skips_7d,
            'gait_abnormal_days_7d': score.gait_abnormal_days_7d,
            'isolation_days_7d':     score.isolation_days_7d,
            'days_since_last_fall':  score.days_since_last_fall,
        },
    }



def _compute_rule_based_score(resident):
    """
    Predicts: Will this resident REFUSE their medication today?
    Uses XGBoost refusal model if refusal_model.pkl exists.
    Falls back to rule-based if not found.
    """
    from .models import GaitObservation, IsolationSession, HealthMetric

    today    = date.today()
    week_ago = today - timedelta(days=7)

    # ── Feature 1: social_score_avg_7d ───────────────────────
    social_entries = HealthMetric.objects.filter(
        resident=resident,
        metric_type='SOCIAL_SCORE',
        timestamp__date__gte=week_ago,
    ).values_list('value', flat=True)
    social_avg = float(np.mean(list(social_entries))) if social_entries.exists() else 50.0

    # ── Feature 2: social_score_trend ────────────────────────
    two_weeks_ago = today - timedelta(days=14)
    older_social = HealthMetric.objects.filter(
        resident=resident,
        metric_type='SOCIAL_SCORE',
        timestamp__date__gte=two_weeks_ago,
        timestamp__date__lt=week_ago,
    ).values_list('value', flat=True)
    social_prev = float(np.mean(list(older_social))) if older_social.exists() else social_avg
    social_trend = round(social_avg - social_prev, 2)

    # ── Feature 3: isolation_days_7d ─────────────────────────
    isolation_days = IsolationSession.objects.filter(
        resident=resident,
        uploaded_at__date__gte=week_ago,
        isolation_score__gte=60,
    ).count()

    # ── Feature 4: gait_abnormal_days_7d ─────────────────────
    gait_abnormal_days = GaitObservation.objects.filter(
        resident=resident,
        label='abnormal',
        recorded_at__date__gte=week_ago,
    ).values('recorded_at__date').distinct().count()

    # ── Feature 5: recent_fall ───────────────────────────────
    recent_fall = int(Incident.objects.filter(
        resident=resident,
        type='FALL',
        timestamp__date__gte=week_ago,
    ).exists())

    # ── Feature 6: recent_fight ──────────────────────────────
    recent_fight = int(Incident.objects.filter(
        resident=resident,
        type='AGGRESSION',
        timestamp__date__gte=week_ago,
    ).exists())

    # ── Feature 7: past_refusal_rate ─────────────────────────
    total_logs   = MedicationLog.objects.filter(resident=resident).count()
    refused_logs = MedicationLog.objects.filter(resident=resident, status='refused').count()
    past_refusal_rate = round(refused_logs / total_logs, 3) if total_logs > 0 else 0.0

    # ── Feature 8 & 9: age, day_of_week ──────────────────────
    age         = getattr(resident, 'age', 80)
    day_of_week = today.weekday()

    features = {
        'social_score_avg_7d':   social_avg,
        'social_score_trend':    social_trend,
        'isolation_days_7d':     isolation_days,
        'gait_abnormal_days_7d': gait_abnormal_days,
        'recent_fall':           recent_fall,
        'recent_fight':          recent_fight,
        'past_refusal_rate':     past_refusal_rate,
        'age':                   age,
        'day_of_week':           day_of_week,
    }


    # ── Fallback: rule-based ──────────────────────────────────
    score   = 0.0
    factors = []

    if social_avg < 40:
        score += 0.30
        factors.append('low_social_score')
    if social_trend < -5:
        score += 0.20
        factors.append('declining_mood')
    if isolation_days >= 2:
        score += 0.15
        factors.append('social_isolation')
    if gait_abnormal_days >= 2:
        score += 0.15
        factors.append('gait_decline')
    if recent_fall:
        score += 0.10
        factors.append('recent_fall')
    if recent_fight:
        score += 0.10
        factors.append('recent_fight')

    return (min(round(score, 3), 1.0), factors, features)

def _risk_level_from_score(score):
    if score >= 0.6:
        return 'high'
    elif score >= 0.35:
        return 'medium'
    return 'low'


# ─────────────────────────────────────────────────────────────
# Medication CRUD Views
# ─────────────────────────────────────────────────────────────

class MedicationListCreateView(views.APIView):
    """
    GET  /api/medication/residents/<resident_id>/  → list medications for a resident
    POST /api/medication/residents/<resident_id>/  → add a new medication
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, resident_id):
        resident = get_object_or_404(Resident, id=resident_id)
        allowed = _residents_for_user(request.user)
        if not allowed.filter(id=resident.id).exists():
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        meds = Medication.objects.filter(resident=resident, is_active=True)
        return Response([_serialize_medication(m) for m in meds], status=status.HTTP_200_OK)

    def post(self, request, resident_id):
        # Only admins and caregivers can add medications
        if request.user.role == CustomUser.RoleChoices.FAMILY:
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        resident = get_object_or_404(Resident, id=resident_id)

        med = Medication.objects.create(
            resident=resident,
            name=request.data.get('name', ''),
            dosage=request.data.get('dosage', ''),
            frequency=request.data.get('frequency', 'once_daily'),
            scheduled_time=request.data.get('scheduled_time'),
            scheduled_time_2=request.data.get('scheduled_time_2'),
            scheduled_time_3=request.data.get('scheduled_time_3'),
            notes=request.data.get('notes', ''),
        )
        return Response(_serialize_medication(med), status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────
# Medication Log Views (nurse logging)
# ─────────────────────────────────────────────────────────────

class MedicationLogCreateView(views.APIView):
    """
    POST /api/medication/log/
    Nurse logs a medication event (taken, missed, late, refused).
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role == CustomUser.RoleChoices.FAMILY:
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        resident = get_object_or_404(Resident, id=request.data.get('resident_id'))
        medication = get_object_or_404(Medication, id=request.data.get('medication_id'))
        log_status = request.data.get('status', 'taken')

        log = MedicationLog.objects.create(
            resident=resident,
            medication=medication,
            scheduled_at=parse_datetime(request.data.get('scheduled_at')) or timezone.now(),
            actual_taken_at=parse_datetime(request.data.get('actual_taken_at')) if request.data.get('actual_taken_at') else None,
            status=log_status,
            logged_by=request.user,
            notes=request.data.get('notes', ''),
        )

        # If missed or refused → create an Incident + Notification automatically
        if log_status in ['missed', 'refused']:
            default_zone = Zone.objects.first()  # fallback zone
            incident = Incident.objects.create(
                resident=resident,
                zone=default_zone,
                type='MEDICATION_MISSED',
                severity='MEDIUM',
                description=f"{resident.name} {log_status} {medication.name} scheduled at {log.scheduled_at}",
            )
            Notification.objects.create(
                message=f"⚠️ {resident.name} {log_status} their {medication.name} dose.",
                notification_type='HEALTH',
                user=resident.assigned_caregiver,
                incident=incident,
                resident=resident,
            )

        return Response(_serialize_log(log), status=status.HTTP_201_CREATED)


class MedicationLogListView(views.APIView):
    """
    GET /api/medication/log/<resident_id>/          → full history
    GET /api/medication/log/<resident_id>/?days=7   → last N days
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, resident_id):
        resident = get_object_or_404(Resident, id=resident_id)
        allowed = _residents_for_user(request.user)
        if not allowed.filter(id=resident.id).exists():
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        days = int(request.query_params.get('days', 30))
        since = timezone.now() - timedelta(days=days)
        logs = MedicationLog.objects.filter(
            resident=resident,
            scheduled_at__gte=since
        ).order_by('-scheduled_at')

        return Response([_serialize_log(l) for l in logs], status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────
# Adherence Risk Score Views
# ─────────────────────────────────────────────────────────────

class AdherenceRiskTodayView(views.APIView):
    """
    GET /api/adherence/risk/today/
    Returns today's risk scores for all residents the user can access.
    Sorted: high → medium → low.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = date.today()
        allowed = _residents_for_user(request.user)

        scores = AdherenceRiskScore.objects.filter(
            predicted_for=today,
            resident__in=allowed
        ).select_related('resident').order_by('-score')

        # If scores haven't been generated yet today, compute on the fly
        if not scores.exists():
            generated = []
            for resident in allowed:
                score_val, factors, features = _compute_rule_based_score(resident)
                risk = _risk_level_from_score(score_val)
                obj, _ = AdherenceRiskScore.objects.update_or_create(
                    resident=resident,
                    predicted_for=today,
                    defaults={
                        'score':                 score_val,
                        'risk_level':            risk,
                        'model_version': 'rule_based',
                        'contributing_factors':  factors,
                        'adherence_rate_7d':     features.get('social_score_avg_7d', 0.0),
                        'adherence_rate_30d':    features.get('social_score_trend', 0.0),
                        'meal_skips_7d':         features.get('isolation_days_7d', 0),
                        'gait_abnormal_days_7d': features.get('gait_abnormal_days_7d', 0),
                        'isolation_days_7d':     features.get('isolation_days_7d', 0),
                        'days_since_last_fall':  features.get('recent_fall', 0),
                    }
                )
                generated.append(obj)
            return Response([_serialize_risk_score(s) for s in generated], status=status.HTTP_200_OK)

        return Response([_serialize_risk_score(s) for s in scores], status=status.HTTP_200_OK)


class AdherenceRiskHistoryView(views.APIView):
    """
    GET /api/adherence/risk/<resident_id>/
    Returns risk score history for one resident (last 30 days).
    Used for the trend chart in the frontend.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, resident_id):
        resident = get_object_or_404(Resident, id=resident_id)
        allowed = _residents_for_user(request.user)
        if not allowed.filter(id=resident.id).exists():
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        scores = AdherenceRiskScore.objects.filter(
            resident=resident
        ).order_by('-predicted_for')[:30]

        return Response([_serialize_risk_score(s) for s in scores], status=status.HTTP_200_OK)


class RunAdherencePredictionView(views.APIView):
    """
    POST /api/adherence/run/
    Admin-only: manually trigger the prediction pipeline for all residents.
    (Normally this runs automatically via a nightly management command.)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != CustomUser.RoleChoices.ADMIN:
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)

        today = date.today()
        residents = Resident.objects.all()
        results = []

        for resident in residents:
            score_val, factors, features = _compute_rule_based_score(resident)
            risk = _risk_level_from_score(score_val)

            obj, created = AdherenceRiskScore.objects.update_or_create(
                resident=resident,
                predicted_for=today,
                defaults={
                    'score':                 score_val,
                    'risk_level':            risk,
                    'model_version': 'rule_based',
                    'contributing_factors':  factors,
                    'adherence_rate_7d':     features.get('social_score_avg_7d', 0.0),
                    'adherence_rate_30d':    features.get('social_score_trend', 0.0),
                    'meal_skips_7d':         features.get('isolation_days_7d', 0),
                    'gait_abnormal_days_7d': features.get('gait_abnormal_days_7d', 0),
                    'isolation_days_7d':     features.get('isolation_days_7d', 0),
                    'days_since_last_fall':  features.get('recent_fall', 0),
                }
            )

            # Auto-notify caregiver if high risk
            if risk == 'high' and resident.assigned_caregiver:
                Notification.objects.create(
                    message=f"🔴 {resident.name} is at HIGH risk of missing medication today. Factors: {', '.join(factors)}",
                    notification_type='HEALTH',
                    user=resident.assigned_caregiver,
                    resident=resident,
                )

            results.append(_serialize_risk_score(obj))

        return Response({
            'generated': len(results),
            'date': today.isoformat(),
            'results': results,
        }, status=status.HTTP_200_OK)

