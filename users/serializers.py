from typing import Any, Dict
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
import re
from .models import UserProfile


# ==============================
# CUSTOM JWT LOGIN SERIALIZER
# ==============================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer for admin authentication.
    Adds 'role' to the token and returns user details.
    """

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

        # Only allow admin/superadmin login
        if user.role not in ['admin', 'superadmin']:
            raise serializers.ValidationError('Access denied. Admin credentials required.')

        data = super().validate(attrs)

        # Return user data
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
    """Serializer for admin user profiles (create/update/list)"""
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
        """Validate phone number format"""
        if value and not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError('Invalid phone number format (9-15 digits)')
        return value

    def validate_age(self, value: int) -> int:
        """Validate age range"""
        if value is not None and (value <= 0 or value > 120):
            raise serializers.ValidationError('Age must be between 1 and 120')
        return value

    def validate_role(self, value: str) -> str:
        """Ensure role is admin or superadmin only"""
        if value not in ['admin', 'superadmin']:
            raise serializers.ValidationError('Role must be admin or superadmin')
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Additional validation logic"""
        # Prevent regular admins from creating superadmins
        request = self.context.get('request')
        if request and request.user.role == 'admin':
            if attrs.get('role') == 'superadmin':
                raise serializers.ValidationError({'role': 'Only superadmins can create other superadmins'})

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> UserProfile:
        """Create a new admin user"""
        password = validated_data.pop('password', None)
        user = UserProfile(**validated_data)

        if password:
            user.set_password(password)
        else:
            # Generate secure random password if not provided
            import secrets
            temp_password = secrets.token_urlsafe(12)
            user.set_password(temp_password)

        user.save()
        return user

    def update(self, instance: UserProfile, validated_data: Dict[str, Any]) -> UserProfile:
        """Update admin user (password handled separately)"""
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
    """Serializer for password change functionality"""
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)

    def validate_old_password(self, value: str) -> str:
        """Verify old password is correct"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Incorrect old password')
        return value

    def validate_new_password(self, value: str) -> str:
        """Validate new password against Django's validators"""
        user = self.context['request'].user
        validate_password(value, user=user)
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure new password is different from old"""
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError({
                'new_password': 'New password must be different from old password'
            })
        return attrs


# ==============================
# PROFILE UPDATE SERIALIZER
# ==============================
class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for user profile updates (no password, no role change)"""
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