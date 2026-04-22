import json as _json
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class CustomUser(AbstractUser):
    class RoleChoices(models.TextChoices):
        ADMIN = 'ADMIN', _('Admin')
        CAREGIVER = 'CAREGIVER', _('Caregiver')
        FAMILY = 'FAMILY', _('Family')

    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.FAMILY
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Zone(models.Model):
    name = models.CharField(max_length=100, help_text="e.g., Dining Hall, Corridor")
    type = models.CharField(max_length=100, blank=True)
    floor_type = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name

class Resident(models.Model):
    class RiskLevelChoices(models.TextChoices):
        LOW = 'LOW', _('Low')
        MEDIUM = 'MEDIUM', _('Medium')
        HIGH = 'HIGH', _('High')

    name = models.CharField(max_length=200)
    age = models.PositiveIntegerField()
    room_number = models.CharField(max_length=50)
    risk_level = models.CharField(
        max_length=20, 
        choices=RiskLevelChoices.choices, 
        default=RiskLevelChoices.LOW
    )
    assigned_caregiver = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_residents',
        limit_choices_to={'role': CustomUser.RoleChoices.CAREGIVER}
    )
    family_member = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='family_residents',
        limit_choices_to={'role': CustomUser.RoleChoices.FAMILY}
    )

    def __str__(self):
        return f"{self.name} - Room {self.room_number}"

class Device(models.Model):
    class TypeChoices(models.TextChoices):
        CAMERA = 'CAMERA', _('Camera')
        MIC = 'MIC', _('Mic')

    device_id = models.CharField(max_length=100, unique=True)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='devices')
    type = models.CharField(max_length=20, choices=TypeChoices.choices)

    def __str__(self):
        return f"{self.get_type_display()} - {self.device_id} ({self.zone.name})"

class HealthMetric(models.Model):
    class MetricTypeChoices(models.TextChoices):
        GAIT_SPEED = 'GAIT_SPEED', _('Gait Speed')
        STRIDE_LENGTH = 'STRIDE_LENGTH', _('Stride Length')
        SOCIAL_SCORE = 'SOCIAL_SCORE', _('Social Score')
        VOCAL_ACTIVITY = 'VOCAL_ACTIVITY', _('Vocal Activity')

    resident = models.ForeignKey(Resident, on_delete=models.CASCADE, related_name='metrics')
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='metrics')
    metric_type = models.CharField(max_length=50, choices=MetricTypeChoices.choices)
    value = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.resident.name} - {self.get_metric_type_display()}: {self.value}"


class MealTime(models.Model):
    name = models.CharField(max_length=50, help_text="e.g., Breakfast, Lunch, Dinner")
    time = models.TimeField(help_text="Scheduled meal time")
    expected_people = models.PositiveIntegerField(default=4, help_text="Expected number of residents")
    zone = models.ForeignKey(
        Zone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meals',
        help_text="Zone where the meal takes place (e.g., Dining Hall)",
    )

    class Meta:
        ordering = ['time']
        verbose_name = "Meal Time"
        verbose_name_plural = "Meal Times"

    def __str__(self):
        return f"{self.name} at {self.time.strftime('%H:%M')}"

class Incident(models.Model):
    class IncidentTypeChoices(models.TextChoices):
        FALL = 'FALL', _('Fall')
        FALL_RISK = 'FALL_RISK', _('Fall Risk')
        AGGRESSION = 'AGGRESSION', _('Aggression')
        WANDERING = 'WANDERING', _('Wandering')
        ABSENCE = 'ABSENCE', _('Absence')
        DISTRESS_CRY = 'DISTRESS_CRY', _('Distress Cry')
        CARDIAC = 'CARDIAC', _('Cardiac')

    class SeverityChoices(models.TextChoices):
        CRITICAL = 'CRITICAL', _('Critical')
        HIGH = 'HIGH', _('High')
        MEDIUM = 'MEDIUM', _('Medium')

    resident = models.ForeignKey(
        Resident, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='incidents'
    )
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='incidents')
    type = models.CharField(max_length=50, choices=IncidentTypeChoices.choices)
    severity = models.CharField(max_length=20, choices=SeverityChoices.choices)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    meal = models.ForeignKey(
        MealTime,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='absence_incidents',
        help_text="Only used for absence incidents tied to a meal schedule.",
    )

    def __str__(self):
        return f"{self.get_severity_display()} {self.get_type_display()} in {self.zone.name}"

class ScheduleEvent(models.Model):
    name = models.CharField(max_length=200)
    expected_zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='scheduled_events')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    expected_residents = models.ManyToManyField(Resident, related_name='schedules')

    def __str__(self):
        return f"{self.name} at {self.expected_zone.name}"


class Notification(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        SENT = 'SENT', _('Sent')
        READ = 'READ', _('Read')

    class NotificationTypeChoices(models.TextChoices):
        INCIDENT = 'INCIDENT', _('Incident Alert')
        ABSENCE = 'ABSENCE', _('Meal Absence Alert')
        HEALTH = 'HEALTH', _('Health Metric Alert')
        INFO = 'INFO', _('Information')

    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationTypeChoices.choices,
        default=NotificationTypeChoices.INFO,
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )
    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )
    meal = models.ForeignKey(
        MealTime,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )
    resident = models.ForeignKey(
        Resident,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_notification_type_display()}: {self.message[:50]}"

    def mark_as_read(self):
        self.is_read = True
        self.status = self.StatusChoices.READ
        self.save(update_fields=['is_read', 'status'])


# ─────────────────────────────────────────────────────────────
# Social Isolation Detection — YOLOv8 + DeepSORT + LSTM
# ─────────────────────────────────────────────────────────────

class IsolationSession(models.Model):
    """One row per video analysis or webcam session."""
    SOURCE_UPLOAD = 'upload'
    SOURCE_WEBCAM = 'webcam'
    SOURCE_CHOICES = [(SOURCE_UPLOAD, 'Video Upload'), (SOURCE_WEBCAM, 'Webcam Live')]

    STATUS_PENDING  = 'pending'
    STATUS_ANALYSED = 'analysed'
    STATUS_ERROR    = 'error'
    STATUS_CHOICES  = [
        (STATUS_PENDING, 'Pending'), (STATUS_ANALYSED, 'Analysed'), (STATUS_ERROR, 'Error')
    ]

    filename          = models.CharField(max_length=255)
    source            = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_UPLOAD)
    video_file        = models.FileField(upload_to='isolation_videos/', blank=True, null=True)
    uploaded_at       = models.DateTimeField(default=timezone.now)
    duration_seconds  = models.PositiveIntegerField(default=0)
    total_frames      = models.PositiveIntegerField(default=0)
    persons_detected  = models.PositiveIntegerField(default=0)
    frames_actif      = models.PositiveIntegerField(default=0)
    frames_vigilance  = models.PositiveIntegerField(default=0)
    frames_isole      = models.PositiveIntegerField(default=0)
    isolation_score   = models.FloatField(default=0.0)          # 0–100
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    weekly_scores_json = models.TextField(default='[]')         # JSON list[7]
    notes             = models.TextField(blank=True)
    resident          = models.ForeignKey(
        Resident, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='isolation_sessions'
    )

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.filename

    @property
    def weekly_scores(self):
        try:    return _json.loads(self.weekly_scores_json)
        except: return []

    @property
    def _total(self):
        return self.frames_actif + self.frames_vigilance + self.frames_isole or 1

    @property
    def actif_pct(self):
        return round(self.frames_actif / self._total * 100)

    @property
    def vigilance_pct(self):
        return round(self.frames_vigilance / self._total * 100)

    @property
    def isolation_pct(self):
        return round(self.frames_isole / self._total * 100)


class IsolationEvent(models.Model):
    """One row per LSTM detection event inside a session."""
    TYPE_ISOLE     = 'isole'
    TYPE_VIGILANCE = 'vigilance'
    TYPE_ACTIF     = 'actif'
    TYPE_CHOICES   = [
        (TYPE_ISOLE, 'Isolé'), (TYPE_VIGILANCE, 'Vigilance'), (TYPE_ACTIF, 'Actif')
    ]

    session           = models.ForeignKey(IsolationSession, on_delete=models.CASCADE, related_name='events')
    track_id          = models.CharField(max_length=50)
    event_type        = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_ISOLE)
    confidence        = models.FloatField(default=0.0)          # 0–100
    timestamp_seconds = models.FloatField(default=0.0)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_event_type_display()} — {self.track_id} @ {self.timestamp_seconds}s"
class GaitObservation(models.Model):
    class LabelChoices(models.TextChoices):
        NORMAL = 'normal', _('Normal')
        ABNORMAL = 'abnormal', _('Abnormal')

    resident = models.ForeignKey(
        Resident,
        on_delete=models.CASCADE,
        related_name='gait_observations',
        null=True,
        blank=True,
    )
    zone = models.ForeignKey(
        Zone,
        on_delete=models.CASCADE,
        related_name='gait_observations',
        null=True,
        blank=True,
    )
    label = models.CharField(max_length=20, choices=LabelChoices.choices)
    confidence = models.FloatField()
    stride_length = models.FloatField(default=0)
    walking_speed = models.FloatField(default=0)
    arm_swing = models.FloatField(default=0)
    step_variability = models.FloatField(default=0)
    cadence = models.FloatField(default=0)
    height_ratio = models.FloatField(default=0)
    recorded_at = models.DateTimeField(auto_now_add=True)
    alert_triggered = models.BooleanField(default=False)
    snapshot = models.ImageField(upload_to='gait_snapshots/', null=True, blank=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        resident_name = self.resident.name if self.resident else 'Unknown'
        return f'{resident_name} - {self.label} ({self.confidence:.0f}%)'
