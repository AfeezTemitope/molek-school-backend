from django.urls import path
from .views import (
    CustomTokenObtainPairView,
    LoginStudentView,
    get_students_by_class,
    UpdateProfileView,
    ExportStudentDataView,
    ChangePasswordView,
)

app_name = 'users'

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/student/', LoginStudentView.as_view(), name='login-student'),
    path('students/by-class/', get_students_by_class, name='students-by-class'),  # Optional: deprecate if using ViewSet filters
    path('profile/update/', UpdateProfileView.as_view(), name='update-profile'),
    path('profile/export/', ExportStudentDataView.as_view(), name='export-student-data'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
]