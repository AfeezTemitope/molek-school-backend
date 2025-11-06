from django.db import models
from django.conf import settings

class Gallery(models.Model):
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    media_urls = models.JSONField(default=list)
    media_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Gallery {self.id} by {self.created_by.username}"