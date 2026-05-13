from django.urls import path
from .diabetes_views import (
    GlucosePredictView,
    GlucoseHistoryView,
    DiabetesModelStatusView,
)
from .face_recognition_views import (
    ResidentPhotoUploadView,
    ResidentListView,
    FaceIdentifyView,
    FaceEncodingStatusView,
)
from .views import (
    TelemetryIngestView,
    IncidentIngestView,
    FallIncidentIngestView,
    AggressionIncidentIngestView,
    MobileDashboardView,
    MobileActivityLogView,
    MobileFacilityIncidentsView,
    ModelAyoubLaunchView,
    ModelAyoubStopView,
    ModelAyoubStatusView,
    ModelAyoubArtifactsView,
    ModelAyoubUploadView,
    ModelAyoubStreamView,
    GaitIngestView,
    GaitHistoryView,
    GaitAllResidentsView,
    AnalyzeVideoView,
    MealTimeListView,
    MealTimeCreateView,
    MealTimeDetailView,
    NotificationListView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
    ChatbotQueryView,
    IncidentListView,
    AbsenceCheckView,
    MealAttendanceStartView,
    MealAttendanceStopView,
    MealAttendanceStatusView,
    MealAttendanceAnalyzeFrameView,
    PersonCountView,
    VideoStreamView,
    IsolationSessionListView,
    IsolationVideoUploadView,
    IsolationSessionDetailView,
    AggressionStreamStartView,
    AggressionStreamStopView,
    AggressionStreamStatusView,
    aggression_stream_feed,
    meal_attendance_feed,
    #medications 
    MedicationListCreateView,
    MedicationLogCreateView,
    MedicationLogListView,
    AdherenceRiskTodayView,
    AdherenceRiskHistoryView,
    RunAdherencePredictionView,
)
from .wandering_views import (
    WanderingPipelineLaunchView,
    WanderingPipelineUploadView,
    WanderingPipelineStatusView,
    WanderingPipelineArtifactsView,
    WanderingPipelineStopView,
    WanderingPipelineStreamView,
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
    path('gait/ingest/', GaitIngestView.as_view(), name='gait-ingest'),
    path('gait/history/<int:resident_id>/', GaitHistoryView.as_view(), name='gait-history'),
    path('gait/all/', GaitAllResidentsView.as_view(), name='gait-all'),
    path('gait/analyze/', AnalyzeVideoView.as_view(), name='gait-analyze'),
    path('incidents/', IncidentListView.as_view(), name='incident-list'),
    path('meals/', MealTimeListView.as_view(), name='meal-list'),
    path('meals/create/', MealTimeCreateView.as_view(), name='meal-create'),
    path('meals/<int:meal_id>/', MealTimeDetailView.as_view(), name='meal-detail'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:notification_id>/read/', NotificationMarkReadView.as_view(), name='notification-read'),
    path('notifications/read-all/', NotificationMarkAllReadView.as_view(), name='notification-read-all'),
    path('chatbot/query/', ChatbotQueryView.as_view(), name='chatbot-query'),
    path('check-absences/', AbsenceCheckView.as_view(), name='check-absences'),
    path('meal-attendance/start/', MealAttendanceStartView.as_view(), name='meal-attendance-start'),
    path('meal-attendance/stop/', MealAttendanceStopView.as_view(), name='meal-attendance-stop'),
    path('meal-attendance/status/', MealAttendanceStatusView.as_view(), name='meal-attendance-status'),
    path('meal-attendance/analyze-frame/', MealAttendanceAnalyzeFrameView.as_view(), name='meal-attendance-analyze-frame'),
    path('meal-attendance/feed/', meal_attendance_feed, name='meal-attendance-feed'),
    path('person-count/', PersonCountView.as_view(), name='person-count'),
    path('video/stream/', VideoStreamView.as_view(), name='video-stream'),

    # Social Isolation Detection
    path('isolation/sessions/', IsolationSessionListView.as_view(), name='isolation-sessions'),
    path('isolation/sessions/<int:pk>/', IsolationSessionDetailView.as_view(), name='isolation-session-detail'),
    path('isolation/upload/', IsolationVideoUploadView.as_view(), name='isolation-upload'),

    # Live Aggression Stream
    path('stream/aggression/start/', AggressionStreamStartView.as_view(), name='stream-aggression-start'),
    path('stream/aggression/stop/', AggressionStreamStopView.as_view(), name='stream-aggression-stop'),
    path('stream/aggression/status/', AggressionStreamStatusView.as_view(), name='stream-aggression-status'),
    path('stream/aggression/feed/', aggression_stream_feed, name='stream-aggression-feed'),

    # Wandering pipeline
    path('wandering/launch/', WanderingPipelineLaunchView.as_view(), name='wandering-launch'),
    path('wandering/upload/', WanderingPipelineUploadView.as_view(), name='wandering-upload'),
    path('wandering/status/', WanderingPipelineStatusView.as_view(), name='wandering-status'),
    path('wandering/artifacts/', WanderingPipelineArtifactsView.as_view(), name='wandering-artifacts'),
    path('wandering/stop/', WanderingPipelineStopView.as_view(), name='wandering-stop'),
    path('wandering/stream/', WanderingPipelineStreamView.as_view(), name='wandering-stream'),

    # Residents
    path('residents/', ResidentListView.as_view(), name='resident-list'),
    path('residents/<int:resident_id>/photo/', ResidentPhotoUploadView.as_view(), name='resident-photo'),

    # Facial Recognition
    path('face/identify/', FaceIdentifyView.as_view(), name='face-identify'),
    path('face/status/', FaceEncodingStatusView.as_view(), name='face-status'),
    
    #medications
    path('medication/residents/<int:resident_id>/', MedicationListCreateView.as_view(), name='medication-list-create'),
    path('medication/log/',                         MedicationLogCreateView.as_view(),  name='medication-log-create'),
    path('medication/log/<int:resident_id>/',        MedicationLogListView.as_view(),    name='medication-log-list'),
 
    # Adherence risk prediction
    path('adherence/risk/today/',                   AdherenceRiskTodayView.as_view(),       name='adherence-risk-today'),
    path('adherence/risk/<int:resident_id>/',        AdherenceRiskHistoryView.as_view(),     name='adherence-risk-history'),
    path('adherence/run/',                           RunAdherencePredictionView.as_view(),   name='adherence-run'),


    # Diabetes & Glycémie
    path('diabetes/predict/',                    GlucosePredictView.as_view(),       name='diabetes-predict'),
    path('diabetes/history/<int:resident_id>/',  GlucoseHistoryView.as_view(),       name='diabetes-history'),
    path('diabetes/status/',                     DiabetesModelStatusView.as_view(),  name='diabetes-status'),
]
