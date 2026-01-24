"""
MOLEK School - Student Portal Views
Views for student authentication and self-service operations
"""
import logging
from django.contrib.auth.hashers import check_password, make_password
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    ActiveStudent, AcademicSession, Term, CAScore, ExamResult
)
from ..serializers import (
    StudentLoginSerializer,
    StudentProfileUpdateSerializer,
    StudentCredentialsSerializer,
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
    CACHE_TIMEOUT_SCORE,
    CACHE_TIMEOUT_ACADEMIC,
)

logger = logging.getLogger(__name__)


class StudentLoginView(APIView):
    """
    Student login using admission number and password.
    
    Request body:
    {
        "admission_number": "MOL/2026/001",
        "password": "student_password"
    }
    
    Returns student credentials on success.
    """
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
        
        # Check password (can be plain or hashed)
        if student.password_plain == password or check_password(password, student.password_hash):
            logger.info(f"Student login successful: {admission_number}")
            return Response({
                'message': 'Login successful',
                'student': StudentCredentialsSerializer(student).data
            })
        
        return Response(
            {'error': 'Invalid admission number or password'},
            status=status.HTTP_401_UNAUTHORIZED
        )


class StudentProfileView(APIView):
    """
    Get and update student profile.
    
    GET: Returns student profile
    PUT/PATCH: Updates student profile (limited fields)
    
    Requires admission_number as query parameter.
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        
        if not admission_number:
            return Response(
                {'error': 'Admission number required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cache_key = make_cache_key('student_profile', admission_number.upper())
        
        def get_profile():
            try:
                student = ActiveStudent.objects.select_related(
                    'class_level', 'enrollment_session'
                ).get(
                    admission_number=admission_number.upper(),
                    is_active=True
                )
                return StudentCredentialsSerializer(student).data
            except ActiveStudent.DoesNotExist:
                return None
        
        data = get_or_set_cache(cache_key, get_profile, timeout=CACHE_TIMEOUT_STUDENT)
        
        if data is None:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(data)
    
    def patch(self, request):
        """Update student profile (limited fields)"""
        admission_number = request.query_params.get('admission_number')
        
        if not admission_number:
            return Response(
                {'error': 'Admission number required'},
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
        
        serializer = StudentProfileUpdateSerializer(
            student,
            data=request.data,
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            
            # Invalidate cache
            cache_key = make_cache_key('student_profile', admission_number.upper())
            invalidate_cache(cache_key)
            
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentChangePasswordView(APIView):
    """
    Change student password.
    
    Request body:
    {
        "admission_number": "MOL/2026/001",
        "old_password": "current_password",
        "new_password": "new_password"
    }
    """
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
        if not (student.password_plain == old_password or 
                check_password(old_password, student.password_hash)):
            return Response(
                {'error': 'Current password is incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update password
        student.password_plain = new_password
        student.password_hash = make_password(new_password)
        student.save(update_fields=['password_plain', 'password_hash'])
        
        logger.info(f"Student password changed: {admission_number}")
        
        return Response({
            'message': 'Password changed successfully'
        })


class StudentGradesView(APIView):
    """
    Get all grades for a student.
    
    Query params:
        - admission_number (required)
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        
        if not admission_number:
            return Response(
                {'error': 'Admission number required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cache_key = make_cache_key('student_grades', admission_number.upper())
        
        def get_grades():
            try:
                student = ActiveStudent.objects.get(
                    admission_number=admission_number.upper(),
                    is_active=True
                )
            except ActiveStudent.DoesNotExist:
                return None
            
            results = ExamResult.objects.filter(
                student=student
            ).select_related(
                'subject', 'session', 'term'
            ).order_by('-session__start_date', 'term__name')
            
            return ExamResultSerializer(results, many=True).data
        
        data = get_or_set_cache(cache_key, get_grades, timeout=CACHE_TIMEOUT_SCORE)
        
        if data is None:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({'grades': data})


class StudentCAScoresView(APIView):
    """
    Get CA scores for a student.
    
    Query params:
        - admission_number (required)
        - session (optional)
        - term (optional)
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
                admission_number=admission_number.upper(),
                is_active=True
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
    """
    Get exam results for a student.
    
    Query params:
        - admission_number (required)
        - session (optional)
        - term (optional)
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
                admission_number=admission_number.upper(),
                is_active=True
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


class StudentReportCardView(APIView):
    """
    Get comprehensive report card.
    
    Query params:
        - admission_number (required)
        - session (required)
        - term (required)
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        session_id = request.query_params.get('session')
        term_id = request.query_params.get('term')
        
        if not all([admission_number, session_id, term_id]):
            return Response(
                {'error': 'Admission number, session, and term required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            student = ActiveStudent.objects.select_related(
                'class_level'
            ).get(
                admission_number=admission_number.upper(),
                is_active=True
            )
            session = AcademicSession.objects.get(id=session_id)
            term = Term.objects.get(id=term_id)
        except (ActiveStudent.DoesNotExist, AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response(
                {'error': 'Invalid parameters'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = ExamResult.objects.filter(
            student=student,
            session=session,
            term=term
        ).select_related('subject')
        
        if not results.exists():
            return Response({
                'session': session.name,
                'term': term.name,
                'student_class': student.class_level.name if student.class_level else '',
                'results': [],
                'total_score': 0,
                'average_percentage': 0,
            })
        
        total_score = sum(float(r.total_score) for r in results)
        average = round(total_score / len(results), 2)
        
        return Response({
            'session': session.name,
            'term': term.name,
            'student_class': student.class_level.name if student.class_level else '',
            'results': ExamResultSerializer(results, many=True).data,
            'total_score': total_score,
            'average_percentage': average,
        })


class StudentSessionsView(APIView):
    """Get all academic sessions (cached)"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        sessions = get_cached_sessions()
        return Response({
            'sessions': AcademicSessionSerializer(sessions, many=True).data
        })


class StudentTermsView(APIView):
    """Get all terms (cached)"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        session_id = request.query_params.get('session')
        terms = get_cached_terms(session_id)
        return Response({
            'terms': TermSerializer(terms, many=True).data
        })