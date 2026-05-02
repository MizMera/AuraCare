from django.urls import path
from . import views

app_name = 'voice'

urlpatterns = [
    # Shifts (admin configurable)
    path('shifts/', views.get_shifts, name='get_shifts'),
    path('shifts/create/', views.create_shift, name='create_shift'),
    path('shifts/<int:shift_id>/update/', views.update_shift, name='update_shift'),
    path('shifts/<int:shift_id>/delete/', views.delete_shift, name='delete_shift'),

    path('upload/', views.upload_audio, name='upload_audio'),
    path('reports/', views.get_reports, name='get_reports'),
    path('reports/<int:report_id>/', views.get_report, name='get_report'),
    path('reports/<int:report_id>/delete/', views.delete_report, name='delete_report'),

    path('reports/<int:report_id>/update/', views.update_transcription, name='update_transcription'),
]
