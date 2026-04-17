from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, Resident, Zone, Device,
    HealthMetric, Incident, ScheduleEvent, MealTime, Notification
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

@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):
    list_display = ('name', 'room_number', 'risk_level', 'assigned_caregiver', 'family_member')
    list_filter = ('risk_level',)
    search_fields = ('name', 'room_number')

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
