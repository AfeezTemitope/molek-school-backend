from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LoginByAdmissionView, ChangePasswordView, UpdateProfileView, ExportStudentDataView
from .views import UserViewSet, StudentViewSet, CustomTokenObtainPairView

router = DefaultRouter()
router.register(r'', UserViewSet, basename='user')
router.register(r'students', StudentViewSet, basename='student')


urlpatterns = [
    path('', include(router.urls)),
    path('login/admission/', LoginByAdmissionView.as_view(), name='login_by_admission'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('profile/update/', UpdateProfileView.as_view(), name='update_profile'),
    path('profile/export/', ExportStudentDataView.as_view(), name='export_student_data'),
]
