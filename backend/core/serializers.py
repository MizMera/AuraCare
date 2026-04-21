from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
try:
    from .fall_incident import record_fall_incident
except ImportError:
    record_fall_incident = None
from .models import Device, HealthMetric, Incident, Resident, Zone, CustomUser

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
        if record_fall_incident is None:
            raise serializers.ValidationError('Fall incident service is not available.')
        return record_fall_incident(
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

    class Meta:
        model = Incident
        fields = ['id', 'type', 'type_display', 'severity', 'severity_display', 'description', 'timestamp', 'zone']

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
