from .models import Device, Incident

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
    return incident
