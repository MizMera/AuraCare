from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from .fall_incident import record_fall_incident
from .aggression_incident import record_aggression_incident
from .utils import create_notifications_for_incident
from .models import Device, HealthMetric, Incident, Resident, Zone, CustomUser, MealTime, Notification

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

    class Meta:
        model = Incident
        fields = ['id', 'type', 'type_display', 'severity', 'severity_display', 'description', 'timestamp', 'zone', 'meal', 'meal_name']

class ResidentDashboardSerializer(serializers.ModelSerializer):
    metrics = serializers.SerializerMethodField()
    incidents = serializers.SerializerMethodField()

    class Meta:
        model = Resident
        fields = ['id', 'name', 'age', 'room_number', 'risk_level', 'metrics', 'incidents']

    def get_metrics(self, obj):
        recent = obj.metrics.order_by('-timestamp')[:5]
        return HealthMetricSerializer(recent, many=True).data

    def get_incidents(self, obj):
        recent = obj.incidents.order_by('-timestamp')[:5]
        return IncidentSerializer(recent, many=True).data


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
