from django.utils import timezone
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from users.models import Student
from .models import Class, AttendanceRecord

class AttendanceViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    # 🔵 GET /molek/attendance/classes/
    @action(detail=False, methods=['get'], url_path='classes', url_name='teacher-classes')
    def teacher_classes(self, request):
        if not request.user.role == 'teacher':
            return Response({"error": "Access denied"}, status=403)

        classes = Class.objects.filter(teacher=request.user)
        data = [
            {
                "id": cls.id,
                "name": cls.name,
                "session_year": cls.session_year
            }
            for cls in classes
        ]
        return Response(data)

    # 🟢 POST /molek/attendance/mark/
    @action(detail=False, methods=['post'], url_path='mark', url_name='mark-attendance')
    def mark_attendance(self, request):
        if request.user.role != 'teacher':
            return Response({"error": "Unauthorized"}, status=403)

        class_id = request.data.get('class_id')
        records = request.data.get('records', [])

        try:
            class_obj = get_object_or_404(Class, id=class_id, teacher=request.user)
        except Exception:
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
                    defaults={'status': status, 'recorded_by': request.user}
                )
                success_count += 1
            except Student.DoesNotExist:
                errors.append(f"Student {adm_num} not found")
            except Exception as e:
                errors.append(str(e))

        return Response({
            "message": f"Attendance marked for {success_count} students",
            "errors": errors
        }, status=201)

    # 🟡 GET /molek/attendance/stats/<admission_number>/
    def student_stats(self, request, admission_number=None):
        try:
            student = Student.objects.get(admission_number=admission_number, is_active=True)
        except Student.DoesNotExist:
            return Response({"error": "Student not found"}, status=404)

        records = AttendanceRecord.objects.filter(student=student)
        total = records.count()

        if total == 0:
            return Response({
                "total_days": 0,
                "present": 0,
                "late": 0,
                "excused": 0,
                "absent": 0,
                "attendance_rate": 0.0
            })

        present = records.filter(status='present').count()
        late = records.filter(status='late').count()
        excused = records.filter(status='excused').count()
        absent = total - (present + late + excused)

        rate = ((present + late + excused) / total) * 100

        return Response({
            "student": {
                "admission_number": student.admission_number,
                "full_name": f"{student.first_name} {student.last_name}",
                "class_name": student.class_name
            },
            "stats": {
                "total_days": total,
                "present": present,
                "late": late,
                "excused": excused,
                "absent": absent,
                "attendance_rate": round(rate, 2)
            }
        })