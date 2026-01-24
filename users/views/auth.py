"""
MOLEK School - Authentication Views
JWT authentication for admin users
"""
from rest_framework_simplejwt.views import TokenObtainPairView
from ..serializers import CustomTokenObtainPairSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT authentication for admin users.
    
    Returns additional user information in the token response.
    """
    serializer_class = CustomTokenObtainPairSerializer