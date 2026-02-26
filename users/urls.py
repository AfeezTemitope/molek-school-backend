"""MOLEK School - Users App URL Configuration"""
from django.urls import path
from django.http import JsonResponse
from django.db.models import Count
from .views import (
    CustomTokenObtainPairView, ProfileView, ChangePasswordView,
    bulk_upload_ca_scores, bulk_upload_exam_results, get_ca_scores, get_exam_results,
    get_promotion_data, promote_students, get_promotion_rules, save_promotion_rules, get_all_subjects,
    StudentLoginView, StudentProfileView, StudentChangePasswordView,
    StudentDashboardStatsView, StudentGradesView, StudentCAScoresView,
    StudentExamResultsView, StudentReportCardView, StudentSessionsView, StudentTermsView,
)


# TEMPORARY DEBUG - Remove after checking
def debug_check_dupes(request):
    from .models import Subject, ActiveStudent, ExamResult
    
    dupes = []
    for d in Subject.objects.values('name').annotate(count=Count('id')).filter(count__gt=1):
        entries = []
        for s in Subject.objects.filter(name=d['name']):
            entries.append({
                'id': s.id, 'code': s.code, 'active': s.is_active,
                'results': ExamResult.objects.filter(subject=s).count()
            })
        dupes.append({'name': d['name'], 'count': d['count'], 'entries': entries})
    
    all_subjects = [
        {'id': s.id, 'name': s.name, 'code': s.code, 'active': s.is_active,
         'results': ExamResult.objects.filter(subject=s).count()}
        for s in Subject.objects.all().order_by('name')
    ]
    
    students = {
        'total': ActiveStudent.objects.count(),
        'active': ActiveStudent.objects.filter(is_active=True).count(),
        'inactive': ActiveStudent.objects.filter(is_active=False).count(),
    }
    
    # Check for duplicate ExamResults (same student + subject + session + term)
    duplicate_results = ExamResult.objects.values(
        'student__admission_number', 'subject__name', 'session__name', 'term__name'
    ).annotate(count=Count('id')).filter(count__gt=1)
    
    dupe_results = [
        {
            'student': d['student__admission_number'],
            'subject': d['subject__name'],
            'session': d['session__name'],
            'term': d['term__name'],
            'count': d['count'],
        }
        for d in duplicate_results
    ]
    
    # Show all Math results to see what's going on
    math_results = [
        {
            'id': r.id,
            'student': r.student.admission_number,
            'subject': r.subject.name,
            'session': r.session.name,
            'term': r.term.name,
            'total': float(r.total_score),
            'grade': r.grade,
        }
        for r in ExamResult.objects.filter(subject__name='Mathematics').select_related(
            'student', 'subject', 'session', 'term'
        ).order_by('student__admission_number', 'term__name')
    ]
    
    return JsonResponse({
        'duplicates': dupes,
        'all_subjects': all_subjects,
        'students': students,
        'duplicate_results': dupe_results,
        'math_results': math_results,
    })
def debug_cleanup_inactive(request):
        from .models import ActiveStudent, ExamResult
        
        if request.GET.get('confirm') != 'yes':
            inactive = ActiveStudent.objects.filter(is_active=False)
            return JsonResponse({
                'warning': 'This will permanently delete inactive students',
                'inactive_count': inactive.count(),
                'inactive_students': [
                    {'id': s.id, 'adm': s.admission_number, 'name': s.full_name}
                    for s in inactive[:50]
                ],
                'action': 'Add ?confirm=yes to URL to delete them'
            })
        
        inactive = ActiveStudent.objects.filter(is_active=False)
        count = inactive.count()
        # Delete their exam results first, then the students
        ExamResult.objects.filter(student__is_active=False).delete()
        inactive.delete()
        
        return JsonResponse({
            'deleted': count,
            'remaining_total': ActiveStudent.objects.count(),
            'remaining_active': ActiveStudent.objects.filter(is_active=True).count(),
        })


app_name = 'users'

urlpatterns = [
    # TEMPORARY DEBUG - Remove after checking
    path('debug/check-dupes/', debug_check_dupes, name='debug-check-dupes'),
    path('debug/cleanup-inactive/', debug_cleanup_inactive, name='debug-cleanup'),
    
    # ADMIN
    path('login/', CustomTokenObtainPairView.as_view(), name='admin-login'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/change-password/', ChangePasswordView.as_view(), name='change-password'),
    # STUDENT PORTAL
    path('student-portal/login/', StudentLoginView.as_view(), name='student-login'),
    path('student-portal/profile/', StudentProfileView.as_view(), name='student-profile'),
    path('student-portal/change-password/', StudentChangePasswordView.as_view(), name='student-change-password'),
    path('student-portal/dashboard-stats/', StudentDashboardStatsView.as_view(), name='student-dashboard-stats'),
    path('student-portal/report-card/', StudentReportCardView.as_view(), name='student-report-card'),
    path('student-portal/grades/', StudentGradesView.as_view(), name='student-grades'),
    path('student-portal/ca-scores/', StudentCAScoresView.as_view(), name='student-ca-scores'),
    path('student-portal/exam-results/', StudentExamResultsView.as_view(), name='student-exam-results'),
    path('student-portal/sessions/', StudentSessionsView.as_view(), name='student-sessions'),
    path('student-portal/terms/', StudentTermsView.as_view(), name='student-terms'),
    path('student/<str:admission_number>/results/', StudentExamResultsView.as_view(), name='student-results'),
    # SCORES
    path('ca-scores/', get_ca_scores, name='ca-scores'),
    path('ca-scores/bulk-upload/', bulk_upload_ca_scores, name='ca-scores-bulk-upload'),
    path('exam-results/', get_exam_results, name='exam-results'),
    path('exam-results/bulk-upload/', bulk_upload_exam_results, name='exam-results-bulk-upload'),
    # PROMOTION
    path('promotion/', get_promotion_data, name='promotion-data'),
    path('promotion/promote/', promote_students, name='promote-students'),
    path('promotion/rules/', get_promotion_rules, name='promotion-rules'),
    path('promotion/rules/save/', save_promotion_rules, name='promotion-rules-save'),
    path('promotion/subjects/', get_all_subjects, name='promotion-subjects'),
]