from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

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
#meriem 
class MealTime(models.Model):
    """Gère les horaires des repas """
    name = models.CharField(max_length=50, help_text="e.g., Breakfast, Lunch, Dinner")
    time = models.TimeField(help_text="Scheduled meal time")
    expected_people = models.IntegerField(default=4, help_text="Expected number of residents")
    zone = models.ForeignKey(
        Zone, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meals',
        help_text="Zone where the meal takes place (e.g., Dining Hall)"
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
    #added by meriem
    meal = models.ForeignKey(
        'MealTime',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='absence_incidents',
        help_text="Only for ABSENCE type incidents"
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
#added by meriem

class Notification(models.Model):
    """
    Gère les notifications envoyées aux utilisateurs (Caregivers, Family, Admin)
    """
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
        default=NotificationTypeChoices.INFO
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Relations
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    meal = models.ForeignKey(
        MealTime,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    resident = models.ForeignKey(
        Resident,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.get_notification_type_display()}: {self.message[:50]} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

    def mark_as_read(self):
        """Marque la notification comme lue"""
        self.is_read = True
        self.status = self.StatusChoices.READ
        self.save()

    def mark_as_sent(self):
        """Marque la notification comme envoyée"""
        self.status = self.StatusChoices.SENT
        self.save()