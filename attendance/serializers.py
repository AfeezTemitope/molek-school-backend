from rest_framework import serializers
from .models import Class, AttendanceRecord
from django.utils import timezone

class ClassSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Class
        fields = '__all__'

    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name()

class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.ReadOnlyField(source='student.admission_number')
    recorded_by = serializers.StringRelatedField()

    class Meta:
        model = AttendanceRecord
        fields = ['id', 'student_name', 'admission_number', 'status', 'date', 'recorded_by']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

class AttendanceStatsSerializer(serializers.Serializer):
    total_days = serializers.IntegerField()
    present = serializers.IntegerField()
    late = serializers.IntegerField()
    excused = serializers.IntegerField()
    absent = serializers.IntegerField()
    attendance_rate = serializers.DecimalField(max_digits=5, decimal_places=2)

class MarkAttendanceSerializer(serializers.Serializer):
    class_id = serializers.IntegerField()
    date = serializers.DateField()
    records = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        )
    )

    def validate_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Cannot mark attendance for past dates.")
        return value