from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from datetime import date, timedelta
from calendar import monthrange
from .models import  AttendanceRecord
from users.models import Student, TeacherAssignment


class TeacherClassesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'teacher':
            return Response({"error": "Only teachers can access"}, status=403)

        assignments = TeacherAssignment.objects.filter(teacher=request.user)
        data = []

        for a in assignments:
            # Build class name like "JSS1 A" or "SS2 Science B"
            base_name = f"{a.level} {a.section}"
            full_name = f"{a.level} {a.stream} {a.section}" if a.stream else base_name

            students = Student.objects.filter(
                class_level=a.level,
                section=a.section,
                is_active=True
            ).values('admission_number', 'first_name', 'last_name')

            data.append({
                "id": a.id,
                "name": full_name,
                "level": a.level,
                "stream": a.stream,
                "section": a.section,
                "session_year": a.session_year,
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
            adm_num = record.get('admission_number')
            status = record.get('status', 'present')

            try:
                student = Student.objects.get(admission_number=adm_num, is_active=True)
                _, created = AttendanceRecord.objects.update_or_create(
                    student=student,
                    date=date.today(),
                    defaults={
                        'status': status,
                        'recorded_by': request.user
                    }
                )
                saved_count += 1
            except Exception as e:
                errors.append(f"{adm_num}: {str(e)}")

        return Response({
            "message": f"Saved for {saved_count} students",
            "errors": errors
        }, status=201)

class StudentMonthlyAttendance(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, admission_number=None):
        try:
            student = Student.objects.get(admission_number=admission_number, is_active=True)
        except Student.DoesNotExist:
            return Response({"error": "Student not found"}, status=404)

        six_months_ago = date.today() - timedelta(days=180)
        records = AttendanceRecord.objects.filter(
            student=student,
            date__gte=six_months_ago
        )

        if not records.exists():
            return Response([])

        # Group by month
        monthly_data = {}
        for r in records:
            key = (r.date.year, r.date.month)
            if key not in monthly_data:
                days_in_month = monthrange(key[0], key[1])[1]
                monthly_data[key] = {
                    "total_days": days_in_month,
                    "present": 0,
                    "late": 0,
                    "excused": 0,
                    "days_counted": 0
                }

            monthly_data[key]["days_counted"] += 1
            if r.status in ['present', 'late', 'excused']:
                monthly_data[key]["present"] += 1

        result = []
        for (y, m), data in sorted(monthly_data.items()):
            dt = date(y, m, 1)
            good = data["present"]
            total = data["days_counted"]
            rate = round((good / max(total, 1)) * 100, 1)

            result.append({
                "month": dt.strftime("%b"),
                "rate": rate
            })

        return Response(result[-6:])