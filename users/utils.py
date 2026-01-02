import random
import string
from datetime import datetime


def generate_admission_number():
    """Generate unique admission number: MOL/YYYY/XXX"""
    from .models import ActiveStudent

    year = datetime.now().year

    last_student = ActiveStudent.objects.filter(
        admission_number__startswith=f'MOL/{year}/'
    ).order_by('-admission_number').first()

    if last_student:
        last_num = int(last_student.admission_number.split('/')[-1])
        new_num = last_num + 1
    else:
        new_num = 1

    return f'MOL/{year}/{new_num:03d}'


def generate_password(length=8):
    """Generate secure random password"""
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789abcdefghjkmnpqrstuvwxyz'
    password = ''.join(random.choice(chars) for _ in range(length))
    return password


def calculate_grade(percentage):
    """Calculate grade from percentage"""
    if percentage >= 70:
        return 'A', 'A - Excellent'
    elif percentage >= 60:
        return 'B', 'B - Very Good'
    elif percentage >= 50:
        return 'C', 'C - Good'
    elif percentage >= 40:
        return 'D', 'D - Fair'
    else:
        return 'F', 'F - Fail'


def calculate_position_and_stats(student, subject, session, term):
    """Calculate student's position in class for a subject"""
    from .models import ExamResult

    results = ExamResult.objects.filter(
        subject=subject,
        session=session,
        term=term,
        student__class_level=student.class_level,
        student__is_active=True
    ).order_by('-total_score', 'student__admission_number')

    position = 1
    total_students = results.count()
    highest_score = results.first().total_score if results.exists() else 0
    lowest_score = results.last().total_score if results.exists() else 0

    total_sum = sum(r.total_score for r in results)
    class_average = round(total_sum / total_students, 2) if total_students > 0 else 0

    for idx, result in enumerate(results, 1):
        if result.student == student:
            position = idx
            break

    return {
        'position': position,
        'total_students': total_students,
        'class_average': class_average,
        'highest_score': highest_score,
        'lowest_score': lowest_score
    }