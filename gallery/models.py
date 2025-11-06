from django.db import models
from django.conf import settings

class ActiveManager(models.Manager):
    """Reusable: Filters active items (encapsulates soft-delete logic)."""
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)

    def all_active(self):
        """Alias for clarity: Gallery.objects.all_active()."""
        return self.get_queryset()

class Gallery(models.Model):
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    media_urls = models.JSONField(default=list)
    media_count = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)  # 👈 New: Enables soft deletes

    objects = ActiveManager()  # Default manager = active only

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Gallery {self.id} by {self.created_by.username}"

    def soft_delete(self):
        """Reusable method: Set inactive (no hard delete)."""
        self.is_active = False
        self.save(update_fields=['is_active'])