from django.contrib import admin
from .models import ContentItem

@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'published', 'created_by', 'publish_date']
    readonly_fields = ['slug', 'created_by', 'updated_at', 'publish_date']
    search_fields = ['title', 'description']
    list_filter = ['published', 'created_by__role', 'publish_date']

    fields = ['title', 'description', 'image', 'published', 'is_active']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role in ['superadmin', 'admin', 'teacher']:
            return qs.filter(is_active=True)
        return qs.none()

    def has_add_permission(self, request):
        return request.user.role in ['superadmin', 'admin', 'teacher']

    def has_change_permission(self, request, obj=None):
        return request.user.role in ['superadmin', 'admin', 'teacher']

    def has_delete_permission(self, request, obj=None):
        return request.user.role in ['superadmin', 'admin']

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)