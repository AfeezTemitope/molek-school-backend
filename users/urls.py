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
    
    # Debug: simulate what _get_session_report does for MOL/2026/023
    from .models import AcademicSession, Term
    debug_session_report = None
    try:
        student = ActiveStudent.objects.get(admission_number='MOL/2026/023')
        session = AcademicSession.objects.get(name='2025/2026')
        terms = Term.objects.filter(session=session).order_by('id')
        
        subject_ids = ExamResult.objects.filter(
            student=student, session=session
        ).values_list('subject_id', flat=True).distinct()
        
        debug_subjects = []
        for sid in subject_ids:
            from .models import Subject as Subj
            subj = Subj.objects.get(id=sid)
            term_data = {}
            for t in terms:
                r = ExamResult.objects.filter(student=student, session=session, term=t, subject_id=sid).first()
                term_data[t.name] = float(r.total_score) if r else None
            debug_subjects.append({
                'subject_id': sid,
                'subject_name': subj.name,
                'terms': term_data,
            })
        
        debug_session_report = {
            'student': student.admission_number,
            'unique_subject_ids': list(subject_ids),
            'subjects': debug_subjects,
        }
    except Exception as e:
        debug_session_report = {'error': str(e)}
    
    return JsonResponse({
        'duplicates': dupes,
        'all_subjects': all_subjects,
        'students': students,
        'duplicate_results': dupe_results,
        'math_results': math_results,
        'debug_session_report': debug_session_report,
    })


app_name = 'users'

# TEMPORARY DEBUG - cleanup inactive students
def debug_cleanup_inactive(request):
    from .models import ActiveStudent
    
    action = request.GET.get('action', '')
    confirm = request.GET.get('confirm', '')
    
    inactive = ActiveStudent.objects.filter(is_active=False)
    
    if action == 'activate' and confirm == 'yes':
        count = inactive.count()
        inactive.update(is_active=True)
        return JsonResponse({
            'activated': count,
            'total_active': ActiveStudent.objects.filter(is_active=True).count(),
        })
    
    if action == 'delete' and confirm == 'yes':
        from .models import ExamResult
        count = inactive.count()
        ExamResult.objects.filter(student__is_active=False).delete()
        inactive.delete()
        return JsonResponse({
            'deleted': count,
            'remaining': ActiveStudent.objects.count(),
        })
    
    return JsonResponse({
        'inactive_count': inactive.count(),
        'inactive_students': [
            {'id': s.id, 'adm': s.admission_number, 'name': s.full_name}
            for s in inactive[:50]
        ],
        'actions': {
            'activate_all': '?action=activate&confirm=yes',
            'delete_all': '?action=delete&confirm=yes',
        }
    })


# TEMPORARY DEBUG - clear all data, keep tables and academic setup
def debug_clear_all_data(request):
    if request.GET.get('confirm') != 'CLEAR_ALL':
        from .models import ExamResult, CAScore, ActiveStudent, PromotionRule
        return JsonResponse({
            'warning': 'This will DELETE all student data, results, CA scores. Tables and academic setup remain.',
            'current_counts': {
                'exam_results': ExamResult.objects.count(),
                'ca_scores': CAScore.objects.count(),
                'students': ActiveStudent.objects.count(),
                'promotion_rules': PromotionRule.objects.count(),
            },
            'action': 'Add ?confirm=CLEAR_ALL to proceed',
        })
    
    from .models import ExamResult, CAScore, ActiveStudent, PromotionRule
    
    counts = {
        'exam_results': ExamResult.objects.count(),
        'ca_scores': CAScore.objects.count(),
        'students': ActiveStudent.objects.count(),
        'promotion_rules': PromotionRule.objects.count(),
    }
    
    ExamResult.objects.all().delete()
    CAScore.objects.all().delete()
    PromotionRule.objects.all().delete()
    ActiveStudent.objects.all().delete()
    
    return JsonResponse({
        'deleted': counts,
        'status': 'All data cleared. Sessions, terms, subjects, classes preserved.',
    })

urlpatterns = [
    # TEMPORARY DEBUG - Remove after use
    path('debug/check-dupes/', debug_check_dupes, name='debug-check-dupes'),
    path('debug/cleanup-inactive/', debug_cleanup_inactive, name='debug-cleanup'),
    path('debug/clear-all-data/', debug_clear_all_data, name='debug-clear-data'),
    
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