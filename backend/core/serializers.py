from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from .fall_incident import record_fall_incident
from .aggression_incident import record_aggression_incident
from .utils import create_notifications_for_incident
from .models import Device, HealthMetric, Incident, Resident, Zone, CustomUser, MealTime, Notification, ResidentEnrollmentImage, DailySummary

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['username'] = user.username
        token['role'] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Add user details to the response body
        data.update({
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'email': self.user.email,
                'role': self.user.role,
            }
        })
        return data

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'password', 'role', 'first_name', 'last_name')
        
    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            role=validated_data.get('role', CustomUser.RoleChoices.FAMILY),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user

class HealthMetricIngestSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthMetric
        fields = ['resident', 'zone', 'metric_type', 'value']

class IncidentIngestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incident
        fields = ['resident', 'zone', 'type', 'severity', 'description']

    def create(self, validated_data):
        incident = super().create(validated_data)
        create_notifications_for_incident(incident)
        return incident


class FallIncidentIngestSerializer(serializers.Serializer):
    """
    Fall events are keyed by camera device_id. Zone is taken from Device.zone;
    Incident never stores a device FK.
    """
    device_id = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_device_id(self, value):
        if not Device.objects.filter(device_id=value).exists():
            raise serializers.ValidationError('Unknown device_id.')
        return value

    def create(self, validated_data):
        return record_fall_incident(
            validated_data['device_id'],
            validated_data.get('description', ''),
        )

class AggressionIncidentIngestSerializer(serializers.Serializer):
    """
    Aggression events are keyed by camera device_id. Zone is taken from Device.zone;
    Incident never stores a device FK.
    """
    device_id = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_device_id(self, value):
        if not Device.objects.filter(device_id=value).exists():
            raise serializers.ValidationError('Unknown device_id.')
        return value

    def create(self, validated_data):
        return record_aggression_incident(
            validated_data['device_id'],
            validated_data.get('description', ''),
        )


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zone
        fields = ['id', 'name', 'type', 'floor_type']

class HealthMetricSerializer(serializers.ModelSerializer):
    zone = ZoneSerializer(read_only=True)
    metric_type_display = serializers.CharField(source='get_metric_type_display', read_only=True)
    
    class Meta:
        model = HealthMetric
        fields = ['id', 'metric_type', 'metric_type_display', 'value', 'timestamp', 'zone']

class IncidentSerializer(serializers.ModelSerializer):
    zone = ZoneSerializer(read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    meal_name = serializers.CharField(source='meal.name', read_only=True, allow_null=True)
    resident_name = serializers.CharField(source='resident.name', read_only=True, allow_null=True)
    resident_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = ['id', 'type', 'type_display', 'severity', 'severity_display', 'description', 'timestamp', 'zone', 'meal', 'meal_name', 'resident', 'resident_name', 'resident_photo_url']

    def get_resident_photo_url(self, obj):
        if not obj.resident or not obj.resident.photo:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.resident.photo.url)
        return obj.resident.photo.url

class ResidentDashboardSerializer(serializers.ModelSerializer):
    metrics = serializers.SerializerMethodField()
    incidents = serializers.SerializerMethodField()
    medications = serializers.SerializerMethodField()

    class Meta:
        model = Resident
        fields = ['id', 'name', 'age', 'room_number', 'risk_level', 'metrics', 'incidents', 'medications']

    def get_metrics(self, obj):
        gait_obs = obj.gait_observations.order_by('-recorded_at')[:3]
        if gait_obs.exists():
            return [
                {
                    'metric_type': 'GAIT_SPEED',
                    'metric_type_display': 'Gait Speed',
                    'value': round(obs.walking_speed, 2),
                    'timestamp': obs.recorded_at.isoformat(),
                    'label': obs.label,
                    'confidence': round(obs.confidence, 1),
                }
                for obs in gait_obs
            ]
        recent = obj.metrics.order_by('-timestamp')[:3]
        return HealthMetricSerializer(recent, many=True).data


    def get_incidents(self, obj):
        recent = obj.incidents.order_by('-timestamp')[:5]
        return IncidentSerializer(recent, many=True).data
    
    def get_medications(self, obj):
        meds = obj.medications.filter(is_active=True).order_by('scheduled_time')
        result = []
        for med in meds:
            last_log = med.logs.order_by('-scheduled_at').first()
            result.append({
                'name': med.name,
                'dosage': med.dosage,
                'scheduled_time': str(med.scheduled_time),
                'last_status': last_log.status if last_log else None,
            })
        return result


class MealTimeSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source='zone.name', read_only=True)

    class Meta:
        model = MealTime
        fields = ['id', 'name', 'time', 'expected_people', 'zone', 'zone_name']


class NotificationSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    incident_type = serializers.CharField(source='incident.type', read_only=True, allow_null=True)
    incident_severity = serializers.CharField(source='incident.severity', read_only=True, allow_null=True)
    incident_severity_display = serializers.CharField(source='incident.get_severity_display', read_only=True, allow_null=True)
    meal_name = serializers.CharField(source='meal.name', read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'message', 'notification_type', 'status', 'is_read', 'created_at',
            'user', 'user_name', 'incident', 'incident_type', 'meal', 'meal_name',
            'resident', 'incident_severity', 'incident_severity_display',
        ]


# ---------------------------------------------------------------------------
# Serializers integrated from monitoring pipeline project
# ---------------------------------------------------------------------------

class ResidentEnrollmentImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ResidentEnrollmentImage
        fields = ['id', 'image_url', 'created_at']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if not obj.image:
            return None
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


class DeviceMonitoringSerializer(serializers.ModelSerializer):
    zone = ZoneSerializer(read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Device
        fields = [
            'id', 'device_id', 'name', 'type', 'type_display',
            'source', 'is_active', 'last_seen', 'zone',
        ]


class DailySummarySerializer(serializers.ModelSerializer):
    resident_name = serializers.CharField(source='resident.name', read_only=True)
    zone = ZoneSerializer(read_only=True)
    device = DeviceMonitoringSerializer(read_only=True)

    class Meta:
        model = DailySummary
        fields = [
            'id', 'resident', 'resident_name', 'zone', 'device',
            'date', 'location', 'summary_text',
            'start_datetime', 'end_datetime', 'created_at',
        ]


class DailySummaryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailySummary
        fields = [
            'resident', 'zone', 'device', 'date', 'location',
            'summary_text', 'start_datetime', 'end_datetime',
        ]
        extra_kwargs = {
            'device': {'required': False, 'allow_null': True},
            'location': {'required': False, 'allow_blank': True},
            'start_datetime': {'required': False, 'allow_null': True},
            'end_datetime': {'required': False, 'allow_null': True},
        }


class ResidentManagementSerializer(serializers.ModelSerializer):
    assigned_caregiver_name = serializers.CharField(source='assigned_caregiver.get_full_name', read_only=True)
    family_member_name = serializers.CharField(source='family_member.get_full_name', read_only=True)
    image_count = serializers.IntegerField(source='enrollment_images.count', read_only=True)
    latest_summary = serializers.SerializerMethodField()
    enrollment_images = ResidentEnrollmentImageSerializer(many=True, read_only=True)

    class Meta:
        model = Resident
        fields = [
            'id', 'resident_id', 'resident_code', 'name', 'age', 'room_number',
            'risk_level', 'assigned_caregiver', 'assigned_caregiver_name',
            'family_member', 'family_member_name',
            'image_count', 'latest_summary', 'enrollment_images',
        ]

    def get_latest_summary(self, obj):
        summary = obj.daily_summaries.select_related('zone', 'device').first()
        if not summary:
            return None
        return DailySummarySerializer(summary, context=self.context).data


class ResidentWriteSerializer(serializers.ModelSerializer):
    resident_id = serializers.IntegerField(required=False, min_value=1)

    class Meta:
        model = Resident
        fields = [
            'id', 'resident_id', 'name', 'age', 'room_number',
            'risk_level', 'assigned_caregiver', 'family_member',
        ]

    def validate_resident_id(self, value):
        instance = getattr(self, 'instance', None)
        queryset = Resident.objects.filter(resident_id=value)
        if instance is not None:
            queryset = queryset.exclude(pk=instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('Resident ID already exists.')
        return value
