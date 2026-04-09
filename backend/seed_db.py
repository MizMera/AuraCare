import os
import django
import random
from datetime import timedelta, datetime
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from core.models import CustomUser, Resident, Zone, Device, HealthMetric, Incident

def run_seed():
    print("Flushing DB...")
    # Basic flush 
    HealthMetric.objects.all().delete()
    Incident.objects.all().delete()
    Device.objects.all().delete()
    Resident.objects.all().delete()
    Zone.objects.all().delete()
    CustomUser.objects.all().delete()

    print("Creating Family User: family@auracare.com...")
    family_user = CustomUser.objects.create_user(
        username="family_smith",
        email="family@auracare.com",
        password="auracare2026",
        role=CustomUser.RoleChoices.FAMILY
    )

    admin_user = CustomUser.objects.create_superuser(
        username="admin",
        email="admin@auracare.com",
        password="admin"
    )

    print("Creating Zones & Devices...")
    zone_living = Zone.objects.create(name="Central Living Room", type="Public Connect")
    zone_dining = Zone.objects.create(name="Dining Hall", type="Public Dining")
    
    Device.objects.create(device_id="CAM_LIVING_01", zone=zone_living, type="CAMERA")
    Device.objects.create(device_id="MIC_LIVING_01", zone=zone_living, type="MIC")

    print("Creating Resident: John Smith...")
    resident = Resident.objects.create(
        name="John Smith",
        age=82,
        room_number="214-B",
        risk_level=Resident.RiskLevelChoices.MEDIUM,
        family_member=family_user
    )

    print("Seeding Dummy Health Metrics (7 Days)...")
    now = timezone.now()
    
    # Generate 5 metrics per day
    for day in range(7):
        target_date = now - timedelta(days=day)
        for i in range(5):
            h_time = target_date - timedelta(hours=random.randint(1, 10))
            
            # Gait Speed (average 0.9m/s)
            HealthMetric.objects.create(
                resident=resident, zone=zone_living, metric_type="GAIT_SPEED", value=round(random.uniform(0.6, 1.1), 2)
            ).timestamp = h_time
            
            # Social Score (out of 100)
            HealthMetric.objects.create(
                resident=resident, zone=zone_living, metric_type="SOCIAL_SCORE", value=round(random.uniform(50, 95), 2)
            ).timestamp = h_time
            
            HealthMetric.objects.filter(id__in=[HealthMetric.objects.last().id]).update(timestamp=h_time)

    print("Seeding Incidents...")
    # Fall Incident 2 days ago
    inc_fall = Incident.objects.create(
        resident=resident, zone=zone_living, 
        type="FALL", severity="CRITICAL", 
        description="YOLO mapped rapid horizontal descent near sofa."
    )
    inc_fall.timestamp = now - timedelta(days=2)
    inc_fall.save()
    
    inc_wand = Incident.objects.create(
        resident=resident, zone=zone_dining, 
        type="WANDERING", severity="MEDIUM", 
        description="Movement detected at 3 AM outside safe parameters."
    )
    inc_wand.timestamp = now - timedelta(hours=14)
    inc_wand.save()

    print("Database seeding completed successfully.")

if __name__ == '__main__':
    run_seed()
