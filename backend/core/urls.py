from django.urls import path
from .views import (
    TelemetryIngestView,
    IncidentIngestView,
    FallIncidentIngestView,
    AggressionIncidentIngestView,
    MobileDashboardView,
    MobileActivityLogView,
    MobileFacilityIncidentsView,
    AggressionStreamStartView,
    AggressionStreamStopView,
    AggressionStreamStatusView,
    aggression_stream_feed,
)

urlpatterns = [
    path('ingest/telemetry/', TelemetryIngestView.as_view(), name='ingest-telemetry'),
    path('ingest/incident/', IncidentIngestView.as_view(), name='ingest-incident'),
    path('ingest/fall/', FallIncidentIngestView.as_view(), name='ingest-fall'),
    path('ingest/aggression/', AggressionIncidentIngestView.as_view(), name='ingest-aggression'),

    # Mobile App API Endpoints (Secured via SimpleJWT)
    path('mobile/dashboard/', MobileDashboardView.as_view(), name='mobile-dashboard'),
    path('mobile/activity-log/', MobileActivityLogView.as_view(), name='mobile-activity-log'),
    path('mobile/facility-incidents/', MobileFacilityIncidentsView.as_view(), name='mobile-facility-incidents'),

    # Live Aggression Stream
    path('stream/aggression/start/', AggressionStreamStartView.as_view(), name='stream-aggression-start'),
    path('stream/aggression/stop/', AggressionStreamStopView.as_view(), name='stream-aggression-stop'),
    path('stream/aggression/status/', AggressionStreamStatusView.as_view(), name='stream-aggression-status'),
    path('stream/aggression/feed/', aggression_stream_feed, name='stream-aggression-feed'),
]
