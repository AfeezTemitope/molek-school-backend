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
from users.student_views import (
    AcademicSessionViewSet,
    TermViewSet,
    ClassLevelViewSet,
    SubjectViewSet,
    ActiveStudentViewSet,
    CAScoreViewSet,
    ExamResultViewSet,
)

# Setup main router for ALL ViewSets
router = DefaultRouter()

# Admin Management
router.register(r'admins', AdminViewSet, basename='admin')

# Student Management System (for Admin Portal)
router.register(r'academic-sessions', AcademicSessionViewSet, basename='session')
router.register(r'terms', TermViewSet, basename='term')
router.register(r'class-levels', ClassLevelViewSet, basename='class-level')
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'students', ActiveStudentViewSet, basename='student')
router.register(r'ca-scores', CAScoreViewSet, basename='ca-score')
router.register(r'exam-results', ExamResultViewSet, basename='exam-result')


urlpatterns = [
    # Django Admin (Superadmin only)
    path('admin/', admin.site.urls),

    # JWT Authentication
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # API Router (ALL ViewSets - Admin Management + Student Management)
    path('api/', include(router.urls)),

    # User/Profile Management (profile, change-password, student login)
    path('api/users/', include('users.urls')),

    # Content Management (images, videos, news)
    path('api/', include('content.urls')),

    # Gallery Management
    path('api/galleries/', include('gallery.urls')),
]