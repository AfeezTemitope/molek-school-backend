from rest_framework import serializers
from .models import Class, AttendanceRecord



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

    class Meta:
        model = AttendanceRecord
        fields = '__all__'

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

class AttendanceStatsSerializer(serializers.Serializer):
    total_days = serializers.IntegerField()
    present = serializers.IntegerField()
    late = serializers.IntegerField()
    excused = serializers.IntegerField()
    absent = serializers.IntegerField()
    attendance_rate = serializers.DecimalField(max_digits=5, decimal_places=2)