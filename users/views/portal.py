"""
MOLEK School - Student Portal Views
Views for student authentication and self-service operations
"""
import logging
from decimal import Decimal
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Avg, Max, Min, Count, Sum
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from ..models import (
    ActiveStudent, AcademicSession, Term, CAScore, ExamResult, Subject
)
from ..serializers import (
    StudentLoginSerializer,
    StudentProfileUpdateSerializer,
    AcademicSessionSerializer,
    TermSerializer,
    CAScoreSerializer,
    ExamResultSerializer,
)
from ..cache_utils import (
    make_cache_key,
    get_or_set_cache,
    invalidate_cache,
    get_cached_sessions,
    get_cached_terms,
    CACHE_TIMEOUT_STUDENT,
)

logger = logging.getLogger(__name__)


def get_student_portal_data(student):
    """Helper to format student data for portal"""
    passport_url = None
    if student.passport:
        try:
            passport_url = student.passport.url
        except:
            pass
    
    return {
        'id': student.id,
        'admission_number': student.admission_number,
        'first_name': student.first_name,
        'middle_name': student.middle_name,
        'last_name': student.last_name,
        'full_name': student.full_name,
        'date_of_birth': student.date_of_birth,
        'gender': student.gender,
        'email': student.email,
        'phone_number': student.phone_number,
        'address': student.address,
        'state_of_origin': student.state_of_origin,
        'local_govt_area': student.local_govt_area,
        'class_level_name': student.class_level.name if student.class_level else None,
        'enrollment_session_name': student.enrollment_session.name if student.enrollment_session else None,
        'parent_name': student.parent_name,
        'parent_email': student.parent_email,
        'parent_phone': student.parent_phone,
        'passport_url': passport_url,
        'is_active': student.is_active,
    }


def get_grade(score):
    """Convert score to letter grade"""
    score = float(score) if score else 0
    if score >= 70:
        return 'A'
    elif score >= 60:
        return 'B'
    elif score >= 50:
        return 'C'
    elif score >= 40:
        return 'D'
    return 'F'


def get_remark(score):
    """Get remark based on score"""
    score = float(score) if score else 0
    if score >= 70:
        return 'Excellent'
    elif score >= 60:
        return 'Very Good'
    elif score >= 50:
        return 'Good'
    elif score >= 40:
        return 'Fair'
    return 'Poor'


class StudentLoginView(APIView):
    """Student login using admission number and password."""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = StudentLoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid credentials format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        admission_number = serializer.validated_data['admission_number'].upper()
        password = serializer.validated_data['password']
        
        try:
            student = ActiveStudent.objects.select_related(
                'class_level', 'enrollment_session'
            ).get(
                admission_number=admission_number,
                is_active=True
            )
        except ActiveStudent.DoesNotExist:
            return Response(
                {'error': 'Invalid admission number or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if student.password_plain == password or check_password(password, student.password_hash):
            logger.info(f"Student login successful: {admission_number}")
            return Response({
                'message': 'Login successful',
                'student': get_student_portal_data(student)
            })
        
        return Response(
            {'error': 'Invalid admission number or password'},
            status=status.HTTP_401_UNAUTHORIZED
        )


class StudentProfileView(APIView):
    """Get and update student profile."""
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        
        if not admission_number:
            return Response(
                {'error': 'Admission number required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            student = ActiveStudent.objects.select_related(
                'class_level', 'enrollment_session'
            ).get(admission_number=admission_number.upper())
            return Response(get_student_portal_data(student))
        except ActiveStudent.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def put(self, request):
        return self._update_profile(request)
    
    def patch(self, request):
        return self._update_profile(request)
    
    def _update_profile(self, request):
        admission_number = request.query_params.get('admission_number')
        
        if not admission_number:
            return Response(
                {'error': 'Admission number required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            student = ActiveStudent.objects.select_related(
                'class_level', 'enrollment_session'
            ).get(admission_number=admission_number.upper())
        except ActiveStudent.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = StudentProfileUpdateSerializer(
            student, data=request.data, partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            cache_key = make_cache_key('student_profile', admission_number.upper())
            invalidate_cache(cache_key)
            student.refresh_from_db()
            return Response(get_student_portal_data(student))
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentChangePasswordView(APIView):
    """Change student password."""
    permission_classes = [AllowAny]
    
    def post(self, request):
        admission_number = request.data.get('admission_number')
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not all([admission_number, old_password, new_password]):
            return Response(
                {'error': 'All fields required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            student = ActiveStudent.objects.get(
                admission_number=admission_number.upper(),
                is_active=True
            )
        except ActiveStudent.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify old password
        if student.password_plain != old_password and not check_password(old_password, student.password_hash):
            return Response(
                {'error': 'Current password is incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update password
        student.password_plain = new_password
        student.password_hash = make_password(new_password)
        student.save(update_fields=['password_plain', 'password_hash'])
        
        logger.info(f"Password changed for student: {admission_number}")
        
        return Response({'message': 'Password changed successfully'})


class StudentDashboardStatsView(APIView):
    """Get dashboard statistics for a student."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        
        if not admission_number:
            return Response(
                {'error': 'Admission number required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            student = ActiveStudent.objects.select_related(
                'class_level', 'enrollment_session'
            ).get(admission_number=admission_number.upper())
        except ActiveStudent.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all exam results for this student
        results = ExamResult.objects.filter(student=student).select_related(
            'session', 'term', 'subject'
        )
        
        # Overall stats
        total_exams = results.count()
        if total_exams > 0:
            avg_score = results.aggregate(avg=Avg('total_score'))['avg'] or 0
            passed = results.filter(total_score__gte=40).count()
            failed = total_exams - passed
        else:
            avg_score = 0
            passed = 0
            failed = 0
        
        # Get sessions with results
        sessions_data = []
        sessions = AcademicSession.objects.filter(
            exam_results__student=student
        ).distinct().order_by('-start_date')
        
        for session in sessions:
            session_results = results.filter(session=session)
            terms = Term.objects.filter(session=session).order_by('id')
            
            terms_data = []
            for term in terms:
                term_results = session_results.filter(term=term)
                term_count = term_results.count()
                
                if term_count > 0:
                    term_avg = term_results.aggregate(avg=Avg('total_score'))['avg'] or 0
                    term_passed = term_results.filter(total_score__gte=40).count()
                    terms_data.append({
                        'id': term.id,
                        'name': term.name,
                        'totalExams': term_count,
                        'averageScore': round(float(term_avg), 1),
                        'passedSubjects': term_passed,
                        'failedSubjects': term_count - term_passed,
                        'grade': get_grade(term_avg),
                    })
            
            # Session cumulative
            session_count = session_results.count()
            if session_count > 0:
                session_avg = session_results.aggregate(avg=Avg('total_score'))['avg'] or 0
                session_passed = session_results.filter(total_score__gte=40).count()
            else:
                session_avg = 0
                session_passed = 0
            
            sessions_data.append({
                'id': session.id,
                'name': session.name,
                'is_current': session.is_current,
                'terms': terms_data,
                'cumulative': {
                    'totalExams': session_count,
                    'averageScore': round(float(session_avg), 1),
                    'passedSubjects': session_passed,
                    'failedSubjects': session_count - session_passed,
                    'grade': get_grade(session_avg),
                }
            })
        
        return Response({
            'student': get_student_portal_data(student),
            'overall': {
                'totalExams': total_exams,
                'averageScore': round(float(avg_score), 1),
                'passedSubjects': passed,
                'failedSubjects': failed,
                'grade': get_grade(avg_score),
            },
            'sessions': sessions_data,
        })


class StudentReportCardView(APIView):
    """
    Generate report card data for a student.
    
    Query params:
    - admission_number: Required
    - session: Optional session ID (for single session report)
    - term: Optional term ID (for single term report)
    
    Modes:
    1. Single term report: ?session=X&term=Y
    2. Full session cumulative: ?session=X (no term)
    3. All sessions: no session/term params
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        session_id = request.query_params.get('session')
        term_id = request.query_params.get('term')
        
        if not admission_number:
            return Response(
                {'error': 'Admission number required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            student = ActiveStudent.objects.select_related(
                'class_level', 'enrollment_session'
            ).get(admission_number=admission_number.upper())
        except ActiveStudent.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Determine report mode
        if session_id and term_id:
            return self._get_term_report(student, session_id, term_id)
        elif session_id:
            return self._get_session_report(student, session_id)
        else:
            return self._get_all_sessions_report(student)
    
    def _get_term_report(self, student, session_id, term_id):
        """Get single term report with detailed breakdown"""
        try:
            session = AcademicSession.objects.get(id=session_id)
            term = Term.objects.get(id=term_id)
        except (AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response(
                {'error': 'Invalid session or term'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = ExamResult.objects.filter(
            student=student, session=session, term=term
        ).select_related('subject').order_by('subject__name')
        
        subjects = []
        for result in results:
            ca_score = float(result.ca_score or 0)
            theory_score = float(result.theory_score or 0)
            exam_score = float(result.exam_score or 0)
            total = float(result.total_score or 0)
            
            # Split CA into CA1 and CA2 for display (MOLEK format)
            ca1 = round(ca_score / 2, 1)
            ca2 = round(ca_score - ca1, 1)
            
            subjects.append({
                'subjectName': result.subject.name,
                'ca1': ca1,
                'ca2': ca2,
                'caTotal': ca_score,
                'theoryScore': theory_score,
                'examScore': exam_score,
                'examTotal': theory_score + exam_score,  # Theory + Exam = 70
                'totalScore': total,
                'grade': result.grade or get_grade(total),
                'position': result.position,
                'totalStudents': result.total_students,
                'classAverage': round(float(result.class_average or 0), 1),
                'remark': get_remark(total),
            })
        
        # Calculate summary
        total_subjects = len(subjects)
        if total_subjects > 0:
            avg_score = sum(s['totalScore'] for s in subjects) / total_subjects
            passed = len([s for s in subjects if s['totalScore'] >= 40])
        else:
            avg_score = 0
            passed = 0
        
        return Response({
            'student': get_student_portal_data(student),
            'session': {
                'id': session.id,
                'name': session.name,
            },
            'term': {
                'id': term.id,
                'name': term.name,
            },
            'subjects': subjects,
            'summary': {
                'totalSubjects': total_subjects,
                'averageScore': round(avg_score, 1),
                'passedSubjects': passed,
                'failedSubjects': total_subjects - passed,
                'grade': get_grade(avg_score),
            }
        })
    
    def _get_session_report(self, student, session_id):
        """Get full session report with cumulative scores across all terms"""
        try:
            session = AcademicSession.objects.get(id=session_id)
        except AcademicSession.DoesNotExist:
            return Response(
                {'error': 'Invalid session'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get all terms for this session
        terms = Term.objects.filter(session=session).order_by('id')
        term_order = {t.id: idx for idx, t in enumerate(terms)}
        
        # Get all results for this session
        results = ExamResult.objects.filter(
            student=student, session=session
        ).select_related('subject', 'term')
        
        # Group by subject
        subject_data = {}
        for result in results:
            subject_name = result.subject.name
            if subject_name not in subject_data:
                subject_data[subject_name] = {
                    'terms': {},
                }
            
            term_idx = term_order.get(result.term_id, 0)
            term_name = result.term.name
            
            subject_data[subject_name]['terms'][term_name] = {
                'total': float(result.total_score or 0),
                'grade': result.grade or get_grade(result.total_score or 0),
                'position': result.position,
            }
        
        # Build cumulative report
        cumulative_subjects = []
        for subject_name, data in subject_data.items():
            # Get scores for each term
            first = data['terms'].get('First Term', {}).get('total', 0)
            second = data['terms'].get('Second Term', {}).get('total', 0)
            third = data['terms'].get('Third Term', {}).get('total', 0)
            
            terms_with_scores = sum([1 for t in [first, second, third] if t > 0])
            cumulative_total = first + second + third
            cumulative_avg = round(cumulative_total / terms_with_scores, 1) if terms_with_scores > 0 else 0
            
            # Get class average for cumulative
            class_cumulative = ExamResult.objects.filter(
                session=session, subject__name=subject_name,
                student__class_level=student.class_level
            ).aggregate(avg=Avg('total_score'))['avg'] or 0
            
            cumulative_subjects.append({
                'subjectName': subject_name,
                'firstTerm': first,
                'secondTerm': second,
                'thirdTerm': third,
                'cumulativeTotal': cumulative_total,
                'cumulativePercent': round((cumulative_total / (terms_with_scores * 100)) * 100, 1) if terms_with_scores > 0 else 0,
                'studentAverage': cumulative_avg,
                'classAverage': round(float(class_cumulative), 1),
                'grade': get_grade(cumulative_avg),
                'remark': get_remark(cumulative_avg),
                'terms': data['terms'],
            })
        
        # Sort subjects alphabetically
        cumulative_subjects.sort(key=lambda x: x['subjectName'])
        
        # Overall cumulative
        all_cumulative_totals = [s['cumulativeTotal'] for s in cumulative_subjects]
        all_student_avgs = [s['studentAverage'] for s in cumulative_subjects if s['studentAverage'] > 0]
        
        overall_cumulative = sum(all_cumulative_totals)
        overall_avg = round(sum(all_student_avgs) / len(all_student_avgs), 1) if all_student_avgs else 0
        
        return Response({
            'student': get_student_portal_data(student),
            'session': {
                'id': session.id,
                'name': session.name,
            },
            'terms': [{'id': t.id, 'name': t.name} for t in terms],
            'subjects': cumulative_subjects,
            'cumulative': {
                'totalSubjects': len(cumulative_subjects),
                'totalScore': overall_cumulative,
                'averageScore': overall_avg,
                'grade': get_grade(overall_avg),
                'passedSubjects': len([s for s in cumulative_subjects if s['studentAverage'] >= 40]),
                'failedSubjects': len([s for s in cumulative_subjects if s['studentAverage'] < 40]),
            }
        })
    
    def _get_all_sessions_report(self, student):
        """Get report for all sessions"""
        sessions = AcademicSession.objects.filter(
            exam_results__student=student
        ).distinct().order_by('-start_date')
        
        sessions_data = []
        for session in sessions:
            report = self._get_session_report(student, session.id)
            if report.status_code == 200:
                sessions_data.append(report.data)
        
        return Response({
            'student': get_student_portal_data(student),
            'sessions': sessions_data,
        })


class StudentGradesView(APIView):
    """Get all grades for a student."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        
        if not admission_number:
            return Response(
                {'error': 'Admission number required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            student = ActiveStudent.objects.get(
                admission_number=admission_number.upper()
            )
        except ActiveStudent.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        results = ExamResult.objects.filter(
            student=student
        ).select_related(
            'subject', 'session', 'term'
        ).order_by('-session__start_date', 'term__name')
        
        grades = []
        for r in results:
            grades.append({
                'id': r.id,
                'subject_name': r.subject.name,
                'session': r.session.id,
                'session_name': r.session.name,
                'term': r.term.id,
                'term_name': r.term.name,
                'ca_score': float(r.ca_score),
                'theory_score': float(r.theory_score),
                'exam_score': float(r.exam_score),
                'total_score': float(r.total_score),
                'grade': r.grade,
                'position': r.position,
                'total_students': r.total_students,
                'class_average': float(r.class_average) if r.class_average else None,
            })
        
        return Response({'grades': grades})


class StudentCAScoresView(APIView):
    """Get CA scores for a student."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        session_id = request.query_params.get('session')
        term_id = request.query_params.get('term')
        
        if not admission_number:
            return Response(
                {'error': 'Admission number required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            student = ActiveStudent.objects.get(
                admission_number=admission_number.upper()
            )
        except ActiveStudent.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        ca_scores = CAScore.objects.filter(student=student)
        
        if session_id:
            ca_scores = ca_scores.filter(session_id=session_id)
        if term_id:
            ca_scores = ca_scores.filter(term_id=term_id)
        
        ca_scores = ca_scores.select_related(
            'subject', 'session', 'term'
        ).order_by('-session__start_date')
        
        return Response({
            'ca_scores': CAScoreSerializer(ca_scores, many=True).data
        })


class StudentExamResultsView(APIView):
    """Get exam results for a student."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        session_id = request.query_params.get('session')
        term_id = request.query_params.get('term')
        
        if not admission_number:
            return Response(
                {'error': 'Admission number required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            student = ActiveStudent.objects.get(
                admission_number=admission_number.upper()
            )
        except ActiveStudent.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        results = ExamResult.objects.filter(student=student)
        
        if session_id:
            results = results.filter(session_id=session_id)
        if term_id:
            results = results.filter(term_id=term_id)
        
        results = results.select_related(
            'subject', 'session', 'term'
        ).order_by('-session__start_date')
        
        return Response({
            'exam_results': ExamResultSerializer(results, many=True).data
        })


class StudentSessionsView(APIView):
    """Get all academic sessions"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        sessions = get_cached_sessions()
        return Response({
            'sessions': AcademicSessionSerializer(sessions, many=True).data
        })


class StudentTermsView(APIView):
    """Get all terms"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        session_id = request.query_params.get('session')
        terms = get_cached_terms(session_id)
        return Response({
            'terms': TermSerializer(terms, many=True).data
        })