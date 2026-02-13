"""MOLEK School - Views Module"""
from .auth import CustomTokenObtainPairView
from .admin import AdminViewSet, ProfileView, ChangePasswordView
from .academic import AcademicSessionViewSet, TermViewSet, ClassLevelViewSet, SubjectViewSet
from .student import ActiveStudentViewSet
from .score import CAScoreViewSet, ExamResultViewSet, bulk_upload_ca_scores, bulk_upload_exam_results, get_ca_scores, get_exam_results
from .promotion import get_promotion_data, promote_students, get_promotion_rules, save_promotion_rules, get_all_subjects
from .portal import (
    StudentLoginView, StudentProfileView, StudentChangePasswordView,
    StudentDashboardStatsView, StudentGradesView, StudentCAScoresView,
    StudentExamResultsView, StudentReportCardView, StudentSessionsView, StudentTermsView,
)

__all__ = [
    'CustomTokenObtainPairView',
    'AdminViewSet', 'ProfileView', 'ChangePasswordView',
    'AcademicSessionViewSet', 'TermViewSet', 'ClassLevelViewSet', 'SubjectViewSet',
    'ActiveStudentViewSet',
    'CAScoreViewSet', 'ExamResultViewSet', 'bulk_upload_ca_scores', 'bulk_upload_exam_results', 'get_ca_scores', 'get_exam_results',
    'get_promotion_data', 'promote_students', 'get_promotion_rules', 'save_promotion_rules', 'get_all_subjects',
    'StudentLoginView', 'StudentProfileView', 'StudentChangePasswordView',
    'StudentDashboardStatsView', 'StudentGradesView', 'StudentCAScoresView',
    'StudentExamResultsView', 'StudentReportCardView', 'StudentSessionsView', 'StudentTermsView',
]