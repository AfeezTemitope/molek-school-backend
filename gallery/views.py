import cloudinary.uploader
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Gallery
from .serializers import GallerySerializer, GalleryCreateSerializer
from .permissions import IsAdminOrSuperAdmin


class GalleryListCreateView(APIView):
    permission_classes = [IsAdminOrSuperAdmin]  # Default for non-GET methods

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]  # Public access for listing galleries
        return super().get_permissions()  # Use custom permission for POST

    def get(self, request):
        """List all galleries (with image URLs preloaded) - Public"""
        galleries = Gallery.objects.all()
        serializer = GallerySerializer(galleries, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Upload 1–20 images and create a gallery - Authenticated teachers/admins/superadmins"""
        serializer = GalleryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        images = serializer.validated_data['images']
        title = serializer.validated_data.get('title', '')

        uploaded_urls = []
        try:
            # Upload all images to Cloudinary
            for image in images:
                upload_result = cloudinary.uploader.upload(
                    image,
                    folder="galleries",  # Optional: organize in Cloudinary
                    resource_type="image"
                )
                uploaded_urls.append(upload_result['secure_url'])
        except Exception as e:
            return Response(
                {'error': 'Upload failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Save denormalized data in ONE DB write
        gallery = Gallery.objects.create(
            title=title,
            created_by=request.user,
            image_urls=uploaded_urls,
            image_count=len(uploaded_urls)
        )

        output_serializer = GallerySerializer(gallery)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class GalleryDetailView(APIView):
    permission_classes = [IsAdminOrSuperAdmin]  # Default for non-GET methods

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]  # Public access for retrieving a gallery
        return super().get_permissions()  # Use custom permission for DELETE

    def get(self, request, pk):
        """Get a single gallery with all image URLs - Public"""
        try:
            gallery = Gallery.objects.get(pk=pk)
        except Gallery.DoesNotExist:
            return Response({'error': 'Gallery not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = GallerySerializer(gallery)
        return Response(serializer.data)

    def delete(self, request, pk):
        """Delete gallery (images remain in Cloudinary — optional cleanup) - Authenticated teachers/admins/superadmins"""
        try:
            gallery = Gallery.objects.get(pk=pk)
            gallery.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Gallery.DoesNotExist:
            return Response({'error': 'Gallery not found'}, status=status.HTTP_404_NOT_FOUND)