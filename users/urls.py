from django.urls import path
from .views import (
    CustomTokenObtainPairView,
    ProfileView,
    ChangePasswordView,
)

app_name = 'users'

urlpatterns = [
    # Authentication
    path('login/', CustomTokenObtainPairView.as_view(), name='admin-login'),

    # Profile Management
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/change-password/', ChangePasswordView.as_view(), name='change-password'),
]