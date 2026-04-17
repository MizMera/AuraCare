from django.urls import path
from .views import (
    TelemetryIngestView,
    IncidentIngestView,
    MobileDashboardView,
    MobileActivityLogView,
    IsolationSessionListView,
    IsolationVideoUploadView,
    IsolationSessionDetailView,
)

urlpatterns = [
    path('ingest/telemetry/', TelemetryIngestView.as_view(), name='ingest-telemetry'),
    path('ingest/incident/', IncidentIngestView.as_view(), name='ingest-incident'),
    path('mobile/dashboard/', MobileDashboardView.as_view(), name='mobile-dashboard'),
    path('mobile/activity-log/', MobileActivityLogView.as_view(), name='mobile-activity-log'),
    # Isolation Detection
    path('isolation/sessions/', IsolationSessionListView.as_view(), name='isolation-sessions'),
    path('isolation/sessions/<int:pk>/', IsolationSessionDetailView.as_view(), name='isolation-session-detail'),
    path('isolation/upload/', IsolationVideoUploadView.as_view(), name='isolation-upload'),
]
