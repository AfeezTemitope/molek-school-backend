from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
import logging

from .models import ContentItem
from .serializers import ContentItemSerializer
from .cache_utils import (
    make_cache_key,
    make_list_cache_key,
    get_or_set_cache,
    invalidate_content_cache,
    get_cached_content_stats,
    CACHE_TIMEOUT_PUBLIC,
    CACHE_TIMEOUT_DETAIL,
)
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
    
    Caching:
    - List views cached for 5 minutes
    - Stats cached for 2 minutes
    - Cache invalidated on create/update/delete
    """
    serializer_class = ContentItemSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    renderer_classes = [JSONRenderer]
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

    def retrieve(self, request, *args, **kwargs):
        """Cached detail view"""
        pk = kwargs.get('pk')
        cache_key = make_cache_key('detail', pk)
        
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Content detail cache HIT: {pk}")
            return Response(cached_data)
        
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        cache.set(cache_key, serializer.data, CACHE_TIMEOUT_DETAIL)
        logger.debug(f"Content detail cache SET: {pk}")
        
        return Response(serializer.data)

    def perform_create(self, serializer):
        """Set created_by to current user and invalidate cache"""
        serializer.save(created_by=self.request.user)
        
        # Invalidate relevant caches
        invalidate_content_cache(
            content_id=serializer.instance.id,
            content_type=serializer.instance.content_type
        )
        
        logger.info(f"Content created: {serializer.instance.title} by {self.request.user.username}")

    def perform_update(self, serializer):
        """Log content updates and invalidate cache"""
        old_content_type = serializer.instance.content_type
        serializer.save()
        
        # Invalidate relevant caches
        invalidate_content_cache(
            content_id=serializer.instance.id,
            content_type=old_content_type
        )
        invalidate_content_cache(content_type=serializer.instance.content_type)
        
        logger.info(f"Content updated: {serializer.instance.title} by {self.request.user.username}")

    def perform_destroy(self, instance):
        """Soft delete content and invalidate cache"""
        content_type = instance.content_type
        content_id = instance.id
        
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        
        # Invalidate relevant caches
        invalidate_content_cache(content_id=content_id, content_type=content_type)
        
        logger.info(f"Content deleted: {instance.title} by {self.request.user.username}")

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def public(self, request):
        """
        Public endpoint for retrieving published content with caching.
        Accessible without authentication.

        Usage:
        - GET /api/content/public/
        - GET /api/content/public/?content_type=news
        - GET /api/content/public/?search=keyword
        """
        # Generate cache key from query params
        cache_key = make_list_cache_key('public', request.query_params)
        
        # Try to get from cache
        cached_response = cache.get(cache_key)
        if cached_response:
            logger.debug(f"Public content cache HIT: {cache_key}")
            return Response(cached_response, status=status.HTTP_200_OK)
        
        # Cache miss - fetch from database
        queryset = self.filter_queryset(
            self.get_queryset().filter(published=True)
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data).data
            
            # Cache paginated response
            cache.set(cache_key, response_data, CACHE_TIMEOUT_PUBLIC)
            logger.debug(f"Public content cache SET: {cache_key}")
            
            return Response(response_data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(queryset, many=True)
        response_data = {'results': serializer.data}
        
        # Cache response
        cache.set(cache_key, response_data, CACHE_TIMEOUT_PUBLIC)
        logger.debug(f"Public content cache SET: {cache_key}")
        
        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsAdminOrSuperAdmin])
    def stats(self, request):
        """Get cached content statistics (Admin only)"""
        stats = get_cached_content_stats()
        return Response(stats)