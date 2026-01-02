from django.urls import path

from .views import (
    CustomTokenObtainPairView,
    ProfileView,
    ChangePasswordView,
)
from .student_views import (
    StudentLoginView,
    StudentResultsView,
    #Additional student portal views
    StudentProfileView,
    StudentChangePasswordView,
    StudentGradesView,
    StudentCAScoresView,
    StudentExamResultsView,
    StudentReportCardView,
    StudentSessionsView,
    StudentTermsView,
)

app_name = 'users'

urlpatterns = [
    # ============================================
    # ADMIN ROUTES
    # ============================================
    # Admin Authentication
    path('login/', CustomTokenObtainPairView.as_view(), name='admin-login'),

    # Admin Profile Management
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/change-password/', ChangePasswordView.as_view(), name='change-password'),

    # ============================================
    # STUDENT PORTAL ROUTES
    # ============================================
    # Authentication
    path('student-portal/login/', StudentLoginView.as_view(), name='student-login'),

    # Profile & Account
    path('student-portal/profile/', StudentProfileView.as_view(), name='student-profile'),
    path('student-portal/change-password/', StudentChangePasswordView.as_view(), name='student-change-password'),

    # Academic Records
    path('student-portal/grades/', StudentGradesView.as_view(), name='student-grades'),
    path('student-portal/ca-scores/', StudentCAScoresView.as_view(), name='student-ca-scores'),
    path('student-portal/exam-results/', StudentExamResultsView.as_view(), name='student-exam-results'),
    path('student-portal/report-card/', StudentReportCardView.as_view(), name='student-report-card'),

    # Academic Setup
    path('student-portal/sessions/', StudentSessionsView.as_view(), name='student-sessions'),
    path('student-portal/terms/', StudentTermsView.as_view(), name='student-terms'),

    # Legacy route (keep for backwards compatibility)
    path('student/<str:admission_number>/results/', StudentResultsView.as_view(), name='student-results'),
]