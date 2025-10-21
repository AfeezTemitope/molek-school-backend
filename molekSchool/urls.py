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
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import UserProfileViewSet, StudentViewSet, csrf
from content.views import ContentItemViewSet

router = DefaultRouter()
router.register(r'userprofile', UserProfileViewSet)
router.register(r'contentitem', ContentItemViewSet)
router.register(r'students', StudentViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/csrf/", csrf),

    path('api/', include(router.urls)),
    path('molek/', include('content.urls')),
    path('molek/users/', include('users.urls')),

]
