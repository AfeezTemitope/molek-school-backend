"""
MOLEK School - Student Portal Views
Views for student authentication and self-service operations

Updated for Nigerian Secondary School Grading:
- CA1: 15 marks
- CA2: 15 marks
- OBJ/CBT: 30 marks
- Theory: 40 marks
- Total: 100 marks
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
    """
    Convert score to letter grade using Nigerian Secondary School grading scale
    
    Grading Scale:
    - A: 75-100 (Excellent)
    - B: 70-74 (Very Good)
    - C: 60-69 (Good)
    - D: 50-59 (Pass)
    - E: 45-49 (Fair)
    - F: 0-44 (Fail)
    """
    score = float(score) if score else 0
    if score >= 75:
        return 'A'
    elif score >= 70:
        return 'B'
    elif score >= 60:
        return 'C'
    elif score >= 50:
        return 'D'
    elif score >= 45:
        return 'E'
    return 'F'


def get_remark(score):
    """Get remark based on Nigerian grading scale"""
    score = float(score) if score else 0
    if score >= 75:
        return 'Excellent'
    elif score >= 70:
        return 'Very Good'
    elif score >= 60:
        return 'Good'
    elif score >= 50:
        return 'Pass'
    elif score >= 45:
        return 'Fair'
    return 'Fail'


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


class StudentGradesView(APIView):
    """
    Get all grades for a student.
    
    Returns Nigerian School Grading Format:
    - ca1_score: First CA (max 15)
    - ca2_score: Second CA (max 15)
    - obj_score: OBJ/CBT score (max 30)
    - theory_score: Theory/Essay score (max 40)
    - total_score: Sum of all components (max 100)
    - grade: A/B/C/D/E/F
    - remark: Excellent/Very Good/Good/Pass/Fair/Fail
    """
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
            # Nigerian School Grading Format
            grades.append({
                'id': r.id,
                'subject_name': r.subject.name,
                'session': r.session.id,
                'session_name': r.session.name,
                'term': r.term.id,
                'term_name': r.term.name,
                # Score components (Nigerian format)
                'ca1_score': float(r.ca1_score or 0),
                'ca2_score': float(r.ca2_score or 0),
                'obj_score': float(r.obj_score or 0),
                'theory_score': float(r.theory_score or 0),
                # Calculated fields
                'total_ca': float((r.ca1_score or 0) + (r.ca2_score or 0)),
                'exam_total': float((r.obj_score or 0) + (r.theory_score or 0)),
                'total_score': float(r.total_score or 0),
                'grade': r.grade,
                'remark': r.remark,
                # Class statistics
                'position': r.position,
                'total_students': r.total_students,
                'class_average': float(r.class_average) if r.class_average else None,
                'highest_score': float(r.highest_score) if r.highest_score else None,
                'lowest_score': float(r.lowest_score) if r.lowest_score else None,
                # Cumulative (for 2nd/3rd term)
                'first_term_total': float(r.first_term_total) if r.first_term_total else None,
                'second_term_total': float(r.second_term_total) if r.second_term_total else None,
                'third_term_total': float(r.third_term_total) if r.third_term_total else None,
                'cumulative_score': float(r.cumulative_score) if r.cumulative_score else None,
                'cumulative_grade': r.cumulative_grade,
            })
        
        return Response({'grades': grades})


class StudentCAScoresView(APIView):
    """
    Get CA scores for a student.
    
    Returns:
    - ca1_score: First CA (max 15)
    - ca2_score: Second CA (max 15)
    - total_ca: Combined CA score (max 30)
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
        
        # Overall stats - using Nigerian pass mark (45 for E grade, 50 for D)
        total_exams = results.count()
        if total_exams > 0:
            avg_score = results.aggregate(avg=Avg('total_score'))['avg'] or 0
            passed = results.filter(total_score__gte=45).count()  # E grade or above
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
                    term_passed = term_results.filter(total_score__gte=45).count()
                    terms_data.append({
                        'id': term.id,
                        'name': term.name,
                        'totalExams': term_count,
                        'averageScore': round(float(term_avg), 1),
                        'passedSubjects': term_passed,
                        'failedSubjects': term_count - term_passed,
                        'grade': get_grade(term_avg),
                        'remark': get_remark(term_avg),
                    })
            
            # Session cumulative
            session_count = session_results.count()
            if session_count > 0:
                session_avg = session_results.aggregate(avg=Avg('total_score'))['avg'] or 0
                session_passed = session_results.filter(total_score__gte=45).count()
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
                    'remark': get_remark(session_avg),
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
                'remark': get_remark(avg_score),
            },
            'sessions': sessions_data,
        })


class StudentReportCardView(APIView):
    """
    Generate report card data for a student.
    
    Nigerian School Format:
    - CA1: 15 marks
    - CA2: 15 marks
    - OBJ: 30 marks
    - Theory: 40 marks
    - Total: 100 marks
    
    Query params:
    - admission_number: Required
    - session: Optional session ID (for single session report)
    - term: Optional term ID (for single term report)
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
        for r in results:
            subjects.append({
                'subjectName': r.subject.name,
                # Nigerian grading components
                'ca1Score': float(r.ca1_score or 0),
                'ca2Score': float(r.ca2_score or 0),
                'totalCA': float((r.ca1_score or 0) + (r.ca2_score or 0)),
                'objScore': float(r.obj_score or 0),
                'theoryScore': float(r.theory_score or 0),
                'examTotal': float((r.obj_score or 0) + (r.theory_score or 0)),
                'totalScore': float(r.total_score or 0),
                'grade': r.grade,
                'remark': r.remark,
                # Class statistics
                'position': r.position,
                'totalStudents': r.total_students,
                'classAverage': float(r.class_average) if r.class_average else None,
                'highestScore': float(r.highest_score) if r.highest_score else None,
                'lowestScore': float(r.lowest_score) if r.lowest_score else None,
            })
        
        # Summary stats
        if subjects:
            total_score = sum(s['totalScore'] for s in subjects)
            avg_score = total_score / len(subjects)
            passed = len([s for s in subjects if s['totalScore'] >= 45])
        else:
            total_score = 0
            avg_score = 0
            passed = 0
        
        return Response({
            'student': get_student_portal_data(student),
            'session': {'id': session.id, 'name': session.name},
            'term': {'id': term.id, 'name': term.name},
            'subjects': subjects,
            'summary': {
                'totalSubjects': len(subjects),
                'totalScore': round(total_score, 1),
                'averageScore': round(avg_score, 1),
                'grade': get_grade(avg_score),
                'remark': get_remark(avg_score),
                'passedSubjects': passed,
                'failedSubjects': len(subjects) - passed,
            }
        })
    
    def _get_session_report(self, student, session_id):
        """Get cumulative session report"""
        try:
            session = AcademicSession.objects.get(id=session_id)
        except AcademicSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        terms = Term.objects.filter(session=session).order_by('id')
        
        # Get all subjects for this session
        subjects_in_session = ExamResult.objects.filter(
            student=student, session=session
        ).values_list('subject__name', flat=True).distinct()
        
        cumulative_subjects = []
        
        for subject_name in subjects_in_session:
            term_scores = {}
            
            for term in terms:
                result = ExamResult.objects.filter(
                    student=student, session=session, term=term,
                    subject__name=subject_name
                ).first()
                
                if result:
                    term_scores[term.name] = {
                        'ca1': float(result.ca1_score or 0),
                        'ca2': float(result.ca2_score or 0),
                        'obj': float(result.obj_score or 0),
                        'theory': float(result.theory_score or 0),
                        'total': float(result.total_score or 0),
                        'grade': result.grade,
                    }
                else:
                    term_scores[term.name] = None
            
            # Calculate cumulative
            valid_totals = [ts['total'] for ts in term_scores.values() if ts]
            cumulative_avg = sum(valid_totals) / len(valid_totals) if valid_totals else 0
            
            cumulative_subjects.append({
                'subjectName': subject_name,
                'termScores': term_scores,
                'cumulativeAverage': round(cumulative_avg, 1),
                'cumulativeGrade': get_grade(cumulative_avg),
                'cumulativeRemark': get_remark(cumulative_avg),
                'termsCompleted': len(valid_totals),
            })
        
        # Sort by subject name
        cumulative_subjects.sort(key=lambda x: x['subjectName'])
        
        # Overall cumulative
        all_avgs = [s['cumulativeAverage'] for s in cumulative_subjects if s['cumulativeAverage'] > 0]
        overall_avg = sum(all_avgs) / len(all_avgs) if all_avgs else 0
        
        return Response({
            'student': get_student_portal_data(student),
            'session': {'id': session.id, 'name': session.name},
            'terms': [{'id': t.id, 'name': t.name} for t in terms],
            'subjects': cumulative_subjects,
            'cumulative': {
                'totalSubjects': len(cumulative_subjects),
                'averageScore': round(overall_avg, 1),
                'grade': get_grade(overall_avg),
                'remark': get_remark(overall_avg),
                'passedSubjects': len([s for s in cumulative_subjects if s['cumulativeAverage'] >= 45]),
                'failedSubjects': len([s for s in cumulative_subjects if s['cumulativeAverage'] < 45]),
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