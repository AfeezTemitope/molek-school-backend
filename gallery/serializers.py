from rest_framework import serializers
from .models import Gallery

class GallerySerializer(serializers.ModelSerializer):
    class Meta:
        model = Gallery
        fields = ['id', 'title', 'created_at', 'media_urls', 'media_count']
        read_only_fields = ['id', 'created_at', 'media_urls', 'media_count']

class GalleryCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    media = serializers.ListField(
        child=serializers.FileField(),
        allow_empty=False,
        max_length=20
    )