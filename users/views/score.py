"""
MOLEK School - Score Management Views
Updated for Nigerian Secondary School Grading:
- CA1: 15 marks (manual)
- CA2: 15 marks (manual)
- OBJ/CBT: 30 marks (from CBT)
- Theory: 40 marks (manual)
- Total: 100 marks

Grading Scale:
- A: 75-100 (Excellent)
- B: 70-74 (Very Good)
- C: 60-69 (Good)
- D: 50-59 (Pass)
- E: 45-49 (Fair)
- F: 0-44 (Fail)
"""
import csv
import io
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg
from django.http import HttpResponse
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
    """
    Convert score to letter grade using Nigerian Secondary School grading scale
    
    Returns: (grade, remark) tuple
    """
    score = float(score) if score else 0
    if score >= 75:
        return ('A', 'Excellent')
    elif score >= 70:
        return ('B', 'Very Good')
    elif score >= 60:
        return ('C', 'Good')
    elif score >= 50:
        return ('D', 'Pass')
    elif score >= 45:
        return ('E', 'Fair')
    else:
        return ('F', 'Fail')


# ==============================================================================
# CA SCORE VIEWSET (CA1 + CA2)
# ==============================================================================
class CAScoreViewSet(viewsets.ModelViewSet):
    """
    CRUD for CA scores (CA1 + CA2).
    
    Nigerian School Format:
    - CA1: max 15 marks
    - CA2: max 15 marks
    - Total CA: 30 marks
    """
    queryset = CAScore.objects.all()
    serializer_class = CAScoreSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'subject', 'session', 'term']
    
    def get_queryset(self):
        queryset = CAScore.objects.select_related(
            'student', 'student__class_level', 'subject', 'session', 'term', 'uploaded_by'
        ).all()
        
        class_level = self.request.query_params.get('class_level')
        if class_level:
            queryset = queryset.filter(student__class_level_id=class_level)
        
        return queryset
    
    @action(detail=False, methods=['post'], url_path='bulk-upload')
    def bulk_upload(self, request):
        """
        Bulk upload CA scores (CA1 + CA2) via CSV.
        
        CSV Format:
            admission_number,subject,ca1_score,ca2_score
            MOL/2026/001,Mathematics,12,13
        """
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        session_id = request.data.get('session')
        term_id = request.data.get('term')
        
        if not session_id or not term_id:
            return Response({'error': 'Session and term are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            session = AcademicSession.objects.get(id=session_id)
            term = Term.objects.get(id=term_id)
        except (AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response({'error': 'Invalid session or term'}, status=status.HTTP_400_BAD_REQUEST)
        
        csv_file = request.FILES['file']
        
        try:
            decoded_file = csv_file.read().decode('utf-8')
        except UnicodeDecodeError:
            return Response({'error': 'Invalid file encoding. Use UTF-8.'}, status=status.HTTP_400_BAD_REQUEST)
        
        reader = csv.DictReader(io.StringIO(decoded_file))
        
        created, updated, subjects_created = 0, 0, 0
        errors = []
        row_num = 1
        
        for row in reader:
            row_num += 1
            try:
                admission_number = row.get('admission_number', '').strip().upper()
                subject_name = row.get('subject', '').strip()
                ca1_score = Decimal(row.get('ca1_score', '0').strip() or '0')
                ca2_score = Decimal(row.get('ca2_score', '0').strip() or '0')
                
                if not admission_number or not subject_name:
                    errors.append({'row': row_num, 'error': 'Missing required fields'})
                    continue
                
                if ca1_score > 15 or ca2_score > 15:
                    errors.append({'row': row_num, 'error': 'CA score exceeds max (15)'})
                    continue
                
                try:
                    student = ActiveStudent.objects.get(admission_number=admission_number, is_active=True)
                except ActiveStudent.DoesNotExist:
                    errors.append({'row': row_num, 'error': f'Student {admission_number} not found'})
                    continue
                
                subject, subj_created = Subject.objects.get_or_create(
                    name__iexact=subject_name,
                    defaults={'name': subject_name, 'code': subject_name[:3].upper() + '101', 'is_active': True}
                )
                if subj_created:
                    subjects_created += 1
                
                ca_obj, is_new = CAScore.objects.update_or_create(
                    student=student, subject=subject, session=session, term=term,
                    defaults={'ca1_score': ca1_score, 'ca2_score': ca2_score, 'uploaded_by': request.user}
                )
                
                created += 1 if is_new else 0
                updated += 0 if is_new else 1
                
            except Exception as e:
                errors.append({'row': row_num, 'error': str(e)})
        
        invalidate_score_cache(session_id, term_id)
        logger.info(f"CA scores uploaded: {created} created, {updated} updated by {request.user.username}")
        
        return Response({
            'success': True, 'created': created, 'updated': updated,
            'subjects_created': subjects_created, 'failed': len(errors), 'errors': errors[:10]
        })
    
    @action(detail=False, methods=['get'], url_path='export-template')
    def export_template(self, request):
        """Export CA scores template CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="ca_scores_template.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['admission_number', 'subject', 'ca1_score', 'ca2_score'])
        writer.writerow(['MOL/2026/001', 'Mathematics', '12', '13'])
        writer.writerow(['MOL/2026/001', 'English Language', '14', '12'])
        writer.writerow(['# NOTE: CA1 max = 15, CA2 max = 15', '', '', ''])
        
        return response


# ==============================================================================
# EXAM RESULT VIEWSET
# ==============================================================================
class ExamResultViewSet(viewsets.ModelViewSet):
    """
    CRUD for exam results.
    
    Nigerian School Format:
    - CA1: 15 marks (from CAScore)
    - CA2: 15 marks (from CAScore)
    - OBJ/CBT: 30 marks (from CBT export)
    - Theory: 40 marks (manual entry)
    - Total: 100 marks
    """
    queryset = ExamResult.objects.all()
    serializer_class = ExamResultSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'subject', 'session', 'term']
    
    def get_queryset(self):
        queryset = ExamResult.objects.select_related(
            'student', 'student__class_level', 'subject', 'session', 'term', 'uploaded_by'
        ).order_by('-uploaded_at')
        
        class_level = self.request.query_params.get('class_level')
        if class_level:
            queryset = queryset.filter(student__class_level_id=class_level)
        
        return queryset
    
    @action(detail=False, methods=['post'], url_path='import-obj-scores')
    def import_obj_scores(self, request):
        """
        Import OBJ/CBT scores from CBT export CSV.
        
        CSV Format:
            admission_number,subject,obj_score,total_questions
            MOL/2026/001,Mathematics,25,30
        
        - obj_score: RAW score (max 30)
        - Auto-pulls CA1+CA2 from CAScore table
        """
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        session_id = request.data.get('session')
        term_id = request.data.get('term')
        
        if not session_id or not term_id:
            return Response({'error': 'Session and term are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            session = AcademicSession.objects.get(id=session_id)
            term = Term.objects.get(id=term_id)
        except (AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response({'error': 'Invalid session or term'}, status=status.HTTP_400_BAD_REQUEST)
        
        csv_file = request.FILES['file']
        
        try:
            decoded_file = csv_file.read().decode('utf-8')
        except UnicodeDecodeError:
            return Response({'error': 'Invalid file encoding. Use UTF-8.'}, status=status.HTTP_400_BAD_REQUEST)
        
        reader = csv.DictReader(io.StringIO(decoded_file))
        
        created, updated, subjects_created = 0, 0, 0
        missing_ca, errors = [], []
        row_num = 1
        
        with transaction.atomic():
            for row in reader:
                row_num += 1
                try:
                    admission_number = row.get('admission_number', '').strip().upper()
                    subject_name = row.get('subject', '').strip()
                    obj_score = Decimal(row.get('obj_score', '0').strip() or '0')
                    total_questions = int(row.get('total_questions', '30').strip() or '30')
                    
                    if not admission_number or not subject_name:
                        errors.append({'row': row_num, 'error': 'Missing required fields'})
                        continue
                    
                    if obj_score > 30:
                        errors.append({'row': row_num, 'error': 'OBJ score exceeds max (30)'})
                        continue
                    
                    try:
                        student = ActiveStudent.objects.get(admission_number=admission_number, is_active=True)
                    except ActiveStudent.DoesNotExist:
                        errors.append({'row': row_num, 'error': f'Student {admission_number} not found'})
                        continue
                    
                    subject, subj_created = Subject.objects.get_or_create(
                        name__iexact=subject_name,
                        defaults={'name': subject_name, 'code': subject_name[:3].upper() + '101', 'is_active': True}
                    )
                    if subj_created:
                        subjects_created += 1
                    
                    # Get CA scores
                    ca1_score, ca2_score = Decimal('0'), Decimal('0')
                    try:
                        ca_obj = CAScore.objects.get(student=student, subject=subject, session=session, term=term)
                        ca1_score = ca_obj.ca1_score or Decimal('0')
                        ca2_score = ca_obj.ca2_score or Decimal('0')
                    except CAScore.DoesNotExist:
                        missing_ca.append({'admission_number': admission_number, 'subject': subject_name})
                    
                    result, is_created = ExamResult.objects.update_or_create(
                        student=student, subject=subject, session=session, term=term,
                        defaults={
                            'ca1_score': ca1_score, 'ca2_score': ca2_score,
                            'obj_score': obj_score, 'total_obj_questions': total_questions,
                            'uploaded_by': request.user
                        }
                    )
                    
                    created += 1 if is_created else 0
                    updated += 0 if is_created else 1
                    
                except Exception as e:
                    errors.append({'row': row_num, 'error': str(e)})
        
        _calculate_class_positions(session, term)
        invalidate_score_cache(session_id, term_id)
        
        return Response({
            'success': True, 'created': created, 'updated': updated,
            'subjects_created': subjects_created, 'missing_ca_scores': missing_ca[:10],
            'failed': len(errors), 'errors': errors[:10]
        })
    
    @action(detail=False, methods=['post'], url_path='import-theory-scores')
    def import_theory_scores(self, request):
        """
        Import Theory scores from CSV.
        
        CSV Format:
            admission_number,subject,theory_score
            MOL/2026/001,Mathematics,35
        
        - theory_score: max 40
        """
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        session_id = request.data.get('session')
        term_id = request.data.get('term')
        
        if not session_id or not term_id:
            return Response({'error': 'Session and term are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            session = AcademicSession.objects.get(id=session_id)
            term = Term.objects.get(id=term_id)
        except (AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response({'error': 'Invalid session or term'}, status=status.HTTP_400_BAD_REQUEST)
        
        csv_file = request.FILES['file']
        
        try:
            decoded_file = csv_file.read().decode('utf-8')
        except UnicodeDecodeError:
            return Response({'error': 'Invalid file encoding. Use UTF-8.'}, status=status.HTTP_400_BAD_REQUEST)
        
        reader = csv.DictReader(io.StringIO(decoded_file))
        
        created, updated, subjects_created = 0, 0, 0
        errors = []
        row_num = 1
        
        with transaction.atomic():
            for row in reader:
                row_num += 1
                try:
                    admission_number = row.get('admission_number', '').strip().upper()
                    subject_name = row.get('subject', '').strip()
                    theory_score = Decimal(row.get('theory_score', '0').strip() or '0')
                    
                    if not admission_number or not subject_name:
                        errors.append({'row': row_num, 'error': 'Missing required fields'})
                        continue
                    
                    if theory_score > 40:
                        errors.append({'row': row_num, 'error': 'Theory score exceeds max (40)'})
                        continue
                    
                    try:
                        student = ActiveStudent.objects.get(admission_number=admission_number, is_active=True)
                    except ActiveStudent.DoesNotExist:
                        errors.append({'row': row_num, 'error': f'Student {admission_number} not found'})
                        continue
                    
                    subject, subj_created = Subject.objects.get_or_create(
                        name__iexact=subject_name,
                        defaults={'name': subject_name, 'code': subject_name[:3].upper() + '101', 'is_active': True}
                    )
                    if subj_created:
                        subjects_created += 1
                    
                    try:
                        result = ExamResult.objects.get(student=student, subject=subject, session=session, term=term)
                        result.theory_score = theory_score
                        result.save()
                        updated += 1
                    except ExamResult.DoesNotExist:
                        # Get CA scores if available
                        ca1_score, ca2_score = Decimal('0'), Decimal('0')
                        try:
                            ca_obj = CAScore.objects.get(student=student, subject=subject, session=session, term=term)
                            ca1_score = ca_obj.ca1_score or Decimal('0')
                            ca2_score = ca_obj.ca2_score or Decimal('0')
                        except CAScore.DoesNotExist:
                            pass
                        
                        ExamResult.objects.create(
                            student=student, subject=subject, session=session, term=term,
                            ca1_score=ca1_score, ca2_score=ca2_score,
                            obj_score=Decimal('0'), theory_score=theory_score,
                            uploaded_by=request.user
                        )
                        created += 1
                        
                except Exception as e:
                    errors.append({'row': row_num, 'error': str(e)})
        
        _calculate_class_positions(session, term)
        invalidate_score_cache(session_id, term_id)
        
        return Response({
            'success': True, 'created': created, 'updated': updated,
            'subjects_created': subjects_created, 'failed': len(errors), 'errors': errors[:10]
        })
    
    @action(detail=False, methods=['post'], url_path='recalculate-positions')
    def recalculate_positions(self, request):
        """Recalculate positions for all results in a session/term."""
        session_id = request.data.get('session')
        term_id = request.data.get('term')
        class_level_id = request.data.get('class_level')
        
        if not session_id or not term_id:
            return Response({'error': 'Session and term are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            session = AcademicSession.objects.get(id=session_id)
            term = Term.objects.get(id=term_id)
        except (AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response({'error': 'Invalid session or term'}, status=status.HTTP_400_BAD_REQUEST)
        
        subjects_processed = _calculate_class_positions(session, term, class_level_id)
        invalidate_score_cache(session_id, term_id)
        
        return Response({
            'success': True, 'message': 'Positions recalculated',
            'subjects_processed': subjects_processed
        })
    
    @action(detail=False, methods=['post'], url_path='sync-ca-scores')
    def sync_ca_scores(self, request):
        """Sync CA1+CA2 scores from CAScore table to ExamResult table."""
        session_id = request.data.get('session')
        term_id = request.data.get('term')
        
        if not session_id or not term_id:
            return Response({'error': 'Session and term are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            session = AcademicSession.objects.get(id=session_id)
            term = Term.objects.get(id=term_id)
        except (AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response({'error': 'Invalid session or term'}, status=status.HTTP_400_BAD_REQUEST)
        
        updated = 0
        ca_scores = CAScore.objects.filter(session=session, term=term)
        
        with transaction.atomic():
            for ca in ca_scores:
                try:
                    result = ExamResult.objects.get(
                        student=ca.student, subject=ca.subject, session=session, term=term
                    )
                    result.ca1_score = ca.ca1_score
                    result.ca2_score = ca.ca2_score
                    result.save()
                    updated += 1
                except ExamResult.DoesNotExist:
                    pass
        
        invalidate_score_cache(session_id, term_id)
        
        return Response({'success': True, 'updated': updated})
    
    @action(detail=False, methods=['get'], url_path='export-template-obj')
    def export_template_obj(self, request):
        """Export OBJ scores template CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="obj_scores_template.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['admission_number', 'subject', 'obj_score', 'total_questions'])
        writer.writerow(['MOL/2026/001', 'Mathematics', '25', '30'])
        writer.writerow(['# NOTE: obj_score max = 30 (RAW score)', '', '', ''])
        
        return response
    
    @action(detail=False, methods=['get'], url_path='export-template-theory')
    def export_template_theory(self, request):
        """Export Theory scores template CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="theory_scores_template.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['admission_number', 'subject', 'theory_score'])
        writer.writerow(['MOL/2026/001', 'Mathematics', '35'])
        writer.writerow(['# NOTE: theory_score max = 40', '', ''])
        
        return response


# ==============================================================================
# STANDALONE API VIEWS
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminOrSuperAdmin])
def bulk_upload_ca_scores(request):
    """
    Upload CA scores (CA1 + CA2) from CSV file.
    
    CSV Format: admission_number, subject, ca1_score, ca2_score
    """
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    csv_file = request.FILES['file']
    session_id = request.data.get('session_id') or request.data.get('session')
    term_id = request.data.get('term_id') or request.data.get('term')
    
    if not session_id or not term_id:
        return Response({'error': 'session_id and term_id are required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        session = AcademicSession.objects.get(id=session_id)
        term = Term.objects.get(id=term_id)
    except (AcademicSession.DoesNotExist, Term.DoesNotExist):
        return Response({'error': 'Invalid session or term'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        decoded_file = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded_file))
        rows = list(reader)
    except Exception as e:
        return Response({'error': f'Failed to parse CSV: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not rows:
        return Response({'error': 'CSV file is empty'}, status=status.HTTP_400_BAD_REQUEST)
    
    created_count, updated_count, subjects_created = 0, 0, 0
    errors = []
    
    with transaction.atomic():
        for idx, row in enumerate(rows, start=2):
            try:
                admission_number = row.get('admission_number', '').strip().upper()
                subject_name = row.get('subject', '').strip()
                ca1_score = Decimal(row.get('ca1_score', '0').strip() or '0')
                ca2_score = Decimal(row.get('ca2_score', '0').strip() or '0')
                
                if not admission_number or not subject_name:
                    errors.append({'row': idx, 'error': 'Missing required fields'})
                    continue
                
                if ca1_score > 15:
                    errors.append({'row': idx, 'admission_number': admission_number, 'error': 'CA1 score exceeds 15'})
                    continue
                
                if ca2_score > 15:
                    errors.append({'row': idx, 'admission_number': admission_number, 'error': 'CA2 score exceeds 15'})
                    continue
                
                try:
                    student = ActiveStudent.objects.get(admission_number=admission_number)
                except ActiveStudent.DoesNotExist:
                    errors.append({'row': idx, 'admission_number': admission_number, 'error': 'Student not found'})
                    continue
                
                subject, subj_created = Subject.objects.get_or_create(
                    name__iexact=subject_name,
                    defaults={'name': subject_name, 'code': subject_name[:3].upper() + '101', 'is_active': True}
                )
                if subj_created:
                    subjects_created += 1
                
                ca_obj, created = CAScore.objects.update_or_create(
                    student=student, subject=subject, session=session, term=term,
                    defaults={'ca1_score': ca1_score, 'ca2_score': ca2_score, 'uploaded_by': request.user}
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                    
            except Exception as e:
                errors.append({'row': idx, 'admission_number': row.get('admission_number', 'N/A'), 'error': str(e)})
    
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
    Upload exam results from CSV file.
    
    CSV Format: admission_number, subject, obj_score, theory_score
    OR (legacy): admission_number, subject, exam_score
    
    - Pulls CA1 + CA2 from CAScore table
    - obj_score max = 30
    - theory_score max = 40
    """
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    csv_file = request.FILES['file']
    session_id = request.data.get('session_id') or request.data.get('session')
    term_id = request.data.get('term_id') or request.data.get('term')
    
    if not session_id or not term_id:
        return Response({'error': 'session_id and term_id are required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        session = AcademicSession.objects.get(id=session_id)
        term = Term.objects.get(id=term_id)
    except (AcademicSession.DoesNotExist, Term.DoesNotExist):
        return Response({'error': 'Invalid session or term'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        decoded_file = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded_file))
        rows = list(reader)
    except Exception as e:
        return Response({'error': f'Failed to parse CSV: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not rows:
        return Response({'error': 'CSV file is empty'}, status=status.HTTP_400_BAD_REQUEST)
    
    created_count, updated_count, subjects_created = 0, 0, 0
    missing_ca_scores = []
    errors = []
    
    with transaction.atomic():
        for idx, row in enumerate(rows, start=2):
            try:
                admission_number = row.get('admission_number', '').strip().upper()
                subject_name = row.get('subject', '').strip()
                
                # Support both new format (obj_score, theory_score) and legacy (exam_score)
                if 'obj_score' in row:
                    obj_score = Decimal(row.get('obj_score', '0').strip() or '0')
                    theory_score = Decimal(row.get('theory_score', '0').strip() or '0')
                else:
                    # Legacy format: exam_score was scaled to 70, now we need to split
                    exam_score = Decimal(row.get('exam_score', '0').strip() or '0')
                    # Assume 30/40 split for legacy data
                    obj_score = min(exam_score * Decimal('0.43'), Decimal('30'))  # ~30% of 70
                    theory_score = min(exam_score * Decimal('0.57'), Decimal('40'))  # ~40% of 70
                
                if not admission_number or not subject_name:
                    errors.append({'row': idx, 'error': 'Missing required fields'})
                    continue
                
                if obj_score > 30:
                    errors.append({'row': idx, 'admission_number': admission_number, 'error': 'OBJ score exceeds 30'})
                    continue
                
                if theory_score > 40:
                    errors.append({'row': idx, 'admission_number': admission_number, 'error': 'Theory score exceeds 40'})
                    continue
                
                try:
                    student = ActiveStudent.objects.get(admission_number=admission_number)
                except ActiveStudent.DoesNotExist:
                    errors.append({'row': idx, 'admission_number': admission_number, 'error': 'Student not found'})
                    continue
                
                subject, subj_created = Subject.objects.get_or_create(
                    name__iexact=subject_name,
                    defaults={'name': subject_name, 'code': subject_name[:3].upper() + '101', 'is_active': True}
                )
                if subj_created:
                    subjects_created += 1
                
                # Get CA scores
                ca1_score, ca2_score = Decimal('0'), Decimal('0')
                try:
                    ca_obj = CAScore.objects.get(student=student, subject=subject, session=session, term=term)
                    ca1_score = ca_obj.ca1_score or Decimal('0')
                    ca2_score = ca_obj.ca2_score or Decimal('0')
                except CAScore.DoesNotExist:
                    missing_ca_scores.append({'admission_number': admission_number, 'subject': subject_name})
                
                result, created = ExamResult.objects.update_or_create(
                    student=student, subject=subject, session=session, term=term,
                    defaults={
                        'ca1_score': ca1_score,
                        'ca2_score': ca2_score,
                        'obj_score': obj_score,
                        'theory_score': theory_score,
                        'uploaded_by': request.user
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                    
            except Exception as e:
                errors.append({'row': idx, 'admission_number': row.get('admission_number', 'N/A'), 'error': str(e)})
    
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
        'student', 'student__class_level', 'subject', 'session', 'term'
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
        'success': True, 'count': queryset.count(), 'ca_scores': serializer.data
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
        'student', 'student__class_level', 'subject', 'session', 'term'
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
        'success': True, 'count': queryset.count(), 'results': serializer.data
    })


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def _calculate_class_positions(session, term, class_level_id=None):
    """Calculate positions within each class/subject combination."""
    results_query = ExamResult.objects.filter(
        session=session, term=term
    ).select_related('student', 'student__class_level')
    
    if class_level_id:
        results_query = results_query.filter(student__class_level_id=class_level_id)
    
    class_subject_groups = {}
    for result in results_query:
        if result.student.class_level_id:
            key = (result.student.class_level_id, result.subject.id)
            if key not in class_subject_groups:
                class_subject_groups[key] = []
            class_subject_groups[key].append(result)
    
    subjects_processed = 0
    
    for key, group_results in class_subject_groups.items():
        sorted_results = sorted(group_results, key=lambda x: float(x.total_score or 0), reverse=True)
        
        total_students = len(sorted_results)
        scores = [float(r.total_score or 0) for r in sorted_results]
        avg_score = sum(scores) / total_students if total_students > 0 else 0
        highest = max(scores) if scores else 0
        lowest = min(scores) if scores else 0
        
        position, prev_score = 0, None
        
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
        subjects_processed += 1
    
    return subjects_processed