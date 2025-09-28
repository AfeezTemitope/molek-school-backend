from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from django.contrib.auth.password_validation import validate_password
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model, authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from django.core.exceptions import ValidationError
from .models import Student, UserProfile
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import UserCreateSerializer, UserLoginSerializer, StudentSerializer, CustomTokenObtainPairSerializer

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
        # Automatically assign the logged-in user as creator
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
    permission_classes = []

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