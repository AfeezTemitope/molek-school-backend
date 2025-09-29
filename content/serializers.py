from rest_framework import serializers
from .models import ContentItem

class ContentItemSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ContentItem
        fields = '__all__'

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None

    def get_created_by(self, obj):
        user = obj.created_by
        if not user:
            return None

        # Safely get admission number from student profile
        try:
            admission_number = user.student_profile.admission_number
        except Exception:
            admission_number = None

        return {
            'id': user.id,
            'full_name': user.get_full_name(),
            'role': user.role,
            'username': user.username,
            'admission_number': admission_number,
        }