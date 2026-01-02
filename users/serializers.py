from typing import Any, Dict
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
import re

from .models import (
    UserProfile,
    AcademicSession,
    Term,
    ClassLevel,
    Subject,
    ActiveStudent,
    CAScore,
    ExamResult
)


# ==============================
# CUSTOM JWT LOGIN SERIALIZER
# ==============================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT serializer for admin authentication"""

    @classmethod
    def get_token(cls, user: UserProfile) -> RefreshToken:
        token = super().get_token(user)
        token['role'] = user.role
        token['full_name'] = user.full_name
        return token

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        credentials = {
            'username': attrs.get('username'),
            'password': attrs.get('password')
        }
        user = authenticate(**credentials)

        if user is None:
            raise serializers.ValidationError('Invalid credentials')

        if user.role not in ['admin', 'superadmin']:
            raise serializers.ValidationError('Access denied. Admin credentials required.')

        data = super().validate(attrs)

        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.full_name,
            'role': user.role,
            'phone_number': user.phone_number,
            'is_active': user.is_active,
            'age': user.age,
            'sex': user.sex,
            'address': user.address,
            'state_of_origin': user.state_of_origin,
            'local_govt_area': user.local_govt_area,
        }

        return data


# ==============================
# ADMIN USER PROFILE SERIALIZER
# ==============================
class AdminProfileSerializer(serializers.ModelSerializer):
    """Serializer for admin user profiles"""
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'phone_number', 'is_active',
            'age', 'sex', 'address', 'state_of_origin', 'local_govt_area',
            'password', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_active', 'full_name', 'created_at', 'updated_at']

    def validate_phone_number(self, value: str) -> str:
        if value and not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError('Invalid phone number format')
        return value

    def validate_age(self, value: int) -> int:
        if value is not None and (value <= 0 or value > 120):
            raise serializers.ValidationError('Age must be between 1 and 120')
        return value

    def validate_role(self, value: str) -> str:
        if value not in ['admin', 'superadmin']:
            raise serializers.ValidationError('Role must be admin or superadmin')
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context.get('request')
        if request and request.user.role == 'admin':
            if attrs.get('role') == 'superadmin':
                raise serializers.ValidationError({'role': 'Only superadmins can create other superadmins'})
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> UserProfile:
        password = validated_data.pop('password', None)
        user = UserProfile(**validated_data)

        if password:
            user.set_password(password)
        else:
            import secrets
            temp_password = secrets.token_urlsafe(12)
            user.set_password(temp_password)

        user.save()
        return user

    def update(self, instance: UserProfile, validated_data: Dict[str, Any]) -> UserProfile:
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance


# ==============================
# CHANGE PASSWORD SERIALIZER
# ==============================
class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change"""
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)

    def validate_old_password(self, value: str) -> str:
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Incorrect old password')
        return value

    def validate_new_password(self, value: str) -> str:
        user = self.context['request'].user
        validate_password(value, user=user)
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError({
                'new_password': 'New password must be different from old password'
            })
        return attrs


# ==============================
# PROFILE UPDATE SERIALIZER
# ==============================
class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for user profile updates"""
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'phone_number', 'age', 'sex', 'address', 'state_of_origin', 'local_govt_area'
        ]
        read_only_fields = ['id', 'username', 'email', 'full_name']

    def validate_phone_number(self, value: str) -> str:
        if value and not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError('Invalid phone number format')
        return value


# ============================================================
# CBT INTEGRATION SERIALIZERS
# ============================================================

# ACADEMIC MANAGEMENT SERIALIZERS
class TermSerializer(serializers.ModelSerializer):
    """Serializer for terms"""
    session_name = serializers.CharField(source='session.name', read_only=True)

    class Meta:
        model = Term
        fields = ['id', 'session', 'session_name', 'name', 'start_date', 'end_date', 'is_current', 'created_at']
        read_only_fields = ['id', 'created_at']


class AcademicSessionSerializer(serializers.ModelSerializer):
    """Serializer for academic sessions"""
    terms = TermSerializer(many=True, read_only=True)

    class Meta:
        model = AcademicSession
        fields = ['id', 'name', 'start_date', 'end_date', 'is_current', 'terms', 'created_at']
        read_only_fields = ['id', 'created_at']


class ClassLevelSerializer(serializers.ModelSerializer):
    """Serializer for class levels"""
    display_name = serializers.CharField(source='get_name_display', read_only=True)
    student_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ClassLevel
        fields = ['id', 'name', 'display_name', 'order', 'student_count']
        read_only_fields = ['id']

    def get_student_count(self, obj):
        return obj.active_students.filter(is_active=True).count()


class SubjectSerializer(serializers.ModelSerializer):
    """Serializer for subjects"""
    class_levels = ClassLevelSerializer(many=True, read_only=True)
    class_level_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        queryset=ClassLevel.objects.all(),
        source='class_levels',
        required=False
    )

    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'class_levels', 'class_level_ids', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


# STUDENT SERIALIZERS
class ActiveStudentSerializer(serializers.ModelSerializer):
    """Serializer for student CRUD operations"""
    full_name = serializers.CharField(read_only=True)
    class_name = serializers.CharField(source='class_level.name', read_only=True)
    class_display = serializers.CharField(source='class_level.get_name_display', read_only=True)
    session_name = serializers.CharField(source='enrollment_session.name', read_only=True)
    subjects = SubjectSerializer(many=True, read_only=True)
    subject_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        queryset=Subject.objects.all(),
        source='subjects',
        required=False
    )

    class Meta:
        model = ActiveStudent
        fields = [
            'id', 'admission_number', 'first_name', 'middle_name', 'last_name', 'full_name',
            'password_plain', 'date_of_birth', 'gender', 'email', 'phone_number',
            'address', 'state_of_origin', 'local_govt_area',
            'class_level', 'class_name', 'class_display', 'enrollment_session', 'session_name',
            'subjects', 'subject_ids',
            'parent_name', 'parent_email', 'parent_phone', 'passport',
            'is_active', 'graduation_date', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'admission_number', 'full_name', 'class_name', 'class_display', 'session_name',
                            'created_at', 'updated_at']
        extra_kwargs = {
            'password_plain': {'required': False}
        }


class StudentBulkUploadSerializer(serializers.Serializer):
    """Serializer for bulk CSV upload"""
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150)
    date_of_birth = serializers.DateField(input_formats=['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'])
    gender = serializers.ChoiceField(choices=['M', 'F'])
    class_level = serializers.CharField(max_length=10)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(max_length=15, required=False, allow_blank=True, allow_null=True)
    parent_name = serializers.CharField(max_length=200, required=False, allow_blank=True, allow_null=True)
    parent_email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    parent_phone = serializers.CharField(max_length=15, required=False, allow_blank=True, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    state_of_origin = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    local_govt_area = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)


class StudentCredentialsSerializer(serializers.ModelSerializer):
    """Serializer for exporting student credentials (for CBT)"""
    full_name = serializers.CharField(read_only=True)
    class_level = serializers.CharField(source='class_level.name', read_only=True)
    session = serializers.CharField(source='enrollment_session.name', read_only=True)
    password = serializers.CharField(source='password_plain', read_only=True)

    class Meta:
        model = ActiveStudent
        fields = [
            'admission_number',
            'password',  # Plain text password for CBT
            'full_name',
            'first_name',
            'middle_name',
            'last_name',
            'class_level',
            'session',
            'email',
            'date_of_birth',
            'gender'
        ]


# CA SCORE SERIALIZERS
class CAScoreSerializer(serializers.ModelSerializer):
    """Serializer for CA scores"""
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_admission = serializers.CharField(source='student.admission_number', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    session_name = serializers.CharField(source='session.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = CAScore
        fields = [
            'id', 'student', 'student_name', 'student_admission',
            'subject', 'subject_name', 'subject_code',
            'session', 'session_name', 'term', 'term_name',
            'score', 'max_score', 'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_at']


class CAScoreBulkUploadSerializer(serializers.Serializer):
    """Serializer for bulk CA score upload"""
    admission_number = serializers.CharField(max_length=50)
    subject_code = serializers.CharField(max_length=10)
    ca_score = serializers.IntegerField(min_value=0, max_value=100)


# EXAM RESULT SERIALIZERS
class ExamResultSerializer(serializers.ModelSerializer):
    """Serializer for exam results"""
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    student_class = serializers.CharField(source='student.class_level.name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    session_name = serializers.CharField(source='session.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)
    grade_display = serializers.CharField(source='get_grade_display', read_only=True)

    class Meta:
        model = ExamResult
        fields = [
            'id', 'student', 'student_name', 'admission_number', 'student_class',
            'subject', 'subject_name', 'subject_code',
            'session', 'session_name', 'term', 'term_name',
            'ca_score', 'exam_score', 'total_score', 'percentage',
            'grade', 'grade_display', 'position', 'class_average',
            'total_students', 'highest_score', 'lowest_score',
            'submitted_at', 'uploaded_at'
        ]
        read_only_fields = ['id', 'total_score', 'percentage', 'grade', 'uploaded_at']


class ExamResultBulkUploadSerializer(serializers.Serializer):
    """Serializer for bulk exam result upload from CBT"""
    admission_number = serializers.CharField(max_length=50)
    subject_code = serializers.CharField(max_length=10)
    exam_score = serializers.IntegerField(min_value=0, max_value=100)
    submitted_at = serializers.DateTimeField(input_formats=['%Y-%m-%d %H:%M:%S', 'iso-8601'])


# STUDENT PORTAL LOGIN SERIALIZER
class StudentLoginSerializer(serializers.Serializer):
    """Serializer for student portal login"""
    admission_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        from django.contrib.auth.hashers import check_password

        admission_number = attrs.get('admission_number')
        password = attrs.get('password')

        try:
            student = ActiveStudent.objects.get(
                admission_number=admission_number.upper(),
                is_active=True
            )
        except ActiveStudent.DoesNotExist:
            raise serializers.ValidationError('Invalid credentials')

        if not check_password(password, student.password_hash):
            raise serializers.ValidationError('Invalid credentials')

        attrs['student'] = student
        return attrs