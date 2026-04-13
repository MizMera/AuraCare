# detection/utils.py
from datetime import timedelta
from django.utils import timezone
from core.models import MealTime, Incident, Notification, CustomUser, Zone

# Variables globales
current_person_count = 0
alert_sent_for_meal = {}  # Dictionnaire pour suivre les alertes envoyées

def update_person_count(count):
    global current_person_count
    current_person_count = count

def get_current_person_count():
    return current_person_count

def get_current_meal():
    """Retourne le repas qui doit être vérifié (15 min après)"""
    now = timezone.localtime()
    now_minutes = now.hour * 60 + now.minute
    

    for meal in MealTime.objects.all():
        meal_minutes = meal.time.hour * 60 + meal.time.minute
        
        # POUR TESTER: 1 minute
        alert_time_minutes = meal_minutes + 1
        
        if alert_time_minutes >= 1440:
            alert_time_minutes -= 1440

        if now_minutes == alert_time_minutes:
            return meal
    
    return None

def check_absence_alert(nb_personnes, frame=None):
    """Vérifie et crée une alerte UNIQUEMENT à l'heure exacte"""
    global current_person_count, alert_sent_for_meal
    current_person_count = nb_personnes
    
    meal = get_current_meal()
    if not meal:
        return None
    
    # Vérifier si une alerte a déjà été envoyée pour ce repas
    meal_id_key = f"meal_{meal.id}"
    if alert_sent_for_meal.get(meal_id_key, False):
        return None  # Déjà envoyée, on ignore
    
    expected = meal.expected_people
    
    # Créer l'incident (même si assez de personnes, on log)
    zone = meal.zone
    if not zone:
        zone, _ = Zone.objects.get_or_create(name="Dining Room", defaults={
            'type': 'SOCIAL',
            'floor_type': 'TILE'
        })
    
    missing_count = max(0, expected - nb_personnes)
    
    # Créer l'incident (toujours, pour tracer)
    incident = Incident.objects.create(
        type=Incident.IncidentTypeChoices.ABSENCE,
        severity=Incident.SeverityChoices.MEDIUM if missing_count > 0 else Incident.SeverityChoices.LOW,
        zone=zone,
        meal=meal,
        description=f"{meal.name}: {nb_personnes}/{expected} personnes - Alerte à {timezone.localtime().strftime('%H:%M')}"
    )
    
    # Si des personnes manquent, envoyer des notifications
    if missing_count > 0:
        users = CustomUser.objects.filter(
            role__in=[CustomUser.RoleChoices.CAREGIVER, CustomUser.RoleChoices.ADMIN]
        )
        
        for user in users:
            Notification.objects.create(
                message=f"⚠️ ALERTE: {missing_count} personne(s) absente(s) au {meal.name}! (Détecté: {nb_personnes}/{expected})",
                notification_type='ABSENCE',
                user=user,
                incident=incident,
                meal=meal
            )
        
        print(f"📢 ALERTE ENVOYÉE à {timezone.localtime().strftime('%H:%M')}: {missing_count} absents au {meal.name}")
    else:
        print(f"✅ CHECK à {timezone.localtime().strftime('%H:%M')}: {meal.name} complet ({nb_personnes}/{expected})")
    
    # Marquer l'alerte comme envoyée pour ce repas
    alert_sent_for_meal[meal_id_key] = True
    
    return incident