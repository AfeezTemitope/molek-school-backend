from rest_framework import serializers
from .models import ContentItem

class ContentItemSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    media_url = serializers.SerializerMethodField()

    class Meta:
        model = ContentItem
        fields = [
            'id', 'title', 'description', 'content_type', 'media_url',
            'slug', 'published', 'publish_date', 'created_by', 'updated_at', 'is_active'
        ]
        read_only_fields = ['id', 'slug', 'publish_date', 'created_by', 'updated_at']

    def get_media_url(self, obj):
        if not obj.media:
            return None
        try:
            if obj.content_type == 'video':
                return obj.media.build_url(fetch_format='auto', resource_type='video')
            return obj.media.url  # Use raw URL for images
        except Exception:
            return None  # Fallback to None if URL generation fails

    def get_created_by(self, obj):
        if not obj.created_by:
            return {'full_name': 'Admin', 'id': None, 'role': None, 'username': None}
        try:
            return {
                'id': obj.created_by.id,
                'full_name': obj.created_by.get_full_name() or obj.created_by.username,
                'role': obj.created_by.role,
                'username': obj.created_by.username,
            }
        except Exception:
            return {'full_name': 'Admin', 'id': None, 'role': None, 'username': None}

    def validate_content_type(self, value):
        valid_types = [choice[0] for choice in ContentItem.CONTENT_TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError(f"Content type must be one of: {', '.join(valid_types)}")
        return value