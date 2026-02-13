"""
MOLEK School - Student Promotion Views (Bug 7 Fix)

Now reads from PromotionRule model for configurable:
- Pass marks (global + per-category)
- Compulsory subject checking (Math+English or whatever admin sets)
- Minimum additional subjects
- Carryover/resit support
- Auto/Recommend/Manual modes
"""
import logging
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import (
    ActiveStudent, AcademicSession, ClassLevel, Term,
    ExamResult, Subject, PromotionRule
)
from ..serializers import BulkPromotionSerializer
from ..cache_utils import invalidate_student_cache

logger = logging.getLogger(__name__)

CLASS_PROGRESSION = {
    'JSS1': 'JSS2', 'JSS2': 'JSS3', 'JSS3': 'SS1',
    'SS1': 'SS2', 'SS2': 'SS3', 'SS3': 'GRADUATED'
}


def _get_next_class_level(current_class):
    return CLASS_PROGRESSION.get(current_class, 'UNKNOWN')


def _get_promotion_rules(session_id, class_level_name):
    """
    Fetch rules: class-specific → global → hardcoded defaults.
    """
    rule = PromotionRule.objects.filter(
        session_id=session_id, class_level__name=class_level_name, is_active=True
    ).first()
    if not rule:
        rule = PromotionRule.objects.filter(
            session_id=session_id, class_level__isnull=True, is_active=True
        ).first()

    if rule:
        return {
            'rule_id': rule.id,
            'pass_mark_percentage': float(rule.pass_mark_percentage),
            'compulsory_subject_ids': rule.compulsory_subject_ids or [],
            'minimum_additional_subjects': rule.minimum_additional_subjects,
            'promotion_mode': rule.promotion_mode,
            'allow_carryover': rule.allow_carryover,
            'max_carryover_subjects': rule.max_carryover_subjects,
            'category_pass_marks': getattr(rule, 'category_pass_marks', None) or {},
        }

    # Fallback: find Math + English IDs
    math_id = Subject.objects.filter(
        Q(name__icontains='mathematics') | Q(name__icontains='math')
    ).values_list('id', flat=True).first()
    english_id = Subject.objects.filter(
        Q(name__icontains='english')
    ).values_list('id', flat=True).first()

    return {
        'rule_id': None,
        'pass_mark_percentage': 50.0,
        'compulsory_subject_ids': [x for x in [math_id, english_id] if x],
        'minimum_additional_subjects': 5,
        'promotion_mode': 'recommend',
        'allow_carryover': False,
        'max_carryover_subjects': 2,
        'category_pass_marks': {},
    }


def _get_pass_mark(subject, rules):
    cat_marks = rules.get('category_pass_marks', {})
    if cat_marks and hasattr(subject, 'category') and subject.category:
        mark = cat_marks.get(subject.category.lower())
        if mark is not None:
            return float(mark)
    return rules['pass_mark_percentage']


def _check_student_promotion(student, session, rules):
    """Check one student against configurable rules."""
    terms = Term.objects.filter(session=session).order_by('-id')
    results = None
    used_term = None
    for term in terms:
        qs = ExamResult.objects.filter(
            student=student, session=session, term=term
        ).select_related('subject')
        if qs.exists():
            results = qs
            used_term = term
            break

    total_min = len(rules['compulsory_subject_ids']) + rules['minimum_additional_subjects']

    if not results or not results.exists():
        return {
            'student_id': student.id,
            'admission_number': student.admission_number,
            'full_name': student.full_name or f"{student.first_name} {student.last_name}",
            'promotion_status': 'No Data',
            'promotion_status_display': 'No Data',
            'remarks': 'No exam results found',
            'total_subjects_passed': 0, 'total_minimum_required': total_min,
            'compulsory_passed': 0, 'compulsory_required': len(rules['compulsory_subject_ids']),
            'additional_passed': 0, 'additional_required': rules['minimum_additional_subjects'],
            'subject_details': [], 'failed_compulsory': [], 'failed_other': [],
            'can_carryover': False, 'carryover_subjects': [],
            'cumulative_average': 0, 'term_used': None,
        }

    compulsory_ids = rules['compulsory_subject_ids']
    details = []
    comp_results = []
    other_results = []

    for r in results:
        score = float(r.cumulative_score) if r.cumulative_score else float(r.total_score or 0)
        pm = _get_pass_mark(r.subject, rules)
        passed = score >= pm
        d = {
            'subject_id': r.subject.id, 'subject_name': r.subject.name,
            'score': round(score, 2), 'pass_mark': pm,
            'grade': r.cumulative_grade or r.grade or 'F', 'passed': passed,
            'is_compulsory': r.subject.id in compulsory_ids,
        }
        details.append(d)
        (comp_results if r.subject.id in compulsory_ids else other_results).append(d)

    failed_comp = [s for s in comp_results if not s['passed']]
    comp_passed = len(comp_results) - len(failed_comp)
    failed_others = [s for s in other_results if not s['passed']]
    other_passed = len(other_results) - len(failed_others)
    total_passed = comp_passed + other_passed

    all_scores = [d['score'] for d in details]
    cum_avg = sum(all_scores) / len(all_scores) if all_scores else 0

    remarks = []
    can_carryover = False
    carryover_subjects = []

    if failed_comp:
        pstatus = 'Not Promoted'
        remarks.append(f"Failed compulsory: {', '.join(s['subject_name'] for s in failed_comp)}")
    elif other_passed < rules['minimum_additional_subjects']:
        deficit = rules['minimum_additional_subjects'] - other_passed
        if rules['allow_carryover'] and deficit <= rules['max_carryover_subjects']:
            pstatus = 'Promoted with Carryover'
            can_carryover = True
            sorted_f = sorted(failed_others, key=lambda x: x['score'], reverse=True)
            carryover_subjects = [s['subject_name'] for s in sorted_f[:deficit]]
            remarks.append(f"Carryover {deficit} subject(s): {', '.join(carryover_subjects)}")
        else:
            pstatus = 'Not Promoted'
            remarks.append(f"Passed {other_passed} additional, needs {rules['minimum_additional_subjects']}")
    elif total_passed < total_min:
        pstatus = 'Not Promoted'
        remarks.append(f"Passed {total_passed} total, needs {total_min}")
    else:
        pstatus = 'Promoted'
        remarks.append(f"Passed {total_passed} subjects including all compulsory")

    display = f"{pstatus} (Pending Review)" if rules['promotion_mode'] in ('recommend', 'manual') else pstatus

    return {
        'student_id': student.id,
        'admission_number': student.admission_number,
        'full_name': student.full_name or f"{student.first_name} {student.last_name}",
        'promotion_status': pstatus, 'promotion_status_display': display,
        'remarks': '; '.join(remarks),
        'total_subjects_passed': total_passed, 'total_minimum_required': total_min,
        'compulsory_passed': comp_passed, 'compulsory_required': len(compulsory_ids),
        'additional_passed': other_passed, 'additional_required': rules['minimum_additional_subjects'],
        'subject_details': details,
        'failed_compulsory': [s['subject_name'] for s in failed_comp],
        'failed_other': [{'name': s['subject_name'], 'score': s['score'], 'pass_mark': s['pass_mark']} for s in failed_others],
        'can_carryover': can_carryover, 'carryover_subjects': carryover_subjects,
        'cumulative_average': round(cum_avg, 2), 'term_used': used_term.name if used_term else None,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_promotion_rules(request):
    """GET /promotion/rules/?session_id=X&class_level=JSS1"""
    session_id = request.query_params.get('session_id')
    class_level_name = request.query_params.get('class_level')
    if not session_id:
        return Response({'error': 'session_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    rules = _get_promotion_rules(session_id, class_level_name)
    comp_names = list(Subject.objects.filter(id__in=rules['compulsory_subject_ids']).values_list('name', flat=True))
    return Response({
        'success': True,
        'rules': {**rules, 'compulsory_subject_names': comp_names,
                  'total_minimum_subjects': len(rules['compulsory_subject_ids']) + rules['minimum_additional_subjects']}
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_promotion_rules(request):
    """POST /promotion/rules/save/"""
    data = request.data
    session_id = data.get('session_id')
    if not session_id:
        return Response({'error': 'session_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        session = AcademicSession.objects.get(id=session_id)
    except AcademicSession.DoesNotExist:
        return Response({'error': 'Invalid session'}, status=status.HTTP_400_BAD_REQUEST)

    class_level = None
    if data.get('class_level'):
        try:
            class_level = ClassLevel.objects.get(name=data['class_level'])
        except ClassLevel.DoesNotExist:
            return Response({'error': f'Invalid class: {data["class_level"]}'}, status=status.HTTP_400_BAD_REQUEST)

    comp_ids = data.get('compulsory_subject_ids', [])
    if comp_ids and Subject.objects.filter(id__in=comp_ids).count() != len(comp_ids):
        return Response({'error': 'Invalid compulsory subject ID(s)'}, status=status.HTTP_400_BAD_REQUEST)

    defaults = {
        'pass_mark_percentage': data.get('pass_mark_percentage', 50),
        'compulsory_subject_ids': comp_ids,
        'minimum_additional_subjects': data.get('minimum_additional_subjects', 5),
        'promotion_mode': data.get('promotion_mode', 'recommend'),
        'allow_carryover': data.get('allow_carryover', False),
        'max_carryover_subjects': data.get('max_carryover_subjects', 2),
        'created_by': request.user.profile if hasattr(request.user, 'profile') else None,
    }
    rule, created = PromotionRule.objects.update_or_create(
        session=session, class_level=class_level, is_active=True, defaults=defaults
    )
    if hasattr(rule, 'category_pass_marks'):
        rule.category_pass_marks = data.get('category_pass_marks', {})
        rule.save(update_fields=['category_pass_marks'])

    return Response({'success': True, 'message': f'Rules {"created" if created else "updated"}', 'rule_id': rule.id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_promotion_data(request):
    """GET /promotion/?class_level=JSS1&session_id=1"""
    class_level_name = request.query_params.get('class_level')
    session_id = request.query_params.get('session_id')
    if not class_level_name or not session_id:
        return Response({'error': 'class_level and session_id required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        class_level = ClassLevel.objects.get(name=class_level_name)
        session = AcademicSession.objects.get(id=session_id)
    except (ClassLevel.DoesNotExist, AcademicSession.DoesNotExist):
        return Response({'error': 'Invalid class_level or session'}, status=status.HTTP_400_BAD_REQUEST)

    rules = _get_promotion_rules(session_id, class_level_name)
    comp_names = list(Subject.objects.filter(id__in=rules['compulsory_subject_ids']).values_list('name', flat=True))
    students = ActiveStudent.objects.filter(class_level=class_level, is_active=True).select_related('class_level').order_by('last_name', 'first_name')
    promotion_data = [_check_student_promotion(s, session, rules) for s in students]
    promotion_data.sort(key=lambda x: x['cumulative_average'], reverse=True)

    return Response({
        'success': True, 'class_level': class_level_name,
        'next_class': _get_next_class_level(class_level_name),
        'session': session.name, 'session_id': session.id,
        'total_students': len(promotion_data),
        'statistics': {
            'promoted': sum(1 for s in promotion_data if s['promotion_status'] == 'Promoted'),
            'promoted_with_carryover': sum(1 for s in promotion_data if s['promotion_status'] == 'Promoted with Carryover'),
            'not_promoted': sum(1 for s in promotion_data if s['promotion_status'] == 'Not Promoted'),
            'no_data': sum(1 for s in promotion_data if s['promotion_status'] == 'No Data'),
        },
        'rules_applied': {
            'rule_id': rules['rule_id'], 'pass_mark': rules['pass_mark_percentage'],
            'compulsory_subjects': comp_names, 'compulsory_subject_ids': rules['compulsory_subject_ids'],
            'minimum_additional': rules['minimum_additional_subjects'],
            'total_minimum': len(rules['compulsory_subject_ids']) + rules['minimum_additional_subjects'],
            'mode': rules['promotion_mode'], 'allow_carryover': rules['allow_carryover'],
            'max_carryover': rules['max_carryover_subjects'], 'category_pass_marks': rules['category_pass_marks'],
        },
        'students': promotion_data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def promote_students(request):
    """POST /promotion/promote/"""
    serializer = BulkPromotionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': 'Invalid data', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    data = serializer.validated_data
    try:
        from_class = ClassLevel.objects.get(name=data['from_class'])
        to_class = ClassLevel.objects.get(name=data['to_class']) if data['to_class'] != 'GRADUATED' else None
    except ClassLevel.DoesNotExist:
        return Response({'error': 'Invalid class level'}, status=status.HTTP_400_BAD_REQUEST)
    expected = CLASS_PROGRESSION.get(data['from_class'])
    if expected != data['to_class']:
        return Response({'error': f"Invalid: {data['from_class']}→{data['to_class']}, expected {expected}"}, status=status.HTTP_400_BAD_REQUEST)

    promoted = graduated = 0
    errors = []
    with transaction.atomic():
        for sid in data['student_ids']:
            try:
                s = ActiveStudent.objects.get(id=sid, class_level=from_class, is_active=True)
                if data['to_class'] == 'GRADUATED':
                    s.is_active = False
                    s.graduation_date = timezone.now().date()
                    s.save(update_fields=['is_active', 'graduation_date'])
                    graduated += 1
                else:
                    s.class_level = to_class
                    s.save(update_fields=['class_level'])
                    promoted += 1
            except ActiveStudent.DoesNotExist:
                errors.append({'student_id': sid, 'error': 'Not found or wrong class'})
    invalidate_student_cache()
    return Response({'success': True, 'promoted': promoted, 'graduated': graduated, 'errors': errors or None})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_subjects(request):
    """GET /promotion/subjects/"""
    return Response({'subjects': list(Subject.objects.all().order_by('name').values('id', 'name'))})