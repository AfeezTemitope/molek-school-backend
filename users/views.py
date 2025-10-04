import re

from django.utils import timezone
from rest_framework import viewsets, permissions, status
from django.contrib.auth.password_validation import validate_password
from rest_framework.decorators import api_view, permission_classes
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
    permission_classes = (AllowAny,)
    def post(self, request):
        username = request.data.get('username')  # Can be admission or email
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {'error': 'Username and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔍 Try to match as STUDENT: Admission Number + Last Name
        try:
            student = Student.objects.get(admission_number=username, is_active=True)
            user = authenticate(
                request,
                username=student.user.username,  # Use Django user
                password=password  # Should be student.last_name
            )
            if user:
                return self._build_response(user)
        except Student.DoesNotExist:
            pass  # Not a student — move to staff check

        # 🔍 Try as STAFF/TEACHER: Email-based login
        try:
            user_profile = UserProfile.objects.get(email__iexact=username, role__in=['staff', 'teacher', 'superadmin'], is_active=True)
            user = authenticate(request, username=user_profile.username, password=password)
            if user:
                return self._build_response(user)
        except UserProfile.DoesNotExist:
            pass

        # ❌ Both failed
        return Response(
            {'error': 'Invalid login credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    def _build_response(self, user):
        refresh = RefreshToken.for_user(user)
        serializer = UserLoginSerializer(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': serializer.data
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_students_by_class(request):
    """
    Returns list of students in a given class.
    Usage: /api/users/students/by-class/?class=JSS1%20Science
    """
    class_name = request.GET.get('class')
    if not class_name:
        return Response({'error': 'Class name required'}, status=400)

    # Extract base level like "JSS1", "SS2" from full class name
    base_class = class_name.split()[0]  # e.g., "SS2 Science" → "SS2"

    students = Student.objects.filter(
        is_active=True,
        class_name__startswith=base_class
    ).values('admission_number', 'first_name', 'last_name')

    return Response({
        'count': len(students),
        'students': list(students)
    })