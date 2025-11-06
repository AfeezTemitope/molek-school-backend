import cloudinary.uploader
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Gallery
from .serializers import GallerySerializer, GalleryCreateSerializer
from .permissions import IsAdminOrSuperAdmin
import mimetypes  # For type detection


class MediaUploadMixin:
    """Reusable mixin for Cloudinary uploads (images/videos)."""

    @staticmethod
    def upload_media(file_obj, folder="galleries"):
        # Auto-detect resource_type
        mime_type, _ = mimetypes.guess_type(file_obj.name)
        resource_type = "auto"  # Cloudinary detects image/video
        if mime_type and "video/" in mime_type:
            resource_type = "video"
        elif mime_type and "image/" in mime_type:
            resource_type = "image"

        upload_result = cloudinary.uploader.upload(
            file_obj,
            folder=folder,
            resource_type=resource_type
        )
        return upload_result['secure_url']


class GalleryListCreateView(APIView, MediaUploadMixin):  # Inherit reusable upload logic
    permission_classes = [IsAdminOrSuperAdmin]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get(self, request):
        """List all galleries (with media URLs preloaded) - Public"""
        galleries = Gallery.objects.all()
        serializer = GallerySerializer(galleries, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Upload 1–20 media files (images/videos) and create a gallery - Authenticated admins"""
        serializer = GalleryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        media_files = serializer.validated_data['media']
        title = serializer.validated_data.get('title', '')

        uploaded_urls = []
        try:
            # Upload all media to Cloudinary (reusable via mixin)
            for media_file in media_files:
                url = self.upload_media(media_file)
                uploaded_urls.append(url)
        except Exception as e:
            return Response(
                {'error': 'Upload failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Save denormalized data in ONE DB write
        gallery = Gallery.objects.create(
            title=title,
            created_by=request.user,
            media_urls=uploaded_urls,
            media_count=len(uploaded_urls)
        )

        output_serializer = GallerySerializer(gallery)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class GalleryDetailView(APIView, MediaUploadMixin):
    permission_classes = [IsAdminOrSuperAdmin]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get(self, request, pk):
        """Get a single gallery with all media URLs - Public"""
        try:
            gallery = Gallery.objects.get(pk=pk)
        except Gallery.DoesNotExist:
            return Response({'error': 'Gallery not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = GallerySerializer(gallery)
        return Response(serializer.data)

    def delete(self, request, pk):
        """Delete gallery (media remains in Cloudinary — optional cleanup) - Authenticated admins"""
        try:
            gallery = Gallery.objects.get(pk=pk)
            gallery.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Gallery.DoesNotExist:
            return Response({'error': 'Gallery not found'}, status=status.HTTP_404_NOT_FOUND)