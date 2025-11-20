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

from .models import Gallery, GalleryImage
from .serializers import GallerySerializer
from users.permissions import IsAdminOrSuperAdmin

logger = logging.getLogger(__name__)


class GalleryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing galleries.

    Permissions:
    - Admin/SuperAdmin: Full CRUD access
    - Public (GET only): List galleries without authentication
    """
    serializer_class = GallerySerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    renderer_classes = [JSONRenderer]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'title']
    ordering = ['-created_at']

    def get_queryset(self):
        """Return all active galleries with images"""
        queryset = Gallery.objects.filter(
            is_active=True
        ).select_related('created_by').prefetch_related('images')

        logger.info(f"Gallery queryset count: {queryset.count()}")
        return queryset

    def get_permissions(self):
        """
        Allow public read access to list and retrieve.
        Require admin for create, update, delete.
        """
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        else:
            return [IsAuthenticated(), IsAdminOrSuperAdmin()]

    # ✅ REMOVED CACHE - Was causing stale data
    def list(self, request, *args, **kwargs):
        """Public endpoint for listing galleries (NO CACHE)"""
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            logger.info(f"Returning {len(serializer.data)} galleries (paginated)")
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        logger.info(f"Returning {len(serializer.data)} galleries (non-paginated)")
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """
        Create gallery with multiple media files

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
                is_active=True  # ✅ Explicitly set to True
            )

            # Create GalleryImage entries for each file
            for index, media_file in enumerate(media_files):
                GalleryImage.objects.create(
                    gallery=gallery,
                    media=media_file,
                    order=index,
                    is_active=True  # ✅ Explicitly set to True
                )

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

    def perform_destroy(self, instance):
        """Soft delete gallery"""
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        logger.info(
            f"Gallery soft-deleted: ID={instance.id}, Title={instance.title}, User={self.request.user.username}")