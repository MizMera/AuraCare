from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, Resident, Zone, Device,
    HealthMetric, Incident, ScheduleEvent, MealTime, Notification, GaitObservation,
    ResidentEnrollmentImage, DailySummary,
)

@admin.register(MealTime)
class MealTimeAdmin(admin.ModelAdmin):
    list_display = ('name', 'time', 'expected_people', 'zone')
    list_filter = ('zone',)
    search_fields = ('name',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('message', 'notification_type', 'user', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('message', 'user__username')
    readonly_fields = ('created_at',)


@admin.register(GaitObservation)
class GaitObservationAdmin(admin.ModelAdmin):
    list_display = ('resident', 'label', 'confidence', 'alert_triggered', 'zone', 'recorded_at')
    list_filter = ('label', 'alert_triggered', 'zone', 'recorded_at')
    search_fields = ('resident__name', 'zone__name')
    readonly_fields = ('recorded_at',)

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser')
    fieldsets = UserAdmin.fieldsets + (
        ('Role Information', {'fields': ('role',)}),
    )

@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'floor_type')
    search_fields = ('name', 'type')

class ResidentEnrollmentImageInline(admin.StackedInline):
    model = ResidentEnrollmentImage
    extra = 5
    max_num = 5
    fields = ('image',)
    verbose_name = 'Enrollment Photo'
    verbose_name_plural = 'Enrollment Photos (5 required for face recognition)'


@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):
    list_display = ('name', 'room_number', 'risk_level', 'assigned_caregiver', 'family_member')
    list_filter = ('risk_level',)
    search_fields = ('name', 'room_number')
    inlines = [ResidentEnrollmentImageInline]
    exclude = ('photo',)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        resident = form.instance
        image_count = resident.enrollment_images.count()
        if image_count > 0:
            try:
                from .machine7_bridge import sync_machine7_resident_enrollment
                result = sync_machine7_resident_enrollment(resident)
                if result.get('synced'):
                    self.message_user(
                        request,
                        f'"{resident.name}" enrolled in machine7 face recognition ({image_count} photo(s)).',
                        level=messages.SUCCESS,
                    )
                else:
                    self.message_user(
                        request,
                        f'Saved, but machine7 enrollment skipped: {result.get("error")}',
                        level=messages.WARNING,
                    )
            except Exception as exc:
                self.message_user(
                    request,
                    f'Saved, but machine7 enrollment error: {exc}',
                    level=messages.WARNING,
                )

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'type', 'zone')
    list_filter = ('type', 'zone')
    search_fields = ('device_id',)

@admin.register(HealthMetric)
class HealthMetricAdmin(admin.ModelAdmin):
    list_display = ('resident', 'metric_type', 'value', 'zone', 'timestamp')
    list_filter = ('metric_type', 'zone', 'timestamp')
    search_fields = ('resident__name',)

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('type', 'severity', 'resident', 'zone', 'timestamp')
    list_filter = ('severity', 'type', 'timestamp', 'zone')
    search_fields = ('resident__name', 'description')

@admin.register(ScheduleEvent)
class ScheduleEventAdmin(admin.ModelAdmin):
    list_display = ('name', 'expected_zone', 'start_time', 'end_time')
    list_filter = ('expected_zone', 'start_time', 'end_time')
    search_fields = ('name',)
    filter_horizontal = ('expected_residents',)

#medications
from .models import Medication, MedicationLog, AdherenceRiskScore

@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ['resident', 'name', 'dosage', 'frequency', 'scheduled_time', 'is_active']
    list_filter = ['frequency', 'is_active']
    search_fields = ['resident__name', 'name']

@admin.register(MedicationLog)
class MedicationLogAdmin(admin.ModelAdmin):
    list_display = ['resident', 'medication', 'status', 'scheduled_at', 'logged_by']
    list_filter = ['status']
    search_fields = ['resident__name', 'medication__name']

@admin.register(AdherenceRiskScore)
class AdherenceRiskScoreAdmin(admin.ModelAdmin):
    list_display = ['resident', 'score', 'risk_level', 'predicted_for', 'contributing_factors']
    list_filter = ['risk_level', 'model_version']


@admin.register(ResidentEnrollmentImage)
class ResidentEnrollmentImageAdmin(admin.ModelAdmin):
    list_display = ('resident', 'created_at')
    search_fields = ('resident__name', 'resident__resident_code')


@admin.register(DailySummary)
class DailySummaryAdmin(admin.ModelAdmin):
    list_display = ('resident', 'date', 'zone', 'device', 'created_at')
    list_filter = ('date', 'zone')
    search_fields = ('resident__name', 'location', 'summary_text')

