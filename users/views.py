from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import api_view, permission_classes
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.core.cache import cache
from django.contrib.auth import authenticate
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import UserProfile, Student
from .serializers import UserProfileSerializer, StudentSerializer, UserLoginSerializer, ChangePasswordSerializer
from .permissions import IsSuperAdmin

class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user
        token = serializer.validated_data
        user_data = UserProfileSerializer(user, context={'request': request}).data
        return Response({
            'access': str(token['access']),
            'refresh': str(token['refresh']),
            'user': user_data
        }, status=status.HTTP_200_OK)

class UserViewSet(ModelViewSet):
    queryset = UserProfile.objects.filter(is_active=True)
    serializer_class = UserProfileSerializer
    permission_classes = [IsSuperAdmin]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class StudentViewSet(ModelViewSet):
    queryset = Student.objects.filter(is_active=True).select_related('user')
    serializer_class = StudentSerializer
    permission_classes = [IsAdminUser]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class LoginStudentView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = UserLoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response({"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAdminUser])
@cache_page(60 * 5)
def get_students_by_class(request):
    class_level = request.query_params.get('class_level')
    stream = request.query_params.get('stream')
    section = request.query_params.get('section')
    cache_key = f'students_{class_level}_{stream}_{section}'
    cached_data = cache.get(cache_key)
    if cached_data:
        return Response(cached_data, status=status.HTTP_200_OK)

    queryset = Student.objects.filter(is_active=True).select_related('user')
    if class_level:
        queryset = queryset.filter(class_level=class_level)
    if stream:
        queryset = queryset.filter(stream=stream)
    if section:
        queryset = queryset.filter(section=section)

    serializer = StudentSerializer(queryset, many=True, context={'request': request})
    cache.set(cache_key, serializer.data, timeout=60 * 5)
    return Response(serializer.data, status=status.HTTP_200_OK)

class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = UserProfileSerializer(user, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            cache_key = f'user_{user.id}'
            cache.delete(cache_key)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(cache_page(60 * 15), name='get')
class ExportStudentDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        try:
            student = Student.objects.get(user=user, is_active=True)
            serializer = StudentSerializer(student, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Student.DoesNotExist:
            return Response({"detail": "Student profile not found"}, status=status.HTTP_404_NOT_FOUND)

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"detail": "Password changed successfully"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)