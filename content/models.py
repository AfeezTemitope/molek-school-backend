from django.db import models
from django.utils.text import slugify
from cloudinary.models import CloudinaryField
from users.models import UserProfile

class ContentItem(models.Model):
    CONTENT_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPE_CHOICES)
    media = CloudinaryField(
        'media',
        folder='content/media',
        blank=True,
        null=True,
        resource_type='auto',
        transformation=[{'fetch_format': 'auto'}],  # Auto-convert to WebP for images, WebM for videos
    )
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    published = models.BooleanField(default=True)
    publish_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, related_name='created_content')
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-publish_date']
        verbose_name = "Content Item"
        verbose_name_plural = "Content Items"
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['published', 'is_active']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug or self.pk is None:
            base_slug = slugify(self.title)
            unique_slug = base_slug or 'content-item'
            num = 1
            while ContentItem.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{num}"
                num += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.content_type})"