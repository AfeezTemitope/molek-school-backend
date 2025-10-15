from django.urls import path
from .views import TeacherClassesAPIView, MarkAttendanceAPIView, StudentMonthlyAttendance, TeacherAttendanceReport, \
    CheckAttendanceAPIView, StudentsByClassAPIView

app_name = 'attendance'


urlpatterns = [
    path('classes/', TeacherClassesAPIView.as_view(), name='teacher-classes'),
    path('mark/', MarkAttendanceAPIView.as_view(), name='mark-attendance'),
    path('stats/<str:admission_number>/monthly/', StudentMonthlyAttendance.as_view(), name='student-monthly-stats'),
    path('report/', TeacherAttendanceReport.as_view(), name='teacher-report'),
    path('check/', CheckAttendanceAPIView.as_view(), name='check-attendance'),
    path('users/students/by-class/', StudentsByClassAPIView.as_view(), name='students-by-class'),
]