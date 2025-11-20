from django.contrib import admin
from .models import Gallery, GalleryImage


class GalleryImageInline(admin.TabularInline):
    model = GalleryImage
    extra = 1
    fields = ['media', 'caption', 'order', 'is_active']


@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ['title', 'media_count', 'created_by', 'created_at', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at', 'media_count']
    inlines = [GalleryImageInline]

    def save_model(self, request, obj, form, change):
        if not change:  # If creating new
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ['gallery', 'caption', 'order', 'is_active', 'created_at']
    list_filter = ['is_active', 'gallery']
    search_fields = ['caption', 'gallery__title']
    ordering = ['gallery', 'order', '-created_at']