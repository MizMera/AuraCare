from .models import Device, Incident
from .utils import create_notifications_for_incident


def record_fall_incident(device_id, description=''):
    try:
        device = Device.objects.select_related('zone').get(device_id=device_id)
        zone = device.zone
    except Device.DoesNotExist:
        raise ValueError(f"Device {device_id} is unknown.")

    incident = Incident.objects.create(
        zone=zone,
        type=Incident.IncidentTypeChoices.FALL,
        severity=Incident.SeverityChoices.CRITICAL,
        description=description
    )
    create_notifications_for_incident(incident)
    return incident
