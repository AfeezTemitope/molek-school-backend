"""
MOLEK School - Score Management Views
ViewSets and functions for CA scores and exam results management
"""
import csv
import io
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg
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
)
from ..permissions import IsAdminOrSuperAdmin
from ..cache_utils import (
    invalidate_score_cache,
)

logger = logging.getLogger(__name__)


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
        """Optimized queryset with select_related and additional filters"""
        queryset = CAScore.objects.select_related(
            'student', 'subject', 'session', 'term', 'uploaded_by'
        ).all()
        
        # Additional filter for class_level
        class_level = self.request.query_params.get('class_level')
        if class_level:
            queryset = queryset.filter(student__class_level_id=class_level)
        
        return queryset
    
    @action(detail=False, methods=['post'], url_path='bulk-upload')
    def bulk_upload(self, request):
        """
        Bulk upload CA + Theory scores via CSV.
        
        CSV Format: admission_number, subject, ca_score, theory_score
        Example:
            admission_number,subject,ca_score,theory_score
            MOL/2026/001,Mathematics,25,18
            MOL/2026/001,English Language,22,15
            MOL/2026/001,Science,28,20
        
        - Subject is auto-created if not exists
        - ca_score: max 30
        - theory_score: varies by subject (teacher decides max)
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
                admission_number = row.get('admission_number', '').strip().upper()
                subject_name = row.get('subject', '').strip()
                ca_score_str = row.get('ca_score', '0').strip()
                theory_score_str = row.get('theory_score', '0').strip()
                
                if not admission_number or not subject_name:
                    errors.append({
                        'row': row_num,
                        'error': 'admission_number and subject are required'
                    })
                    continue
                
                # Parse scores
                try:
                    ca_score = Decimal(ca_score_str) if ca_score_str else Decimal('0')
                    theory_score = Decimal(theory_score_str) if theory_score_str else Decimal('0')
                except:
                    errors.append({
                        'row': row_num,
                        'error': 'Invalid score format'
                    })
                    continue
                
                # Validate CA score (max 30)
                if ca_score > 30:
                    errors.append({
                        'row': row_num,
                        'error': f'CA score {ca_score} exceeds maximum of 30'
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
                        'error': f'Student {admission_number} not found'
                    })
                    continue
                
                # Get or CREATE subject by NAME
                subject, subj_created = Subject.objects.get_or_create(
                    name__iexact=subject_name,
                    defaults={
                        'name': subject_name,
                        'code': subject_name[:3].upper() + '101',
                        'is_active': True
                    }
                )
                if subj_created:
                    subjects_created += 1
                
                # Create or update CA score
                ca_obj, is_new = CAScore.objects.update_or_create(
                    student=student,
                    subject=subject,
                    session=session,
                    term=term,
                    defaults={
                        'ca_score': ca_score,
                        'theory_score': theory_score,
                        'uploaded_by': request.user
                    }
                )
                
                if is_new:
                    created += 1
                else:
                    updated += 1
                
            except Exception as e:
                errors.append({'row': row_num, 'error': str(e)})
        
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
        """Export CA + Theory scores template CSV"""
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="ca_theory_scores_template.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['admission_number', 'subject', 'ca_score', 'theory_score'])
        writer.writerow(['MOL/2026/001', 'Mathematics', '25', '18'])
        writer.writerow(['MOL/2026/001', 'English Language', '22', '15'])
        writer.writerow(['MOL/2026/001', 'Science', '28', '20'])
        writer.writerow(['MOL/2026/002', 'Mathematics', '20', '14'])
        writer.writerow(['MOL/2026/002', 'English Language', '24', '16'])
        writer.writerow(['MOL/2026/002', 'Science', '26', '18'])
        
        return response


class ExamResultViewSet(viewsets.ModelViewSet):
    """
    CRUD for exam results.
    
    Features:
    - Filter by student, subject, session, term, class_level
    - Bulk import from CBT CSV
    - Recalculate positions
    - Auto-calculate total and grade on create/update
    """
    queryset = ExamResult.objects.all()
    serializer_class = ExamResultSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'subject', 'session', 'term']
    
    def get_queryset(self):
        """Optimized queryset with select_related and additional filters"""
        queryset = ExamResult.objects.select_related(
            'student', 'subject', 'session', 'term', 'uploaded_by'
        ).order_by('-uploaded_at')
        
        # Additional filter for class_level
        class_level = self.request.query_params.get('class_level')
        if class_level:
            queryset = queryset.filter(student__class_level_id=class_level)
        
        return queryset
    
    def perform_create(self, serializer):
        """Auto-calculate total, grade on create"""
        instance = serializer.save(uploaded_by=self.request.user)
        self._calculate_result(instance)
    
    def perform_update(self, serializer):
        """Auto-calculate total, grade on update"""
        instance = serializer.save()
        self._calculate_result(instance)
    
    def _calculate_result(self, instance):
        """Calculate total score and grade"""
        ca = float(instance.ca_score or 0)
        theory = float(instance.theory_score or 0)
        exam = float(instance.exam_score or 0)
        
        total = ca + theory + exam
        instance.total_score = Decimal(str(total))
        instance.grade = get_grade(total)
        instance.save(update_fields=['total_score', 'grade'])
    
    @action(detail=False, methods=['post'], url_path='recalculate-positions')
    def recalculate_positions(self, request):
        """
        Recalculate positions for all results in a session/term.
        
        Request body:
        {
            "session": 1,
            "term": 1,
            "class_level": 1  // optional
        }
        """
        session_id = request.data.get('session')
        term_id = request.data.get('term')
        class_level_id = request.data.get('class_level')
        
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
        
        # Get all subjects with results
        results_query = ExamResult.objects.filter(
            session_id=session_id,
            term_id=term_id
        )
        
        if class_level_id:
            results_query = results_query.filter(student__class_level_id=class_level_id)
        
        subjects = results_query.values_list('subject_id', flat=True).distinct()
        
        subjects_processed = 0
        for subject_id in subjects:
            # Get results for this subject, ordered by total score
            subject_results = list(results_query.filter(
                subject_id=subject_id
            ).order_by('-total_score'))
            
            if not subject_results:
                continue
            
            total_students = len(subject_results)
            scores = [float(r.total_score or 0) for r in subject_results]
            class_avg = sum(scores) / total_students if total_students > 0 else 0
            highest = max(scores) if scores else 0
            lowest = min(scores) if scores else 0
            
            # Assign positions (handle ties)
            position = 0
            prev_score = None
            
            for idx, result in enumerate(subject_results):
                current_score = float(result.total_score or 0)
                if current_score != prev_score:
                    position = idx + 1
                    prev_score = current_score
                
                result.position = position
                result.total_students = total_students
                result.class_average = Decimal(str(round(class_avg, 2)))
                result.highest_score = Decimal(str(highest))
                result.lowest_score = Decimal(str(lowest))
            
            # Bulk update
            ExamResult.objects.bulk_update(
                subject_results,
                ['position', 'total_students', 'class_average', 'highest_score', 'lowest_score']
            )
            subjects_processed += 1
        
        invalidate_score_cache(session_id, term_id)
        
        logger.info(f"Positions recalculated: {subjects_processed} subjects by {request.user.username}")
        
        return Response({
            'success': True,
            'message': 'Positions recalculated successfully',
            'subjects_processed': subjects_processed
        })
    
    @action(detail=False, methods=['post'], url_path='bulk-import')
    def bulk_import(self, request):
        """
        Bulk import exam results from CBT CSV.
        
        CSV Format: admission_number, subject, exam_score
        Example:
            admission_number,subject,exam_score
            MOL/2026/001,Mathematics,56
            MOL/2026/001,English Language,49
        
        - Subject is auto-created if not exists
        - CA + Theory scores are pulled from CAScore table
        - Total = CA + Theory + Exam
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
        missing_ca = []
        errors = []
        row_num = 1
        
        for row in reader:
            row_num += 1
            try:
                admission_number = row.get('admission_number', '').strip().upper()
                subject_name = row.get('subject', '').strip()
                exam_score_str = row.get('exam_score', '0').strip()
                
                if not admission_number or not subject_name:
                    errors.append({
                        'row': row_num,
                        'error': 'admission_number and subject are required'
                    })
                    continue
                
                # Parse exam score
                try:
                    exam_score = Decimal(exam_score_str) if exam_score_str else Decimal('0')
                except:
                    errors.append({
                        'row': row_num,
                        'error': 'Invalid exam score format'
                    })
                    continue
                
                # Validate exam score (max 70 for CBT portion)
                if exam_score > 70:
                    errors.append({
                        'row': row_num,
                        'error': f'Exam score {exam_score} exceeds maximum of 70'
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
                        'error': f'Student {admission_number} not found'
                    })
                    continue
                
                # Get or CREATE subject by NAME
                subject, subj_created = Subject.objects.get_or_create(
                    name__iexact=subject_name,
                    defaults={
                        'name': subject_name,
                        'code': subject_name[:3].upper() + '101',
                        'is_active': True
                    }
                )
                if subj_created:
                    subjects_created += 1
                
                # Get CA + Theory scores if exists
                ca_score = Decimal('0')
                theory_score = Decimal('0')
                try:
                    ca_obj = CAScore.objects.get(
                        student=student, subject=subject, session=session, term=term
                    )
                    ca_score = ca_obj.ca_score
                    theory_score = ca_obj.theory_score
                except CAScore.DoesNotExist:
                    missing_ca.append({
                        'admission_number': admission_number,
                        'subject': subject_name
                    })
                
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
                        'uploaded_by': request.user
                    }
                )
                
                if is_new:
                    created += 1
                else:
                    updated += 1
                
            except Exception as e:
                errors.append({'row': row_num, 'error': str(e)})
        
        # Calculate positions after import
        _calculate_class_positions(session, term)
        
        invalidate_score_cache(session_id, term_id)
        
        logger.info(f"Exam results imported: {created} created, {updated} updated by {request.user.username}")
        
        return Response({
            'created': created,
            'updated': updated,
            'subjects_created': subjects_created,
            'failed': len(errors),
            'missing_ca_scores': missing_ca[:10] if missing_ca else None,
            'errors': errors[:10],
        })
    
    @action(detail=False, methods=['get'], url_path='export-template')
    def export_template(self, request):
        """Export exam results template CSV (CBT format)"""
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="exam_results_template.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['admission_number', 'subject', 'exam_score'])
        writer.writerow(['MOL/2026/001', 'Mathematics', '56'])
        writer.writerow(['MOL/2026/001', 'English Language', '49'])
        writer.writerow(['MOL/2026/001', 'Science', '42'])
        writer.writerow(['MOL/2026/002', 'Mathematics', '63'])
        
        return response


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminOrSuperAdmin])
def bulk_upload_ca_scores(request):
    """
    Upload CA + Theory scores from CSV file.
    
    CSV Format: admission_number, subject, ca_score, theory_score
    
    - ca_score: Continuous Assessment (max 30)
    - theory_score: Theory/Essay score (varies by subject)
    - Subjects are auto-created if they don't exist
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
    
    created_count = 0
    updated_count = 0
    subjects_created = 0
    errors = []
    
    with transaction.atomic():
        for idx, row in enumerate(rows, start=2):
            try:
                admission_number = row.get('admission_number', '').strip().upper()
                subject_name = row.get('subject', '').strip()
                ca_score = Decimal(row.get('ca_score', '0').strip() or '0')
                theory_score = Decimal(row.get('theory_score', '0').strip() or '0')
                
                if not admission_number or not subject_name:
                    errors.append({
                        'row': idx,
                        'error': 'admission_number and subject are required'
                    })
                    continue
                
                # Validate CA score
                if ca_score > 30:
                    errors.append({
                        'row': idx,
                        'admission_number': admission_number,
                        'error': 'CA score exceeds 30'
                    })
                    continue
                
                # Get student
                try:
                    student = ActiveStudent.objects.get(admission_number=admission_number)
                except ActiveStudent.DoesNotExist:
                    errors.append({
                        'row': idx,
                        'admission_number': admission_number,
                        'error': 'Student not found'
                    })
                    continue
                
                # Get or CREATE subject
                subject, subj_created = Subject.objects.get_or_create(
                    name__iexact=subject_name,
                    defaults={
                        'name': subject_name,
                        'code': subject_name[:3].upper() + '101',
                        'is_active': True
                    }
                )
                if subj_created:
                    subjects_created += 1
                
                # Create or update CA score
                ca_obj, created = CAScore.objects.update_or_create(
                    student=student,
                    subject=subject,
                    session=session,
                    term=term,
                    defaults={
                        'ca_score': ca_score,
                        'theory_score': theory_score,
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
                    'error': str(e)
                })
    
    invalidate_score_cache(session_id, term_id)
    
    logger.info(f"CA scores uploaded: {created_count} created, {updated_count} updated by {request.user.username}")
    
    return Response({
        'success': True,
        'message': f'Processed {len(rows)} CA scores',
        'created': created_count,
        'updated': updated_count,
        'subjects_created': subjects_created,
        'errors': errors[:10] if errors else None
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminOrSuperAdmin])
def bulk_upload_exam_results(request):
    """
    Upload exam results from CBT CSV file.
    
    CSV Format: admission_number, subject, exam_score
    
    - Pulls CA + Theory from CAScore table
    - Calculates: Total = CA + Theory + Exam
    - Subjects are auto-created if they don't exist
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
    
    created_count = 0
    updated_count = 0
    subjects_created = 0
    missing_ca_scores = []
    errors = []
    
    with transaction.atomic():
        for idx, row in enumerate(rows, start=2):
            try:
                admission_number = row.get('admission_number', '').strip().upper()
                subject_name = row.get('subject', '').strip()
                exam_score = Decimal(row.get('exam_score', '0').strip() or '0')
                
                if not admission_number or not subject_name:
                    errors.append({
                        'row': idx,
                        'error': 'admission_number and subject are required'
                    })
                    continue
                
                # Validate exam score
                if exam_score > 70:
                    errors.append({
                        'row': idx,
                        'admission_number': admission_number,
                        'error': 'Exam score exceeds 70'
                    })
                    continue
                
                # Get student
                try:
                    student = ActiveStudent.objects.get(admission_number=admission_number)
                except ActiveStudent.DoesNotExist:
                    errors.append({
                        'row': idx,
                        'admission_number': admission_number,
                        'error': 'Student not found'
                    })
                    continue
                
                # Get or CREATE subject
                subject, subj_created = Subject.objects.get_or_create(
                    name__iexact=subject_name,
                    defaults={
                        'name': subject_name,
                        'code': subject_name[:3].upper() + '101',
                        'is_active': True
                    }
                )
                if subj_created:
                    subjects_created += 1
                
                # Get CA + Theory scores
                ca_score = Decimal('0')
                theory_score = Decimal('0')
                try:
                    ca_obj = CAScore.objects.get(
                        student=student, subject=subject, session=session, term=term
                    )
                    ca_score = ca_obj.ca_score
                    theory_score = ca_obj.theory_score
                except CAScore.DoesNotExist:
                    missing_ca_scores.append({
                        'admission_number': admission_number,
                        'subject': subject_name
                    })
                
                # Create or update exam result
                result, created = ExamResult.objects.update_or_create(
                    student=student,
                    subject=subject,
                    session=session,
                    term=term,
                    defaults={
                        'ca_score': ca_score,
                        'theory_score': theory_score,
                        'exam_score': exam_score,
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
                    'error': str(e)
                })
    
    # Calculate positions
    _calculate_class_positions(session, term)
    
    invalidate_score_cache(session_id, term_id)
    
    logger.info(f"Exam results imported: {created_count} created, {updated_count} updated by {request.user.username}")
    
    return Response({
        'success': True,
        'message': f'Processed {len(rows)} results',
        'created': created_count,
        'updated': updated_count,
        'subjects_created': subjects_created,
        'missing_ca_scores': missing_ca_scores[:10] if missing_ca_scores else None,
        'errors': errors[:10] if errors else None
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
    
    class_subject_groups = {}
    for result in results:
        key = (result.student.class_level_id, result.subject_id)
        if key not in class_subject_groups:
            class_subject_groups[key] = []
        class_subject_groups[key].append(result)
    
    for key, group_results in class_subject_groups.items():
        sorted_results = sorted(group_results, key=lambda x: float(x.total_score or 0), reverse=True)
        
        total_students = len(sorted_results)
        scores = [float(r.total_score or 0) for r in sorted_results]
        avg_score = sum(scores) / total_students if total_students > 0 else 0
        highest = max(scores) if scores else 0
        lowest = min(scores) if scores else 0
        
        # Handle ties
        position = 0
        prev_score = None
        
        for idx, result in enumerate(sorted_results):
            current_score = float(result.total_score or 0)
            if current_score != prev_score:
                position = idx + 1
                prev_score = current_score
            
            result.position = position
            result.class_average = Decimal(str(round(avg_score, 2)))
            result.total_students = total_students
            result.highest_score = Decimal(str(highest))
            result.lowest_score = Decimal(str(lowest))
        
        ExamResult.objects.bulk_update(
            sorted_results,
            ['position', 'class_average', 'total_students', 'highest_score', 'lowest_score']
        )