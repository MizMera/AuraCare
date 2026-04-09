from django.urls import path
from .views import (
    TelemetryIngestView, 
    IncidentIngestView,
    MobileDashboardView,
    MobileActivityLogView
)

urlpatterns = [
    # AI Ingestion Webhooks (Secured via custom X-API-KEY)
    path('ingest/telemetry/', TelemetryIngestView.as_view(), name='ingest-telemetry'),
    path('ingest/incident/', IncidentIngestView.as_view(), name='ingest-incident'),

    # Mobile App API Endpoints (Secured via SimpleJWT)
    path('mobile/dashboard/', MobileDashboardView.as_view(), name='mobile-dashboard'),
    path('mobile/activity-log/', MobileActivityLogView.as_view(), name='mobile-activity-log'),
]
