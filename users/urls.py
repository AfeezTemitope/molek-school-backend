from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LoginByAdmissionView
from .views import UserViewSet, StudentViewSet, CustomTokenObtainPairView

router = DefaultRouter()
router.register(r'', UserViewSet, basename='user')
router.register(r'students', StudentViewSet, basename='student')


urlpatterns = [
    path('', include(router.urls)),
    path('login/admission/', LoginByAdmissionView.as_view(), name='login_by_admission'),
]