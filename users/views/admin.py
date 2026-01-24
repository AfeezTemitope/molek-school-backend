"""
MOLEK School - Admin Management Views
ViewSets and APIViews for admin user management and profile operations
"""
import logging
from django.core.cache import cache
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from ..models import UserProfile
from ..serializers import (
    AdminProfileSerializer,
    ChangePasswordSerializer,
    ProfileUpdateSerializer,
)
from ..permissions import IsAdminOrSuperAdmin
from ..cache_utils import (
    make_cache_key,
    get_or_set_cache,
    invalidate_cache,
    CACHE_TIMEOUT_STUDENT,
)

logger = logging.getLogger(__name__)


class AdminViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing admin users.
    
    Provides CRUD operations for admin/superadmin users with:
    - Search by username, email, first/last name
    - Filter by role, is_active
    - Ordering by created_at, username, email
    - Caching for list operations
    """
    serializer_class = AdminProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    filterset_fields = ['role', 'is_active']
    ordering_fields = ['created_at', 'username', 'email']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Return active admin/superadmin users with optimized field selection.
        """
        return UserProfile.objects.filter(
            is_active=True,
            role__in=['admin', 'superadmin']
        ).only(
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone_number', 'is_active', 'created_at'
        )
    
    def perform_create(self, serializer):
        """Log admin creation"""
        serializer.save()
        logger.info(f"Admin user created: {serializer.instance.username} by {self.request.user.username}")
    
    def perform_update(self, serializer):
        """Update and invalidate cache"""
        serializer.save()
        cache_key = make_cache_key('admin', serializer.instance.id)
        invalidate_cache(cache_key)
        logger.info(f"Admin user updated: {serializer.instance.username} by {self.request.user.username}")
    
    def perform_destroy(self, instance):
        """Soft delete (deactivate) admin user"""
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        cache_key = make_cache_key('admin', instance.id)
        invalidate_cache(cache_key)
        logger.info(f"Admin user deactivated: {instance.username} by {self.request.user.username}")
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get admin statistics.
        
        Returns:
            - total_admins: Count of admin role users
            - total_superadmins: Count of superadmin role users
            - total: Total count
        """
        cache_key = make_cache_key('admin_stats')
        
        def get_stats():
            queryset = self.get_queryset()
            return {
                'total_admins': queryset.filter(role='admin').count(),
                'total_superadmins': queryset.filter(role='superadmin').count(),
                'total': queryset.count()
            }
        
        stats = get_or_set_cache(cache_key, get_stats, timeout=CACHE_TIMEOUT_STUDENT)
        return Response(stats)


class ProfileView(APIView):
    """
    Get and update current user's profile.
    
    GET: Returns current user's profile data
    PUT: Full update of profile
    PATCH: Partial update of profile
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current user's profile"""
        cache_key = make_cache_key('profile', request.user.id)
        
        def get_profile():
            serializer = AdminProfileSerializer(request.user)
            return serializer.data
        
        data = get_or_set_cache(cache_key, get_profile, timeout=CACHE_TIMEOUT_STUDENT)
        return Response(data, status=status.HTTP_200_OK)
    
    def put(self, request):
        """Full update of profile"""
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=False,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            cache_key = make_cache_key('profile', request.user.id)
            invalidate_cache(cache_key)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request):
        """Partial update of profile"""
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            cache_key = make_cache_key('profile', request.user.id)
            invalidate_cache(cache_key)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """
    Change current user's password.
    
    Requires:
        - old_password: Current password
        - new_password: New password
    """
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
            return Response(
                {'detail': 'Password changed successfully'},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)