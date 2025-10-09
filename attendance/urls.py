# attendance/urls.py

from django.urls import path
from .views import TeacherClassesAPIView, MarkAttendanceAPIView, StudentMonthlyAttendance

app_name = 'attendance'

urlpatterns = [
    path('classes/', TeacherClassesAPIView.as_view(), name='teacher-classes'),
    path('mark/', MarkAttendanceAPIView.as_view(), name='mark-attendance'),
    path('stats/<str:admission_number>/monthly/', StudentMonthlyAttendance.as_view(), name='student-monthly-stats'),
]