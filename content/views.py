from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import ContentItem
from .serializers import ContentItemSerializer
from .permissions import IsTeacherAdminOrSuperAdmin, IsAdminOrSuperAdmin

class ContentItemListCreateView(generics.ListCreateAPIView):
    queryset = ContentItem.objects.filter(is_active=True, published=True)
    serializer_class = ContentItemSerializer
    permission_classes = [IsTeacherAdminOrSuperAdmin]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        queryset = super().get_queryset()
        content_type = self.request.query_params.get('content_type')
        if content_type:
            queryset = queryset.filter(content_type=content_type)
        return queryset

class ContentItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ContentItem.objects.filter(is_active=True)
    serializer_class = ContentItemSerializer
    permission_classes = [IsAdminOrSuperAdmin]

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

@method_decorator(cache_page(60 * 15), name='get')
class ContentListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            queryset = ContentItem.objects.filter(is_active=True, published=True).order_by('-publish_date')
            serializer = ContentItemSerializer(queryset, many=True, context={'request': request})
            return Response({"results": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# NEW: Admin CRUD ViewSet (mirrors User/StudentViewSet)
class ContentItemViewSet(viewsets.ModelViewSet):
    queryset = ContentItem.objects.filter(is_active=True).order_by('-publish_date')
    serializer_class = ContentItemSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['content_type', 'published', 'is_active']  # ?content_type=image
    search_fields = ['title', 'description']  # ?search=math

    def get_permissions(self):
        """
        Teachers/Admins: list/create
        Admins/SuperAdmins: retrieve/update/destroy
        """
        if self.action in ['list', 'create']:
            permission_classes = [IsTeacherAdminOrSuperAdmin]
        elif self.action in ['update', 'partial_update', 'destroy', 'retrieve']:
            permission_classes = [IsAdminOrSuperAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)  # Add updated_by to model if needed

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()  # Soft delete, like your DetailView