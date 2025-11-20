"""
URL configuration for molekSchool project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
"""
URL configuration for molekSchool project.
Cleaned and optimized for admin-only backend.
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from users.views import AdminViewSet, CustomTokenObtainPairView

# Setup router for ViewSets
router = DefaultRouter()
router.register(r'admins', AdminViewSet, basename='admin')

urlpatterns = [
    # Django Admin (Superadmin only)
    path('admin/', admin.site.urls),

    # JWT Authentication
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # API Router (Admin Management)
    path('api/', include(router.urls)),

    # User/Profile Management
    path('api/users/', include('users.urls')),

    # Content Management (images, videos, news)
    path('api/', include('content.urls')),

    # Gallery Management
    path('api/galleries/', include('gallery.urls')),
]