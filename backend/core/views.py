import os
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
from django.db.models import Avg, Count
from django.utils import timezone
from datetime import timedelta
from .models import HealthMetric, Incident, Resident, CustomUser
from .serializers import (
    HealthMetricIngestSerializer, 
    IncidentIngestSerializer,
    ResidentDashboardSerializer,
    IncidentSerializer,
    UserRegistrationSerializer,
    CustomTokenObtainPairSerializer
)
##gaitmodel
from .models import HealthMetric, Incident, Resident, CustomUser, Zone, GaitObservation
from django.utils import timezone
from datetime import timedelta
from rest_framework import parsers
import subprocess
import sys


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

class MobileDashboardView(views.APIView):
    """
    Returns recent metrics and incidents for the assigned residents.
    GET Only, secured by JWT.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role == CustomUser.RoleChoices.FAMILY:
            residents = Resident.objects.filter(family_member=user)
        elif user.role == CustomUser.RoleChoices.CAREGIVER:
            residents = Resident.objects.filter(assigned_caregiver=user)
        else:
            return Response({"error": "Only family members and caregivers can access this dashboard endpoint."}, status=status.HTTP_403_FORBIDDEN)
        
        if not residents.exists():
            return Response({"error": "No residents assigned to your account."}, status=status.HTTP_404_NOT_FOUND)

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
        if user.role == CustomUser.RoleChoices.FAMILY:
            residents = Resident.objects.filter(family_member=user)
        elif user.role == CustomUser.RoleChoices.CAREGIVER:
            residents = Resident.objects.filter(assigned_caregiver=user)
        else:
            return Response({"error": "Forbidden: Invalid role"}, status=status.HTTP_403_FORBIDDEN)
        
        if not residents.exists():
            return Response({"error": "No residents assigned."}, status=status.HTTP_404_NOT_FOUND)
        
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


##gaitmodel
class GaitIngestView(views.APIView):
    permission_classes = [HasAPIKey]
    parser_classes = [parsers.MultiPartParser, parsers.JSONParser]

    def post(self, request, *args, **kwargs):
        data       = request.data
        patient_id = data.get('patient_id')
        zone_name  = data.get('zone', 'East Wing Corridor')
        label      = data.get('label', 'normal')
        confidence = float(data.get('confidence', 0))
        features   = data.get('features', {})
        video_clip = request.FILES.get('snapshot')

        if isinstance(features, str):
            import json
            features = json.loads(features)

        resident = None
        if patient_id and patient_id != 'unknown':
            resident = Resident.objects.filter(
                name__icontains=patient_id
            ).first()

        zone = Zone.objects.filter(name__icontains=zone_name).first()

        alert = False
        if resident and label == 'abnormal':
            four_days_ago = timezone.now() - timedelta(days=4)
            recent_abnormal = GaitObservation.objects.filter(
                resident=resident,
                label='abnormal',
                recorded_at__gte=four_days_ago
            ).count()
            if recent_abnormal >= 3:
                alert = True
                Incident.objects.create(
                    resident=resident,
                    zone=zone or Zone.objects.first(),
                    type='FALL',
                    severity='HIGH',
                    description=f'Abnormal gait detected. Confidence: {confidence:.0f}%'
                )

        obs = GaitObservation.objects.create(
            resident=resident,
            zone=zone,
            label=label,
            confidence=confidence,
            stride_length=features.get('stride_length', 0),
            walking_speed=features.get('walking_speed', 0),
            arm_swing=features.get('arm_swing', 0),
            step_variability=features.get('step_variability', 0),
            cadence=features.get('cadence', 0),
            height_ratio=features.get('height_ratio', 0),
            alert_triggered=alert,
            snapshot=video_clip,
        )

        return Response({
            'status': 'success',
            'observation_id': obs.id,
            'alert_triggered': alert,
        }, status=status.HTTP_201_CREATED)
        
class GaitHistoryView(views.APIView):
    """
    Returns gait observations for a specific resident.
    GET secured by JWT.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, resident_id, *args, **kwargs):
        try:
            resident = Resident.objects.get(id=resident_id)
        except Resident.DoesNotExist:
            return Response({'error': 'Resident not found'}, status=status.HTTP_404_NOT_FOUND)

        observations = GaitObservation.objects.filter(
            resident=resident
        ).order_by('-recorded_at')[:10]

        data = [{
            'id':            obs.id,
            'label':         obs.label,
            'confidence':    obs.confidence,
            'recorded_at':   obs.recorded_at,
            'alert_triggered': obs.alert_triggered,
            'features': {
                'stride_length':    obs.stride_length,
                'walking_speed':    obs.walking_speed,
                'arm_swing':        obs.arm_swing,
                'step_variability': obs.step_variability,
                'cadence':          obs.cadence,
                'height_ratio':     obs.height_ratio,
            }
        } for obs in observations]

        return Response(data, status=status.HTTP_200_OK)
    
class GaitAllResidentsView(views.APIView):
    """
    Returns gait history for all residents assigned to the caregiver.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role == CustomUser.RoleChoices.CAREGIVER:
            residents = Resident.objects.filter(assigned_caregiver=user)
        elif user.role == CustomUser.RoleChoices.ADMIN:
            residents = Resident.objects.all()
        else:
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        data = []
        for resident in residents:
            observations = GaitObservation.objects.filter(
                resident=resident
            ).order_by('-recorded_at')[:20]

            data.append({
                'resident_id':   resident.id,
                'resident_name': resident.name,
                'room_number':   resident.room_number,
                'age':           resident.age,
                'risk_level':    resident.risk_level,
                'observations': [{
                    'id':              obs.id,
                    'label':           obs.label,
                    'confidence':      obs.confidence,
                    'recorded_at':     obs.recorded_at,
                    'alert_triggered': obs.alert_triggered,
                    'snapshot': obs.snapshot.url if obs.snapshot else None,

                    'features': {
                        'stride_length':    obs.stride_length,
                        'walking_speed':    obs.walking_speed,
                        'arm_swing':        obs.arm_swing,
                        'step_variability': obs.step_variability,
                        'cadence':          obs.cadence,
                        'height_ratio':     obs.height_ratio,
                    }
                } for obs in observations]
            })

        return Response(data, status=status.HTTP_200_OK)
    
class AnalyzeVideoView(views.APIView):
    """
    Receives a video file and launches gait analysis in background.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser]

    def post(self, request, *args, **kwargs):
        video_file = request.FILES.get('video')
        if not video_file:
            return Response({'error': 'No video provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Save video to media folder
        import os
        from django.conf import settings
        video_dir  = os.path.join(settings.MEDIA_ROOT, 'uploads')
        os.makedirs(video_dir, exist_ok=True)
        video_path = os.path.join(video_dir, video_file.name)

        with open(video_path, 'wb') as f:
            for chunk in video_file.chunks():
                f.write(chunk)

        # Path to gait_model script
        gait_script = os.path.join(
            settings.BASE_DIR, '..', 'gait_model', 'realtime_gait_v4.py'
        )
        gait_script = os.path.abspath(gait_script)

        # Launch analysis in background
        # Use gait_env Python
        gait_python = os.path.abspath(os.path.join(
            settings.BASE_DIR, '..', 'gait_model', 
            'gait_env', 'Scripts', 'python.exe'
        ))       
        subprocess.Popen(
            [gait_python, gait_script, '--mode', 'video', '--path', video_path],
            cwd=os.path.dirname(gait_script),
        )

        return Response({
            'status': 'analysis_started',
            'message': f'Analyzing {video_file.name} — results will appear in dashboard shortly.',
            'video': video_file.name,
        }, status=status.HTTP_202_ACCEPTED)