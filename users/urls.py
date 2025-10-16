from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomTokenObtainPairView,
    UserViewSet,
    StudentViewSet,
    LoginStudentView,
    get_students_by_class,
    UpdateProfileView,
    ExportStudentDataView,
    ChangePasswordView,
)

app_name = 'users'

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'students', StudentViewSet, basename='student')

urlpatterns = [
    path('', include(router.urls)),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/student/', LoginStudentView.as_view(), name='login-student'),
    path('students/by-class/', get_students_by_class, name='students-by-class'),
    path('profile/update/', UpdateProfileView.as_view(), name='update-profile'),
    path('profile/export/', ExportStudentDataView.as_view(), name='export-student-data'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
]