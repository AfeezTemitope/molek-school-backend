from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework import status
from .models import ContentItem
from .serializers import ContentItemSerializer
from .permissions import IsAdminOrSuperAdmin

class ContentItemListCreateView(generics.ListCreateAPIView):
    queryset = ContentItem.objects.filter(is_active=True, published=True).order_by('-publish_date')
    serializer_class = ContentItemSerializer
    permission_classes = [IsAdminOrSuperAdmin]

    def get_queryset(self):
        # Publicly accessible: only published & active
        if self.request.method == 'GET':
            return ContentItem.objects.filter(is_active=True, published=True).order_by('-publish_date')
        # For POST (create), only staff can do it — handled by permission class
        return super().get_queryset()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class ContentItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ContentItem.objects.all()
    serializer_class = ContentItemSerializer
    permission_classes = [IsAdminOrSuperAdmin]

    def get_object(self):
        # Allow public viewing of published items
        if self.request.method == 'GET' and self.kwargs.get('pk'):
            pk = self.kwargs['pk']
            try:
                obj = ContentItem.objects.get(pk=pk, is_active=True, published=True)
                return obj
            except ContentItem.DoesNotExist:
                pass
        # For PUT/PATCH/DELETE — require staff
        return super().get_object()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False  # Soft delete
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

class ContentListAPIView(generics.ListAPIView):
    """
    Public API: List all published content items.
    """
    queryset = ContentItem.objects.filter(is_active=True, published=True).order_by('-publish_date')
    serializer_class = ContentItemSerializer
    permission_classes = []