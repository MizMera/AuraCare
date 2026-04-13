from django.urls import path
from .views import (
    TelemetryIngestView, 
    IncidentIngestView,
    MobileDashboardView,
    MobileActivityLogView,
    MealTimeListView,
    MealTimeCreateView,
    MealTimeDetailView,
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    AbsenceCheckView,
    VideoStreamView,
    PersonCountView,
    IncidentListView

)

urlpatterns = [
    # AI Ingestion Webhooks (Secured via custom X-API-KEY)
    path('ingest/telemetry/', TelemetryIngestView.as_view(), name='ingest-telemetry'),
    path('ingest/incident/', IncidentIngestView.as_view(), name='ingest-incident'),

    # Mobile App API Endpoints (Secured via SimpleJWT)
    path('mobile/dashboard/', MobileDashboardView.as_view(), name='mobile-dashboard'),
    path('mobile/activity-log/', MobileActivityLogView.as_view(), name='mobile-activity-log'),
   # Meal Time endpoints
    path('meals/', MealTimeListView.as_view(), name='meal-list'),
    path('meals/create/', MealTimeCreateView.as_view(), name='meal-create'),
    path('meals/<int:meal_id>/', MealTimeDetailView.as_view(), name='meal-detail'),
    
    # Notification endpoints
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:notification_id>/read/', NotificationMarkReadView.as_view(), name='notification-read'),
    path('notifications/read-all/', NotificationMarkAllReadView.as_view(), name='notification-read-all'),
    
    # Absence detection
    path('check-absences/', AbsenceCheckView.as_view(), name='check-absences'),
    path('video/stream/', VideoStreamView.as_view(), name='video-stream'),
    path('person-count/', PersonCountView.as_view(), name='person-count'),
    path('incidents/', IncidentListView.as_view(), name='incident-list'),
]
