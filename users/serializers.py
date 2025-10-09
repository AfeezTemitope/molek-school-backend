from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Student, UserProfile

User = get_user_model()

class UserCreateSerializer(serializers.ModelSerializer):
    """
    Used by Super Admin to create Admin/Teacher users.
    Only superadmin can use this.
    """
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES)

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'password', 'role', 'is_active']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        role = validated_data.pop('role')
        user = UserProfile.objects.create_user(**validated_data)
        user.role = role
        user.save()
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Add user role to JWT payload.
    Frontend will use this to route permissions.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['user_id'] = user.id
        token['full_name'] = user.get_full_name()
        return token

    def validate(self, attrs):
        # Only return refresh and access tokens
        data = super().validate(attrs)
        return data

class StudentSerializer(serializers.ModelSerializer):
    admission_number = serializers.CharField(read_only=True)
    created_by = serializers.StringRelatedField(read_only=True)
    passport_url = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'first_name', 'last_name', 'gender', 'age', 'address',
            'class_level', 'class_name', 'section', 'parent_phone', 'parent_email',
            'admission_number', 'passport_url', 'created_by', 'created_at', 'is_active'
        ]
        read_only_fields = ['admission_number', 'created_by', 'created_at', 'id']

    def get_passport_url(self, obj):
        if obj.passport_url:
            return obj.passport_url.url
        return None

    def validate_parent_phone(self, value):
        import re
        pattern = r'^\+234\d{10}$'
        if not re.match(pattern, value):
            raise serializers.ValidationError("Phone must be in +23480... format")
        return value

    def validate_age(self, value):
        if value < 3 or value > 18:
            raise serializers.ValidationError("Age must be between 3 and 18")
        return value

    def validate_class_level(self, value):
        valid_levels = ['JSS1', 'JSS2', 'JSS3', 'SS1', 'SS2', 'SS3']
        if value not in valid_levels:
            raise serializers.ValidationError(f"Class level must be one of: {', '.join(valid_levels)}")
        return value

class UserLoginSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    admission_number = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    parent_phone = serializers.SerializerMethodField()
    parent_email = serializers.SerializerMethodField()
    passport_url = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'id',
            'username',
            'full_name',
            'role',
            'admission_number',
            'class_name',
            'parent_phone',
            'parent_email',
            'passport_url'
        ]
        read_only_fields = fields

    def get_admission_number(self, obj):
        try:
            return obj.student_profile.admission_number
        except Exception:
            return None

    def get_class_name(self, obj):
        try:
            return f"{obj.student_profile.class_level} {obj.student_profile.section or ''}".strip()
        except Exception:
            return None

    def get_parent_phone(self, obj):
        try:
            return obj.student_profile.parent_phone
        except Exception:
            return None

    def get_parent_email(self, obj):
        try:
            return obj.student_profile.parent_email
        except Exception:
            return None

    def get_passport_url(self, obj):
        try:
            return obj.student_profile.passport_url.url
        except Exception:
            return None