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
# HELPER: Parse CSV safely
# ==============================================================================
def _parse_csv(request):
    """Parse CSV from request.FILES['file'], return (rows, error_response)."""
    if 'file' not in request.FILES:
        return None, Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

    csv_file = request.FILES['file']

    try:
        decoded_file = csv_file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        return None, Response({'error': 'Invalid file encoding. Use UTF-8.'}, status=status.HTTP_400_BAD_REQUEST)

    reader = csv.DictReader(io.StringIO(decoded_file))
    if reader.fieldnames:
        reader.fieldnames = [f.strip() for f in reader.fieldnames]

    rows = list(reader)
    if not rows:
        return None, Response({'error': 'CSV file is empty'}, status=status.HTTP_400_BAD_REQUEST)

    return rows, None


def _get_session_and_term(request):
    """Extract and validate session/term from request data. Returns (session, term, error_response)."""
    session_id = request.data.get('session_id') or request.data.get('session')
    term_id = request.data.get('term_id') or request.data.get('term')

    if not session_id or not term_id:
        return None, None, Response(
            {'error': 'Session and term are required'}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        session = AcademicSession.objects.get(id=session_id)
        term = Term.objects.get(id=term_id)
    except (AcademicSession.DoesNotExist, Term.DoesNotExist):
        return None, None, Response(
            {'error': 'Invalid session or term'}, status=status.HTTP_400_BAD_REQUEST
        )

    return session, term, None


def _prefetch_students_and_subjects(rows):
    """
    Pre-fetch all students and subjects referenced in CSV rows.
    Returns (students_map, subjects_map) keyed by admission_number and lowercase name.
    """
    admission_numbers = set()
    subject_names = set()

    for row in rows:
        adm = row.get('admission_number', '').strip().upper()
        subj = row.get('subject', '').strip()
        if adm:
            admission_numbers.add(adm)
        if subj:
            subject_names.add(subj)

    students_map = {
        s.admission_number: s
        for s in ActiveStudent.objects.filter(
            admission_number__in=admission_numbers, is_active=True
        )
    }

    subjects_map = {}
    if subject_names:
        for s in Subject.objects.all():
            if s.name.lower() in {n.lower() for n in subject_names}:
                subjects_map[s.name.lower()] = s

    return students_map, subjects_map


def _get_or_create_subject(subject_name, subjects_map):
    """
    Get subject from cache or create it. Returns (subject, was_created).
    Mutates subjects_map to cache newly created subjects.
    """
    subject = subjects_map.get(subject_name.lower())
    if subject:
        return subject, False

    subject, created = Subject.objects.get_or_create(
        name__iexact=subject_name,
        defaults={
            'name': subject_name,
            'code': subject_name[:3].upper() + '101',
            'is_active': True,
        }
    )
    subjects_map[subject_name.lower()] = subject
    return subject, created


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
        session, term, err = _get_session_and_term(request)
        if err:
            return err

        rows, err = _parse_csv(request)
        if err:
            return err

        students_map, subjects_map = _prefetch_students_and_subjects(rows)

        created, updated, subjects_created = 0, 0, 0
        errors = []
        to_create = []
        to_update = []

        with transaction.atomic():
            # Pre-fetch existing CA scores for this session/term in one query
            existing_scores = {
                (ca.student_id, ca.subject_id): ca
                for ca in CAScore.objects.filter(
                    session=session, term=term
                ).select_for_update()
            }

            for idx, row in enumerate(rows, start=2):
                try:
                    admission_number = row.get('admission_number', '').strip().upper()
                    subject_name = row.get('subject', '').strip()
                    ca1_score = Decimal(row.get('ca1_score', '0').strip() or '0')
                    ca2_score = Decimal(row.get('ca2_score', '0').strip() or '0')

                    if not admission_number or not subject_name:
                        errors.append({'row': idx, 'error': 'Missing required fields'})
                        continue

                    if ca1_score > 15 or ca2_score > 15:
                        errors.append({'row': idx, 'error': 'CA score exceeds max (15)'})
                        continue

                    student = students_map.get(admission_number)
                    if not student:
                        errors.append({'row': idx, 'error': f'Student {admission_number} not found'})
                        continue

                    subject, subj_created = _get_or_create_subject(subject_name, subjects_map)
                    if subj_created:
                        subjects_created += 1

                    key = (student.id, subject.id)
                    existing = existing_scores.get(key)

                    if existing:
                        existing.ca1_score = ca1_score
                        existing.ca2_score = ca2_score
                        existing.uploaded_by = request.user
                        to_update.append(existing)
                        updated += 1
                    else:
                        new_obj = CAScore(
                            student=student, subject=subject,
                            session=session, term=term,
                            ca1_score=ca1_score, ca2_score=ca2_score,
                            uploaded_by=request.user
                        )
                        to_create.append(new_obj)
                        # Track in existing_scores to handle duplicate rows in same CSV
                        existing_scores[key] = new_obj
                        created += 1

                except Exception as e:
                    errors.append({'row': idx, 'error': str(e)})

            if to_create:
                CAScore.objects.bulk_create(to_create)
            if to_update:
                CAScore.objects.bulk_update(to_update, ['ca1_score', 'ca2_score', 'uploaded_by'])

        invalidate_score_cache(session.id, term.id)
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
    
    def list(self, request, *args, **kwargs):
        """
        List exam results with brought-forward term totals and cumulative averages.
        
        Enriches each result with:
        - first_term_total: Student's total for this subject in 1st term
        - second_term_total: Student's total for this subject in 2nd term
        - third_term_total: Student's total for this subject in 3rd term
        - cumulative_score: Average of available term totals
        """
        queryset = self.filter_queryset(self.get_queryset())
        session_id = request.query_params.get('session')
        
        page = self.paginate_queryset(queryset)
        result_objects = list(page) if page is not None else list(queryset)
        
        serializer = self.get_serializer(result_objects, many=True)
        data = serializer.data
        
        # Enrich with B/F term totals and cumulative averages
        if session_id and result_objects:
            self._enrich_with_bf_data(data, result_objects, session_id)
        
        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)
    
    def _enrich_with_bf_data(self, serialized_data, result_objects, session_id):
        """
        Add brought-forward term totals and cumulative scores.
        
        For each result, looks up the same student+subject across all terms
        in the session to populate B/F columns and cumulative average.
        Uses a single DB query for all lookups.
        """
        terms = list(Term.objects.filter(session_id=session_id).order_by('id'))
        if not terms:
            return
        
        # Collect unique student+subject combos from current page
        student_ids = {r.student_id for r in result_objects}
        subject_ids = {r.subject_id for r in result_objects}
        
        # Single query: all scores for these combos across all terms in the session
        all_scores = ExamResult.objects.filter(
            session_id=session_id,
            student_id__in=student_ids,
            subject_id__in=subject_ids,
        ).values_list('student_id', 'subject_id', 'term_id', 'total_score')
        
        # Build lookup: (student_id, subject_id, term_id) -> total_score
        score_lookup = {}
        for sid, subid, tid, total in all_scores:
            score_lookup[(sid, subid, tid)] = float(total) if total is not None else None
        
        # Enrich each serialized result (matched by index with result_objects)
        for i, item in enumerate(serialized_data):
            obj = result_objects[i]
            
            term_totals = []
            for tidx, term in enumerate(terms):
                score = score_lookup.get((obj.student_id, obj.subject_id, term.id))
                if tidx == 0:
                    item['first_term_total'] = score
                elif tidx == 1:
                    item['second_term_total'] = score
                elif tidx == 2:
                    item['third_term_total'] = score
                if score is not None:
                    term_totals.append(score)
            
            item['cumulative_score'] = (
                round(sum(term_totals) / len(term_totals), 2)
                if term_totals else None
            )
    
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
        session, term, err = _get_session_and_term(request)
        if err:
            return err

        rows, err = _parse_csv(request)
        if err:
            return err

        students_map, subjects_map = _prefetch_students_and_subjects(rows)

        created, updated, subjects_created = 0, 0, 0
        missing_ca, errors = [], []
        to_create = []
        to_update = []

        with transaction.atomic():
            # Pre-fetch existing exam results and CA scores
            existing_results = {
                (r.student_id, r.subject_id): r
                for r in ExamResult.objects.filter(
                    session=session, term=term
                ).select_for_update()
            }

            ca_scores_map = {
                (ca.student_id, ca.subject_id): ca
                for ca in CAScore.objects.filter(session=session, term=term)
            }

            for idx, row in enumerate(rows, start=2):
                try:
                    admission_number = row.get('admission_number', '').strip().upper()
                    subject_name = row.get('subject', '').strip()
                    obj_score = Decimal(row.get('obj_score', '0').strip() or '0')
                    total_questions = int(row.get('total_questions', '30').strip() or '30')

                    if not admission_number or not subject_name:
                        errors.append({'row': idx, 'error': 'Missing required fields'})
                        continue

                    if obj_score > 30:
                        errors.append({'row': idx, 'error': 'OBJ score exceeds max (30)'})
                        continue

                    student = students_map.get(admission_number)
                    if not student:
                        errors.append({'row': idx, 'error': f'Student {admission_number} not found'})
                        continue

                    subject, subj_created = _get_or_create_subject(subject_name, subjects_map)
                    if subj_created:
                        subjects_created += 1

                    # Get CA scores from pre-fetched map
                    ca1_score, ca2_score = Decimal('0'), Decimal('0')
                    ca_key = (student.id, subject.id)
                    ca_obj = ca_scores_map.get(ca_key)
                    if ca_obj:
                        ca1_score = ca_obj.ca1_score or Decimal('0')
                        ca2_score = ca_obj.ca2_score or Decimal('0')
                    else:
                        missing_ca.append({'admission_number': admission_number, 'subject': subject_name})

                    key = (student.id, subject.id)
                    existing = existing_results.get(key)

                    if existing:
                        existing.ca1_score = ca1_score
                        existing.ca2_score = ca2_score
                        existing.obj_score = obj_score
                        existing.total_obj_questions = total_questions
                        existing.uploaded_by = request.user
                        to_update.append(existing)
                        updated += 1
                    else:
                        new_obj = ExamResult(
                            student=student, subject=subject,
                            session=session, term=term,
                            ca1_score=ca1_score, ca2_score=ca2_score,
                            obj_score=obj_score, total_obj_questions=total_questions,
                            uploaded_by=request.user
                        )
                        to_create.append(new_obj)
                        existing_results[key] = new_obj
                        created += 1

                except Exception as e:
                    errors.append({'row': idx, 'error': str(e)})

            if to_create:
                ExamResult.objects.bulk_create(to_create)
            if to_update:
                ExamResult.objects.bulk_update(
                    to_update,
                    ['ca1_score', 'ca2_score', 'obj_score', 'total_obj_questions', 'uploaded_by']
                )

        _recalculate_totals(session, term)
        _calculate_class_positions(session, term)
        invalidate_score_cache(session.id, term.id)

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
        session, term, err = _get_session_and_term(request)
        if err:
            return err

        rows, err = _parse_csv(request)
        if err:
            return err

        students_map, subjects_map = _prefetch_students_and_subjects(rows)

        created, updated, subjects_created = 0, 0, 0
        errors = []
        to_create = []
        to_update = []

        with transaction.atomic():
            existing_results = {
                (r.student_id, r.subject_id): r
                for r in ExamResult.objects.filter(
                    session=session, term=term
                ).select_for_update()
            }

            ca_scores_map = {
                (ca.student_id, ca.subject_id): ca
                for ca in CAScore.objects.filter(session=session, term=term)
            }

            for idx, row in enumerate(rows, start=2):
                try:
                    admission_number = row.get('admission_number', '').strip().upper()
                    subject_name = row.get('subject', '').strip()
                    theory_score = Decimal(row.get('theory_score', '0').strip() or '0')

                    if not admission_number or not subject_name:
                        errors.append({'row': idx, 'error': 'Missing required fields'})
                        continue

                    if theory_score > 40:
                        errors.append({'row': idx, 'error': 'Theory score exceeds max (40)'})
                        continue

                    student = students_map.get(admission_number)
                    if not student:
                        errors.append({'row': idx, 'error': f'Student {admission_number} not found'})
                        continue

                    subject, subj_created = _get_or_create_subject(subject_name, subjects_map)
                    if subj_created:
                        subjects_created += 1

                    key = (student.id, subject.id)
                    existing = existing_results.get(key)

                    if existing:
                        existing.theory_score = theory_score
                        to_update.append(existing)
                        updated += 1
                    else:
                        # Get CA scores if available
                        ca1_score, ca2_score = Decimal('0'), Decimal('0')
                        ca_obj = ca_scores_map.get(key)
                        if ca_obj:
                            ca1_score = ca_obj.ca1_score or Decimal('0')
                            ca2_score = ca_obj.ca2_score or Decimal('0')

                        new_obj = ExamResult(
                            student=student, subject=subject,
                            session=session, term=term,
                            ca1_score=ca1_score, ca2_score=ca2_score,
                            obj_score=Decimal('0'), theory_score=theory_score,
                            uploaded_by=request.user
                        )
                        to_create.append(new_obj)
                        existing_results[key] = new_obj
                        created += 1

                except Exception as e:
                    errors.append({'row': idx, 'error': str(e)})

            if to_create:
                ExamResult.objects.bulk_create(to_create)
            if to_update:
                ExamResult.objects.bulk_update(to_update, ['theory_score'])

        _recalculate_totals(session, term)
        _calculate_class_positions(session, term)
        invalidate_score_cache(session.id, term.id)

        return Response({
            'success': True, 'created': created, 'updated': updated,
            'subjects_created': subjects_created, 'failed': len(errors), 'errors': errors[:10]
        })
    
    @action(detail=False, methods=['post'], url_path='recalculate-positions')
    def recalculate_positions(self, request):
        """Recalculate totals, grades, cumulative, and positions for all results in a session/term."""
        session, term, err = _get_session_and_term(request)
        if err:
            return err

        class_level_id = request.data.get('class_level')
        totals_fixed = _recalculate_totals(session, term)
        subjects_processed = _calculate_class_positions(session, term, class_level_id)
        invalidate_score_cache(session.id, term.id)

        return Response({
            'success': True, 'message': 'Totals and positions recalculated',
            'totals_fixed': totals_fixed,
            'subjects_processed': subjects_processed
        })
    
    @action(detail=False, methods=['post'], url_path='sync-ca-scores')
    def sync_ca_scores(self, request):
        """Sync CA1+CA2 scores from CAScore table to ExamResult table."""
        session, term, err = _get_session_and_term(request)
        if err:
            return err

        updated = 0

        with transaction.atomic():
            ca_scores_map = {
                (ca.student_id, ca.subject_id): ca
                for ca in CAScore.objects.filter(session=session, term=term)
            }

            results = list(
                ExamResult.objects.filter(session=session, term=term).select_for_update()
            )

            to_update = []
            for result in results:
                key = (result.student_id, result.subject_id)
                ca = ca_scores_map.get(key)
                if ca:
                    result.ca1_score = ca.ca1_score
                    result.ca2_score = ca.ca2_score
                    to_update.append(result)

            if to_update:
                ExamResult.objects.bulk_update(to_update, ['ca1_score', 'ca2_score'])
                updated = len(to_update)

        invalidate_score_cache(session.id, term.id)

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
    session, term, err = _get_session_and_term(request)
    if err:
        return err

    rows, err = _parse_csv(request)
    if err:
        return err

    students_map, subjects_map = _prefetch_students_and_subjects(rows)

    created_count, updated_count, subjects_created = 0, 0, 0
    errors = []
    to_create = []
    to_update = []

    with transaction.atomic():
        existing_scores = {
            (ca.student_id, ca.subject_id): ca
            for ca in CAScore.objects.filter(
                session=session, term=term
            ).select_for_update()
        }

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

                student = students_map.get(admission_number)
                if not student:
                    errors.append({'row': idx, 'admission_number': admission_number, 'error': 'Student not found'})
                    continue

                subject, subj_created = _get_or_create_subject(subject_name, subjects_map)
                if subj_created:
                    subjects_created += 1

                key = (student.id, subject.id)
                existing = existing_scores.get(key)

                if existing:
                    existing.ca1_score = ca1_score
                    existing.ca2_score = ca2_score
                    existing.uploaded_by = request.user
                    to_update.append(existing)
                    updated_count += 1
                else:
                    new_obj = CAScore(
                        student=student, subject=subject,
                        session=session, term=term,
                        ca1_score=ca1_score, ca2_score=ca2_score,
                        uploaded_by=request.user
                    )
                    to_create.append(new_obj)
                    existing_scores[key] = new_obj
                    created_count += 1

            except Exception as e:
                errors.append({'row': idx, 'admission_number': row.get('admission_number', 'N/A'), 'error': str(e)})

        if to_create:
            CAScore.objects.bulk_create(to_create)
        if to_update:
            CAScore.objects.bulk_update(to_update, ['ca1_score', 'ca2_score', 'uploaded_by'])

    invalidate_score_cache(session.id, term.id)
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
    session, term, err = _get_session_and_term(request)
    if err:
        return err

    rows, err = _parse_csv(request)
    if err:
        return err

    students_map, subjects_map = _prefetch_students_and_subjects(rows)

    created_count, updated_count, subjects_created = 0, 0, 0
    missing_ca_scores = []
    errors = []
    to_create = []
    to_update = []

    with transaction.atomic():
        existing_results = {
            (r.student_id, r.subject_id): r
            for r in ExamResult.objects.filter(
                session=session, term=term
            ).select_for_update()
        }

        ca_scores_map = {
            (ca.student_id, ca.subject_id): ca
            for ca in CAScore.objects.filter(session=session, term=term)
        }

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
                    obj_score = min(exam_score * Decimal('0.43'), Decimal('30'))
                    theory_score = min(exam_score * Decimal('0.57'), Decimal('40'))

                if not admission_number or not subject_name:
                    errors.append({'row': idx, 'error': 'Missing required fields'})
                    continue

                if obj_score > 30:
                    errors.append({'row': idx, 'admission_number': admission_number, 'error': 'OBJ score exceeds 30'})
                    continue

                if theory_score > 40:
                    errors.append({'row': idx, 'admission_number': admission_number, 'error': 'Theory score exceeds 40'})
                    continue

                student = students_map.get(admission_number)
                if not student:
                    errors.append({'row': idx, 'admission_number': admission_number, 'error': 'Student not found'})
                    continue

                subject, subj_created = _get_or_create_subject(subject_name, subjects_map)
                if subj_created:
                    subjects_created += 1

                # Get CA scores from pre-fetched map
                ca1_score, ca2_score = Decimal('0'), Decimal('0')
                ca_key = (student.id, subject.id)
                ca_obj = ca_scores_map.get(ca_key)
                if ca_obj:
                    ca1_score = ca_obj.ca1_score or Decimal('0')
                    ca2_score = ca_obj.ca2_score or Decimal('0')
                else:
                    missing_ca_scores.append({'admission_number': admission_number, 'subject': subject_name})

                key = (student.id, subject.id)
                existing = existing_results.get(key)

                if existing:
                    existing.ca1_score = ca1_score
                    existing.ca2_score = ca2_score
                    existing.obj_score = obj_score
                    existing.theory_score = theory_score
                    existing.uploaded_by = request.user
                    to_update.append(existing)
                    updated_count += 1
                else:
                    new_obj = ExamResult(
                        student=student, subject=subject,
                        session=session, term=term,
                        ca1_score=ca1_score, ca2_score=ca2_score,
                        obj_score=obj_score, theory_score=theory_score,
                        uploaded_by=request.user
                    )
                    to_create.append(new_obj)
                    existing_results[key] = new_obj
                    created_count += 1

            except Exception as e:
                errors.append({'row': idx, 'admission_number': row.get('admission_number', 'N/A'), 'error': str(e)})

        if to_create:
            ExamResult.objects.bulk_create(to_create)
        if to_update:
            ExamResult.objects.bulk_update(
                to_update,
                ['ca1_score', 'ca2_score', 'obj_score', 'theory_score', 'uploaded_by']
            )

    _recalculate_totals(session, term)
    _calculate_class_positions(session, term)
    invalidate_score_cache(session.id, term.id)

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

def _recalculate_totals(session, term):
    """
    Recalculate total_score, grade, remark, and cumulative for all results
    in a session/term. Optimized to avoid N+1 queries.
    """
    results = list(ExamResult.objects.filter(
        session=session, term=term
    ).select_related('term', 'student', 'subject'))
    
    if not results:
        return 0
    
    # Pre-load ALL results for this session to avoid per-result DB queries
    all_session_results = ExamResult.objects.filter(
        session=session
    ).select_related('term').values_list(
        'student_id', 'subject_id', 'term__name', 'total_score'
    )
    
    # Build lookup: (student_id, subject_id) -> {term_name: total_score}
    cumulative_lookup = {}
    for student_id, subject_id, term_name, total_score in all_session_results:
        key = (student_id, subject_id)
        if key not in cumulative_lookup:
            cumulative_lookup[key] = {}
        cumulative_lookup[key][term_name] = float(total_score or 0)
    
    to_update = []
    
    for r in results:
        new_total = (
            (r.ca1_score or 0) +
            (r.ca2_score or 0) +
            (r.obj_score or 0) +
            (r.theory_score or 0)
        )
        
        needs_update = (r.total_score != new_total) or not r.grade
        
        if needs_update:
            r.total_score = new_total
            r.grade, r.remark = r.calculate_grade(r.total_score)
        
        # Calculate cumulative without extra DB queries
        key = (r.student_id, r.subject_id)
        term_data = cumulative_lookup.get(key, {})
        
        # Override current term's score with freshly calculated total
        current_term_name = r.term.name if r.term else ''
        term_data[current_term_name] = float(new_total)
        
        r.first_term_total = Decimal(str(term_data.get('First Term', 0))) if 'First Term' in term_data else None
        r.second_term_total = Decimal(str(term_data.get('Second Term', 0))) if 'Second Term' in term_data else None
        r.third_term_total = Decimal(str(term_data.get('Third Term', 0))) if 'Third Term' in term_data else None
        
        # Calculate cumulative average
        term_scores = [v for v in [
            float(r.first_term_total) if r.first_term_total is not None else None,
            float(r.second_term_total) if r.second_term_total is not None else None,
            float(r.third_term_total) if r.third_term_total is not None else None,
        ] if v is not None]
        
        if term_scores:
            r.cumulative_score = Decimal(str(round(sum(term_scores) / len(term_scores), 2)))
            r.cumulative_grade, _ = r.calculate_grade(r.cumulative_score)
        else:
            r.cumulative_score = new_total
            r.cumulative_grade, _ = r.calculate_grade(new_total)
        
        to_update.append(r)
    
    if to_update:
        ExamResult.objects.bulk_update(
            to_update,
            ['total_score', 'grade', 'remark',
             'first_term_total', 'second_term_total', 'third_term_total',
             'cumulative_score', 'cumulative_grade']
        )
    
    return len(to_update)


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