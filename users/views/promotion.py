"""
MOLEK School - Student Promotion Views
Views for calculating and processing student promotions
"""
import logging
from django.utils import timezone
from django.db import transaction
from django.db.models import Avg
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import ActiveStudent, AcademicSession, ClassLevel, Term, ExamResult
from ..serializers import BulkPromotionSerializer
from ..cache_utils import invalidate_student_cache

logger = logging.getLogger(__name__)

# Class progression mapping
CLASS_PROGRESSION = {
    'JSS1': 'JSS2',
    'JSS2': 'JSS3',
    'JSS3': 'SS1',
    'SS1': 'SS2',
    'SS2': 'SS3',
    'SS3': 'GRADUATED'
}


def _get_next_class_level(current_class):
    """Get the next class level for promotion"""
    return CLASS_PROGRESSION.get(current_class, 'UNKNOWN')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_promotion_data(request):
    """
    Get students eligible for promotion with their cumulative averages.
    
    Query params:
        - class_level: Current class (e.g., 'JSS1')
        - session_id: Academic session ID
    
    Returns:
        - students: List of students with term averages and cumulative average
        - passed_count: Number of students who passed (avg >= 50)
        - failed_count: Number of students who failed
        - next_class: The class they will be promoted to
    """
    class_level_name = request.query_params.get('class_level')
    session_id = request.query_params.get('session_id')
    
    if not class_level_name or not session_id:
        return Response(
            {'error': 'class_level and session_id are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        class_level = ClassLevel.objects.get(name=class_level_name)
        session = AcademicSession.objects.get(id=session_id)
    except (ClassLevel.DoesNotExist, AcademicSession.DoesNotExist):
        return Response(
            {'error': 'Invalid class_level or session'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get all students in this class
    students = ActiveStudent.objects.filter(
        class_level=class_level,
        is_active=True
    ).select_related('class_level')
    
    # Get all terms for this session
    terms = Term.objects.filter(session=session).order_by('id')
    
    promotion_data = []
    
    for student in students:
        term_averages = []
        all_scores = []
        subjects_count = 0
        
        for term in terms:
            results = ExamResult.objects.filter(
                student=student,
                session=session,
                term=term
            )
            
            if results.exists():
                term_avg = results.aggregate(avg=Avg('total_score'))['avg']
                term_averages.append(float(term_avg) if term_avg else 0)
                all_scores.extend([float(r.total_score) for r in results])
                subjects_count = max(subjects_count, results.count())
        
        # Calculate cumulative average
        cumulative_avg = sum(all_scores) / len(all_scores) if all_scores else 0
        
        # Determine if passed (average >= 50)
        passed = cumulative_avg >= 50
        
        promotion_data.append({
            'student_id': student.id,
            'admission_number': student.admission_number,
            'full_name': f"{student.first_name} {student.last_name}",
            'current_class': class_level_name,
            'term1_average': term_averages[0] if len(term_averages) > 0 else None,
            'term2_average': term_averages[1] if len(term_averages) > 1 else None,
            'term3_average': term_averages[2] if len(term_averages) > 2 else None,
            'cumulative_average': round(cumulative_avg, 2),
            'passed': passed,
            'subjects_count': subjects_count
        })
    
    # Sort by cumulative average descending
    promotion_data.sort(key=lambda x: x['cumulative_average'], reverse=True)
    
    # Get next class level
    next_class = _get_next_class_level(class_level_name)
    
    return Response({
        'success': True,
        'class_level': class_level_name,
        'next_class': next_class,
        'session': session.name,
        'total_students': len(promotion_data),
        'passed_count': sum(1 for s in promotion_data if s['passed']),
        'failed_count': sum(1 for s in promotion_data if not s['passed']),
        'students': promotion_data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def promote_students(request):
    """
    Bulk promote selected students to next class.
    
    POST data:
    {
        "student_ids": [1, 2, 3, 5],
        "from_class": "JSS1",
        "to_class": "JSS2",
        "session_id": 1
    }
    """
    serializer = BulkPromotionSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    data = serializer.validated_data
    
    try:
        from_class = ClassLevel.objects.get(name=data['from_class'])
        
        # For graduation, to_class won't exist as a ClassLevel
        if data['to_class'] != 'GRADUATED':
            to_class = ClassLevel.objects.get(name=data['to_class'])
        else:
            to_class = None
            
    except ClassLevel.DoesNotExist:
        return Response(
            {'error': 'Invalid class level'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate class progression
    expected_to_class = CLASS_PROGRESSION.get(data['from_class'])
    if expected_to_class != data['to_class']:
        return Response(
            {'error': f"Invalid progression: {data['from_class']} -> {data['to_class']}. Expected: {expected_to_class}"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Promote students
    promoted_count = 0
    graduated_count = 0
    errors = []
    
    with transaction.atomic():
        for student_id in data['student_ids']:
            try:
                student = ActiveStudent.objects.get(
                    id=student_id,
                    class_level=from_class,
                    is_active=True
                )
                
                if data['to_class'] == 'GRADUATED':
                    # Mark as graduated
                    student.is_active = False
                    student.graduation_date = timezone.now().date()
                    student.save(update_fields=['is_active', 'graduation_date'])
                    graduated_count += 1
                    logger.info(f"Student graduated: {student.admission_number}")
                else:
                    # Promote to next class
                    student.class_level = to_class
                    student.save(update_fields=['class_level'])
                    promoted_count += 1
                    logger.info(f"Student promoted: {student.admission_number} -> {to_class.name}")
                
            except ActiveStudent.DoesNotExist:
                errors.append({
                    'student_id': student_id,
                    'error': 'Student not found or not in expected class'
                })
    
    # Invalidate student cache
    invalidate_student_cache()
    
    return Response({
        'success': True,
        'message': 'Promotion complete',
        'promoted': promoted_count,
        'graduated': graduated_count,
        'errors': errors if errors else None
    })