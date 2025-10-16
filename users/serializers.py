from typing import Any, Dict, List, Optional
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .models import UserProfile, Student
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
import re

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user: UserProfile) -> RefreshToken:
        token = super().get_token(user)
        token['role'] = user.role
        return token

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        credentials = {
            'username': attrs.get('username'),
            'password': attrs.get('password')
        }
        user = authenticate(**credentials)
        if user is None:
            raise serializers.ValidationError('Invalid credentials')
        data = super().validate(attrs)
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': f"{user.first_name} {user.last_name}".strip(),
            'role': user.role,
            'phone_number': user.phone_number,
            'is_active': user.is_active
        }
        try:
            student = user.student_profile
            data['user']['admission_number'] = student.admission_number
            data['user']['passport_url'] = student.passport.url if student.passport else None
            data['user']['parent_email'] = student.parent_email
            data['user']['parent_phone_number'] = student.parent_phone_number
        except Student.DoesNotExist:
            data['user']['admission_number'] = None
            data['user']['passport_url'] = None
            data['user']['parent_email'] = None
            data['user']['parent_phone_number'] = None
        return data

class UserLoginSerializer(serializers.Serializer):
    admission_number = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=150)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        admission_number = attrs.get('admission_number')
        last_name = attrs.get('last_name')

        if not re.match(r'^\d{4}/[A-Z0-9]+/[A-Za-z]+/[A-Z]/\d{3}$', admission_number):
            raise serializers.ValidationError({
                'admission_number': f'Invalid format: {admission_number}. Expected: YYYY/CLASS/STREAM/SECTION/NNN (e.g., 2025/SS1/SCI/A/001)'
            })

        try:
            student = Student.objects.get(
                admission_number__iexact=admission_number,
                user__last_name__iexact=last_name,
                user__is_active=True
            )
            user = student.user
        except Student.DoesNotExist:
            raise serializers.ValidationError({
                'detail': f'No active student found with admission_number="{admission_number}" and last_name="{last_name}"'
            })

        token = CustomTokenObtainPairSerializer.get_token(user)
        return {
            'token': {
                'access': str(token.access_token),
                'refresh': str(token)
            },
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': f"{user.first_name} {user.last_name}".strip(),
                'role': user.role,
                'phone_number': user.phone_number,
                'is_active': user.is_active,
                'passport_url': student.passport.url if student.passport else None,
                'admission_number': student.admission_number,
                'parent_email': student.parent_email,
                'parent_phone_number': student.parent_phone_number
            }
        }

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'is_active']
        read_only_fields = ['id', 'is_active']

    def validate_phone_number(self, value: Optional[str]) -> Optional[str]:
        if value and not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError('Invalid phone number format')
        return value

class StudentSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer()
    passport_url = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'user', 'admission_number', 'class_level', 'stream', 'section',
            'class_name', 'passport_url', 'parent_email', 'parent_phone_number', 'is_active'
        ]
        read_only_fields = ['id', 'admission_number', 'is_active']

    def get_passport_url(self, obj: Student) -> Optional[str]:
        if obj.passport:
            return obj.passport.url
        return None

    def get_class_name(self, obj: Student) -> str:
        parts = [obj.class_level]
        if obj.stream:
            parts.append(obj.stream)
        if obj.section:
            parts.append(obj.section)
        return ' '.join(parts)

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        class_level = data.get('class_level')
        stream = data.get('stream')
        section = data.get('section')

        valid_class_levels = [choice[0] for choice in Student.CLASS_LEVEL_CHOICES]
        if class_level and class_level not in valid_class_levels:
            raise serializers.ValidationError({'class_level': f'Invalid class level. Choose from: {", ".join(valid_class_levels)}'})

        valid_streams = [choice[0] for choice in Student.STREAM_CHOICES]
        if stream and stream not in valid_streams:
            raise serializers.ValidationError({'stream': f'Invalid stream. Choose from: {", ".join(valid_streams)}'})

        valid_sections = [choice[0] for choice in Student.SECTION_CHOICES]
        if section and section not in valid_sections:
            raise serializers.ValidationError({'section': f'Invalid section. Choose from: {", ".join(valid_sections)}'})

        return data

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        old_password = attrs.get('old_password')
        new_password = attrs.get('new_password')
        user = self.context['request'].user

        if not user.check_password(old_password):
            raise serializers.ValidationError({'old_password': 'Incorrect old password'})

        try:
            validate_password(new_password, user=user)
        except serializers.ValidationError as e:
            raise serializers.ValidationError({'new_password': str(e)})

        return attrs