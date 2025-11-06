import cloudinary.uploader
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Gallery
from .serializers import GallerySerializer, GalleryCreateSerializer
from .permissions import IsAdminOrSuperAdmin
import mimetypes

class MediaCarouselMixin:
    @staticmethod
    def infer_media_type(url):
        """Infer type from URL (no DB hit; reusable)."""
        if url.endswith(('.mp4', '.mov', '.avi')):
            return 'video'
        return 'image'

class MediaUploadMixin:
    """Reusable mixin for Cloudinary uploads (images/videos)."""
    @staticmethod
    def upload_media(file_obj, folder="galleries"):
        mime_type, _ = mimetypes.guess_type(file_obj.name)
        resource_type = "auto"
        if mime_type and "video/" in mime_type:
            resource_type = "video"
        elif mime_type and "image/" in mime_type:
            resource_type = "image"
        upload_result = cloudinary.uploader.upload(
            file_obj, folder=folder, resource_type=resource_type
        )
        return upload_result['secure_url']

class GalleryListCreateView(APIView, MediaUploadMixin, MediaCarouselMixin):
    permission_classes = [IsAdminOrSuperAdmin]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get(self, request):
        """List all galleries - Public, optimized query (leverages ActiveManager)."""
        # Gallery.objects.all() = active only via manager; no explicit filter
        galleries = Gallery.objects.select_related('created_by').only(
            'id', 'title', 'created_at', 'media_urls', 'media_count', 'created_by__username', 'is_active'
        )  # ONE query: Joins + limits (defers extras like created_by__email)
        serializer = GallerySerializer(galleries, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Upload 1–20 media files and create a gallery - Authenticated admins."""
        serializer = GalleryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        media_files = serializer.validated_data['media']
        title = serializer.validated_data.get('title', '')

        uploaded_urls = []
        try:
            for media_file in media_files:
                url = self.upload_media(media_file)
                uploaded_urls.append(url)
        except Exception as e:
            return Response({'error': 'Upload failed', 'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # ONE DB write: Atomic create
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
        """Get a single gallery - Public (active only via manager)."""
        try:
            gallery = Gallery.objects.get(pk=pk)  # Manager auto-filters active
        except Gallery.DoesNotExist:
            return Response({'error': 'Gallery not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = GallerySerializer(gallery)
        return Response(serializer.data)

    def delete(self, request, pk):
        """Soft delete gallery - Authenticated admins (reusable via model method)."""
        try:
            gallery = Gallery.objects.get(pk=pk)
            gallery.soft_delete()  # 👈 Calls model method: Set inactive (no media purge)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Gallery.DoesNotExist:
            return Response({'error': 'Gallery not found'}, status=status.HTTP_404_NOT_FOUND)