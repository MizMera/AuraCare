from django.utils import timezone

from .models import CustomUser, Incident, MealTime, Notification, Zone

current_person_count = 0
alert_sent_for_meal = {}


def create_notifications_for_incident(incident):
    recipients = CustomUser.objects.filter(
        role__in=[CustomUser.RoleChoices.CAREGIVER, CustomUser.RoleChoices.ADMIN]
    )
    incident_label = incident.get_type_display() if hasattr(incident, 'get_type_display') else 'Incident'
    zone_name = incident.zone.name if getattr(incident, 'zone', None) else 'Unknown zone'
    description = incident.description or f'{incident_label} detected.'

    for user in recipients:
        Notification.objects.create(
            message=f"{incident_label} in {zone_name}: {description}",
            notification_type=Notification.NotificationTypeChoices.INCIDENT,
            status=Notification.StatusChoices.SENT,
            user=user,
            incident=incident,
            meal=getattr(incident, 'meal', None),
            resident=getattr(incident, 'resident', None),
        )


def update_person_count(count):
    global current_person_count
    current_person_count = int(count)


def get_current_person_count():
    return current_person_count


def get_current_meal():
    now = timezone.localtime()
    now_minutes = now.hour * 60 + now.minute

    for meal in MealTime.objects.all():
        meal_minutes = meal.time.hour * 60 + meal.time.minute
        alert_time_minutes = meal_minutes + 1
        if alert_time_minutes >= 1440:
            alert_time_minutes -= 1440
        if now_minutes == alert_time_minutes:
            return meal
    return None


def check_absence_alert(nb_personnes, _frame=None):
    global current_person_count, alert_sent_for_meal
    current_person_count = int(nb_personnes)

    meal = get_current_meal()
    if not meal:
        return None

    meal_id_key = f"meal_{meal.id}"
    if alert_sent_for_meal.get(meal_id_key, False):
        return None

    expected = meal.expected_people
    zone = meal.zone
    if not zone:
        zone, _ = Zone.objects.get_or_create(
            name="Dining Room",
            defaults={'type': 'SOCIAL', 'floor_type': 'TILE'},
        )

    missing_count = max(0, expected - nb_personnes)
    
    # Création de l'incident
    incident = Incident.objects.create(
        type=Incident.IncidentTypeChoices.ABSENCE,
        severity=Incident.SeverityChoices.MEDIUM if missing_count > 0 else Incident.SeverityChoices.LOW,
        zone=zone,
        meal=meal,
        description=(
            f"{meal.name}: {nb_personnes}/{expected} residents present - "
            f"Checked at {timezone.localtime().strftime('%H:%M')}"
        ),
    )

    if missing_count > 0:
        users = CustomUser.objects.filter(
            role__in=[CustomUser.RoleChoices.CAREGIVER, CustomUser.RoleChoices.ADMIN]
        )
        
        # Message professionnel
        if missing_count == 1:
            message = (
                f"Attendance Alert – {meal.name}\n"
                f"• {missing_count} resident is missing\n"
                f"• Present: {nb_personnes}/{expected}\n"
                f"• Location: {zone.name}"
            )
        else:
            message = (
                f"Attendance Alert – {meal.name}\n"
                f"• {missing_count} residents are missing\n"
                f"• Present: {nb_personnes}/{expected}\n"
                f"• Location: {zone.name}"
            )
        
        for user in users:
            Notification.objects.create(
                message=message,
                notification_type=Notification.NotificationTypeChoices.ABSENCE,
                status=Notification.StatusChoices.SENT,
                user=user,
                incident=incident,
                meal=meal,
            )
        
        print(f" [ATTENDANCE] {meal.name}: {missing_count} absent, {nb_personnes}/{expected} present")

    alert_sent_for_meal[meal_id_key] = True
    return incident