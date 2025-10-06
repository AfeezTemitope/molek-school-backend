# attendance/views.py

from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from users.models import Student, UserProfile
from .models import Class, AttendanceRecord
from django.utils import timezone


class AttendanceViewSet(ViewSet):
    permission_classes = [IsAuthenticated]
    @action(detail=False, methods=['get'], url_path='classes')
    def teacher_classes(self, request):
        """List all classes taught by this teacher"""
        if not request.user.role == 'teacher':
            return Response(
                {"error": "Only teachers can access this"},
                status=403
            )

        classes = Class.objects.filter(teacher=request.user).values(
            'id', 'name', 'session_year'
        )
        return Response(list(classes))
    @action(detail=False, methods=['post'], url_path='mark')
    def mark_attendance(self, request):
        """Mark daily attendance for students"""
        if request.user.role != 'teacher':
            return Response({"error": "Unauthorized"}, status=403)

        class_id = request.data.get('class_id')
        records = request.data.get('records', [])

        try:
            class_obj = Class.objects.get(id=class_id, teacher=request.user)
        except Class.DoesNotExist:
            return Response({"error": "Class not found or not assigned to you"}, status=404)

        success_count = 0
        errors = []

        for record in records:
            adm_num = record.get('admission_number')
            status = record.get('status', 'present')

            try:
                student = Student.objects.get(admission_number=adm_num, is_active=True)
                _, created = AttendanceRecord.objects.update_or_create(
                    student=student,
                    class_obj=class_obj,
                    date=timezone.now().date(),
                    defaults={
                        'status': status,
                        'recorded_by': request.user
                    }
                )
                success_count += 1
            except Exception as e:
                errors.append(f"{adm_num}: {str(e)}")

        return Response({
            "message": f"Attendance saved for {success_count} students",
            "errors": errors
        }, status=201)
    @action(detail=False, methods=['get'], url_path='stats/(?P<admission>[^/.]+)')
    def student_stats(self, request, admission=None):
        """Get attendance stats for one student"""
        try:
            student = Student.objects.get(admission_number=admission, is_active=True)
        except Student.DoesNotExist:
            return Response({"error": "Student not found"}, status=404)

        total = AttendanceRecord.objects.filter(student=student).count()
        if total == 0:
            rate = 0
            present = late = excused = absent = 0
        else:
            present = AttendanceRecord.objects.filter(student=student, status='present').count()
            late = AttendanceRecord.objects.filter(student=student, status='late').count()
            excused = AttendanceRecord.objects.filter(student=student, status='excused').count()
            absent = total - (present + late + excused)
            rate = round(((present + late + excused) / total) * 100, 1)

        return Response({
            "student": {
                "full_name": f"{student.first_name} {student.last_name}",
                "admission_number": student.admission_number,
                "class_name": student.class_name
            },
            "stats": {
                "total_days": total,
                "present": present,
                "late": late,
                "excused": excused,
                "absent": absent,
                "attendance_rate": rate
            }
        })