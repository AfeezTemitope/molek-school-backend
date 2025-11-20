from rest_framework import serializers
from .models import ContentItem


class ContentItemSerializer(serializers.ModelSerializer):
    """Serializer for ContentItem with optimized fields"""
    created_by = serializers.SerializerMethodField()
    media_url = serializers.SerializerMethodField()
    content_type_display = serializers.CharField(source='get_content_type_display', read_only=True)
    media = serializers.FileField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = ContentItem
        fields = [
            'id', 'title', 'description', 'content_type', 'content_type_display',
            'media', 'media_url', 'slug', 'published', 'publish_date', 'created_by',
            'updated_at', 'is_active'
        ]
        read_only_fields = ['id', 'slug', 'publish_date', 'created_by', 'updated_at', 'media_url']

    def get_media_url(self, obj):
        """Get media URL with proper handling"""
        return obj.media_url

    def get_created_by(self, obj):
        """Get creator info"""
        if not obj.created_by:
            return {'full_name': 'Admin', 'id': None, 'username': None}
        return {
            'id': obj.created_by.id,
            'full_name': obj.created_by.full_name,
            'username': obj.created_by.username,
        }

    def validate_content_type(self, value):
        """Validate content type"""
        valid_types = [choice[0] for choice in ContentItem.CONTENT_TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Content type must be one of: {', '.join(valid_types)}"
            )
        return value

    def validate(self, data):
        """Additional validation"""
        content_type = data.get('content_type')
        media = data.get('media')

        # For images and videos, media is required (unless updating existing)
        if content_type in ['image', 'video'] and not media and not self.instance:
            raise serializers.ValidationError({
                'media': f'Media file is required for {content_type} content type.'
            })

        # News articles don't require media
        if content_type == 'news':
            return data

        return data