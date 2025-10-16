from django import forms
from django.contrib import admin
from users.models import UserProfile
from .models import ContentItem
from cloudinary.uploader import upload
from typing import Type, TypeVar, Dict

ContentItemT = TypeVar('ContentItemT', bound=ContentItem)

class ContentItemAdminForm(forms.ModelForm):
    class Meta:
        model = ContentItem
        fields = '__all__'

    def clean(self) -> Dict[str, any]:
        cleaned_data = super().clean()
        content_type: str = cleaned_data.get('content_type')
        media = cleaned_data.get('media')

        if media and content_type:
            image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']
            video_extensions = ['mp4', 'webm', 'mov', 'avi', 'mkv', 'flv', 'wmv']
            file_extension = media.name.split('.')[-1].lower()

            if content_type == 'image' and file_extension not in image_extensions:
                raise forms.ValidationError(
                    f"Invalid image file type. Allowed types: {', '.join(image_extensions)}"
                )
            if content_type == 'video' and file_extension not in video_extensions:
                raise forms.ValidationError(
                    f"Invalid video file type. Allowed types: {', '.join(video_extensions)}"
                )

        return cleaned_data

@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    form = ContentItemAdminForm
    list_display = ['title', 'content_type', 'slug', 'published', 'created_by', 'publish_date', 'is_active']
    list_filter = ['content_type', 'published', 'is_active', 'created_by']
    search_fields = ['title', 'description']
    ordering = ['-publish_date']
    readonly_fields = ['slug', 'publish_date', 'updated_at', 'created_by']
    fieldsets = (
        ('Content Info', {
            'fields': ('title', 'description', 'content_type', 'media')
        }),
        ('Publication', {
            'fields': ('published', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'publish_date', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj: ContentItem, form: Type[ContentItemAdminForm], change: bool) -> None:
        if not change:
            obj.created_by = request.user
        if obj.media and not change:
            transformation = {'fetch_format': 'webp'} if obj.content_type == 'image' else {'fetch_format': 'auto'}
            upload(obj.media.file, resource_type=obj.content_type, folder='content/media', **transformation)
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role != 'superadmin':
            return qs.filter(created_by=request.user)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'created_by':
            kwargs['queryset'] = UserProfile.objects.filter(id=request.user.id)
            kwargs['initial'] = request.user.id
        return super().formfield_for_foreignkey(db_field, request, **kwargs)