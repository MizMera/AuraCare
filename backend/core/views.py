import os
from django.http import StreamingHttpResponse, JsonResponse
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
    FallIncidentIngestSerializer,
    AggressionIncidentIngestSerializer,
    ResidentDashboardSerializer,
    IncidentSerializer,
    UserRegistrationSerializer,
    CustomTokenObtainPairSerializer
)

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


# -----------------------------------------------------------------------------
# LIVE AGGRESSION STREAM
# -----------------------------------------------------------------------------
from .aggression_stream import get_engine

class AggressionStreamStartView(views.APIView):
    """
    POST: Start the live aggression detection stream.
    Body (optional): { "camera": 0, "device_id": "CAM_01" }
    """
    permission_classes = [HasAPIKey]

    def post(self, request):
        camera = request.data.get('camera', 0)
        device_id = request.data.get('device_id', 'CAM_01')
        engine = get_engine(camera_idx=camera, device_id=device_id)
        engine.start()
        return Response({"status": "started", **engine.status}, status=status.HTTP_200_OK)


class AggressionStreamStopView(views.APIView):
    """POST: Stop the live aggression detection stream."""
    permission_classes = [HasAPIKey]

    def post(self, request):
        engine = get_engine()
        engine.stop()
        return Response({"status": "stopped"}, status=status.HTTP_200_OK)


class AggressionStreamStatusView(views.APIView):
    """GET: Get the current status of the aggression stream."""
    permission_classes = []

    def get(self, request):
        engine = get_engine()
        return Response(engine.status, status=status.HTTP_200_OK)


def aggression_stream_feed(request):
    """
    MJPEG video feed endpoint.
    Usage: <img src="http://localhost:8000/api/stream/aggression/feed/" />
    """
    engine = get_engine()
    if not engine._running:
        return JsonResponse({"error": "Stream not started. POST to /api/stream/aggression/start/ first."}, status=503)
    return StreamingHttpResponse(
        engine.generate_mjpeg(),
        content_type='multipart/x-mixed-replace; boundary=frame',
    )
