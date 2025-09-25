from django.urls import path
from .views import ContentItemListCreateView, ContentItemDetailView, ContentListAPIView

urlpatterns = [
    path('content/', ContentItemListCreateView.as_view(), name='content-list-create'),
    path('content/<int:pk>/', ContentItemDetailView.as_view(), name='content-detail'),
    path('content/public/', ContentListAPIView.as_view(), name='content-public'),
]