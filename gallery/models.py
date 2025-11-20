from django.db import models
from cloudinary.models import CloudinaryField
from users.models import UserProfile


class Gallery(models.Model):
    """Gallery model for organizing media collections"""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True, default='')  # Optional field
    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        related_name='galleries'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Gallery"
        verbose_name_plural = "Galleries"
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.title

    @property
    def media_count(self):
        """Get count of media items in gallery"""
        return self.images.filter(is_active=True).count()

    @property
    def media_urls(self):
        """Get list of all media URLs"""
        return [img.image_url for img in self.images.filter(is_active=True)]


class GalleryImage(models.Model):
    """Individual images/videos in a gallery"""
    gallery = models.ForeignKey(
        Gallery,
        on_delete=models.CASCADE,
        related_name='images'
    )
    media = CloudinaryField(
        'media',
        folder='gallery/media',
        resource_type='auto',
        transformation=[{'fetch_format': 'auto', 'quality': 'auto:eco'}],
    )
    caption = models.CharField(max_length=255, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "Gallery Image"
        verbose_name_plural = "Gallery Images"

    def __str__(self):
        return f"{self.gallery.title} - Image {self.order}"

    @property
    def image_url(self):
        """Get media URL"""
        if self.media:
            try:
                return self.media.url
            except Exception:
                return None
        return None