from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenRefreshView
from core.views import CustomTokenObtainPairView, RegisterUserView

def api_root_view(request):
    return JsonResponse({
        "message": "Welcome to the AuraCare API Backend.",
        "note": "The React frontend typically runs on a different port (e.g., http://localhost:5173). API endpoints are at /api/ and admin is at /admin/"
    })

urlpatterns = [
    path('', api_root_view, name='api_root'),
    path('admin/', admin.site.urls),
    
    # Core API Endpoints
    path('api/', include('core.urls')),
    
    # Authentication endpoints for Flutter
    path('api/auth/register/', RegisterUserView.as_view(), name='register_user'),
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
