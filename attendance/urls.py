from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AttendanceViewSet

router = DefaultRouter()
router.register(r'classes', AttendanceViewSet, basename='teacher-classes')
router.register(r'mark', AttendanceViewSet, basename='mark-attendance')

urlpatterns = [
    # Main route: /molek/attendance/
    path('', include(router.urls)),

    # Custom URL for stats (not handled by router)
    path('stats/<str:admission_number>/',
         AttendanceViewSet.as_view({'get': 'student_stats'}), name='student-attendance-stats'),
]