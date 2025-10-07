from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from users.models import Student, UserProfile
from .models import Class, AttendanceRecord
from django.utils import timezone
from datetime import datetime
from .serializers import AttendanceRecordSerializer
import logging

logger = logging.getLogger(__name__)

class AttendanceViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='classes')
    def teacher_classes(self, request):
        """List all classes taught by this teacher"""
        if not request.user.role == 'teacher':
            return Response({"error": "Only teachers can access this"}, status=403)

        classes = Class.objects.filter(teacher=request.user).values('id', 'name', 'session_year')
        return Response(list(classes))

    @action(detail=False, methods=['post'], url_path='mark')
    def mark_attendance(self, request):
        """Mark daily attendance for students in bulk"""
        logger.debug(f"User {request.user.username} attempting to mark attendance")
        if request.user.role != 'teacher':
            logger.warning(f"Unauthorized access by user {request.user.username} with role {request.user.role}")
            return Response({"error": "Unauthorized"}, status=403)

        class_id = request.data.get('class_id')
        records = request.data.get('records', [])
        date_str = request.data.get('date')

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.now().date()
        except ValueError:
            logger.error(f"Invalid date format: {date_str}")
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        try:
            class_obj = Class.objects.get(id=class_id, teacher=request.user)
        except Class.DoesNotExist:
            logger.error(f"Class {class_id} not found for user {request.user.username}")
            return Response({"error": "Class not found or not assigned to you"}, status=404)

        attendance_records = []
        errors = []
        existing_records = {
            (r.student_id, r.date): r
            for r in AttendanceRecord.objects.filter(
                class_obj=class_obj,
                date=date
            ).select_related('student')
        }

        for record in records:
            adm_num = record.get('admission_number')
            status = record.get('status', 'present')

            try:
                student = Student.objects.get(admission_number=adm_num, is_active=True)
                record_key = (student.id, date)
                if record_key in existing_records:
                    existing_record = existing_records[record_key]
                    existing_record.status = status
                    existing_record.recorded_by = request.user
                    existing_record.save()
                else:
                    attendance_records.append(
                        AttendanceRecord(
                            student=student,
                            class_obj=class_obj,
                            date=date,
                            status=status,
                            recorded_by=request.user
                        )
                    )
            except Exception as e:
                logger.error(f"Error processing student {adm_num}: {str(e)}")
                errors.append(f"{adm_num}: {str(e)}")

        if attendance_records:
            AttendanceRecord.objects.bulk_create(attendance_records)

        logger.info(f"Attendance saved for {len(records) - len(errors)} students on {date} by {request.user.username}")
        return Response({
            "message": f"Attendance saved for {len(records) - len(errors)} students on {date}",
            "errors": errors
        }, status=201)

    @action(detail=False, methods=['get'], url_path='records')
    def get_attendance_records(self, request):
        """Get attendance records for a class and date"""
        if request.user.role != 'teacher':
            return Response({"error": "Only teachers can access this"}, status=403)

        class_name = request.GET.get('class')
        date_str = request.GET.get('date')

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        try:
            class_obj = Class.objects.get(name=class_name, teacher=request.user)
        except Class.DoesNotExist:
            return Response({"error": "Class not found or not assigned to you"}, status=404)

        records = AttendanceRecord.objects.filter(
            class_obj=class_obj,
            date=date
        ).select_related('student', 'recorded_by')

        serializer = AttendanceRecordSerializer(records, many=True)
        return Response(serializer.data)

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