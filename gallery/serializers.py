from rest_framework import serializers
from .models import Gallery

class GallerySerializer(serializers.ModelSerializer):
    class Meta:
        model = Gallery
        fields = ['id', 'title', 'created_at', 'image_urls', 'image_count']
        read_only_fields = ['id', 'created_at', 'image_urls', 'image_count']

class GalleryCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    images = serializers.ListField(
        child=serializers.ImageField(),
        allow_empty=False,
        max_length=20  # Enforce max 20 images
    )