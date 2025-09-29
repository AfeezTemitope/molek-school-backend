import re

from django.utils import timezone
from rest_framework import viewsets, permissions, status
from django.contrib.auth.password_validation import validate_password
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth import get_user_model, authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from django.core.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Student, UserProfile
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import UserCreateSerializer, UserLoginSerializer, StudentSerializer, CustomTokenObtainPairSerializer
import json
from django.http import HttpResponse


User = get_user_model()


# =============================
# 1. JWT Login View
# =============================
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

# =============================
# 2. User Management ViewSet (Super Admin Only)
# =============================
class UserViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            # Only superadmin can create/delete users
            return [permissions.IsAuthenticated(), IsSuperAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        # Superadmin sees all, others see only themselves (future)
        user = self.request.user
        if user.role == 'superadmin':
            return UserProfile.objects.all()
        return UserProfile.objects.filter(id=user.id)

class IsSuperAdmin(permissions.BasePermission):
    """Custom permission: only superadmin can create/delete users"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'superadmin'

# =============================
# 3. Student ViewSet (Admin/Teacher Only)
# =============================
class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.filter(is_active=True)
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'superadmin':
            return Student.objects.filter(is_active=True)
        else:
            # Admin/Teacher can only see students they created
            return Student.objects.filter(created_by=user, is_active=True)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class ChangePasswordView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not old_password or not new_password:
            return Response(
                {'error': 'Both old and new password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user

        # Check if old password is correct
        if not user.check_password(old_password):
            return Response(
                {'error': 'Current password is incorrect'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Validate new password strength
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return Response({'error': e.messages}, status=status.HTTP_400_BAD_REQUEST)

        # Set new password
        user.set_password(new_password)
        user.save()

        return Response(
            {'message': 'Password updated successfully'},
            status=status.HTTP_200_OK
        )

class LoginByAdmissionView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        admission_number = request.data.get('admission_number')
        password = request.data.get('password')

        if not admission_number or not password:
            return Response(
                {'error': 'Admission number and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            student = Student.objects.get(admission_number=admission_number, is_active=True)
        except Student.DoesNotExist:
            return Response(
                {'error': 'Invalid admission number or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = authenticate(username=student.user.username, password=password)

        if user is None:
            return Response(
                {'error': 'Invalid admission number or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # ✅ Use UserLoginSerializer to serialize the user object
        serializer = UserLoginSerializer(user)

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': serializer.data  # ✅ Now returns clean, structured user data
        }, status=status.HTTP_200_OK)

class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user = request.user
        try:
            student = user.student_profile
        except Student.DoesNotExist:
            return Response(
                {"error": "No linked student profile"},
                status=status.HTTP_404_NOT_FOUND
            )

        data = request.data.copy()
        passport_url = request.FILES.get('passport_url')

        # Update fields if provided
        if 'parent_email' in data:
            student.parent_email = data['parent_email']
        if 'parent_phone' in data:
            student.parent_phone = data['parent_phone']


        if student.parent_phone:
            if not re.match(r'^\+234\d{10}$', student.parent_phone):
                return Response(
                    {"error": "Phone must be in +23480... format"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Save passport URL via Cloudinary
        if passport_url:
            # This will upload to Cloudinary automatically thanks to CloudinaryField
            student.passport_url = passport_url

        student.save()

        return Response({
            "message": "Profile updated successfully",
            "user": {
                "full_name": f"{student.first_name} {student.last_name}",
                "admission_number": student.admission_number,
                "parent_email": student.parent_email,
                "parent_phone": student.parent_phone,
                "passport_url": student.passport_url.url if student.passport_url else None,
            }
        }, status=status.HTTP_200_OK)


class ExportStudentDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            student = request.user.student_profile
        except Student.DoesNotExist:
            return Response(
                {"error": "No student profile found"},
                status=status.HTTP_404_NOT_FOUND
            )

        data = {
            "student": {
                "first_name": student.first_name,
                "last_name": student.last_name,
                "admission_number": student.admission_number,
                "class_name": student.class_name,
                "gender": student.gender,
                "age": student.age,
                "address": student.address,
                "parent_phone": student.parent_phone,
                "parent_email": student.parent_email,
                "created_at": student.created_at.isoformat(),
            },
            "generated_on": timezone.now().isoformat(),
            "school": "Molek Schools"
        }

        json_str = json.dumps(data, indent=2)
        response = HttpResponse(json_str, content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="student_{student.admission_number}_data.json"'
        return response