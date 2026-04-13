import os
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
from django.db.models import Avg, Count
from django.utils import timezone
from datetime import timedelta
from .models import HealthMetric, Incident, Resident, CustomUser,MealTime, Notification,Zone
from .serializers import (
    HealthMetricIngestSerializer, 
    IncidentIngestSerializer,
    ResidentDashboardSerializer,
    IncidentSerializer,
    UserRegistrationSerializer,
    CustomTokenObtainPairSerializer,
    MealTimeSerializer, NotificationSerializer
)
from .utils import get_current_person_count
from django.http import StreamingHttpResponse
from .detection import process_frame
import cv2
class PersonCountView(views.APIView):
    """
    Retourne le nombre actuel de personnes détectées.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "count": get_current_person_count(),
            "timestamp": timezone.now()
        })
class VideoStreamView(views.APIView):
    """
    Endpoint pour le streaming vidéo avec détection YOLO.
    """
    permission_classes = []  # Ouvert pour l'affichage
    
    def get(self, request):
        cap = cv2.VideoCapture(0)
        
        def generate_frames():
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Traiter le frame avec YOLO (détection + alerte absence)
                annotated_frame = process_frame(frame)
                
                _, buffer = cv2.imencode('.jpg', annotated_frame)
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        return StreamingHttpResponse(
            generate_frames(),
            content_type='multipart/x-mixed-replace; boundary=frame'
        )
    
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class RegisterUserView(views.APIView):
    """
    Endpoint for adding/registering a new user.
    Open by default, but you might want to restrict it to IsAdminUser later.
    """
    permission_classes = [] 

    def post(self, request, *args, **kwargs):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "User registered successfully", 
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class HasAPIKey(BasePermission):
    """
    Custom permission to check for a valid API Key in the headers.
    Expects header: X-API-KEY
    """
    def has_permission(self, request, view):
        api_key = request.META.get('HTTP_X_API_KEY')
        # In a real setup, this would be validated securely against the DB or Hash
        expected_key = os.environ.get('SILVERGUARD_API_KEY', 'default-secret-key')
        return api_key == expected_key

class TelemetryIngestView(views.APIView):
    """
    Webhook for AI Telemetry data ingestion.
    POST Only, secured by API Key.
    """
    permission_classes = [HasAPIKey]

    def post(self, request, *args, **kwargs):
        serializer = HealthMetricIngestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"status": "success", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class IncidentIngestView(views.APIView):
    """
    Webhook for AI Emergency incidents ingestion.
    POST Only, secured by API Key.
    """
    permission_classes = [HasAPIKey]

    def post(self, request, *args, **kwargs):
        serializer = IncidentIngestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"status": "success", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MobileDashboardView(views.APIView):
    """
    Returns recent metrics and incidents for the assigned residents.
    GET Only, secured by JWT.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role == CustomUser.RoleChoices.FAMILY:
            residents = Resident.objects.filter(family_member=user)
        elif user.role == CustomUser.RoleChoices.CAREGIVER:
            residents = Resident.objects.filter(assigned_caregiver=user)
        elif user.role == CustomUser.RoleChoices.ADMIN:
            # Les admins voient tous les résidents
            residents = Resident.objects.all()
        else:
            return Response({"error": "Only family members and caregivers can access this dashboard endpoint."}, status=status.HTTP_403_FORBIDDEN)
        
        if not residents.exists():
            return Response({"error": "No residents assigned to your account."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ResidentDashboardSerializer(residents, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class MobileActivityLogView(views.APIView):
    """
    Returns a daily aggregated summary of incidents and telemetry.
    GET Only, secured by JWT.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role == CustomUser.RoleChoices.FAMILY:
            residents = Resident.objects.filter(family_member=user)
        elif user.role == CustomUser.RoleChoices.CAREGIVER:
            residents = Resident.objects.filter(assigned_caregiver=user)
        else:
            return Response({"error": "Forbidden: Invalid role"}, status=status.HTTP_403_FORBIDDEN)
        
        if not residents.exists():
            return Response({"error": "No residents assigned."}, status=status.HTTP_404_NOT_FOUND)
        
        # Generate summary for the first associated resident
        resident = residents.first()
        seven_days_ago = timezone.now() - timedelta(days=7)

        incidents = Incident.objects.filter(resident=resident, timestamp__gte=seven_days_ago)
        incident_counts = incidents.values('type').annotate(count=Count('id'))

        metrics = HealthMetric.objects.filter(resident=resident, timestamp__gte=seven_days_ago)
        avg_social = metrics.filter(metric_type='SOCIAL_SCORE').aggregate(Avg('value'))

        return Response({
            "resident_id": resident.id,
            "resident_name": resident.name,
            "incident_summary": list(incident_counts),
            "average_social_score_7d": avg_social.get('value__avg'),
            "recent_incidents": IncidentSerializer(incidents.order_by('-timestamp')[:10], many=True).data
        }, status=status.HTTP_200_OK)

#meriem
# ========== MEAL TIME ENDPOINTS ==========

class MealTimeListView(views.APIView):
    """Liste tous les repas (Admin/Caregiver)"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        meals = MealTime.objects.all().order_by('time')
        serializer = MealTimeSerializer(meals, many=True)
        return Response(serializer.data)

class MealTimeCreateView(views.APIView):
    """Crée un nouveau repas (Admin seulement)"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Vérifier que l'utilisateur est Admin
        if request.user.role != CustomUser.RoleChoices.ADMIN:
            return Response({"error": "Only admins can create meals"}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = MealTimeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MealTimeDetailView(views.APIView):
    """Récupère, modifie ou supprime un repas spécifique"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, meal_id):
        meal = get_object_or_404(MealTime, id=meal_id)
        serializer = MealTimeSerializer(meal)
        return Response(serializer.data)

    def put(self, request, meal_id):
        if request.user.role != CustomUser.RoleChoices.ADMIN:
            return Response({"error": "Only admins can modify meals"}, status=status.HTTP_403_FORBIDDEN)
        
        meal = get_object_or_404(MealTime, id=meal_id)
        serializer = MealTimeSerializer(meal, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, meal_id):
        if request.user.role != CustomUser.RoleChoices.ADMIN:
            return Response({"error": "Only admins can delete meals"}, status=status.HTTP_403_FORBIDDEN)
        
        meal = get_object_or_404(MealTime, id=meal_id)
        meal.delete()
        return Response({"message": "Meal deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

# ========== NOTIFICATION ENDPOINTS ==========

class NotificationListView(views.APIView):
    """Liste les notifications de l'utilisateur connecté"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        
        # Paramètre optionnel pour filtrer les non lues
        unread_only = request.query_params.get('unread', 'false').lower() == 'true'
        if unread_only:
            notifications = notifications.filter(is_read=False)
        
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)

class NotificationMarkReadView(views.APIView):
    """Marque une notification comme lue"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.mark_as_read()
        return Response({"status": "ok", "message": "Notification marked as read"})

class NotificationMarkAllReadView(views.APIView):
    """Marque toutes les notifications de l'utilisateur comme lues"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True, status='READ')
        return Response({"status": "ok", "message": f"{count} notifications marked as read"})

# ========== ABSENCE DETECTION (intégré avec Incident) ==========

class AbsenceCheckView(views.APIView):
    """
    Endpoint pour vérifier les absences aux repas.
    Appelé périodiquement par un cron job ou un scheduler.
    """
    permission_classes = [HasAPIKey]  # Sécurisé par API Key

    def post(self, request):
        from django.utils import timezone
        from datetime import timedelta
        
        current_time = timezone.now()
        # Chercher les repas dans les 30 minutes passées
        meal_time_threshold = current_time - timedelta(minutes=30)
        
        # Repas qui viennent d'avoir lieu
        meals_to_check = MealTime.objects.filter(
            time__lte=current_time.time(),
            time__gte=meal_time_threshold.time()
        )
        
        absences_detected = []
        
        for meal in meals_to_check:
            # Logique pour déterminer qui est présent (à implémenter selon votre système)
            # Pour l'exemple, on suppose que le nombre réel vient d'une caméra/IA
            actual_people = request.data.get(f'actual_people_meal_{meal.id}', meal.expected_people)
            
            if actual_people < meal.expected_people:
                # Créer un incident d'absence
                zone = meal.zone or Zone.objects.filter(name='Dining Hall').first()
                
                incident = Incident.objects.create(
                    type=Incident.IncidentTypeChoices.ABSENCE,
                    severity=Incident.SeverityChoices.MEDIUM,
                    zone=zone,
                    meal=meal,
                    description=f"Attendance issue at {meal.name}: expected {meal.expected_people}, detected {actual_people}"
                )
                
                # Créer des notifications pour les caregivers
                caregivers = CustomUser.objects.filter(role=CustomUser.RoleChoices.CAREGIVER, is_on_duty=True)
                for caregiver in caregivers:
                    Notification.objects.create(
                        message=f"⚠️ Attendance alert at {meal.name}! Expected {meal.expected_people} people, but only {actual_people} detected.",
                        notification_type=Notification.NotificationTypeChoices.ABSENCE,
                        user=caregiver,
                        incident=incident,
                        meal=meal
                    )
                
                absences_detected.append({
                    "meal_id": meal.id,
                    "meal_name": meal.name,
                    "expected": meal.expected_people,
                    "actual": actual_people,
                    "incident_id": incident.id
                })
        
        return Response({
            "status": "success",
            "absences_detected": absences_detected
        })
    
# Ajouter à la fin de core/views.py, avant les commentaires
class IncidentListView(views.APIView):
    """Liste tous les incidents (pour admin/caregiver)"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        incidents = Incident.objects.all().order_by('-timestamp')
        serializer = IncidentSerializer(incidents, many=True)
        return Response(serializer.data)