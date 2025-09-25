from rest_framework import serializers
from .models import ContentItem
from users.models import UserProfile

class ContentItemSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    image_url = serializers.URLField(required=False, allow_blank=True)

    class Meta:
        model = ContentItem
        fields = [
            'id', 'title', 'description', 'image_url', 'slug',
            'published', 'publish_date', 'created_by', 'created_by_name',
            'updated_at', 'is_active'
        ]
        read_only_fields = ['id', 'publish_date', 'updated_at']

    def get_created_by(self, obj):
        if obj.created_by:
            return {
                'id': obj.created_by.id,
                'full_name': obj.created_by.full_name,
                'role': obj.created_by.role,
                'admission_number': obj.created_by.admission_number,
                'passport_url': obj.created_by.passport_url,
            }
        return None

    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else "Unknown"

    def validate_image_url(self, value):
        # Optional: Validate URL format or Cloudinary domain
        if value and not value.startswith(('https://res.cloudinary.com/', 'http://')):
            raise serializers.ValidationError("Image URL must be valid.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['created_by'] = user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user = self.context['request'].user
        validated_data['created_by'] = user  # Keep original creator
        return super().update(instance, validated_data)