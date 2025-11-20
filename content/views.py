from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.renderers import JSONRenderer
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
import logging

from .models import ContentItem
from .serializers import ContentItemSerializer
from users.permissions import IsAdminOrSuperAdmin

logger = logging.getLogger(__name__)


class ContentItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing content items (images, videos, news).

    Permissions:
    - Admin/SuperAdmin: Full CRUD access
    - Public (GET only): Access via /public/ endpoint

    Filtering:
    - ?content_type=news (or image, video)
    - ?published=true
    - ?search=keyword
    """
    serializer_class = ContentItemSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    renderer_classes = [JSONRenderer]  # ✅ ONLY JSON, NO HTML
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['content_type', 'published', 'is_active']
    search_fields = ['title', 'description']
    ordering_fields = ['publish_date', 'title', 'updated_at']
    ordering = ['-publish_date']

    def get_queryset(self):
        """
        Optimized queryset with select_related.
        Only returns active content.
        """
        return ContentItem.objects.filter(is_active=True).select_related('created_by').only(
            'id', 'title', 'description', 'content_type', 'media',
            'slug', 'published', 'publish_date', 'updated_at', 'is_active',
            'created_by__id', 'created_by__first_name', 'created_by__last_name', 'created_by__username'
        )

    def get_permissions(self):
        """
        Public access ONLY for 'public' action.
        Admin/SuperAdmin for everything else.
        """
        if self.action == 'public':
            return [AllowAny()]
        elif self.action == 'stats':
            return [IsAuthenticated(), IsAdminOrSuperAdmin()]
        else:
            return [IsAuthenticated(), IsAdminOrSuperAdmin()]

    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)
        logger.info(f"Content created: {serializer.instance.title} by {self.request.user.username}")

    def perform_update(self, serializer):
        """Log content updates"""
        serializer.save()
        logger.info(f"Content updated: {serializer.instance.title} by {self.request.user.username}")

    def perform_destroy(self, instance):
        """Soft delete content"""
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        logger.info(f"Content deleted: {instance.title} by {self.request.user.username}")

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def public(self, request):
        """
        Public endpoint for retrieving published content.
        Accessible without authentication.

        Usage:
        - GET /api/content/public/
        - GET /api/content/public/?content_type=news
        - GET /api/content/public/?search=keyword
        """
        queryset = self.filter_queryset(
            self.get_queryset().filter(published=True)
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({'results': serializer.data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsAdminOrSuperAdmin])
    def stats(self, request):
        """Get content statistics (Admin only)"""
        queryset = self.get_queryset()
        return Response({
            'total_content': queryset.count(),
            'total_images': queryset.filter(content_type='image').count(),
            'total_videos': queryset.filter(content_type='video').count(),
            'total_news': queryset.filter(content_type='news').count(),
            'published_content': queryset.filter(published=True).count(),
        })