"""
MOLEK School - Score Management Views
ViewSets and functions for CA scores and exam results management
"""
import csv
import io
import logging
from decimal import Decimal

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from ..models import (
    ActiveStudent, AcademicSession, Term, Subject, CAScore, ExamResult
)
from ..serializers import (
    CAScoreSerializer,
    ExamResultSerializer,
    CAScoreUploadSerializer,
    ExamResultUploadSerializer,
    CAScoreBulkUploadSerializer,
    ExamResultBulkUploadSerializer,
)
from ..permissions import IsAdminOrSuperAdmin
from ..cache_utils import (
    make_cache_key,
    get_or_set_cache,
    invalidate_cache,
    invalidate_score_cache,
    CACHE_TIMEOUT_SCORE,
)
from ..utils import calculate_grade

logger = logging.getLogger(__name__)


class CAScoreViewSet(viewsets.ModelViewSet):
    """
    CRUD for CA scores.
    
    Features:
    - Filter by student, subject, session, term
    - Bulk upload via CSV
    - Export template CSV
    """
    queryset = CAScore.objects.all()
    serializer_class = CAScoreSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'subject', 'session', 'term']
    
    def get_queryset(self):
        """Optimized queryset with select_related"""
        return CAScore.objects.select_related(
            'student', 'subject', 'session', 'term', 'uploaded_by'
        ).all()
    
    @action(detail=False, methods=['post'], url_path='bulk-upload')
    def bulk_upload(self, request):
        """
        Bulk upload CA scores via CSV.
        
        Expected columns: admission_number, subject_code, subject_name, ca_score
        """
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        session_id = request.data.get('session')
        term_id = request.data.get('term')
        
        if not session_id or not term_id:
            return Response(
                {'error': 'Session and term are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            session = AcademicSession.objects.get(id=session_id)
            term = Term.objects.get(id=term_id)
        except (AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response(
                {'error': 'Invalid session or term'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        csv_file = request.FILES['file']
        
        try:
            decoded_file = csv_file.read().decode('utf-8')
        except UnicodeDecodeError:
            return Response(
                {'error': 'Invalid file encoding. Please save CSV as UTF-8.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        
        created = 0
        updated = 0
        subjects_created = 0
        errors = []
        row_num = 1
        
        for row in reader:
            row_num += 1
            try:
                serializer = CAScoreBulkUploadSerializer(data=row)
                if not serializer.is_valid():
                    errors.append({
                        'row': row_num,
                        'error': f"Validation failed: {serializer.errors}"
                    })
                    continue
                
                admission_number = serializer.validated_data['admission_number'].upper()
                subject_code = serializer.validated_data['subject_code'].upper()
                subject_name = serializer.validated_data.get('subject_name', subject_code)
                ca_score = serializer.validated_data['ca_score']
                
                # Validate CA score
                if ca_score > 30:
                    errors.append({
                        'row': row_num,
                        'error': f"CA score {ca_score} exceeds maximum of 30"
                    })
                    continue
                
                # Get student
                try:
                    student = ActiveStudent.objects.get(
                        admission_number=admission_number, is_active=True
                    )
                except ActiveStudent.DoesNotExist:
                    errors.append({
                        'row': row_num,
                        'error': f"Student {admission_number} not found"
                    })
                    continue
                
                # Get or create subject
                subject, subject_is_new = Subject.objects.get_or_create(
                    code=subject_code,
                    defaults={'name': subject_name, 'is_active': True}
                )
                if subject_is_new:
                    subjects_created += 1
                
                # Create or update CA score
                ca_obj, is_new = CAScore.objects.update_or_create(
                    student=student,
                    subject=subject,
                    session=session,
                    term=term,
                    defaults={
                        'ca_score': ca_score,
                        'theory_score': 0,
                        'uploaded_by': request.user
                    }
                )
                
                if is_new:
                    created += 1
                else:
                    updated += 1
                
            except Exception as e:
                errors.append({'row': row_num, 'error': str(e)})
        
        # Invalidate score cache
        invalidate_score_cache(session_id, term_id)
        
        logger.info(f"CA scores uploaded: {created} created, {updated} updated by {request.user.username}")
        
        return Response({
            'created': created,
            'updated': updated,
            'subjects_created': subjects_created,
            'failed': len(errors),
            'errors': errors[:10],
        })
    
    @action(detail=False, methods=['get'], url_path='export-template')
    def export_template(self, request):
        """Export CA scores template CSV"""
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="ca_scores_template.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['admission_number', 'subject_code', 'subject_name', 'ca_score'])
        writer.writerow(['MOL/2026/001', 'GNS101', 'General Studies', '25'])
        writer.writerow(['MOL/2026/002', 'GNS101', 'General Studies', '28'])
        
        return response


class ExamResultViewSet(viewsets.ModelViewSet):
    """
    CRUD for exam results.
    
    Features:
    - Filter by student, subject, session, term
    - Bulk import from CBT CSV
    """
    queryset = ExamResult.objects.all()
    serializer_class = ExamResultSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'subject', 'session', 'term']
    
    def get_queryset(self):
        """Optimized queryset with select_related"""
        return ExamResult.objects.select_related(
            'student', 'subject', 'session', 'term', 'uploaded_by'
        ).all()
    
    @action(detail=False, methods=['post'], url_path='bulk-import')
    def bulk_import(self, request):
        """
        Bulk import exam results from CBT CSV.
        
        Expected columns: admission_number, subject_code, subject_name, exam_score, submitted_at
        """
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        session_id = request.data.get('session')
        term_id = request.data.get('term')
        
        if not session_id or not term_id:
            return Response(
                {'error': 'Session and term are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            session = AcademicSession.objects.get(id=session_id)
            term = Term.objects.get(id=term_id)
        except (AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response(
                {'error': 'Invalid session or term'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        csv_file = request.FILES['file']
        
        try:
            decoded_file = csv_file.read().decode('utf-8')
        except UnicodeDecodeError:
            return Response(
                {'error': 'Invalid file encoding. Please save CSV as UTF-8.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        
        created = 0
        updated = 0
        subjects_created = 0
        errors = []
        row_num = 1
        
        for row in reader:
            row_num += 1
            try:
                serializer = ExamResultBulkUploadSerializer(data=row)
                if not serializer.is_valid():
                    errors.append({
                        'row': row_num,
                        'error': f"Validation failed: {serializer.errors}"
                    })
                    continue
                
                admission_number = serializer.validated_data['admission_number'].upper()
                subject_code = serializer.validated_data['subject_code'].upper()
                subject_name = serializer.validated_data.get('subject_name', subject_code)
                exam_score = serializer.validated_data['exam_score']
                submitted_at = serializer.validated_data.get('submitted_at')
                
                # Validate exam score
                if exam_score > 70:
                    errors.append({
                        'row': row_num,
                        'error': f"Exam score {exam_score} exceeds maximum of 70"
                    })
                    continue
                
                # Get student
                try:
                    student = ActiveStudent.objects.get(
                        admission_number=admission_number, is_active=True
                    )
                except ActiveStudent.DoesNotExist:
                    errors.append({
                        'row': row_num,
                        'error': f"Student {admission_number} not found"
                    })
                    continue
                
                # Get or create subject
                subject, subject_is_new = Subject.objects.get_or_create(
                    code=subject_code,
                    defaults={'name': subject_name, 'is_active': True}
                )
                if subject_is_new:
                    subjects_created += 1
                
                # Get CA score if exists
                try:
                    ca_obj = CAScore.objects.get(
                        student=student, subject=subject, session=session, term=term
                    )
                    ca_score = ca_obj.ca_score
                    theory_score = ca_obj.theory_score
                except CAScore.DoesNotExist:
                    ca_score = Decimal('0')
                    theory_score = Decimal('0')
                
                # Create or update exam result
                result, is_new = ExamResult.objects.update_or_create(
                    student=student,
                    subject=subject,
                    session=session,
                    term=term,
                    defaults={
                        'ca_score': ca_score,
                        'theory_score': theory_score,
                        'exam_score': exam_score,
                        'submitted_at': submitted_at,
                        'uploaded_by': request.user
                    }
                )
                
                if is_new:
                    created += 1
                else:
                    updated += 1
                
            except Exception as e:
                errors.append({'row': row_num, 'error': str(e)})
        
        # Calculate class positions
        _calculate_class_positions(session, term)
        
        # Invalidate score cache
        invalidate_score_cache(session_id, term_id)
        
        logger.info(f"Exam results imported: {created} created, {updated} updated by {request.user.username}")
        
        return Response({
            'created': created,
            'updated': updated,
            'subjects_created': subjects_created,
            'failed': len(errors),
            'errors': errors[:10],
        })


# ==============================================================================
# Function-based views for CA + Theory score bulk upload
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_upload_ca_scores(request):
    """
    Bulk upload CA + Theory scores from CSV.
    
    CSV Format:
    admission_number,subject,ca_score,theory_score
    MOL/2026/001,Mathematics,25,18
    """
    if 'file' not in request.FILES:
        return Response(
            {'error': 'No file provided'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    csv_file = request.FILES['file']
    session_id = request.data.get('session_id')
    term_id = request.data.get('term_id')
    
    if not session_id or not term_id:
        return Response(
            {'error': 'session_id and term_id are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        session = AcademicSession.objects.get(id=session_id)
        term = Term.objects.get(id=term_id)
    except (AcademicSession.DoesNotExist, Term.DoesNotExist):
        return Response(
            {'error': 'Invalid session or term'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Parse CSV
    try:
        decoded_file = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded_file))
        rows = list(reader)
    except Exception as e:
        return Response(
            {'error': f'Failed to parse CSV: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not rows:
        return Response(
            {'error': 'CSV file is empty'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Process
    created_count = 0
    updated_count = 0
    errors = []
    
    with transaction.atomic():
        for idx, row in enumerate(rows, start=2):
            serializer = CAScoreUploadSerializer(data=row)
            
            if not serializer.is_valid():
                errors.append({
                    'row': idx,
                    'admission_number': row.get('admission_number', 'N/A'),
                    'errors': serializer.errors
                })
                continue
            
            data = serializer.validated_data
            
            try:
                student = ActiveStudent.objects.get(
                    admission_number=data['admission_number']
                )
                subject = Subject.objects.get(name__iexact=data['subject'])
                
                ca_score, created = CAScore.objects.update_or_create(
                    student=student,
                    subject=subject,
                    session=session,
                    term=term,
                    defaults={
                        'ca_score': data['ca_score'],
                        'theory_score': data.get('theory_score', 0),
                        'uploaded_by': request.user
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                
            except Exception as e:
                errors.append({
                    'row': idx,
                    'admission_number': row.get('admission_number', 'N/A'),
                    'errors': str(e)
                })
    
    # Invalidate cache
    invalidate_score_cache(session_id, term_id)
    
    return Response({
        'success': True,
        'message': f'Processed {len(rows)} records',
        'created': created_count,
        'updated': updated_count,
        'errors': errors if errors else None,
        'total_processed': created_count + updated_count
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_upload_exam_results(request):
    """
    Bulk upload CBT exam results and combine with CA scores.
    
    CSV Format from CBT:
    admission_number,subject,exam_score,total_questions,submitted_at
    """
    if 'file' not in request.FILES:
        return Response(
            {'error': 'No file provided'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    csv_file = request.FILES['file']
    session_id = request.data.get('session_id')
    term_id = request.data.get('term_id')
    
    if not session_id or not term_id:
        return Response(
            {'error': 'session_id and term_id are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        session = AcademicSession.objects.get(id=session_id)
        term = Term.objects.get(id=term_id)
    except (AcademicSession.DoesNotExist, Term.DoesNotExist):
        return Response(
            {'error': 'Invalid session or term'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Parse CSV
    try:
        decoded_file = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded_file))
        rows = list(reader)
    except Exception as e:
        return Response(
            {'error': f'Failed to parse CSV: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not rows:
        return Response(
            {'error': 'CSV file is empty'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Process
    created_count = 0
    updated_count = 0
    missing_ca_scores = []
    errors = []
    
    with transaction.atomic():
        for idx, row in enumerate(rows, start=2):
            serializer = ExamResultUploadSerializer(data=row)
            
            if not serializer.is_valid():
                errors.append({
                    'row': idx,
                    'admission_number': row.get('admission_number', 'N/A'),
                    'errors': serializer.errors
                })
                continue
            
            data = serializer.validated_data
            
            try:
                student = ActiveStudent.objects.get(
                    admission_number=data['admission_number']
                )
                subject = Subject.objects.get(name__iexact=data['subject'])
                
                # Get CA score
                try:
                    ca_obj = CAScore.objects.get(
                        student=student, subject=subject, session=session, term=term
                    )
                    ca_score = ca_obj.ca_score
                    theory_score = ca_obj.theory_score
                except CAScore.DoesNotExist:
                    missing_ca_scores.append({
                        'admission_number': data['admission_number'],
                        'subject': data['subject']
                    })
                    ca_score = Decimal('0')
                    theory_score = Decimal('0')
                
                # Create or update exam result
                result, created = ExamResult.objects.update_or_create(
                    student=student,
                    subject=subject,
                    session=session,
                    term=term,
                    defaults={
                        'ca_score': ca_score,
                        'theory_score': theory_score,
                        'exam_score': Decimal(str(data['exam_score'])),
                        'total_exam_questions': data.get('total_questions', 0),
                        'submitted_at': data.get('submitted_at'),
                        'uploaded_by': request.user
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                
            except Exception as e:
                errors.append({
                    'row': idx,
                    'admission_number': row.get('admission_number', 'N/A'),
                    'errors': str(e)
                })
    
    # Calculate positions
    _calculate_class_positions(session, term)
    
    # Invalidate cache
    invalidate_score_cache(session_id, term_id)
    
    return Response({
        'success': True,
        'message': f'Processed {len(rows)} results',
        'created': created_count,
        'updated': updated_count,
        'missing_ca_scores': missing_ca_scores if missing_ca_scores else None,
        'errors': errors if errors else None
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_ca_scores(request):
    """Get CA scores with filters"""
    session_id = request.query_params.get('session_id')
    term_id = request.query_params.get('term_id')
    class_level = request.query_params.get('class_level')
    subject_id = request.query_params.get('subject_id')
    
    queryset = CAScore.objects.select_related(
        'student', 'subject', 'session', 'term'
    ).all()
    
    if session_id:
        queryset = queryset.filter(session_id=session_id)
    if term_id:
        queryset = queryset.filter(term_id=term_id)
    if class_level:
        queryset = queryset.filter(student__class_level__name=class_level)
    if subject_id:
        queryset = queryset.filter(subject_id=subject_id)
    
    serializer = CAScoreSerializer(queryset, many=True)
    
    return Response({
        'success': True,
        'count': queryset.count(),
        'ca_scores': serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_exam_results(request):
    """Get exam results with filters"""
    session_id = request.query_params.get('session_id')
    term_id = request.query_params.get('term_id')
    class_level = request.query_params.get('class_level')
    subject_id = request.query_params.get('subject_id')
    
    queryset = ExamResult.objects.select_related(
        'student', 'subject', 'session', 'term'
    ).all()
    
    if session_id:
        queryset = queryset.filter(session_id=session_id)
    if term_id:
        queryset = queryset.filter(term_id=term_id)
    if class_level:
        queryset = queryset.filter(student__class_level__name=class_level)
    if subject_id:
        queryset = queryset.filter(subject_id=subject_id)
    
    serializer = ExamResultSerializer(queryset, many=True)
    
    return Response({
        'success': True,
        'count': queryset.count(),
        'results': serializer.data
    })


def _calculate_class_positions(session, term):
    """Calculate positions within each class/subject"""
    results = ExamResult.objects.filter(session=session, term=term).select_related('student')
    
    # Group by class and subject
    class_subject_groups = {}
    for result in results:
        key = (result.student.class_level_id, result.subject_id)
        if key not in class_subject_groups:
            class_subject_groups[key] = []
        class_subject_groups[key].append(result)
    
    # Calculate positions for each group
    for key, group_results in class_subject_groups.items():
        sorted_results = sorted(group_results, key=lambda x: x.total_score, reverse=True)
        
        total_students = len(sorted_results)
        scores = [r.total_score for r in sorted_results]
        avg_score = sum(scores) / total_students if total_students > 0 else 0
        highest = max(scores) if scores else 0
        lowest = min(scores) if scores else 0
        
        # Bulk update for efficiency
        for position, result in enumerate(sorted_results, start=1):
            result.position = position
            result.class_average = avg_score
            result.total_students = total_students
            result.highest_score = highest
            result.lowest_score = lowest
        
        # Batch update
        ExamResult.objects.bulk_update(
            sorted_results,
            ['position', 'class_average', 'total_students', 'highest_score', 'lowest_score']
        )