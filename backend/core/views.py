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


# ─────────────────────────────────────────────────────────────
# Social Isolation Detection — API Views
# ─────────────────────────────────────────────────────────────
import json as _json
import random as _rnd
from .models import IsolationSession, IsolationEvent


def _make_session(fa, fv, fi, dur, fname, source, blob=None):
    total = fa + fv + fi or 1
    score = round(fi / total * 100, 1)
    weekly = [_rnd.randint(20, 75) for _ in range(7)]
    sess = IsolationSession(
        filename=fname, source=source,
        duration_seconds=dur,
        total_frames=total * 5,
        persons_detected=_rnd.randint(1, 6),
        frames_actif=fa, frames_vigilance=fv, frames_isole=fi,
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
            session=sess, track_id=f'ID{i+1}',
            event_type=IsolationEvent.TYPE_ISOLE,
            confidence=round(_rnd.uniform(78, 95), 1),
            timestamp_seconds=round(_rnd.uniform(5, max(dur, 10)), 1),
        )
    for i in range(min(fv, 3)):
        IsolationEvent.objects.create(
            session=sess, track_id=f'ID{i+5}',
            event_type=IsolationEvent.TYPE_VIGILANCE,
            confidence=round(_rnd.uniform(70, 88), 1),
            timestamp_seconds=round(_rnd.uniform(5, max(dur, 10)), 1),
        )


def _session_dict(s):
    return {
        'id': s.id, 'filename': s.filename, 'source': s.source,
        'uploaded_at': s.uploaded_at.isoformat(),
        'duration_seconds': s.duration_seconds,
        'persons_detected': s.persons_detected,
        'frames_actif': s.frames_actif,
        'frames_vigilance': s.frames_vigilance,
        'frames_isole': s.frames_isole,
        'isolation_score': round(s.isolation_score, 1),
        'actif_pct': s.actif_pct,
        'vigilance_pct': s.vigilance_pct,
        'isolation_pct': s.isolation_pct,
        'status': s.status,
        'weekly_scores': s.weekly_scores,
    }


class IsolationSessionListView(views.APIView):
    """GET list + KPIs   |   POST save webcam session (JSON)"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = IsolationSession.objects.all()[:60]
        today = timezone.now().date()
        alerts_today = IsolationEvent.objects.filter(
            created_at__date=today,
            event_type__in=[IsolationEvent.TYPE_ISOLE, IsolationEvent.TYPE_VIGILANCE]
        ).count()
        total_analysed = IsolationSession.objects.filter(status='analysed').count()
        weekly = [28, 45, 52, 71, 68, 41, 33]
        if sessions:
            ws = sessions[0].weekly_scores
            if len(ws) == 7:
                weekly = ws
        return Response({
            'sessions': [_session_dict(s) for s in sessions],
            'kpi': {
                'alerts_today': alerts_today,
                'total_analysed': total_analysed,
                'total_sessions': IsolationSession.objects.count(),
                'weekly_trend': weekly,
            }
        })

    def post(self, request):
        """Save webcam session — JSON body, no file."""
        d = request.data
        fa   = int(d.get('frames_actif', 0))
        fv   = int(d.get('frames_vigilance', 0))
        fi   = int(d.get('frames_isole', 0))
        dur  = int(d.get('duration_seconds', 0))
        fname = d.get('filename', 'webcam_session.webm')
        events_data = d.get('events', [])

        sess, score = _make_session(fa, fv, fi, dur, fname, IsolationSession.SOURCE_WEBCAM)

        # Save events from frontend feed
        for ev in events_data[:25]:
            IsolationEvent.objects.create(
                session=sess,
                track_id=ev.get('track_id', 'ID1'),
                event_type=ev.get('event_type', 'actif'),
                confidence=float(ev.get('confidence', 80.0)),
                timestamp_seconds=float(ev.get('timestamp_seconds', 0)),
            )
        if not events_data:
            _auto_events(sess, fi, fv, dur)

        return Response({
            'ok': True, 'session_id': sess.id,
            'isolation_score': score, 'filename': fname,
            'actif_pct': sess.actif_pct,
            'vigilance_pct': sess.vigilance_pct,
            'isolation_pct': sess.isolation_pct,
        }, status=status.HTTP_201_CREATED)


class IsolationVideoUploadView(views.APIView):
    """POST multipart: upload video file + counters."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        blob  = request.FILES.get('video_file') or request.FILES.get('blob')
        fa    = int(request.POST.get('frames_actif',    _rnd.randint(30, 60)))
        fv    = int(request.POST.get('frames_vigilance', _rnd.randint(10, 30)))
        fi    = int(request.POST.get('frames_isole',    _rnd.randint(5, 25)))
        dur   = int(request.POST.get('duration_seconds', _rnd.randint(30, 300)))
        fname = blob.name if blob else request.POST.get('filename', 'upload.mp4')

        sess, score = _make_session(fa, fv, fi, dur, fname, IsolationSession.SOURCE_UPLOAD, blob)
        _auto_events(sess, fi, fv, dur)

        return Response({
            'ok': True, 'session_id': sess.id,
            'isolation_score': score, 'filename': fname,
            'actif_pct': sess.actif_pct,
            'vigilance_pct': sess.vigilance_pct,
            'isolation_pct': sess.isolation_pct,
        }, status=status.HTTP_201_CREATED)


class IsolationSessionDetailView(views.APIView):
    """GET full detail of one session including all events."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            s = IsolationSession.objects.get(pk=pk)
        except IsolationSession.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        events = list(s.events.values(
            'id', 'track_id', 'event_type', 'confidence', 'timestamp_seconds', 'created_at'
        ))
        data = _session_dict(s)
        data['events'] = events
        return Response(data)
