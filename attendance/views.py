import calendar
from datetime import date, timedelta

from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action, api_view, permission_classes
from users.models import Student, TeacherAssignment
from .models import AttendanceRecord
import re


class TeacherClassesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'teacher':
            return Response({"error": "Only teachers can access"}, status=403)

        assignments = TeacherAssignment.objects.filter(teacher=request.user)
        data = []

        for assignment in assignments:
            # Extract base level like "SS2", "JSS1"
            base_class = re.split(r'\s+', assignment.class_name)[0]  # SS2 from "SS2 Science"

            students = Student.objects.filter(
                is_active=True,
                class_name__startswith=base_class
            ).values('admission_number', 'first_name', 'last_name')

            data.append({
                "class_name": assignment.class_name,
                "session_year": assignment.session_year,
                "students": list(students),
                "count": len(students)
            })

        return Response(data)

class MarkAttendanceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'teacher':
            return Response({"error": "Unauthorized"}, status=403)

        records = request.data.get('records', [])
        saved_count = 0
        errors = []

        for record in records:
            admission_num = record.get('admission_number')
            status = record.get('status', 'present')

            try:
                student = Student.objects.get(admission_number=admission_num, is_active=True)
                _, created = AttendanceRecord.objects.update_or_create(
                    student=student,
                    date=timezone.now().date(),
                    defaults={
                        'status': status,
                        'recorded_by': request.user
                    }
                )
                saved_count += 1
            except Exception as e:
                errors.append(f"{admission_num}: {str(e)}")

        return Response({
            "message": f"Saved attendance for {saved_count} students",
            "errors": errors
        }, status=201)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_monthly_attendance(request, admission_number):
    """
    Return monthly attendance rates for the last 6 months.
    e.g., [{"month": "Sep", "rate": 95}, ...]
    """
    try:
        student = Student.objects.get(admission_number=admission_number, is_active=True)
    except Student.DoesNotExist:
        return Response({"error": "Student not found"}, status=404)

    today = date.today()
    six_months_ago = today - timedelta(days=180)

    records = AttendanceRecord.objects.filter(
        student=student,
        date__gte=six_months_ago
    ).order_by('date')

    if not records.exists():
        # No data yet — return empty bars
        months = [today - timedelta(days=30 * i) for i in range(5, -1, -1)]
        return Response([
            {"month": m.strftime("%b"), "rate": 0}
            for m in months
        ])

    # Group by month
    monthly_data = {}
    for record in records:
        key = (record.date.year, record.date.month)
        if key not in monthly_data:
            days_in_month = calendar.monthrange(key[0], key[1])[1]
            monthly_data[key] = {
                "total_days": days_in_month,
                "present": 0,
                "late": 0,
                "excused": 0,
                "days_counted": 0
            }

        if record.status in ['present', 'late', 'excused']:
            monthly_data[key]["present"] += 1
        monthly_data[key]["days_counted"] += 1

    # Calculate rates + format as list
    result = []
    for (year, month), data in sorted(monthly_data.items()):
        total = data["days_counted"]
        good = data["present"] + data["late"] + data["excused"]
        rate = round((good / max(total, 1)) * 100, 1)

        dt = date(year, month, 1)
        result.append({
            "month": dt.strftime("%b"),
            "rate": rate
        })

    return Response(result[-6:])  # Last 6 months