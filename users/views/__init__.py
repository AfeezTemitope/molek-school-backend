"""
MOLEK School - Views Module
All views are organized into separate files for better maintainability.
"""

# Authentication Views
from .auth import (
    CustomTokenObtainPairView,
)

# Admin Management Views
from .admin import (
    AdminViewSet,
    ProfileView,
    ChangePasswordView,
)

# Academic Management Views
from .academic import (
    AcademicSessionViewSet,
    TermViewSet,
    ClassLevelViewSet,
    SubjectViewSet,
)

# Student Management Views
from .student import (
    ActiveStudentViewSet,
)

# Score Management Views
from .score import (
    CAScoreViewSet,
    ExamResultViewSet,
    bulk_upload_ca_scores,
    bulk_upload_exam_results,
    get_ca_scores,
    get_exam_results,
)

# Promotion Views
from .promotion import (
    get_promotion_data,
    promote_students,
)

# Student Portal Views
from .portal import (
    StudentLoginView,
    StudentProfileView,
    StudentChangePasswordView,
    StudentDashboardStatsView,  # Added this import
    StudentGradesView,
    StudentCAScoresView,
    StudentExamResultsView,
    StudentReportCardView,
    StudentSessionsView,
    StudentTermsView,
)

__all__ = [
    # Auth
    'CustomTokenObtainPairView',
    
    # Admin
    'AdminViewSet',
    'ProfileView',
    'ChangePasswordView',
    
    # Academic
    'AcademicSessionViewSet',
    'TermViewSet',
    'ClassLevelViewSet',
    'SubjectViewSet',
    
    # Student
    'ActiveStudentViewSet',
    
    # Score
    'CAScoreViewSet',
    'ExamResultViewSet',
    'bulk_upload_ca_scores',
    'bulk_upload_exam_results',
    'get_ca_scores',
    'get_exam_results',
    
    # Promotion
    'get_promotion_data',
    'promote_students',
    
    # Portal
    'StudentLoginView',
    'StudentProfileView',
    'StudentChangePasswordView',
    'StudentDashboardStatsView',  # Added this export
    'StudentGradesView',
    'StudentCAScoresView',
    'StudentExamResultsView',
    'StudentReportCardView',
    'StudentSessionsView',
    'StudentTermsView',
]