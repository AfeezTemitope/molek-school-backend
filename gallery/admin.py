from django.contrib import admin
from .models import Gallery

@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'created_by', 'image_count', 'created_at')
    readonly_fields = ('title', 'created_by', 'image_urls', 'image_count', 'created_at')
    list_filter = ('created_at', 'created_by')
    search_fields = ('title', 'created_by__username')

    def has_add_permission(self, request):
        return False  # Disable adding via admin

    def has_change_permission(self, request, obj=None):
        return False  # Disable editing