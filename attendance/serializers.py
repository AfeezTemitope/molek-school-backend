# attendance/serializers.py

from rest_framework import serializers
from .models import TeacherAssignment, AttendanceRecord
from users.models import Student


class TeacherAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherAssignment
        fields = '__all__'


class AttendanceStatsSerializer(serializers.Serializer):
    total_days = serializers.IntegerField()
    present = serializers.IntegerField()
    late = serializers.IntegerField()
    excused = serializers.IntegerField()
    absent = serializers.IntegerField()
    attendance_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


class StudentAttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ['admission_number', 'first_name', 'last_name', 'class_level', 'section']