import logging

from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from datetime import date, timedelta
from calendar import monthrange
from .models import TeacherAssignment, AttendanceRecord
from users.models import Student, UserProfile
from .serializers import TeacherAssignmentSerializer, AttendanceStatsSerializer, StudentAttendanceSerializer
from django.db.models import Count, Q
from django.db import connection


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from .models import TeacherAssignment, Student

logger = logging.getLogger(__name__)

class TeacherClassesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'teacher':
            return Response({"error": "Only teachers can access"}, status=403)

        cache_key = f"teacher_assignments_{request.user.id}"
        data = cache.get(cache_key)

        if not data:
            logger.info(f"Fetching assignments for teacher {request.user.username} (ID: {request.user.id})")
            assignments = TeacherAssignment.objects.filter(teacher=request.user).select_related('teacher')
            logger.info(f"Found assignments: {list(assignments.values('id', 'level', 'stream', 'section'))}")
            data = []
            for a in assignments:
                students = Student.objects.filter(
                    class_level=a.level,
                    section=a.section,
                    stream=a.stream,
                    is_active=True
                ).values('admission_number', 'first_name', 'last_name')
                full_name = f"{a.level} {a.stream or ''} {a.section}".strip()
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
            cache.set(cache_key, data, 3600)

        return Response(data)
class StudentsByClassAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'teacher':
            return Response({"error": "Unauthorized"}, status=403)
        class_level = request.query_params.get('class')
        section = request.query_params.get('section', '').strip().upper()
        if not class_level:
            return Response({"error": "Class required"}, status=400)
        students = Student.objects.filter(
            class_level=class_level,
            section=section,
            is_active=True
        ).values('admission_number', 'first_name', 'last_name', 'class_level', 'section')
        return Response({
            "count": len(students),
            "students": list(students)
        })
class CheckAttendanceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'teacher':
            return Response({"error": "Unauthorized"}, status=403)

        class_id = request.query_params.get('class_id')
        date_str = request.query_params.get('date')

        try:
            assignment = TeacherAssignment.objects.get(id=class_id, teacher=request.user)
            records = AttendanceRecord.objects.filter(
                student__class_level=assignment.level,
                student__section=assignment.section,
                date=date_str
            ).exists()
            return Response({"submitted": records})
        except TeacherAssignment.DoesNotExist:
            return Response({"error": "Class not found"}, status=404)
class MarkAttendanceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'teacher':
            return Response({"error": "Unauthorized"}, status=403)

        class_id = request.data.get('class_id')
        date_str = request.data.get('date')
        records = request.data.get('records', [])

        try:
            assignment = TeacherAssignment.objects.get(id=class_id, teacher=request.user)

            existing_records = AttendanceRecord.objects.filter(
                student__class_level=assignment.level,
                student__section=assignment.section,
                date=date_str
            ).exists()

            if existing_records:
                return Response({"error": "Attendance already submitted for this class and date"}, status=400)

            saved_count = 0
            errors = []

            for record in records:
                adm_num = record.get('admission_number')
                status = record.get('status', 'present')

                try:
                    student = Student.objects.get(
                        admission_number=adm_num,
                        is_active=True,
                        class_level=assignment.level,
                        section=assignment.section
                    )
                    AttendanceRecord.objects.create(
                        student=student,
                        date=date_str,
                        status=status,
                        recorded_by=request.user
                    )
                    saved_count += 1
                except Student.DoesNotExist:
                    errors.append(f"{adm_num}: Student not found")
                except Exception as e:
                    errors.append(f"{adm_num}: {str(e)}")

            return Response({
                "message": f"Saved for {saved_count} students",
                "errors": errors
            }, status=201)
        except TeacherAssignment.DoesNotExist:
            return Response({"error": "Class not found or unauthorized"}, status=404)
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
        ).values('date__year', 'date__month').annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status__in=['present', 'late', 'excused']))
        ).order_by('-date__year', '-date__month')

        result = []
        for r in records[:6]:
            year, month = r['date__year'], r['date__month']
            days_in_month = monthrange(year, month)[1]
            good = r['present']
            total = r['total']
            rate = round((good / max(total, 1)) * 100, 1)

            result.append({
                "month": date(year, month, 1).strftime("%b"),
                "rate": rate
            })

        return Response(result)
class TeacherAttendanceReport(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'teacher':
            return Response({"error": "Unauthorized"}, status=403)

        date_str = request.query_params.get('date', date.today().isoformat())
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            return Response({"error": "Invalid date format"}, status=400)

        assignments = TeacherAssignment.objects.filter(teacher=request.user)
        data = []

        for a in assignments:
            records = AttendanceRecord.objects.filter(
                student__class_level=a.level,
                student__section=a.section,
                date=target_date
            ).values('status').annotate(count=Count('status'))

            stats = {
                "total_days": 1,
                "present": 0,
                "late": 0,
                "excused": 0,
                "absent": 0
            }
            for r in records:
                stats[r['status']] = r['count']

            stats['attendance_rate'] = round(
                (stats['present'] + stats['late'] + stats['excused']) / max(sum(stats.values()) - 1, 1) * 100, 2)
            serializer = AttendanceStatsSerializer(stats)

            data.append({
                "class_name": f"{a.level} {a.stream or ''} {a.section}".strip(),
                "stats": serializer.data
            })

        return Response(data)