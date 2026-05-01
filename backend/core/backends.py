from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

UserModel = get_user_model()

class EmailBackend(ModelBackend):
    """
    Custom authentication backend to allow users to log in using their email address.
    Django REST Framework's SimpleJWT relies on Django's authenticate() method under the hood.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        
        try:
            # Attempt to fetch user by email
            user = UserModel.objects.get(email=username)
        except UserModel.DoesNotExist:
            # Fallback to standard username
            try:
                user = UserModel.objects.get(username=username)
            except UserModel.DoesNotExist:
                return None
        
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
