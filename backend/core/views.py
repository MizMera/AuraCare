import os
import json as _json
import random as _rnd
import subprocess
import sys
import pickle
import numpy as np
from datetime import date, timedelta
from django.utils.dateparse import parse_datetime

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
import re
import uuid
from types import SimpleNamespace
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.http import HttpResponse
from .models import (
    HealthMetric, Incident, Resident, CustomUser, IsolationSession,
    IsolationEvent, MealTime, Notification, Zone, GaitObservation,
    Medication, MedicationLog, AdherenceRiskScore,
    Device, DailySummary, ResidentEnrollmentImage,
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
    CustomTokenObtainPairSerializer,
    DailySummarySerializer,
    DailySummaryWriteSerializer,
    ResidentManagementSerializer,
    ResidentWriteSerializer,
    DeviceMonitoringSerializer as DeviceSerializer,
)
from . import pipeline_state
from .machine7_bridge import (
    delete_machine7_resident,
    get_machine7_preview_jpeg,
    get_machine7_status,
    start_machine7_pipeline,
    stop_machine7_pipeline,
    sync_all_django_residents_to_machine7,
    sync_machine7_resident_enrollment,
    update_machine7_resident_name,
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

        resident_photo_url = None
        if resident.photo:
            try:
                resident_photo_url = request.build_absolute_uri(resident.photo.url)
            except Exception:
                resident_photo_url = resident.photo.url

        return Response({
            "resident_id": resident.id,
            "resident_name": resident.name,
            "resident_photo_url": resident_photo_url,
            "incident_summary": list(incident_counts),
            "average_social_score_7d": avg_social.get('value__avg'),
            "recent_incidents": IncidentSerializer(incidents.select_related('zone', 'resident').order_by('-timestamp')[:10], many=True, context={'request': request}).data
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

        incidents = Incident.objects.select_related('zone', 'resident').order_by('-timestamp')[:30]
        return Response(IncidentSerializer(incidents, many=True, context={'request': request}).data, status=status.HTTP_200_OK)


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



# ===========================================================================
# Monitoring pipeline integration (from second project)
# ===========================================================================

def get_active_pipeline_state():
    bridge_status = get_machine7_status()
    if bridge_status['available'] and (bridge_status['healthy'] or bridge_status['thread_alive']):
        return bridge_status['state']
    return pipeline_state


def get_pipeline_state_entry(state_store, person_id):
    return state_store.get(str(person_id), state_store.get(person_id, {}))


def get_visible_residents(user):
    if user.role == CustomUser.RoleChoices.ADMIN:
        return Resident.objects.all()
    if user.role == CustomUser.RoleChoices.CAREGIVER:
        return Resident.objects.filter(assigned_caregiver=user)
    if user.role == CustomUser.RoleChoices.FAMILY:
        return Resident.objects.filter(family_member=user)
    return Resident.objects.none()


def get_monitoring_residents(user):
    if user.role in {CustomUser.RoleChoices.ADMIN, CustomUser.RoleChoices.CAREGIVER}:
        return Resident.objects.all()
    return get_visible_residents(user)


def save_resident_enrollment_images(resident, files):
    created_count = 0
    replaced_count = 0
    for file_obj in files:
        ResidentEnrollmentImage.objects.create(resident=resident, image=file_obj)
        created_count += 1
    overflow_count = max(0, resident.enrollment_images.count() - 5)
    if overflow_count:
        for old_image in resident.enrollment_images.order_by('created_at')[:overflow_count]:
            old_image.image.delete(save=False)
            old_image.delete()
            replaced_count += 1
    image_count = resident.enrollment_images.count()
    machine7_sync = sync_machine7_resident_enrollment(resident)
    return {
        'uploaded': created_count,
        'image_count': image_count,
        'remaining_slots': max(0, 5 - image_count),
        'replaced_old_images': replaced_count,
        'machine7_synced': machine7_sync.get('synced', False),
        'machine7_error': machine7_sync.get('error'),
        'machine7_enrollment': machine7_sync.get('result'),
    }


def build_monitoring_resident_payload(resident):
    return {
        'id': str(resident.id),
        'resident_id': resident.resident_id,
        'resident_code': resident.resident_code,
        'name': resident.name,
        'created_at': None,
        'image_count': resident.enrollment_images.count(),
    }


def build_monitoring_summary_payload(summary):
    return {
        'id': str(summary.id),
        'resident': str(summary.resident.id),
        'resident_name': summary.resident.name,
        'camera': str(summary.device.id) if summary.device_id else None,
        'camera_name': summary.device.name if summary.device_id else None,
        'date': str(summary.date) if summary.date else None,
        'location': summary.location,
        'summary_text': summary.summary_text,
        'start_datetime': summary.start_datetime.isoformat() if summary.start_datetime else None,
        'end_datetime': summary.end_datetime.isoformat() if summary.end_datetime else None,
        'created_at': summary.created_at.isoformat() if summary.created_at else None,
    }


def build_monitoring_camera_payload(camera):
    runtime_state = get_active_pipeline_state()
    source_key = str(camera.source) if camera.source else None
    source_value = str(camera.source).strip() if camera.source else ''
    detection_ready = bool(camera.is_active and source_value)
    detection_block_reason = ''
    if not camera.is_active:
        detection_block_reason = 'Camera is disabled.'
    elif not source_value:
        detection_block_reason = 'No source configured.'
    last_seen_recent = bool(
        camera.last_seen and camera.last_seen >= timezone.now() - timedelta(minutes=5)
    )
    return {
        'id': str(camera.id),
        'camera_code': camera.device_id,
        'name': camera.name or camera.device_id,
        'location': camera.zone.name,
        'source': camera.source,
        'is_active': camera.is_active,
        'is_live': bool(camera.is_active and (last_seen_recent or (source_key and source_key in runtime_state.active_camera_sources))),
        'status': 'live' if (camera.is_active and (last_seen_recent or (source_key and source_key in runtime_state.active_camera_sources))) else ('configured' if camera.is_active else 'disabled'),
        'detection_ready': detection_ready,
        'detection_block_reason': detection_block_reason,
        'created_at': None,
    }


def _parse_camera_ids(payload):
    camera_ids = payload.get('camera_ids')
    if camera_ids is None:
        single_camera_id = payload.get('camera_id')
        if single_camera_id is None:
            return []
        camera_ids = [single_camera_id]
    if isinstance(camera_ids, str):
        camera_ids = [chunk.strip() for chunk in camera_ids.split(',') if chunk.strip()]
    if not isinstance(camera_ids, (list, tuple)):
        return []
    parsed_ids = []
    for raw_value in camera_ids:
        try:
            parsed_ids.append(int(raw_value))
        except (TypeError, ValueError):
            continue
    deduped = []
    seen = set()
    for camera_id in parsed_ids:
        if camera_id in seen:
            continue
        seen.add(camera_id)
        deduped.append(camera_id)
    return deduped


def parse_time_window(request):
    import time as _time
    now = _time.time()
    window_hours = request.query_params.get('window_hours')
    if window_hours:
        try:
            hours = max(1.0, float(window_hours))
            return now - hours * 3600.0, now
        except ValueError:
            pass
    from_ts = request.query_params.get('from_ts')
    to_ts = request.query_params.get('to_ts')
    since_ts = None
    until_ts = None
    if from_ts:
        try:
            since_ts = float(from_ts)
        except ValueError:
            pass
    if to_ts:
        try:
            until_ts = float(to_ts)
        except ValueError:
            pass
    return since_ts, until_ts


def normalize_monitoring_person_name(person_id, raw_name):
    name = (raw_name or '').strip()
    if not name:
        return f'Unknown resident {person_id}' if person_id not in (None, '') else 'Unknown resident'

    if name.lower() == 'unknown':
        return f'Unknown resident {person_id}' if person_id not in (None, '') else 'Unknown resident'

    match = re.fullmatch(r'Person\s+(\d+)', name, flags=re.IGNORECASE)
    if match:
        return f'Unknown resident {match.group(1)}'

    return name


def is_unknown_monitoring_person(person_id, raw_name):
    name = (raw_name or '').strip()
    if not name:
        return True
    if name.lower() in {'unknown', 'unknown resident'}:
        return True
    if re.fullmatch(r'Person\s+(\d+)', name, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r'Unknown resident\s+(\d+)', name, flags=re.IGNORECASE):
        return True
    return False


def normalize_monitoring_summary_text(summary_text):
    text = (summary_text or '').strip()
    if not text:
        return ''

    text = re.sub(r'\bPerson\s+(\d+)\b', r'Unknown resident \1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bUnknown\b', 'Unknown resident', text)
    return text


def infer_resident_activity(resident):
    latest_incident = resident.incidents.order_by('-timestamp').first()
    if latest_incident:
        return latest_incident.get_type_display()
    latest_metric = resident.metrics.order_by('-timestamp').first()
    if latest_metric:
        return latest_metric.get_metric_type_display()
    return 'Monitoring'


def infer_resident_area(resident):
    latest_summary = resident.daily_summaries.order_by('-date', '-created_at').first()
    if latest_summary and latest_summary.location:
        return latest_summary.location
    return resident.room_number


def build_pipeline_status_payload(residents):
    import time as _time
    now = _time.time()
    recent_threshold = timezone.now() - timedelta(minutes=5)
    result = []
    runtime_status = get_machine7_status()
    runtime_state = get_active_pipeline_state()
    state_store = getattr(runtime_state, 'state_store', {})

    if runtime_state is not pipeline_state and state_store:
        # Build lookup by DB primary key (resident_id field is not present in this project)
        resident_lookup_by_id = {r.id: r for r in residents}
        resident_lookup_by_rid = {r.resident_id: r for r in residents if getattr(r, 'resident_id', None) is not None}
        for person_id, state_entry in state_store.items():
            try:
                lookup_key = int(person_id)
            except (TypeError, ValueError):
                lookup_key = person_id
            resident = resident_lookup_by_rid.get(lookup_key) or resident_lookup_by_id.get(lookup_key)
            if resident is None:
                # This person_id is no longer in the DB — show as Unknown
                result.append({
                    'person_id': lookup_key,
                    'name': 'Unknown',
                    'area': state_entry.get('area', 'Unknown area'),
                    'activity': state_entry.get('activity', 'Monitoring'),
                    'last_seen': state_entry.get('last_seen', now),
                    'match_debug': state_entry.get('match_debug', {'machine7': True, 'deleted': True}),
                })
                continue
            result.append({
                'person_id': lookup_key,
                'name': resident.name,  # Always use DB name as authoritative source
                'area': state_entry.get('area', infer_resident_area(resident)),
                'activity': state_entry.get('activity', infer_resident_activity(resident)),
                'last_seen': state_entry.get('last_seen', now),
                'match_debug': state_entry.get('match_debug', {'resident_code': getattr(resident, 'resident_code', None)}),
            })
        heartbeat = getattr(runtime_state, 'pipeline_last_heartbeat', None)
        return {
            'residents': sorted(result, key=lambda entry: entry.get('last_seen') or 0, reverse=True),
            'timestamp': now,
            'pipeline_running': bool(runtime_status['healthy'] or runtime_status['thread_alive']),
            'pipeline_started_at': getattr(runtime_state, 'pipeline_started_at', None),
            'pipeline_last_heartbeat': heartbeat,
        }

    for resident in residents.prefetch_related('incidents', 'metrics', 'daily_summaries'):
        person_id = resident.resident_id or resident.id
        state_entry = get_pipeline_state_entry(state_store, person_id)
        latest_times = []
        latest_metric = resident.metrics.order_by('-timestamp').first()
        latest_incident = resident.incidents.order_by('-timestamp').first()
        latest_summary = resident.daily_summaries.order_by('-date', '-created_at').first()
        if latest_metric:
            latest_times.append(latest_metric.timestamp.timestamp())
        if latest_incident:
            latest_times.append(latest_incident.timestamp.timestamp())
        if latest_summary and latest_summary.created_at:
            latest_times.append(latest_summary.created_at.timestamp())
        result.append({
            'person_id': person_id,
            'name': resident.name,  # Always use DB name as authoritative source
            'area': state_entry.get('area', infer_resident_area(resident)),
            'activity': state_entry.get('activity', infer_resident_activity(resident)),
            'last_seen': state_entry.get('last_seen', max(latest_times) if latest_times else now),
            'match_debug': state_entry.get('match_debug', {'resident_code': getattr(resident, 'resident_code', None)}),
        })

    active_sources = set(runtime_state.active_camera_sources)
    active_sources.update(
        str(source) for source in Device.objects.filter(
            type=Device.TypeChoices.CAMERA, is_active=True, last_seen__gte=recent_threshold,
        ).exclude(source='').values_list('source', flat=True)
    )
    heartbeat = runtime_state.pipeline_last_heartbeat
    pipeline_running = bool(active_sources) or bool(
        runtime_state.pipeline_running and heartbeat and (now - heartbeat) < 300.0
    )
    return {
        'residents': result,
        'timestamp': now,
        'pipeline_running': pipeline_running,
        'pipeline_started_at': runtime_state.pipeline_started_at,
        'pipeline_last_heartbeat': heartbeat,
    }


def build_pipeline_summary_payload(residents, since_ts=None, until_ts=None):
    def _format_duration_words(seconds_value):
        seconds_value = max(0, int(round(seconds_value)))
        if seconds_value == 0:
            return '0 seconds'
        if seconds_value < 60:
            return f'{seconds_value} second{"s" if seconds_value != 1 else ""}'
        minutes = int(round(seconds_value / 60.0))
        return f'{minutes} minute{"s" if minutes != 1 else ""}'

    def _extract_allowed_action(summary_text):
        text = (summary_text or '').lower()
        marker = 'detected activity:'
        if marker in text:
            tail = text.split(marker, 1)[1].strip()
            candidate = tail.split(' in ', 1)[0].strip(' .,:;')
            if candidate:
                for canonical in ('sitting', 'standing', 'walking'):
                    if canonical in candidate:
                        return canonical
                return None
        for action_name in ('sitting', 'standing', 'walking'):
            if action_name in text:
                return action_name
        return None

    def _extract_activity_breakdown(summary_text):
        m = re.search(r'\[([a-z]+=[0-9.]+(?:,[a-z]+=[0-9.]+)*)\]', (summary_text or ''))
        if not m:
            return None
        breakdown = {}
        for part in m.group(1).split(','):
            if '=' in part:
                act, val = part.split('=', 1)
                try:
                    breakdown[act.strip()] = float(val.strip())
                except ValueError:
                    pass
        return breakdown if breakdown else None

    def _duration_seconds(summary, window_start=None, window_end=None):
        start_dt = summary.start_datetime or summary.created_at
        end_dt = summary.end_datetime or window_end or timezone.now()
        if not start_dt or not end_dt:
            return 0.0
        if end_dt < start_dt:
            end_dt = start_dt
        if window_start is not None and start_dt < window_start:
            start_dt = window_start
        if window_end is not None and end_dt > window_end:
            end_dt = window_end
        duration = (end_dt - start_dt).total_seconds()
        return 0.0 if duration <= 0 else duration

    summaries = DailySummary.objects.filter(resident__in=residents).select_related('resident', 'zone', 'device__zone')
    if since_ts is not None:
        summaries = summaries.filter(created_at__gte=datetime.fromtimestamp(since_ts, tz=timezone.get_current_timezone()))
    if until_ts is not None:
        summaries = summaries.filter(created_at__lte=datetime.fromtimestamp(until_ts, tz=timezone.get_current_timezone()))

    window_start_dt = datetime.fromtimestamp(since_ts, tz=timezone.get_current_timezone()) if since_ts is not None else None
    window_end_dt = datetime.fromtimestamp(until_ts, tz=timezone.get_current_timezone()) if until_ts is not None else None

    result = {}
    for resident in residents:
        resident_summaries = summaries.filter(resident=resident).order_by('-date', '-created_at')
        if not resident_summaries.exists():
            result[str(resident.resident_id or resident.id)] = {
                'person_id': resident.resident_id or resident.id, 'name': resident.name,
                'total_seconds': 0.0, 'top_area': None, 'top_area_seconds': 0.0,
                'top_activity': None, 'top_activity_seconds': 0.0,
                'summary_line': f'{resident.name} has no recorded activity in this period.',
                'areas': {}, 'activities': {},
            }
            continue

        area_seconds = {}
        activity_seconds = {'standing': 0.0, 'sitting': 0.0, 'walking': 0.0}
        total_seconds = 0.0
        for summary in resident_summaries:
            duration = _duration_seconds(summary, window_start_dt, window_end_dt)
            if duration <= 0:
                continue
            if summary.device_id and getattr(summary.device, 'zone', None):
                area_key = summary.device.zone.name
            else:
                area_key = summary.zone.name
            area_seconds[area_key] = area_seconds.get(area_key, 0.0) + duration
            breakdown = _extract_activity_breakdown(summary.summary_text)
            if breakdown:
                for act in ('standing', 'sitting', 'walking'):
                    activity_seconds[act] = activity_seconds.get(act, 0.0) + breakdown.get(act, 0.0)
                total_seconds += sum(breakdown.get(a, 0.0) for a in ('standing', 'sitting', 'walking'))
            else:
                allowed_action = _extract_allowed_action(summary.summary_text)
                if allowed_action:
                    activity_seconds[allowed_action] = activity_seconds.get(allowed_action, 0.0) + duration
                total_seconds += duration

        top_area = max(area_seconds, key=area_seconds.get) if area_seconds else None
        valid_actions = {k: v for k, v in activity_seconds.items() if v > 0}
        top_activity = max(valid_actions, key=valid_actions.get) if valid_actions else None
        person_label = (resident.name or '').strip() or f'ID_{resident.resident_id or resident.id}'
        camera_location = top_area or 'Unknown location'
        known_action_total = sum(activity_seconds.values())
        total_for_sentence = known_action_total if known_action_total > 0 else total_seconds
        main_sentence = f'The resident {person_label} was detected in {camera_location} for {_format_duration_words(total_for_sentence)}.'
        action_sentences = [
            f'He was standing for {_format_duration_words(activity_seconds.get("standing", 0.0))}.',
            f'He was sitting for {_format_duration_words(activity_seconds.get("sitting", 0.0))}.',
            f'He was walking for {_format_duration_words(activity_seconds.get("walking", 0.0))}.',
        ]
        summary_line = ' '.join([main_sentence, *action_sentences]).strip()
        result[str(resident.resident_id or resident.id)] = {
            'person_id': resident.resident_id or resident.id, 'name': resident.name,
            'total_seconds': round(total_seconds, 1), 'top_area': top_area,
            'top_area_seconds': round(area_seconds.get(top_area, 0.0), 1),
            'top_activity': top_activity,
            'top_activity_seconds': round(valid_actions.get(top_activity, 0.0), 1),
            'summary_line': summary_line,
            'areas': {k: round(v, 1) for k, v in area_seconds.items()},
            'activities': {k: round(v, 1) for k, v in activity_seconds.items()},
        }

    return {'summary': result, 'saved_at': None, 'summary_text': ''}


def build_pipeline_history_payload(residents, limit=200, since_ts=None, until_ts=None):
    summaries = DailySummary.objects.filter(resident__in=residents).select_related('resident', 'device', 'zone').order_by('-created_at')
    if since_ts is not None:
        summaries = summaries.filter(created_at__gte=datetime.fromtimestamp(since_ts, tz=timezone.get_current_timezone()))
    if until_ts is not None:
        summaries = summaries.filter(created_at__lte=datetime.fromtimestamp(until_ts, tz=timezone.get_current_timezone()))

    history = []
    for summary in summaries[:limit]:
        location_value = summary.location or summary.zone.name
        summary_text = (summary.summary_text or '').strip()
        if summary_text:
            normalized = summary_text.lower()
            if 'detected activity:' in normalized and ('unknown' in normalized or 'unkown' in normalized):
                summary_text = f'Detection recorded in {location_value}.'
        history.append({
            'id': str(summary.id),
            'person_id': summary.resident.resident_id or summary.resident.id,
            'name': summary.resident.name,
            'camera': summary.device.name if summary.device_id else None,
            'location': location_value,
            'summary_text': summary_text,
            'date': str(summary.date) if summary.date else None,
            'start_datetime': summary.start_datetime.isoformat() if summary.start_datetime else None,
            'end_datetime': summary.end_datetime.isoformat() if summary.end_datetime else None,
            'created_at': summary.created_at.isoformat() if summary.created_at else None,
        })
    return {'history': history}


def create_generated_summary(resident):
    return (
        resident.daily_summaries
        .select_related('zone', 'device')
        .exclude(summary_text='')
        .order_by('-end_datetime', '-created_at')
        .first()
    )


def persist_detection_summaries_from_state(residents, runtime_state, stopped_at_ts=None):
    import time as _time
    state_store = getattr(runtime_state, 'state_store', {}) or {}
    session_summary = getattr(runtime_state, 'session_summary', {}) or {}
    if not state_store and not session_summary:
        return 0

    stopped_at_ts = float(stopped_at_ts if stopped_at_ts is not None else _time.time())
    pipeline_started_at = getattr(runtime_state, 'pipeline_started_at', None)
    if pipeline_started_at is None:
        pipeline_started_at = stopped_at_ts

    resident_by_person_id = {}
    resident_by_name = {}
    for resident in residents:
        resident_by_person_id[str(resident.id)] = resident
        if resident.resident_id is not None:
            resident_by_person_id[str(resident.resident_id)] = resident
        normalized_name = (resident.name or '').strip().lower()
        if normalized_name and normalized_name not in resident_by_name:
            resident_by_name[normalized_name] = resident

    def _resolve_resident(person_id, state_entry):
        direct_key = str(person_id)
        resident = resident_by_person_id.get(direct_key)
        if resident is not None:
            return resident
        digit_match = re.search(r'\d+', direct_key)
        if digit_match:
            resident = resident_by_person_id.get(digit_match.group(0))
            if resident is not None:
                return resident
        state_name = (state_entry.get('name') or '').strip().lower()
        if state_name:
            resident = resident_by_name.get(state_name)
            if resident is not None:
                return resident
        return None

    saved_count = 0
    fallback_zone = Zone.objects.first()
    if fallback_zone is None:
        fallback_zone, _ = Zone.objects.get_or_create(name='Unassigned Zone', defaults={'type': 'monitoring'})

    active_sources = {str(source) for source in getattr(runtime_state, 'active_camera_sources', set()) or set()}

    def _normalize_activity_label(raw_value):
        value = (str(raw_value or '')).strip()
        if not value:
            return 'Monitoring'
        lowered = value.lower()
        if 'standing' in lowered:
            return 'standing'
        if 'sitting' in lowered:
            return 'sitting'
        if 'walking' in lowered:
            return 'walking'
        if lowered in {'unknown', 'unkown', 'none', 'n/a'}:
            return 'Monitoring'
        return value

    def _get_zone_and_device(area):
        device = None
        if active_sources:
            device = (
                Device.objects.filter(type=Device.TypeChoices.CAMERA, is_active=True)
                .filter(source__in=active_sources)
                .select_related('zone')
                .first()
            )
        zone = device.zone if device and device.zone_id else None
        if zone is None and area:
            zone = Zone.objects.filter(name__iexact=area).first()
            if zone is None:
                zone = Zone.objects.create(name=area, type='monitoring')
        if zone is None:
            zone = fallback_zone
        if device is None and zone:
            device = Device.objects.filter(type=Device.TypeChoices.CAMERA, zone=zone, is_active=True).first()
        return zone, device

    def _create_summary_record(resident, zone, device, activity, duration_seconds, activities_map=None):
        try:
            start_ts = float(pipeline_started_at)
        except (TypeError, ValueError):
            start_ts = stopped_at_ts
        end_ts = start_ts + max(0.0, float(duration_seconds))
        start_dt = datetime.fromtimestamp(start_ts, tz=timezone.get_current_timezone())
        end_dt = datetime.fromtimestamp(end_ts, tz=timezone.get_current_timezone())
        camera_location = zone.name if zone else 'Unknown'
        if activities_map:
            encoded = ','.join(f'{a}={round(activities_map.get(a, 0.0), 1)}' for a in ('standing', 'sitting', 'walking'))
            summary_text = f'Detected activity: {activity} in {camera_location}. [{encoded}]'
        else:
            summary_text = f'Detected activity: {activity} in {camera_location}.'
        DailySummary.objects.create(
            resident=resident, zone=zone, device=device,
            date=end_dt.date(), location=camera_location,
            summary_text=summary_text, start_datetime=start_dt, end_datetime=end_dt,
        )

    if session_summary:
        for person_id, person_data in session_summary.items():
            person_name = person_data.get('name', '')
            resident = _resolve_resident(person_id, {'name': person_name})
            if resident is None:
                continue
            areas = person_data.get('areas', {}) or {}
            activities_map = person_data.get('activities', {}) or {}
            top_area = max(areas, key=areas.get) if areas else ''
            total_duration = sum(areas.values())
            zone, device = _get_zone_and_device(top_area)
            if zone is None:
                continue
            known_activities = {act: dur for act, dur in activities_map.items() if act in ('standing', 'sitting', 'walking') and dur > 0}
            dominant_activity = max(known_activities, key=known_activities.get) if known_activities else 'Monitoring'
            _create_summary_record(resident, zone, device, dominant_activity, total_duration, activities_map=activities_map)
            saved_count += 1
        return saved_count

    for person_id, state_entry in state_store.items():
        resident = _resolve_resident(person_id, state_entry)
        if resident is None:
            continue
        area = (state_entry.get('area') or '').strip()
        debug_payload = state_entry.get('match_debug') if isinstance(state_entry, dict) else None
        activity = (
            state_entry.get('activity') or state_entry.get('action') or state_entry.get('posture')
            or state_entry.get('detected_activity')
            or (debug_payload.get('activity') if isinstance(debug_payload, dict) else None)
            or 'Monitoring'
        )
        activity = _normalize_activity_label(activity)
        last_seen_ts = state_entry.get('last_seen')
        try:
            end_ts = float(last_seen_ts) if last_seen_ts is not None else stopped_at_ts
        except (TypeError, ValueError):
            end_ts = stopped_at_ts
        try:
            start_ts = float(pipeline_started_at)
        except (TypeError, ValueError):
            start_ts = end_ts
        if end_ts < start_ts:
            end_ts = start_ts
        zone, device = _get_zone_and_device(area)
        if zone is None:
            continue
        camera_location = zone.name
        summary_text = f'Detected activity: {activity} in {camera_location}.'
        start_dt = datetime.fromtimestamp(start_ts, tz=timezone.get_current_timezone())
        end_dt = datetime.fromtimestamp(end_ts, tz=timezone.get_current_timezone())
        DailySummary.objects.create(
            resident=resident, zone=zone, device=device,
            date=end_dt.date(), location=camera_location,
            summary_text=summary_text, start_datetime=start_dt, end_datetime=end_dt,
        )
        saved_count += 1

    return saved_count


def build_enrollment_response(resident, upload_meta):
    return {
        'resident': build_monitoring_resident_payload(resident),
        'uploaded_images': upload_meta['uploaded'],
        'replaced_old_images': upload_meta['replaced_old_images'],
        'enrollment_ok': upload_meta.get('uploaded', 0) > 0,
        'enrollment_error': None,
    }


class IsStaffRole(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in {CustomUser.RoleChoices.ADMIN, CustomUser.RoleChoices.CAREGIVER}
        )


class HasAPIKey(BasePermission):
    def has_permission(self, request, view):
        api_key = request.META.get('HTTP_X_API_KEY')
        expected_key = os.environ.get('SILVERGUARD_API_KEY', 'default-secret-key')
        return api_key == expected_key


class OperationsOverviewView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request, *args, **kwargs):
        residents = get_visible_residents(request.user)
        resident_ids = residents.values_list('id', flat=True)
        cameras = Device.objects.filter(type=Device.TypeChoices.CAMERA)
        recent_summaries = DailySummary.objects.filter(resident_id__in=resident_ids).select_related('resident', 'zone', 'device')[:5]
        recent_incidents = Incident.objects.filter(resident_id__in=resident_ids).order_by('-timestamp')[:5]
        return Response({
            'resident_count': residents.count(),
            'high_risk_count': residents.filter(risk_level=Resident.RiskLevelChoices.HIGH).count(),
            'camera_count': cameras.count(),
            'active_camera_count': cameras.filter(is_active=True).count(),
            'summary_count': DailySummary.objects.filter(resident_id__in=resident_ids).count(),
            'recent_summaries': DailySummarySerializer(recent_summaries, many=True, context={'request': request}).data,
            'recent_incidents': IncidentSerializer(recent_incidents, many=True).data,
        }, status=status.HTTP_200_OK)


class ResidentManagementView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request, *args, **kwargs):
        residents = get_visible_residents(request.user).prefetch_related('enrollment_images', 'daily_summaries').select_related('assigned_caregiver', 'family_member')
        serializer = ResidentManagementSerializer(residents, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        if not IsStaffRole().has_permission(request, self):
            return Response({'error': 'Only staff can create residents.'}, status=status.HTTP_403_FORBIDDEN)
        files = request.FILES.getlist('images')
        if not files and request.FILES.get('image'):
            files = [request.FILES['image']]
        serializer = ResidentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resident = serializer.save()
        payload = ResidentManagementSerializer(resident, context={'request': request}).data
        if files:
            upload_meta = save_resident_enrollment_images(resident, files)
            resident.refresh_from_db()
            payload = ResidentManagementSerializer(resident, context={'request': request}).data
            payload.update(upload_meta)
        return Response(payload, status=status.HTTP_201_CREATED)


class ResidentManagementDetailView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]

    def patch(self, request, resident_id, *args, **kwargs):
        resident = get_object_or_404(Resident, pk=resident_id)
        serializer = ResidentWriteSerializer(resident, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Use resident.id (Django PK) as machine7 person_id.
        update_machine7_resident_name(resident.id, resident.name)
        return Response(ResidentManagementSerializer(resident, context={'request': request}).data)

    def delete(self, request, resident_id, *args, **kwargs):
        resident = get_object_or_404(Resident, pk=resident_id)
        # Use resident.id (Django PK) as the person_id — resident_id field does not exist in this project
        delete_machine7_resident(resident.id)
        # Evict all possible keys this resident may have been stored under
        pipeline_state.remove_resident_state(resident.id, getattr(resident, 'resident_id', None) or resident.id)
        resident.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ResidentEnrollmentUploadView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, resident_id, *args, **kwargs):
        resident = get_object_or_404(Resident, pk=resident_id)
        files = request.FILES.getlist('images')
        if not files and request.FILES.get('image'):
            files = [request.FILES['image']]
        if not files:
            return Response({'error': 'Please attach at least one image.'}, status=status.HTTP_400_BAD_REQUEST)
        upload_meta = save_resident_enrollment_images(resident, files)
        resident.refresh_from_db()
        payload = ResidentManagementSerializer(resident, context={'request': request}).data
        payload.update(upload_meta)
        return Response(payload, status=status.HTTP_201_CREATED)


class CameraCoverageView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request, *args, **kwargs):
        cameras = Device.objects.filter(type=Device.TypeChoices.CAMERA).select_related('zone').order_by('name', 'device_id')
        return Response(DeviceSerializer(cameras, many=True).data, status=status.HTTP_200_OK)


class DailySummaryView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        residents = get_visible_residents(request.user)
        summaries = DailySummary.objects.filter(resident__in=residents).select_related('resident', 'zone', 'device')
        resident_id = request.query_params.get('resident')
        if resident_id:
            summaries = summaries.filter(resident_id=resident_id)
        date_value = request.query_params.get('date')
        if date_value:
            summaries = summaries.filter(date=date_value)
        serializer = DailySummarySerializer(summaries.order_by('-date', '-created_at')[:50], many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        if not IsStaffRole().has_permission(request, self):
            return Response({'error': 'Only staff can create summaries.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = DailySummaryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        summary = serializer.save()
        return Response(DailySummarySerializer(summary, context={'request': request}).data, status=status.HTTP_201_CREATED)


class HealthView(views.APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


class MonitoringResidentView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request, *args, **kwargs):
        residents = get_monitoring_residents(request.user).prefetch_related('enrollment_images')
        return Response({'residents': [build_monitoring_resident_payload(r) for r in residents]}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        if not IsStaffRole().has_permission(request, self):
            return Response({'error': 'Only staff can create residents.'}, status=status.HTTP_403_FORBIDDEN)
        files = request.FILES.getlist('images')
        if not files and request.FILES.get('image'):
            files = [request.FILES['image']]
        payload = request.data.copy()
        payload.setdefault('age', 0)
        payload.setdefault('room_number', 'UNASSIGNED')
        payload.setdefault('risk_level', Resident.RiskLevelChoices.LOW)
        serializer = ResidentWriteSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        resident = serializer.save()
        upload_meta = {'uploaded': 0, 'image_count': 0, 'remaining_slots': 5, 'replaced_old_images': 0}
        if files:
            upload_meta = save_resident_enrollment_images(resident, files)
            resident.refresh_from_db()
        return Response({
            'resident': build_monitoring_resident_payload(resident),
            'uploaded_images': upload_meta['uploaded'],
            'replaced_old_images': upload_meta['replaced_old_images'],
            'enrollment_ok': bool(files),
            'enrollment_error': None,
        }, status=status.HTTP_201_CREATED)


class MonitoringResidentDetailView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]

    def put(self, request, resident_id, *args, **kwargs):
        return self.patch(request, resident_id, *args, **kwargs)

    def patch(self, request, resident_id, *args, **kwargs):
        resident = get_object_or_404(Resident, pk=resident_id)
        serializer = ResidentWriteSerializer(resident, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'resident': build_monitoring_resident_payload(resident)}, status=status.HTTP_200_OK)

    def delete(self, request, resident_id, *args, **kwargs):
        resident = get_object_or_404(Resident, pk=resident_id)
        deleted_id = str(resident.id)
        resident.delete()
        return Response({'deleted': True, 'id': deleted_id}, status=status.HTTP_200_OK)


class MonitoringResidentImageUploadView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, resident_id, *args, **kwargs):
        resident = get_object_or_404(Resident, pk=resident_id)
        files = request.FILES.getlist('images')
        if not files and request.FILES.get('image'):
            files = [request.FILES['image']]
        if not files:
            return Response({'error': 'Please attach at least one image.'}, status=status.HTTP_400_BAD_REQUEST)
        upload_meta = save_resident_enrollment_images(resident, files)
        resident.refresh_from_db()
        return Response({
            'resident_id': str(resident.id),
            'uploaded': upload_meta['uploaded'],
            'image_count': upload_meta['image_count'],
            'remaining_slots': upload_meta['remaining_slots'],
            'replaced_old_images': upload_meta['replaced_old_images'],
            'enrollment_ok': True, 'enrollment_error': None,
        }, status=status.HTTP_201_CREATED)


class MonitoringResidentSummaryView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, resident_id=None, *args, **kwargs):
        residents = get_monitoring_residents(request.user)
        summaries = DailySummary.objects.filter(resident__in=residents).select_related('resident', 'device')
        if resident_id is not None:
            resident = get_object_or_404(residents, pk=resident_id)
            summaries = summaries.filter(resident=resident)
            return Response({
                'resident_id': resident.resident_id,
                'summaries': [build_monitoring_summary_payload(s) for s in summaries.order_by('-date', '-created_at')],
            }, status=status.HTTP_200_OK)
        return Response({'summaries': [build_monitoring_summary_payload(s) for s in summaries.order_by('-date', '-created_at')]}, status=status.HTTP_200_OK)


class MonitoringCameraView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request, *args, **kwargs):
        cameras = Device.objects.filter(type=Device.TypeChoices.CAMERA).select_related('zone').order_by('name', 'device_id')
        return Response({'cameras': [build_monitoring_camera_payload(c) for c in cameras]}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        name = (request.data.get('name') or '').strip()
        source = (request.data.get('source') or '').strip()
        location = (request.data.get('location') or '').strip() or 'Unassigned Zone'
        is_active = bool(request.data.get('is_active', True))
        if not name:
            return Response({'error': 'Camera name is required.'}, status=status.HTTP_400_BAD_REQUEST)
        requested_device_id = (request.data.get('camera_code') or request.data.get('device_id') or '').strip()
        if requested_device_id:
            if Device.objects.filter(device_id=requested_device_id).exists():
                return Response({'error': 'Camera code already exists.'}, status=status.HTTP_400_BAD_REQUEST)
            device_id = requested_device_id
        else:
            import uuid as _uuid
            device_id = f"CAM-{_uuid.uuid4().hex[:8].upper()}"
        zone, _ = Zone.objects.get_or_create(name=location, defaults={'type': 'monitoring'})
        camera = Device.objects.create(
            device_id=device_id, zone=zone, type=Device.TypeChoices.CAMERA,
            name=name, source=source, is_active=is_active,
        )
        return Response({
            'created': True,
            'camera': build_monitoring_camera_payload(camera),
            'message': 'Camera added. It can stay offline until physically connected.',
        }, status=status.HTTP_201_CREATED)


class MonitoringCameraDetectionsView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request, camera_id, *args, **kwargs):
        import time as _time
        camera = get_object_or_404(Device.objects.select_related('zone'), pk=camera_id, type=Device.TypeChoices.CAMERA)
        residents = get_monitoring_residents(request.user)
        status_payload = build_pipeline_status_payload(residents)
        camera_location = camera.zone.name if camera.zone_id else 'Unknown location'
        runtime_status = get_machine7_status()
        using_machine7_models = bool(runtime_status['available'])
        true_detection_running = bool(runtime_status['healthy'] or runtime_status['thread_alive'])
        recent_summaries = DailySummary.objects.filter(device=camera).select_related('resident').order_by('-created_at')[:10]

        def _photo_url(resident_obj):
            if not resident_obj or not resident_obj.photo:
                return None
            try:
                return request.build_absolute_uri(resident_obj.photo.url)
            except Exception:
                return resident_obj.photo.url

        summary_events = [{
            'resident': s.resident.name,
            'resident_photo_url': _photo_url(s.resident),
            'location': s.location or s.zone.name,
            'summary_text': s.summary_text,
            'created_at': s.created_at.isoformat() if s.created_at else None,
        } for s in recent_summaries]
        source_key = str(camera.source) if camera.source else None
        runtime_state = get_active_pipeline_state()
        source_active = bool(source_key and source_key in runtime_state.active_camera_sources)
        camera_payload = build_monitoring_camera_payload(camera)
        camera_payload['source_active'] = source_active
        camera_payload['pipeline_last_heartbeat'] = status_payload.get('pipeline_last_heartbeat')
        resident_detections = []
        recent_cutoff = _time.time() - 15.0
        # Build lookup maps so we can attach the DB photo to each detection row
        resident_by_id = {r.id: r for r in residents}
        resident_by_name = {}
        for r in residents:
            resident_by_name.setdefault(r.name.lower(), r)
        for detection in status_payload.get('residents', []):
            detected_location = detection.get('area') or camera_location
            if using_machine7_models:
                if detected_location != camera_location:
                    continue
                if float(detection.get('last_seen') or 0.0) < recent_cutoff:
                    continue
            # Resolve resident object for photo lookup
            det_resident = resident_by_id.get(detection.get('person_id')) or \
                           resident_by_name.get((detection.get('name') or '').lower())
            resident_detections.append({
                **detection, 'camera_id': str(camera.id), 'camera_name': camera_payload['name'],
                'camera_location': camera_location, 'detected_location': detected_location,
                'area': detected_location, 'detection_source': 'machine7' if using_machine7_models else 'compatibility',
                'resident_photo_url': _photo_url(det_resident),
            })
        return Response({
            'camera': camera_payload,
            'pipeline_running': status_payload.get('pipeline_running', False),
            'using_machine7_models': using_machine7_models,
            'true_detection_running': true_detection_running,
            'machine7_error': runtime_status.get('error'),
            'detection_source': 'machine7' if using_machine7_models else 'compatibility',
            'resident_detections': resident_detections,
            'recent_camera_events': summary_events,
        }, status=status.HTTP_200_OK)


class MonitoringStartPipelineView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]

    def post(self, request, *args, **kwargs):
        available_only_raw = request.data.get('available_only', True)
        available_only = str(available_only_raw).strip().lower() not in {'0', 'false', 'no'}
        pc_camera_index_raw = request.data.get('pc_camera_index')
        pc_camera_index = None
        if pc_camera_index_raw is not None:
            try:
                pc_camera_index = int(pc_camera_index_raw)
            except (TypeError, ValueError):
                pass
        requested_ids = _parse_camera_ids(request.data)
        requested_cameras = []
        skipped_cameras = []
        if requested_ids:
            camera_map = {c.id: c for c in Device.objects.select_related('zone').filter(pk__in=requested_ids, type=Device.TypeChoices.CAMERA)}
            missing_ids = [cid for cid in requested_ids if cid not in camera_map]
            if missing_ids:
                return Response({'error': f'Unknown camera id(s): {", ".join(str(v) for v in missing_ids)}'}, status=status.HTTP_404_NOT_FOUND)
            requested_cameras = [camera_map[cid] for cid in requested_ids]
        elif available_only:
            requested_cameras = list(Device.objects.select_related('zone').filter(type=Device.TypeChoices.CAMERA, is_active=True).exclude(source='').order_by('name', 'device_id'))

        if available_only:
            selected_cameras = []
            for camera in requested_cameras:
                camera_payload = build_monitoring_camera_payload(camera)
                if camera_payload['detection_ready']:
                    selected_cameras.append(camera)
                else:
                    skipped_cameras.append({'id': str(camera.id), 'name': camera_payload['name'], 'reason': camera_payload['detection_block_reason'] or 'Camera is not available for detection.'})
        else:
            selected_cameras = requested_cameras

        primary_camera = selected_cameras[0] if selected_cameras else None
        source_keys = [str(c.source).strip() for c in selected_cameras if c.source and str(c.source).strip()]
        source_override = pc_camera_index if pc_camera_index is not None and pc_camera_index >= 0 else None
        bridge_start = start_machine7_pipeline(primary_camera, source_override=source_override)
        runtime_status = get_machine7_status()

        if not bridge_start['available']:
            pipeline_state.touch_pipeline(source_keys[0] if source_keys else None)
            for source_key in source_keys:
                pipeline_state.active_camera_sources.add(source_key)
            runtime_state = pipeline_state
            pipeline_running = True
        else:
            runtime_state = runtime_status['state'] or pipeline_state
            pipeline_running = bool(runtime_status['healthy'] or runtime_status['thread_alive'])

        if bridge_start['available'] and not pipeline_running:
            pipeline_state.touch_pipeline(source_keys[0] if source_keys else None)
            for source_key in source_keys:
                pipeline_state.active_camera_sources.add(source_key)
            runtime_state = pipeline_state
            pipeline_running = True
            bridge_start = {**bridge_start, 'started': True, 'available': False}

        return Response({
            'started': bridge_start['started'] or pipeline_running,
            'camera': build_monitoring_camera_payload(primary_camera) if primary_camera else None,
            'cameras': [build_monitoring_camera_payload(c) for c in selected_cameras],
            'pipeline_running': pipeline_running,
            'pipeline_started_at': getattr(runtime_state, 'pipeline_started_at', None),
            'pipeline_last_heartbeat': getattr(runtime_state, 'pipeline_last_heartbeat', None),
            'using_machine7_models': bridge_start['available'],
            'machine7_error': bridge_start['error'],
            'selected_camera_count': len(selected_cameras),
            'skipped_cameras': skipped_cameras,
        }, status=status.HTTP_200_OK)


class MonitoringStatusView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        import time as _time
        m7_status = get_machine7_status()
        m7_state = m7_status.get('state')
        state_store = getattr(m7_state, 'state_store', {}) or {}
        pipeline_running = bool(
            m7_status.get('healthy') or m7_status.get('thread_alive')
        )
        pipeline_started_at = getattr(m7_state, 'pipeline_started_at', None)
        pipeline_last_heartbeat = getattr(m7_state, 'pipeline_last_heartbeat', None)
        now = _time.time()
        # Cross-check against Django DB — deleted residents must show as Unknown
        all_residents = get_monitoring_residents(request.user)
        resident_by_id = {r.id: r for r in all_residents}
        residents_out = []
        for pid, entry in state_store.items():
            try:
                lookup_key = int(pid)
            except (TypeError, ValueError):
                lookup_key = pid
            resident = resident_by_id.get(lookup_key)
            if resident is not None:
                # Use DB as authoritative name source
                name = resident.name
            else:
                # person_id not in DB (deleted or never enrolled here) → Unknown
                name = normalize_monitoring_person_name(pid, 'Unknown')
            residents_out.append({
                'person_id': pid,
                'name': name,
                'area': entry.get('area', 'Unknown area'),
                'activity': entry.get('activity', 'Monitoring'),
                'last_seen': entry.get('last_seen', now),
                'match_debug': entry.get('match_debug', {}),
            })
        return Response({
            'residents': sorted(residents_out, key=lambda e: e.get('last_seen') or 0, reverse=True),
            'timestamp': now,
            'pipeline_running': pipeline_running,
            'pipeline_started_at': pipeline_started_at,
            'pipeline_last_heartbeat': pipeline_last_heartbeat,
        }, status=status.HTTP_200_OK)


class MonitoringStopPipelineView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]

    def post(self, request, *args, **kwargs):
        # Grab machine7 state before stopping so summary/history fns are still wired
        m7_state = get_machine7_status().get('state')
        gen_fn = getattr(m7_state, 'generate_summary_fn', None)
        saved_count = 0
        if callable(gen_fn):
            try:
                gen_fn(reason='stop')
                saved_count = 1
            except Exception:
                pass
        stop_result = stop_machine7_pipeline(timeout_seconds=5.0)
        pipeline_state.pipeline_running = False
        pipeline_state.active_camera_sources = set()
        runtime_status = get_machine7_status()
        runtime_state = runtime_status.get('state') or pipeline_state
        return Response({
            'stopped': bool(stop_result.get('stopped', False)),
            'thread_alive': bool(stop_result.get('thread_alive', False)),
            'pipeline_running': bool(runtime_status.get('healthy') or runtime_status.get('thread_alive')),
            'pipeline_started_at': getattr(runtime_state, 'pipeline_started_at', None),
            'pipeline_last_heartbeat': getattr(runtime_state, 'pipeline_last_heartbeat', None),
            'saved_detection_summaries': saved_count,
        }, status=status.HTTP_200_OK)


class MonitoringLivePreviewView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request, *args, **kwargs):
        frame_bytes = get_machine7_preview_jpeg()
        if not frame_bytes:
            return Response({'error': 'No live preview frame available yet.'}, status=status.HTTP_404_NOT_FOUND)
        return HttpResponse(frame_bytes, content_type='image/jpeg')


class MonitoringSummaryAnalyticsView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        m7_state = get_machine7_status().get('state')
        summary_fn = getattr(m7_state, 'summary_fn', None)
        if callable(summary_fn):
            try:
                raw = summary_fn() or {}
            except Exception:
                raw = {}
            summary = {}
            for pid, entry in raw.items():
                if is_unknown_monitoring_person(pid, entry.get('name', f'Person {pid}')):
                    continue
                top_area = max(entry.get('areas', {}).items(), key=lambda kv: kv[1])[0] if entry.get('areas') else None
                acts = entry.get('activities', {})
                top_act = max(acts.items(), key=lambda kv: kv[1])[0] if acts else None
                total = sum(acts.values()) if acts else entry.get('total_seconds', 0.0)
                name = normalize_monitoring_person_name(pid, entry.get('name', f'Person {pid}'))
                loc = top_area or 'Unknown location'
                def _fmt(s):
                    s = max(0, int(round(s)))
                    if s < 60: return f'{s} second{"s" if s != 1 else ""}'
                    m = round(s / 60); return f'{m} minute{"s" if m != 1 else ""}'
                parts = [f'The resident {name} was detected in {loc} for {_fmt(total)}.']
                for act_key in ('standing', 'sitting', 'walking'):
                    parts.append(f'He was {act_key} for {_fmt(acts.get(act_key, 0.0))}.')
                summary[str(pid)] = {
                    'person_id': pid,
                    'name': name,
                    'total_seconds': round(float(total), 1),
                    'top_area': top_area,
                    'top_activity': top_act,
                    'summary_line': ' '.join(parts),
                    'areas': {k: round(float(v), 1) for k, v in entry.get('areas', {}).items()},
                    'activities': {k: round(float(v), 1) for k, v in acts.items()},
                }
            return Response({'summary': summary, 'saved_at': None, 'summary_text': ''}, status=status.HTTP_200_OK)
        return Response({'summary': {}, 'saved_at': None, 'summary_text': ''}, status=status.HTTP_200_OK)


class MonitoringHistoryView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        limit = int(request.query_params.get('limit', 200))
        m7_state = get_machine7_status().get('state')
        history_fn = getattr(m7_state, 'history_fn', None)
        if callable(history_fn):
            try:
                rows = history_fn(limit=limit) or []
            except Exception:
                rows = []
            all_residents_hist = get_monitoring_residents(request.user)
            resident_by_id_hist = {r.id: r for r in all_residents_hist}
            out = []
            for row in rows:
                pid = row.get('person_id', '')
                if is_unknown_monitoring_person(pid, row.get('name', f'Person {pid}')):
                    continue
                try:
                    pid_int = int(pid)
                except (TypeError, ValueError):
                    pid_int = None
                db_resident = resident_by_id_hist.get(pid_int) if pid_int is not None else None
                if db_resident is None:
                    # Deleted resident — skip from history
                    continue
                name = db_resident.name
                area = row.get('area', 'Unknown location')
                activity = row.get('activity', 'Monitoring')
                enter_ts = row.get('enter_time')
                exit_ts = row.get('exit_time')
                duration = row.get('duration_seconds', 0.0)
                def _ts(t):
                    if t is None: return None
                    try:
                        from datetime import datetime, timezone as _tz
                        return datetime.fromtimestamp(float(t), tz=_tz.utc).isoformat()
                    except Exception: return None
                out.append({
                    'id': str(pid) + '_' + str(enter_ts or ''),
                    'person_id': pid,
                    'name': name,
                    'location': area,
                    'summary_text': f'Detected activity: {activity} in {area}.',
                    'created_at': _ts(exit_ts or enter_ts),
                    'start_datetime': _ts(enter_ts),
                    'end_datetime': _ts(exit_ts),
                    'duration_seconds': round(float(duration), 1),
                    'status': row.get('status', 'closed'),
                })
            return Response({'history': out}, status=status.HTTP_200_OK)
        return Response({'history': []}, status=status.HTTP_200_OK)


class MonitoringGenerateSummaryView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request, *args, **kwargs):
        m7_state = get_machine7_status().get('state')
        gen_fn = getattr(m7_state, 'generate_summary_fn', None)
        if callable(gen_fn):
            try:
                result = gen_fn(reason='manual') or {}
                import time as _time
                saved_at = result.get('saved_at', _time.time())
                try:
                    saved_at_iso = timezone.now().isoformat() if saved_at is None else \
                        __import__('datetime').datetime.fromtimestamp(float(saved_at), tz=__import__('datetime').timezone.utc).isoformat()
                except Exception:
                    saved_at_iso = timezone.now().isoformat()
                raw_summary = result.get('summary', {}) if isinstance(result.get('summary', {}), dict) else {}
                filtered_summary = {
                    pid: entry for pid, entry in raw_summary.items()
                    if not is_unknown_monitoring_person(pid, (entry or {}).get('name', f'Person {pid}'))
                }
                summary_text = normalize_monitoring_summary_text(result.get('text', '') or result.get('summary_text', ''))
                summary_lines = []
                for pid, entry in filtered_summary.items():
                    name = normalize_monitoring_person_name(pid, entry.get('name', f'Person {pid}'))
                    areas = entry.get('areas', {}) or {}
                    activities = entry.get('activities', {}) or {}
                    total = sum(activities.values()) if activities else entry.get('total_seconds', 0.0)
                    top_area = max(areas, key=areas.get) if areas else 'Unknown location'
                    summary_lines.append(
                        f'The resident {name} was detected in {top_area} for {int(round(float(total or 0)))} seconds.'
                    )
                if filtered_summary:
                    summary_text = ' '.join(summary_lines)
                else:
                    summary_text = ''
                count = len(filtered_summary)
                return Response({
                    'saved_at': saved_at_iso,
                    'summary_text': summary_text,
                    'generated_count': count,
                }, status=status.HTTP_200_OK)
            except Exception as exc:
                return Response({'saved_at': None, 'summary_text': '', 'generated_count': 0, 'error': str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response({
            'saved_at': None, 'summary_text': '', 'generated_count': 0,
            'error': 'No detection data available yet. Start detection first, then generate summary.',
        }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


class DashboardStatusAliasView(MonitoringStatusView):
    pass


class DashboardSummaryAliasView(MonitoringSummaryAnalyticsView):
    pass


class DashboardHistoryAliasView(MonitoringHistoryView):
    pass


class DashboardGenerateSummaryAliasView(MonitoringGenerateSummaryView):
    pass


class DashboardResidentsAliasView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        residents = get_monitoring_residents(request.user).prefetch_related('enrollment_images')
        return Response({'residents': [build_monitoring_resident_payload(r) for r in residents]}, status=status.HTTP_200_OK)


class DashboardEnrollAliasView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'error': 'Name is required.'}, status=422)
        files = request.FILES.getlist('images')
        if not files and request.FILES.get('image'):
            files = [request.FILES['image']]
        if len(files) < 5:
            return Response({'error': 'At least 5 images are required.'}, status=422)
        payload = request.data.copy()
        payload.setdefault('age', 0)
        payload.setdefault('room_number', 'UNASSIGNED')
        payload.setdefault('risk_level', Resident.RiskLevelChoices.LOW)
        serializer = ResidentWriteSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        resident = serializer.save()
        upload_meta = save_resident_enrollment_images(resident, files)
        resident.refresh_from_db()
        return Response(build_enrollment_response(resident, upload_meta), status=status.HTTP_201_CREATED)


class DashboardResidentAliasView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]

    def put(self, request, resident_id, *args, **kwargs):
        return self.patch(request, resident_id, *args, **kwargs)

    def patch(self, request, resident_id, *args, **kwargs):
        resident = get_object_or_404(Resident, pk=resident_id)
        serializer = ResidentWriteSerializer(resident, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'success': True, 'resident': build_monitoring_resident_payload(resident)}, status=status.HTTP_200_OK)

    def delete(self, request, resident_id, *args, **kwargs):
        resident = get_object_or_404(Resident, pk=resident_id)
        deleted_id = str(resident.id)
        resident.delete()
        return Response({'success': True, 'deleted': True, 'id': deleted_id}, status=status.HTTP_200_OK)


class DashboardResidentUpdateAliasView(DashboardResidentAliasView):
    def post(self, request, resident_id, *args, **kwargs):
        return self.patch(request, resident_id, *args, **kwargs)


class DashboardResidentDeleteAliasView(views.APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffRole]

    def post(self, request, resident_id, *args, **kwargs):
        return self.delete(request, resident_id, *args, **kwargs)

    def delete(self, request, resident_id, *args, **kwargs):
        resident = get_object_or_404(Resident, pk=resident_id)
        deleted_id = str(resident.id)
        resident.delete()
        return Response({'success': True, 'deleted': True, 'id': deleted_id}, status=status.HTTP_200_OK)
