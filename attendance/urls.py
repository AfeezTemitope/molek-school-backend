# attendance/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TeacherClassesAPIView, MarkAttendanceAPIView, student_monthly_attendance

urlpatterns = [
    path('classes/', TeacherClassesAPIView.as_view(), name='teacher-classes'),
    path('mark/', MarkAttendanceAPIView.as_view(), name='mark-attendance'),
    path('stats/<str:admission_number>/monthly/', student_monthly_attendance, name='monthly-stats'),
]