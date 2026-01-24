"""
MOLEK School - Users App URL Configuration
"""
from django.urls import path

from .views import (
    # Auth
    CustomTokenObtainPairView,
    
    # Admin
    ProfileView,
    ChangePasswordView,
    
    # Score management
    bulk_upload_ca_scores,
    bulk_upload_exam_results,
    get_ca_scores,
    get_exam_results,
    
    # Promotion
    get_promotion_data,
    promote_students,
    
    # Portal
    StudentLoginView,
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
    # ==============================================================================
    # ADMIN ROUTES
    # ==============================================================================
    
    # Admin Authentication
    path('login/', CustomTokenObtainPairView.as_view(), name='admin-login'),
    
    # Admin Profile Management
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/change-password/', ChangePasswordView.as_view(), name='change-password'),
    
    # ==============================================================================
    # STUDENT PORTAL ROUTES
    # ==============================================================================
    
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
    path('student/<str:admission_number>/results/', StudentExamResultsView.as_view(), name='student-results'),
    
    # ==============================================================================
    # SCORE MANAGEMENT ROUTES
    # ==============================================================================
    
    # CA + Theory Score Management
    path('ca-scores/', get_ca_scores, name='ca-scores'),
    path('ca-scores/bulk-upload/', bulk_upload_ca_scores, name='ca-scores-bulk-upload'),
    
    # Exam Results
    path('exam-results/', get_exam_results, name='exam-results'),
    path('exam-results/bulk-upload/', bulk_upload_exam_results, name='exam-results-bulk-upload'),
    
    # ==============================================================================
    # PROMOTION ROUTES
    # ==============================================================================
    
    path('promotion/', get_promotion_data, name='promotion-data'),
    path('promotion/promote/', promote_students, name='promote-students'),
]