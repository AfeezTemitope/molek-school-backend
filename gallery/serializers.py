from rest_framework import serializers
from .models import Gallery, GalleryImage


class GalleryImageSerializer(serializers.ModelSerializer):
    """Serializer for individual gallery images"""
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = GalleryImage
        fields = ['id', 'image_url', 'caption', 'order', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_image_url(self, obj):
        return obj.image_url


class GallerySerializer(serializers.ModelSerializer):
    """Serializer for galleries with nested images"""
    images = GalleryImageSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField()
    media_count = serializers.SerializerMethodField()
    media_urls = serializers.SerializerMethodField()

    class Meta:
        model = Gallery
        fields = [
            'id', 'title', 'description', 'images', 'media_count',
            'media_urls', 'created_by', 'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_created_by(self, obj):
        if not obj.created_by:
            return {'username': 'Admin', 'id': None}
        return {
            'id': obj.created_by.id,
            'username': obj.created_by.username,
            'full_name': obj.created_by.full_name,
        }

    def get_media_count(self, obj):
        return obj.media_count

    def get_media_urls(self, obj):
        return obj.media_urls