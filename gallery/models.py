from django.db import models
from cloudinary.models import CloudinaryField
from users.models import UserProfile


class Gallery(models.Model):
    """
    Gallery model for organizing media collections.
    Optimized with composite indexes for common query patterns.
    """
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True, default='')
    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        related_name='galleries'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Gallery"
        verbose_name_plural = "Galleries"
        indexes = [
            # Single field indexes
            models.Index(fields=['-created_at']),
            
            # Composite indexes for common query patterns
            models.Index(fields=['is_active', '-created_at'], name='gallery_active_list_idx'),
            models.Index(fields=['created_by', 'is_active'], name='gallery_creator_idx'),
            models.Index(fields=['is_active', 'title'], name='gallery_search_idx'),
        ]

    def __str__(self):
        return self.title

    @property
    def media_count(self):
        """Get count of media items in gallery"""
        # Use prefetched data if available
        if hasattr(self, '_prefetched_objects_cache') and 'images' in self._prefetched_objects_cache:
            return sum(1 for img in self.images.all() if img.is_active)
        return self.images.filter(is_active=True).count()

    @property
    def media_urls(self):
        """Get list of all media URLs"""
        # Use prefetched data if available
        if hasattr(self, '_prefetched_objects_cache') and 'images' in self._prefetched_objects_cache:
            return [img.image_url for img in self.images.all() if img.is_active and img.image_url]
        return [img.image_url for img in self.images.filter(is_active=True) if img.image_url]


class GalleryImage(models.Model):
    """
    Individual images/videos in a gallery.
    Optimized with indexes for efficient gallery queries.
    """
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
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "Gallery Image"
        verbose_name_plural = "Gallery Images"
        indexes = [
            # Composite indexes for efficient gallery image queries
            models.Index(fields=['gallery', 'is_active'], name='galleryimg_gallery_active_idx'),
            models.Index(fields=['gallery', 'order'], name='galleryimg_gallery_order_idx'),
            models.Index(fields=['gallery', 'is_active', 'order'], name='galleryimg_list_idx'),
            models.Index(fields=['-created_at']),
        ]

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