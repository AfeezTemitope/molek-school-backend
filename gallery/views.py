from django.db import models
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from django.db.models import Prefetch
import logging

from .models import Gallery, GalleryImage
from .serializers import GallerySerializer
from .cache_utils import (
    make_cache_key,
    make_list_cache_key,
    invalidate_gallery_cache,
    get_cached_gallery_stats,
    CACHE_TIMEOUT_GALLERY_LIST,
    CACHE_TIMEOUT_GALLERY_DETAIL,
)
from users.permissions import IsAdminOrSuperAdmin

logger = logging.getLogger(__name__)


class GalleryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing galleries.

    Permissions:
    - Admin/SuperAdmin: Full CRUD access
    - Public (GET only): List galleries without authentication

    Caching:
    - List views cached for 5 minutes
    - Detail views cached for 3 minutes
    - Cache invalidated on create/update/delete
    """
    serializer_class = GallerySerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    renderer_classes = [JSONRenderer]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'title']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Return all active galleries with optimized prefetch.
        Only fetches active images, ordered properly.
        """
        # Optimized prefetch for images
        active_images = Prefetch(
            'images',
            queryset=GalleryImage.objects.filter(is_active=True).order_by('order', '-created_at').only(
                'id', 'gallery_id', 'media', 'caption', 'order', 'created_at', 'is_active'
            )
        )
        
        queryset = Gallery.objects.filter(
            is_active=True
        ).select_related('created_by').prefetch_related(active_images).only(
            'id', 'title', 'description', 'created_at', 'updated_at', 'is_active',
            'created_by__id', 'created_by__username', 'created_by__first_name', 'created_by__last_name'
        )

        return queryset

    def get_permissions(self):
        """
        Allow public read access to list and retrieve.
        Require admin for create, update, delete.
        """
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        elif self.action == 'stats':
            return [IsAuthenticated(), IsAdminOrSuperAdmin()]
        else:
            return [IsAuthenticated(), IsAdminOrSuperAdmin()]

    def list(self, request, *args, **kwargs):
        """Public endpoint for listing galleries with caching"""
        # Generate cache key from query params
        cache_key = make_list_cache_key(request.query_params)
        
        # Try to get from cache
        cached_response = cache.get(cache_key)
        if cached_response:
            logger.debug(f"Gallery list cache HIT: {cache_key}")
            return Response(cached_response)
        
        # Cache miss - fetch from database
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data).data
            
            # Cache paginated response
            cache.set(cache_key, response_data, CACHE_TIMEOUT_GALLERY_LIST)
            logger.debug(f"Gallery list cache SET: {cache_key}")
            
            return Response(response_data)

        serializer = self.get_serializer(queryset, many=True)
        response_data = serializer.data
        
        # Cache response
        cache.set(cache_key, response_data, CACHE_TIMEOUT_GALLERY_LIST)
        logger.debug(f"Gallery list cache SET: {cache_key}")
        
        return Response(response_data)

    def retrieve(self, request, *args, **kwargs):
        """Cached detail view"""
        pk = kwargs.get('pk')
        cache_key = make_cache_key('detail', pk)
        
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Gallery detail cache HIT: {pk}")
            return Response(cached_data)
        
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        cache.set(cache_key, serializer.data, CACHE_TIMEOUT_GALLERY_DETAIL)
        logger.debug(f"Gallery detail cache SET: {pk}")
        
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """
        Create gallery with multiple media files and invalidate cache.

        Expected data:
        - title (optional): Gallery title
        - media: Multiple files
        """
        try:
            # Get title (optional)
            title = request.data.get('title', f'Gallery {Gallery.objects.count() + 1}')

            # Get uploaded media files
            media_files = request.FILES.getlist('media')

            if not media_files:
                return Response(
                    {'error': 'No media files provided. Please upload at least one image or video.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create gallery
            gallery = Gallery.objects.create(
                title=title,
                created_by=request.user,
                is_active=True
            )

            # Create GalleryImage entries for each file
            gallery_images = []
            for index, media_file in enumerate(media_files):
                gallery_images.append(GalleryImage(
                    gallery=gallery,
                    media=media_file,
                    order=index,
                    is_active=True
                ))
            
            # Bulk create for efficiency
            GalleryImage.objects.bulk_create(gallery_images)

            # Invalidate cache
            invalidate_gallery_cache()

            # Serialize and return
            serializer = self.get_serializer(gallery)
            logger.info(
                f"Gallery created: ID={gallery.id}, Title={gallery.title}, Media={len(media_files)}, User={request.user.username}")

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating gallery: {str(e)}")
            return Response(
                {'error': f'Failed to create gallery: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def perform_update(self, serializer):
        """Update gallery and invalidate cache"""
        serializer.save()
        
        # Invalidate cache
        invalidate_gallery_cache(gallery_id=serializer.instance.id)
        
        logger.info(f"Gallery updated: ID={serializer.instance.id}, Title={serializer.instance.title}")

    def perform_destroy(self, instance):
        """Soft delete gallery and invalidate cache"""
        gallery_id = instance.id
        
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        
        # Invalidate cache
        invalidate_gallery_cache(gallery_id=gallery_id)
        
        logger.info(
            f"Gallery soft-deleted: ID={instance.id}, Title={instance.title}, User={self.request.user.username}")

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsAdminOrSuperAdmin])
    def stats(self, request):
        """Get cached gallery statistics (Admin only)"""
        stats = get_cached_gallery_stats()
        return Response(stats)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrSuperAdmin])
    def add_images(self, request, pk=None):
        """
        Add more images to an existing gallery.
        
        Expected data:
        - media: Multiple files
        """
        gallery = self.get_object()
        media_files = request.FILES.getlist('media')
        
        if not media_files:
            return Response(
                {'error': 'No media files provided.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get current max order
        max_order = gallery.images.aggregate(max_order=models.Max('order'))['max_order'] or 0
        
        # Create new images
        new_images = []
        for index, media_file in enumerate(media_files):
            new_images.append(GalleryImage(
                gallery=gallery,
                media=media_file,
                order=max_order + index + 1,
                is_active=True
            ))
        
        GalleryImage.objects.bulk_create(new_images)
        
        # Invalidate cache
        invalidate_gallery_cache(gallery_id=gallery.id)
        
        # Return updated gallery
        serializer = self.get_serializer(gallery)
        return Response(serializer.data)

    @action(detail=True, methods=['delete'], permission_classes=[IsAuthenticated, IsAdminOrSuperAdmin])
    def remove_image(self, request, pk=None):
        """
        Remove an image from a gallery (soft delete).
        
        Expected query param:
        - image_id: ID of the image to remove
        """
        gallery = self.get_object()
        image_id = request.query_params.get('image_id')
        
        if not image_id:
            return Response(
                {'error': 'image_id query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            image = gallery.images.get(id=image_id)
            image.is_active = False
            image.save(update_fields=['is_active'])
            
            # Invalidate cache
            invalidate_gallery_cache(gallery_id=gallery.id)
            
            return Response({'message': 'Image removed successfully.'})
        except GalleryImage.DoesNotExist:
            return Response(
                {'error': 'Image not found in this gallery.'},
                status=status.HTTP_404_NOT_FOUND
            )