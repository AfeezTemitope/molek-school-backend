from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework_simplejwt.views import TokenObtainPairView
from django.core.cache import cache
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
import logging

from .models import UserProfile
from .serializers import (
    CustomTokenObtainPairSerializer,
    AdminProfileSerializer,
    ChangePasswordSerializer,
    ProfileUpdateSerializer
)
from .permissions import IsAdminOrSuperAdmin

logger = logging.getLogger(__name__)


# ==============================
# AUTHENTICATION VIEWS
# ==============================
class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT authentication for admin users"""
    serializer_class = CustomTokenObtainPairSerializer


# ==============================
# ADMIN MANAGEMENT VIEWSET
# ==============================
class AdminViewSet(viewsets.ModelViewSet):
    """ViewSet for managing admin users"""
    serializer_class = AdminProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    filterset_fields = ['role', 'is_active']
    ordering_fields = ['created_at', 'username', 'email']
    ordering = ['-created_at']

    def get_queryset(self):
        return UserProfile.objects.filter(
            is_active=True,
            role__in=['admin', 'superadmin']
        ).only(
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone_number', 'is_active', 'created_at'
        )

    def perform_create(self, serializer):
        serializer.save()
        logger.info(f"Admin user created: {serializer.instance.username} by {self.request.user.username}")

    def perform_update(self, serializer):
        serializer.save()
        cache_key = f'admin_{serializer.instance.id}'
        cache.delete(cache_key)
        logger.info(f"Admin user updated: {serializer.instance.username} by {self.request.user.username}")

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        logger.info(f"Admin user deactivated: {instance.username} by {self.request.user.username}")

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get admin statistics"""
        queryset = self.get_queryset()
        return Response({
            'total_admins': queryset.filter(role='admin').count(),
            'total_superadmins': queryset.filter(role='superadmin').count(),
            'total': queryset.count()
        })


# ==============================
# PROFILE MANAGEMENT VIEWS
# ==============================
class ProfileView(APIView):
    """Get and update current user's profile"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = AdminProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=False,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            cache_key = f'profile_{request.user.id}'
            cache.delete(cache_key)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            cache_key = f'profile_{request.user.id}'
            cache.delete(cache_key)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """Change current user's password"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            logger.info(f"Password changed for user: {user.username}")
            return Response({
                'detail': 'Password changed successfully'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)