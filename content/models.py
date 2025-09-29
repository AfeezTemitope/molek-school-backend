from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from cloudinary.models import CloudinaryField

from users.models import UserProfile

User = get_user_model()


class ContentItem(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = CloudinaryField('image', folder='content/images', blank=True, null=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    published = models.BooleanField(default=True)
    publish_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, related_name='created_content')
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # Only generate slug if it's new or title changed
        if not self.slug or self.pk is None:
            base_slug = slugify(self.title)
            if not base_slug:
                base_slug = 'content-item'

            # Ensure uniqueness
            unique_slug = base_slug
            num = 1
            while ContentItem.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{num}"
                num += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-publish_date']
        verbose_name = "Content Item"
        verbose_name_plural = "Content Items"

    def __str__(self):
        return self.title