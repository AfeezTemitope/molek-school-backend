from django.urls import path
from .views import GalleryListCreateView, GalleryDetailView

urlpatterns = [
    path('', GalleryListCreateView.as_view(), name='gallery-list-create'),
    path('<int:pk>/', GalleryDetailView.as_view(), name='gallery-detail'),
]