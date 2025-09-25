from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify

User = get_user_model()

class ContentItem(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()  # HTML content
    image_url = models.URLField(blank=True, null=True)  # From Cloudinary
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    published = models.BooleanField(default=True)
    publish_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_content')
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)  # Soft delete

    class Meta:
        ordering = ['-publish_date']
        verbose_name = "Content Item"
        verbose_name_plural = "Content Items"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title