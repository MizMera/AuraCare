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

    print("Creating Admin...")
    admin_user = CustomUser.objects.create_superuser(
        username="admin",
        email="admin@auracare.com",
        password="admin"
    )

    print("Creating Family Users...")
    family_users = []
    for i in range(1, 6):
        fam = CustomUser.objects.create_user(
            username=f"family_member_{i}",
            email=f"family{i}@auracare.com",
            password="familypassword!",
            role=CustomUser.RoleChoices.FAMILY
        )
        family_users.append(fam)

    print("Creating Caregiver Staff...")
    caregivers = []
    # Primary test caregiver
    caregiver_main = CustomUser.objects.create_user(
        username="caregiver_jane",
        email="caregiver@auracare.com",
        password="caregiver2026",
        role=CustomUser.RoleChoices.CAREGIVER
    )
    caregivers.append(caregiver_main)
    # Other caregivers
    for i in range(2, 5):
        cg = CustomUser.objects.create_user(
            username=f"caregiver_{i}",
            email=f"caregiver{i}@auracare.com",
            password="caregiverpassword!",
            role=CustomUser.RoleChoices.CAREGIVER
        )
        caregivers.append(cg)

    print("Creating Zones & Devices...")
    zones = [
        Zone.objects.create(name="Central Living Room", type="Public Connect"),
        Zone.objects.create(name="Dining Hall", type="Public Dining"),
        Zone.objects.create(name="Garden Array", type="Outdoor Secure"),
        Zone.objects.create(name="East Wing Corridor", type="Hallway"),
    ]
    
    for i, zone in enumerate(zones):
        Device.objects.create(device_id=f"CAM_{i+1:02d}", zone=zone, type="CAMERA")
        Device.objects.create(device_id=f"MIC_{i+1:02d}", zone=zone, type="MIC")

    resident_names = [
        "John Smith", "Alice Abernathy", "Eleanor Rigby", 
        "Margaret Hamilton", "George Washington", "Robert Chase",
        "Martha Stewart", "Thomas Edison", "Rosa Parks"
    ]
    
    risks = [Resident.RiskLevelChoices.LOW, Resident.RiskLevelChoices.MEDIUM, Resident.RiskLevelChoices.HIGH]

    print("Creating Residents and Generating Health & Incident Data...")
    now = timezone.now()

    for idx, name in enumerate(resident_names):
        assigned_cg = caregivers[0] if idx < 4 else random.choice(caregivers) # Give the first 4 to caregiver_main
        resident = Resident.objects.create(
            name=name,
            age=random.randint(65, 95),
            room_number=f"{random.randint(1,4)}0{random.randint(1,9)}",
            risk_level=random.choice(risks),
            family_member=random.choice(family_users),
            assigned_caregiver=assigned_cg
        )
        
        # 7 Days of Health Metrics
        for day in range(7):
            target_date = now - timedelta(days=day)
            for i in range(3):
                h_time = target_date - timedelta(hours=random.randint(1, 10))
                
                # Gait Speed (average ~0.8m/s)
                HealthMetric.objects.create(
                    resident=resident, zone=random.choice(zones), metric_type="GAIT_SPEED", value=round(random.uniform(0.5, 1.0), 2)
                ).timestamp = h_time
                
                # Social Score (out of 100)
                HealthMetric.objects.create(
                    resident=resident, zone=random.choice(zones), metric_type="SOCIAL_SCORE", value=round(random.uniform(40, 90), 2)
                ).timestamp = h_time
                
                HealthMetric.objects.filter(id=HealthMetric.objects.last().id).update(timestamp=h_time)

        # Generating some occasional incidents
        if resident.risk_level in [Resident.RiskLevelChoices.MEDIUM, Resident.RiskLevelChoices.HIGH]:
            # Generate 1 to 3 incidents
            for _ in range(random.randint(1, 3)):
                inc_types = ["FALL", "FALL_RISK", "AGGRESSION", "WANDERING", "ABSENCE", "DISTRESS_CRY", "CARDIAC"]
                severities = ["CRITICAL", "HIGH", "MEDIUM"]
                inc = Incident.objects.create(
                    resident=resident, 
                    zone=random.choice(zones), 
                    type=random.choice(inc_types), 
                    severity=random.choice(severities), 
                    description=random.choice([
                        "Unusual pattern detected by primary camera.",
                        "Audio threshold exceeded for distress signature.",
                        "Subject crossed virtual perimeter.",
                        "Rapid descent tracked on visual feed.",
                        "Elevated heart rate inferred from vitals monitor."
                    ])
                )
                inc.timestamp = now - timedelta(days=random.randint(0, 6), hours=random.randint(1, 23))
                inc.save()

    print("Database seeding completed successfully.")

if __name__ == '__main__':
    run_seed()
