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
    PromotionRule,
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
    """Serializer for active students"""

    class_level_name = serializers.CharField(source="class_level.name", read_only=True)
    enrollment_session_name = serializers.CharField(
        source="enrollment_session.name", read_only=True
    )
    subjects_display = serializers.StringRelatedField(
        source="subjects", many=True, read_only=True
    )
    full_name = serializers.CharField(read_only=True)
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
        """Return full Cloudinary URL"""
        if obj.passport:
            return obj.passport.url
        return None


class ActiveStudentWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating students"""

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
            "password",
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
# CA SCORE SERIALIZERS (CA1 + CA2)
# ==============================
class CAScoreUploadSerializer(serializers.Serializer):
    """
    Serializer for bulk CA score upload (CA1 + CA2)

    CSV Format:
    admission_number,subject,ca1_score,ca2_score
    MOL/2026/001,Mathematics,12,13
    MOL/2026/001,English Language,14,12
    """
    admission_number = serializers.CharField(max_length=50)
    subject = serializers.CharField(max_length=100)
    ca1_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    ca2_score = serializers.DecimalField(max_digits=5, decimal_places=2)

    def validate_admission_number(self, value):
        if not ActiveStudent.objects.filter(admission_number=value.upper()).exists():
            raise serializers.ValidationError(f"Student with admission number {value} not found")
        return value.upper()

    def validate_subject(self, value):
        if not Subject.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError(f"Subject '{value}' not found")
        return value

    def validate_ca1_score(self, value):
        if value < 0 or value > 15:
            raise serializers.ValidationError("CA1 score must be between 0 and 15")
        return value

    def validate_ca2_score(self, value):
        if value < 0 or value > 15:
            raise serializers.ValidationError("CA2 score must be between 0 and 15")
        return value


class CAScoreSerializer(serializers.ModelSerializer):
    """Serializer for CA Score model (CA1 + CA2)"""
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    total_ca = serializers.SerializerMethodField()

    class Meta:
        model = CAScore
        fields = [
            'id', 
            'student', 'student_name', 'admission_number',
            'subject', 'subject_name',
            'session', 'term', 
            'ca1_score', 'ca2_score', 'total_ca',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_admission_number(self, obj):
        return obj.student.admission_number

    def get_subject_name(self, obj):
        return obj.subject.name

    def get_total_ca(self, obj):
        return obj.total_ca_score


class CAScoreBulkUploadSerializer(serializers.Serializer):
    """
    Accepts CSV with: admission_number, subject, ca1_score, ca2_score
    Subject is matched by NAME (not code)
    """
    admission_number = serializers.CharField(max_length=20)
    subject = serializers.CharField(max_length=100)
    ca1_score = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=15)
    ca2_score = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=15)
    
    def validate(self, data):
        # Find student
        try:
            student = ActiveStudent.objects.get(admission_number=data['admission_number'])
            data['student'] = student
        except ActiveStudent.DoesNotExist:
            raise serializers.ValidationError(f"Student not found: {data['admission_number']}")
        
        # Find subject by NAME
        try:
            subject = Subject.objects.get(name__iexact=data['subject'])
            data['subject_obj'] = subject
        except Subject.DoesNotExist:
            raise serializers.ValidationError(f"Subject not found: {data['subject']}")
        
        return data


# ==============================
# EXAM RESULT SERIALIZERS
# ==============================
class ExamResultSerializer(serializers.ModelSerializer):
    """
    Serializer for Exam Result model
    
    Nigerian School Grading:
    - CA1: max 15
    - CA2: max 15
    - OBJ/CBT: max 30
    - Theory: max 40
    - Total: 100
    """
    # Read-only display fields
    student_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    admission_number = serializers.SerializerMethodField()
    session_name = serializers.SerializerMethodField()
    term_name = serializers.SerializerMethodField()
    total_ca = serializers.SerializerMethodField()
    exam_total = serializers.SerializerMethodField()

    class Meta:
        model = ExamResult
        fields = [
            'id', 
            'student', 'student_name', 'admission_number',
            'subject', 'subject_name', 
            'session', 'session_name',
            'term', 'term_name',
            # Score components
            'ca1_score', 'ca2_score', 'total_ca',
            'obj_score', 'theory_score', 'exam_total',
            'total_obj_questions',
            # Calculated
            'total_score', 'grade', 'remark',
            # Class stats
            'position', 'class_average', 'total_students', 'highest_score', 'lowest_score',
            # Cumulative
            'first_term_total', 'second_term_total', 'third_term_total',
            'cumulative_score', 'cumulative_grade',
            # Metadata
            'submitted_at', 'uploaded_at', 'updated_at'
        ]
        read_only_fields = ['id', 'total_score', 'grade', 'remark', 'uploaded_at', 'updated_at',
                           'cumulative_score', 'cumulative_grade']
        extra_kwargs = {
            'student': {'required': False},
            'subject': {'required': False},
            'session': {'required': False},
            'term': {'required': False},
        }

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_subject_name(self, obj):
        return obj.subject.name
    
    def get_admission_number(self, obj):
        return obj.student.admission_number
    
    def get_session_name(self, obj):
        return obj.session.name if obj.session else None
    
    def get_term_name(self, obj):
        return obj.term.name if obj.term else None

    def get_total_ca(self, obj):
        return obj.total_ca

    def get_exam_total(self, obj):
        return obj.exam_total

    def validate_ca1_score(self, value):
        """CA1 score max 15"""
        if value is not None and value > 15:
            raise serializers.ValidationError("CA1 score cannot exceed 15")
        return value or 0

    def validate_ca2_score(self, value):
        """CA2 score max 15"""
        if value is not None and value > 15:
            raise serializers.ValidationError("CA2 score cannot exceed 15")
        return value or 0

    def validate_obj_score(self, value):
        """OBJ/CBT score max 30"""
        if value is not None and value > 30:
            raise serializers.ValidationError("OBJ score cannot exceed 30")
        return value or 0

    def validate_theory_score(self, value):
        """Theory score max 40"""
        if value is not None and value > 40:
            raise serializers.ValidationError("Theory score cannot exceed 40")
        return value or 0

    def validate(self, attrs):
        """Cross-field validation"""
        if not self.instance:
            required_fields = ['student', 'subject', 'session', 'term']
            for field in required_fields:
                if field not in attrs or attrs[field] is None:
                    raise serializers.ValidationError({
                        field: f"{field} is required"
                    })
        
        # Validate total doesn't exceed 100
        ca1 = attrs.get('ca1_score', getattr(self.instance, 'ca1_score', 0) if self.instance else 0) or 0
        ca2 = attrs.get('ca2_score', getattr(self.instance, 'ca2_score', 0) if self.instance else 0) or 0
        obj = attrs.get('obj_score', getattr(self.instance, 'obj_score', 0) if self.instance else 0) or 0
        theory = attrs.get('theory_score', getattr(self.instance, 'theory_score', 0) if self.instance else 0) or 0
        
        total = float(ca1) + float(ca2) + float(obj) + float(theory)
        if total > 100:
            raise serializers.ValidationError({
                'non_field_errors': f"Total score ({total}) cannot exceed 100"
            })
        
        return attrs

    def update(self, instance, validated_data):
        """Handle update - only allow score fields to change"""
        validated_data.pop('student', None)
        validated_data.pop('subject', None)
        validated_data.pop('session', None)
        validated_data.pop('term', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class ExamResultUploadSerializer(serializers.Serializer):
    """
    Serializer for exam results upload (OBJ + Theory)
    
    CSV Format from CBT (OBJ only):
    admission_number,subject,obj_score,total_questions
    MOL/2026/001,Mathematics,25,30
    
    CSV Format with Theory:
    admission_number,subject,obj_score,theory_score
    MOL/2026/001,Mathematics,25,35
    """
    admission_number = serializers.CharField(max_length=50)
    subject = serializers.CharField(max_length=100)
    obj_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    theory_score = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, default=0)
    total_questions = serializers.IntegerField(required=False, default=30)
    submitted_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_admission_number(self, value):
        if not ActiveStudent.objects.filter(admission_number=value.upper()).exists():
            raise serializers.ValidationError(f"Student with admission number {value} not found")
        return value.upper()

    def validate_subject(self, value):
        if not Subject.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError(f"Subject '{value}' not found")
        return value

    def validate_obj_score(self, value):
        if value < 0 or value > 30:
            raise serializers.ValidationError("OBJ score must be between 0 and 30")
        return value

    def validate_theory_score(self, value):
        if value < 0 or value > 40:
            raise serializers.ValidationError("Theory score must be between 0 and 40")
        return value


class ExamResultBulkUploadSerializer(serializers.Serializer):
    """
    Serializer for bulk exam result upload from CBT CSV
    Accepts: admission_number, subject_code, subject_name, obj_score, submitted_at
    
    NOTE: This expects RAW CBT scores (not scaled!)
    """
    admission_number = serializers.CharField(max_length=50)
    subject_code = serializers.CharField(max_length=10)
    subject_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    obj_score = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=30)
    submitted_at = serializers.DateTimeField(
        input_formats=["%Y-%m-%d %H:%M:%S", "iso-8601"], required=False, allow_null=True
    )


# ==============================
# THEORY SCORE UPLOAD SERIALIZER
# ==============================
class TheoryScoreUploadSerializer(serializers.Serializer):
    """
    Serializer for bulk theory score upload
    
    CSV Format:
    admission_number,subject,theory_score
    MOL/2026/001,Mathematics,35
    MOL/2026/001,English Language,32
    """
    admission_number = serializers.CharField(max_length=50)
    subject = serializers.CharField(max_length=100)
    theory_score = serializers.DecimalField(max_digits=5, decimal_places=2)

    def validate_admission_number(self, value):
        if not ActiveStudent.objects.filter(admission_number=value.upper()).exists():
            raise serializers.ValidationError(f"Student with admission number {value} not found")
        return value.upper()

    def validate_subject(self, value):
        if not Subject.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError(f"Subject '{value}' not found")
        return value

    def validate_theory_score(self, value):
        if value < 0 or value > 40:
            raise serializers.ValidationError("Theory score must be between 0 and 40")
        return value


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
# STUDENT PORTAL SERIALIZER (COMPLETE DATA)
# ==============================
class StudentPortalSerializer(serializers.ModelSerializer):
    """Complete serializer for student portal"""
    full_name = serializers.CharField(read_only=True)
    class_level_name = serializers.SerializerMethodField()
    enrollment_session_name = serializers.SerializerMethodField()
    passport_url = serializers.SerializerMethodField()

    class Meta:
        model = ActiveStudent
        fields = [
            'id',
            'admission_number',
            'first_name',
            'middle_name',
            'last_name',
            'full_name',
            'date_of_birth',
            'gender',
            'email',
            'phone_number',
            'address',
            'state_of_origin',
            'local_govt_area',
            'class_level',
            'class_level_name',
            'enrollment_session',
            'enrollment_session_name',
            'parent_name',
            'parent_email',
            'parent_phone',
            'passport_url',
            'is_active',
        ]

    def get_class_level_name(self, obj):
        if obj.class_level:
            return obj.class_level.name
        return None

    def get_enrollment_session_name(self, obj):
        if obj.enrollment_session:
            return obj.enrollment_session.name
        return None

    def get_passport_url(self, obj):
        if obj.passport:
            try:
                return obj.passport.url
            except:
                return None
        return None


# ==============================
# STUDENT PROFILE UPDATE SERIALIZER
# ==============================
class StudentProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for student profile updates"""

    full_name = serializers.CharField(read_only=True)
    class_level_name = serializers.CharField(source="class_level.name", read_only=True)
    enrollment_session_name = serializers.CharField(
        source="enrollment_session.name", read_only=True
    )
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
            "passport",
            "passport_url",
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
            "passport": {"write_only": True}
        }

    def get_passport_url(self, obj):
        if obj.passport:
            return obj.passport.url
        return None

    def validate_email(self, value):
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
    # New fields for Nigerian grading
    passed_compulsory = serializers.BooleanField(required=False)
    passed_subjects_count = serializers.IntegerField(required=False)
    failed_subjects = serializers.ListField(child=serializers.CharField(), required=False)


class BulkPromotionSerializer(serializers.Serializer):
    """Serializer for bulk promotion request"""
    student_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    from_class = serializers.CharField(max_length=10)
    to_class = serializers.CharField(max_length=10)
    session_id = serializers.IntegerField()


# ============================================
# PROMOTION RULE SERIALIZER
# ============================================
class PromotionRuleSerializer(serializers.ModelSerializer):
    """Serializer for promotion rules"""
    session_name = serializers.CharField(source='session.name', read_only=True)
    class_level_name = serializers.CharField(source='class_level.name', read_only=True, allow_null=True)
    compulsory_subjects = serializers.SerializerMethodField()

    class Meta:
        model = PromotionRule
        fields = [
            'id',
            'session', 'session_name',
            'class_level', 'class_level_name',
            'pass_mark_percentage',
            'compulsory_subject_ids', 'compulsory_subjects',
            'minimum_additional_subjects',
            'total_minimum_subjects',
            'promotion_mode',
            'allow_carryover',
            'max_carryover_subjects',
            'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'total_minimum_subjects']

    def get_compulsory_subjects(self, obj):
        """Return list of compulsory subject names"""
        if obj.compulsory_subject_ids:
            subjects = Subject.objects.filter(id__in=obj.compulsory_subject_ids)
            return [{'id': s.id, 'name': s.name} for s in subjects]
        return []


# ============================================
# REPORT CARD SERIALIZER
# ============================================
class ReportCardSerializer(serializers.Serializer):
    """Serializer for student report card data"""
    student = StudentPortalSerializer()
    session = AcademicSessionSerializer()
    term = TermSerializer()
    results = ExamResultSerializer(many=True)
    
    # Summary statistics
    total_subjects = serializers.IntegerField()
    total_score = serializers.DecimalField(max_digits=7, decimal_places=2)
    average_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    average_grade = serializers.CharField()
    overall_position = serializers.IntegerField(allow_null=True)
    total_students_in_class = serializers.IntegerField()
    
    # Cumulative data (for 2nd and 3rd term)
    cumulative_average = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    cumulative_grade = serializers.CharField(allow_null=True)
    
    # Promotion status (3rd term only)
    promotion_status = serializers.CharField(allow_null=True)
    promotion_remarks = serializers.CharField(allow_null=True)