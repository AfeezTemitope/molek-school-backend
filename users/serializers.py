import re
from typing import Any, Dict

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    AcademicSession,
    ActiveStudent,
    CAScore,
    ClassLevel,
    ExamResult,
    Subject,
    Term,
    UserProfile,
)


# ==============================
# CUSTOM JWT LOGIN SERIALIZER
# ==============================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT serializer for admin authentication"""

    @classmethod
    def get_token(cls, user: UserProfile) -> RefreshToken:
        token = super().get_token(user)
        token["role"] = user.role
        token["full_name"] = user.full_name
        return token

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        credentials = {
            "username": attrs.get("username"),
            "password": attrs.get("password"),
        }
        user = authenticate(**credentials)

        if user is None:
            raise serializers.ValidationError("Invalid credentials")

        if user.role not in ["admin", "superadmin"]:
            raise serializers.ValidationError(
                "Access denied. Admin credentials required."
            )

        data = super().validate(attrs)

        data["user"] = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.full_name,
            "role": user.role,
            "phone_number": user.phone_number,
            "is_active": user.is_active,
            "age": user.age,
            "sex": user.sex,
            "address": user.address,
            "state_of_origin": user.state_of_origin,
            "local_govt_area": user.local_govt_area,
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
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "phone_number",
            "is_active",
            "age",
            "sex",
            "address",
            "state_of_origin",
            "local_govt_area",
            "password",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_active", "full_name", "created_at", "updated_at"]

    def validate_phone_number(self, value: str) -> str:
        if value and not re.match(r"^\+?1?\d{9,15}$", value):
            raise serializers.ValidationError("Invalid phone number format")
        return value

    def validate_age(self, value: int) -> int:
        if value is not None and (value <= 0 or value > 120):
            raise serializers.ValidationError("Age must be between 1 and 120")
        return value

    def validate_role(self, value: str) -> str:
        if value not in ["admin", "superadmin"]:
            raise serializers.ValidationError("Role must be admin or superadmin")
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        request = self.context.get("request")
        if request and request.user.role == "admin":
            if attrs.get("role") == "superadmin":
                raise serializers.ValidationError(
                    {"role": "Only superadmins can create other superadmins"}
                )
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> UserProfile:
        password = validated_data.pop("password", None)
        user = UserProfile(**validated_data)

        if password:
            user.set_password(password)
        else:
            import secrets

            temp_password = secrets.token_urlsafe(12)
            user.set_password(temp_password)

        user.save()
        return user

    def update(
        self, instance: UserProfile, validated_data: Dict[str, Any]
    ) -> UserProfile:
        password = validated_data.pop("password", None)

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
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Incorrect old password")
        return value

    def validate_new_password(self, value: str) -> str:
        validate_password(value)
        return value


# ==============================
# PROFILE UPDATE SERIALIZER
# ==============================
class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for user profile updates"""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone_number",
            "age",
            "sex",
            "address",
            "state_of_origin",
            "local_govt_area",
        ]
        read_only_fields = ["id", "username", "email", "full_name"]

    def validate_phone_number(self, value: str) -> str:
        if value and not re.match(r"^\+?1?\d{9,15}$", value):
            raise serializers.ValidationError("Invalid phone number format")
        return value


# ============================================================
# CBT INTEGRATION SERIALIZERS
# ============================================================


# ==============================
# ACADEMIC MANAGEMENT SERIALIZERS
# ==============================
class TermSerializer(serializers.ModelSerializer):
    """Serializer for terms"""

    session_name = serializers.CharField(source="session.name", read_only=True)

    class Meta:
        model = Term
        fields = [
            "id",
            "session",
            "session_name",
            "name",
            "start_date",
            "end_date",
            "is_current",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class AcademicSessionSerializer(serializers.ModelSerializer):
    """Serializer for academic sessions"""

    terms = TermSerializer(many=True, read_only=True)

    class Meta:
        model = AcademicSession
        fields = [
            "id",
            "name",
            "start_date",
            "end_date",
            "is_current",
            "terms",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ClassLevelSerializer(serializers.ModelSerializer):
    """Serializer for class levels"""

    class Meta:
        model = ClassLevel
        fields = ["id", "name", "order"]
        read_only_fields = ["id"]


class SubjectSerializer(serializers.ModelSerializer):
    """Serializer for subjects"""

    class_levels_display = serializers.StringRelatedField(
        source="class_levels", many=True, read_only=True
    )

    class Meta:
        model = Subject
        fields = [
            "id",
            "name",
            "code",
            "class_levels",
            "class_levels_display",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# ==============================
# STUDENT SERIALIZERS
# ==============================
class ActiveStudentSerializer(serializers.ModelSerializer):
    """
    ✅ FIXED: Serializer for active students
    - Fixed password_plain conflict (removed from read_only_fields)
    - Fixed field name: passport (NOT passport_photo)
    - Fixed passport to return Cloudinary URL instead of public_id
    """

    class_level_name = serializers.CharField(source="class_level.name", read_only=True)
    enrollment_session_name = serializers.CharField(
        source="enrollment_session.name", read_only=True
    )
    subjects_display = serializers.StringRelatedField(
        source="subjects", many=True, read_only=True
    )
    full_name = serializers.CharField(read_only=True)

    # ✅ NEW: Use SerializerMethodField to return Cloudinary URL
    passport = serializers.SerializerMethodField()

    class Meta:
        model = ActiveStudent
        fields = [
            "id",
            "admission_number",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "password_plain",
            "date_of_birth",
            "gender",
            "email",
            "phone_number",
            "address",
            "state_of_origin",
            "local_govt_area",
            "class_level",
            "class_level_name",
            "subjects",
            "subjects_display",
            "enrollment_session",
            "enrollment_session_name",
            "parent_name",
            "parent_email",
            "parent_phone",
            "passport",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "admission_number",
            "created_at",
            "updated_at",
            "full_name",
        ]
        extra_kwargs = {"password_plain": {"write_only": True}}

    def get_passport(self, obj):
        """
        ✅ Return full Cloudinary URL instead of just public_id
        """
        if obj.passport:
            return obj.passport.url
        return None


class ActiveStudentWriteSerializer(serializers.ModelSerializer):
    """
    ✅ NEW: Separate serializer for creating/updating students
    This handles file uploads properly while ActiveStudentSerializer handles reading
    """

    class_level_name = serializers.CharField(source="class_level.name", read_only=True)
    enrollment_session_name = serializers.CharField(
        source="enrollment_session.name", read_only=True
    )
    subjects_display = serializers.StringRelatedField(
        source="subjects", many=True, read_only=True
    )
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = ActiveStudent
        fields = [
            "id",
            "admission_number",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "password_plain",
            "date_of_birth",
            "gender",
            "email",
            "phone_number",
            "address",
            "state_of_origin",
            "local_govt_area",
            "class_level",
            "class_level_name",
            "subjects",
            "subjects_display",
            "enrollment_session",
            "enrollment_session_name",
            "parent_name",
            "parent_email",
            "parent_phone",
            "passport",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "admission_number",
            "created_at",
            "updated_at",
            "full_name",
        ]
        extra_kwargs = {"password_plain": {"write_only": True}}


class StudentBulkUploadSerializer(serializers.Serializer):
    """Serializer for bulk student upload"""

    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )
    last_name = serializers.CharField(max_length=150)
    date_of_birth = serializers.DateField(input_formats=["%Y-%m-%d", "%d/%m/%Y"])
    gender = serializers.ChoiceField(choices=["M", "F"])
    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(
        max_length=15, required=False, allow_blank=True
    )
    address = serializers.CharField(required=False, allow_blank=True)
    state_of_origin = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    local_govt_area = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    class_level = serializers.CharField(max_length=10)
    parent_name = serializers.CharField(
        max_length=200, required=False, allow_blank=True
    )
    parent_email = serializers.EmailField(required=False, allow_blank=True)
    parent_phone = serializers.CharField(
        max_length=15, required=False, allow_blank=True
    )


class StudentCredentialsSerializer(serializers.ModelSerializer):
    """Serializer for exporting student credentials (for CBT)"""

    full_name = serializers.CharField(read_only=True)
    class_level = serializers.CharField(source="class_level.name", read_only=True)
    session = serializers.CharField(source="enrollment_session.name", read_only=True)
    password = serializers.CharField(source="password_plain", read_only=True)

    class Meta:
        model = ActiveStudent
        fields = [
            "admission_number",
            "password",  # Plain text password for CBT
            "full_name",
            "first_name",
            "middle_name",
            "last_name",
            "class_level",
            "session",
            "email",
            "date_of_birth",
            "gender",
        ]


# ==============================
# CA SCORE SERIALIZERS
# ==============================
class CAScoreUploadSerializer(serializers.Serializer):
    """
    Serializer for bulk CA + Theory score upload

    CSV Format:
    admission_number,subject,ca_score,theory_score
    MOL/2026/001,Mathematics,25,18
    """
    admission_number = serializers.CharField(max_length=50)
    subject = serializers.CharField(max_length=100)  # Matches by subject NAME
    ca_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    theory_score = serializers.DecimalField(max_digits=5, decimal_places=2)

    def validate_admission_number(self, value):
        if not ActiveStudent.objects.filter(admission_number=value.upper()).exists():
            raise serializers.ValidationError(f"Student with admission number {value} not found")
        return value.upper()

    def validate_subject(self, value):
        # Match by subject NAME (not code)
        if not Subject.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError(f"Subject '{value}' not found")
        return value

    def validate_ca_score(self, value):
        if value < 0 or value > 30:
            raise serializers.ValidationError("CA score must be between 0 and 30")
        return value

    def validate_theory_score(self, value):
        if value < 0:
            raise serializers.ValidationError("Theory score cannot be negative")
        return value


class CAScoreSerializer(serializers.ModelSerializer):
    """Serializer for CA Score model"""
    student_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()

    class Meta:
        model = CAScore
        fields = [
            'id', 'student', 'student_name', 'subject', 'subject_name',
            'session', 'term', 'ca_score', 'theory_score', 'max_theory_score',
            'total_non_exam_score', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_subject_name(self, obj):
        return obj.subject.name


class CAScoreBulkUploadSerializer(serializers.Serializer):
    """Serializer for bulk CA score upload"""

    admission_number = serializers.CharField(max_length=50)
    subject_code = serializers.CharField(max_length=10)
    subject_name = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    ca_score = serializers.IntegerField(min_value=0, max_value=100)


# ==============================
# EXAM RESULT SERIALIZERS
# ==============================
class ExamResultSerializer(serializers.ModelSerializer):
    """Serializer for Exam Result model"""
    student_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    admission_number = serializers.SerializerMethodField()

    class Meta:
        model = ExamResult
        fields = [
            'id', 'student', 'student_name', 'admission_number',
            'subject', 'subject_name', 'session', 'term',
            'ca_score', 'theory_score', 'exam_score', 'total_exam_questions',
            'total_score', 'grade', 'position', 'class_average',
            'total_students', 'highest_score', 'lowest_score',
            'submitted_at', 'uploaded_at'
        ]
        read_only_fields = ['id', 'total_score', 'grade', 'uploaded_at']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_subject_name(self, obj):
        return obj.subject.name

    def get_admission_number(self, obj):
        return obj.student.admission_number

class ExamResultUploadSerializer(serializers.Serializer):
    """
    Serializer for CBT exam results upload

    CSV Format from CBT:
    admission_number,subject,exam_score,total_questions,submitted_at
    MOL/2026/001,Mathematics,35,40,2026-01-19 13:30:55
    """
    admission_number = serializers.CharField(max_length=50)
    subject = serializers.CharField(max_length=100)  # Matches by subject NAME
    exam_score = serializers.IntegerField()
    total_questions = serializers.IntegerField()
    submitted_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_admission_number(self, value):
        if not ActiveStudent.objects.filter(admission_number=value.upper()).exists():
            raise serializers.ValidationError(f"Student with admission number {value} not found")
        return value.upper()

    def validate_subject(self, value):
        if not Subject.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError(f"Subject '{value}' not found")
        return value

class ExamResultBulkUploadSerializer(serializers.Serializer):
    """
    ✅ Serializer for bulk exam result upload from CSV
    Accepts: admission_number, subject_code, subject_name, exam_score, submitted_at
    """

    admission_number = serializers.CharField(max_length=50)
    subject_code = serializers.CharField(max_length=10)
    subject_name = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    exam_score = serializers.IntegerField(min_value=0, max_value=100)
    submitted_at = serializers.DateTimeField(
        input_formats=["%Y-%m-%d %H:%M:%S", "iso-8601"], required=False, allow_null=True
    )


# ==============================
# STUDENT PORTAL LOGIN SERIALIZER
# ==============================
class StudentLoginSerializer(serializers.Serializer):
    """Serializer for student portal login"""

    admission_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        from django.contrib.auth.hashers import check_password

        admission_number = attrs.get("admission_number")
        password = attrs.get("password")

        try:
            student = ActiveStudent.objects.get(
                admission_number=admission_number.upper(), is_active=True
            )
        except ActiveStudent.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials")

        if not check_password(password, student.password_hash):
            raise serializers.ValidationError("Invalid credentials")

        attrs["student"] = student
        return attrs


# ==============================
# STUDENT PROFILE UPDATE SERIALIZER (WITH CLOUDINARY PASSPORT)
# ==============================
class StudentProfileUpdateSerializer(serializers.ModelSerializer):
    """
    ✅ Serializer for student profile updates including passport photo upload
    Used when students update their profile in Student Portal
    Supports Cloudinary image upload for passport field
    """

    full_name = serializers.CharField(read_only=True)
    class_level_name = serializers.CharField(source="class_level.name", read_only=True)
    enrollment_session_name = serializers.CharField(
        source="enrollment_session.name", read_only=True
    )

    # ✅ NEW: Read passport as URL via SerializerMethodField
    passport_url = serializers.SerializerMethodField()

    class Meta:
        model = ActiveStudent
        fields = [
            "id",
            "admission_number",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "date_of_birth",
            "gender",
            "email",
            "phone_number",
            "address",
            "state_of_origin",
            "local_govt_area",
            "class_level_name",
            "enrollment_session_name",
            "parent_name",
            "parent_email",
            "parent_phone",
            "passport",  # ✅ For writing (file upload)
            "passport_url",  # ✅ For reading (Cloudinary URL)
            "is_active",
        ]
        read_only_fields = [
            "id",
            "admission_number",
            "full_name",
            "class_level_name",
            "enrollment_session_name",
            "passport_url",
            "date_of_birth",
            "gender",
        ]
        extra_kwargs = {
            "passport": {
                "write_only": True
            }  # ✅ passport field is write-only, use passport_url for reading
        }

    def get_passport_url(self, obj):
        """
        ✅ Return full Cloudinary URL instead of just public_id
        """
        if obj.passport:
            return obj.passport.url
        return None

    def validate_email(self, value):
        """Ensure email is unique if provided"""
        if value:
            student = self.instance
            if (
                ActiveStudent.objects.exclude(id=student.id)
                .filter(email=value)
                .exists()
            ):
                raise serializers.ValidationError("This email is already in use.")
        return value

    def validate_phone_number(self, value):
        """Validate phone number format"""
        if value and not re.match(r"^\+?1?\d{9,15}$", value):
            raise serializers.ValidationError("Invalid phone number format")
        return value

# ============================================
# PROMOTION SERIALIZERS
# ============================================

class StudentPromotionSerializer(serializers.Serializer):
    """Serializer for promotion data"""
    student_id = serializers.IntegerField()
    admission_number = serializers.CharField()
    full_name = serializers.CharField()
    current_class = serializers.CharField()
    term1_average = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    term2_average = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    term3_average = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    cumulative_average = serializers.DecimalField(max_digits=5, decimal_places=2)
    passed = serializers.BooleanField()
    subjects_count = serializers.IntegerField()


class BulkPromotionSerializer(serializers.Serializer):
    """Serializer for bulk promotion request"""
    student_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    from_class = serializers.CharField(max_length=10)
    to_class = serializers.CharField(max_length=10)
    session_id = serializers.IntegerField()