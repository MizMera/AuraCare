from django.utils import timezone

from .models import CustomUser, HealthMetric, Incident, MealTime, Notification


def build_chatbot_documents_for_user(user, residents_qs):
    resident_ids = list(residents_qs.values_list('id', flat=True))
    total_residents = residents_qs.model.objects.count()
    accessible_residents = residents_qs.count()

    incidents_qs = Incident.objects.order_by('-timestamp')
    metrics_qs = HealthMetric.objects.order_by('-timestamp')
    meals_qs = MealTime.objects.order_by('time')
    notifications_qs = Notification.objects.filter(user=user).order_by('-created_at')

    if user.role != CustomUser.RoleChoices.ADMIN:
        incidents_qs = incidents_qs.filter(resident_id__in=resident_ids)
        metrics_qs = metrics_qs.filter(resident_id__in=resident_ids)

    documents = [
        f"Global resident count in facility: {total_residents}.",
        f"Resident records accessible to current user: {accessible_residents}.",
    ]

    for resident in residents_qs[:100]:
        documents.append(
            f"Resident profile: name={resident.name}, room={resident.room_number}, age={resident.age}, "
            f"risk={resident.risk_level}."
        )

    for incident in incidents_qs[:250]:
        resident_name = incident.resident.name if incident.resident else "Unknown resident"
        zone_name = incident.zone.name if incident.zone else "Unknown zone"
        documents.append(
            f"Incident event: resident={resident_name}, type={incident.type}, severity={incident.severity}, "
            f"zone={zone_name}, time={timezone.localtime(incident.timestamp).strftime('%Y-%m-%d %H:%M')}, "
            f"description={incident.description or 'No details'}."
        )

    for metric in metrics_qs[:250]:
        resident_name = metric.resident.name if metric.resident else "Unknown resident"
        zone_name = metric.zone.name if metric.zone else "Unknown zone"
        documents.append(
            f"Health metric: resident={resident_name}, metric_type={metric.metric_type}, value={metric.value}, "
            f"zone={zone_name}, time={timezone.localtime(metric.timestamp).strftime('%Y-%m-%d %H:%M')}."
        )

    for meal in meals_qs[:100]:
        zone_name = meal.zone.name if meal.zone else "Unknown zone"
        documents.append(
            f"Meal schedule: meal={meal.name}, time={meal.time.strftime('%H:%M')}, zone={zone_name}, "
            f"expected_people={meal.expected_people}."
        )

    for notification in notifications_qs[:250]:
        incident_type = notification.incident.type if notification.incident else "NONE"
        documents.append(
            f"Notification: type={notification.notification_type}, linked_incident={incident_type}, "
            f"is_read={notification.is_read}, created={timezone.localtime(notification.created_at).strftime('%Y-%m-%d %H:%M')}, "
            f"message={notification.message}"
        )

    return documents
