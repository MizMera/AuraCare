from .models import Device, Incident


def record_fall_incident(device_id: str, description: str = "") -> Incident:
    """Create a fall incident: zone from Device.zone; resident always unset."""
    device = Device.objects.get(device_id=device_id)
    return Incident.objects.create(
        resident=None,
        zone=device.zone,
        type=Incident.IncidentTypeChoices.FALL,
        severity=Incident.SeverityChoices.CRITICAL,
        description=description or "",
    )
