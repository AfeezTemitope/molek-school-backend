"""
Cache utilities for the gallery app.
Provides centralized cache management for galleries and images.
"""
from django.core.cache import cache
from django.conf import settings
import hashlib
import logging

logger = logging.getLogger(__name__)

# Cache timeout constants (in seconds)
CACHE_TIMEOUT_GALLERY_LIST = getattr(settings, 'CACHE_TIMEOUT_GALLERY_LIST', 300)  # 5 minutes for list
CACHE_TIMEOUT_GALLERY_DETAIL = getattr(settings, 'CACHE_TIMEOUT_GALLERY_DETAIL', 180)  # 3 minutes for detail
CACHE_TIMEOUT_GALLERY_STATS = getattr(settings, 'CACHE_TIMEOUT_GALLERY_STATS', 120)  # 2 minutes for stats

# Cache key prefixes
GALLERY_CACHE_PREFIX = 'gallery'


def make_cache_key(prefix: str, *args) -> str:
    """
    Generate a cache key from prefix and arguments.
    
    Args:
        prefix: Cache key prefix
        *args: Additional arguments to include in key
        
    Returns:
        Cache key string
    """
    key_parts = [GALLERY_CACHE_PREFIX, prefix] + [str(arg) for arg in args if arg is not None]
    key = ':'.join(key_parts)
    
    # Hash if key is too long
    if len(key) > 200:
        key = f"{GALLERY_CACHE_PREFIX}:{prefix}:{hashlib.md5(key.encode()).hexdigest()}"
    
    return key


def make_list_cache_key(query_params: dict) -> str:
    """
    Generate cache key for list views based on query parameters.
    
    Args:
        query_params: Request query parameters
        
    Returns:
        Cache key string
    """
    # Sort and filter relevant params
    relevant_params = ['search', 'ordering', 'page', 'page_size']
    params_str = '&'.join(
        f"{k}={query_params.get(k, '')}"
        for k in sorted(relevant_params)
        if query_params.get(k)
    )
    
    return make_cache_key('list', params_str or 'all')


def get_or_set_cache(key: str, callback, timeout: int = None):
    """
    Get value from cache or set it using callback.
    
    Args:
        key: Cache key
        callback: Function to call if cache miss
        timeout: Cache timeout in seconds
        
    Returns:
        Cached or computed value
    """
    value = cache.get(key)
    
    if value is None:
        value = callback()
        if timeout is None:
            timeout = CACHE_TIMEOUT_GALLERY_LIST
        cache.set(key, value, timeout)
        logger.debug(f"Cache MISS: {key}")
    else:
        logger.debug(f"Cache HIT: {key}")
    
    return value


def invalidate_gallery_cache(gallery_id: int = None):
    """
    Invalidate gallery-related cache entries.
    
    Args:
        gallery_id: Specific gallery ID to invalidate
    """
    keys_to_delete = []
    
    # Always invalidate list cache
    keys_to_delete.append(make_cache_key('list', 'all'))
    keys_to_delete.append(make_cache_key('stats'))
    
    # Invalidate specific gallery
    if gallery_id:
        keys_to_delete.append(make_cache_key('detail', gallery_id))
    
    for key in keys_to_delete:
        cache.delete(key)
        logger.debug(f"Cache invalidated: {key}")


def invalidate_all_gallery_cache():
    """
    Invalidate all gallery caches.
    Used when bulk operations occur.
    """
    # Get all keys with gallery prefix and delete them
    # Note: This is a simple approach; in production with Redis,
    # you would use pattern matching
    patterns = ['list', 'detail', 'stats']
    for pattern in patterns:
        cache.delete(make_cache_key(pattern))
    
    logger.info("All gallery caches invalidated")


def get_cached_gallery_stats():
    """
    Get cached gallery statistics.
    
    Returns:
        Dictionary with gallery statistics
    """
    from .models import Gallery, GalleryImage
    
    def compute_stats():
        galleries = Gallery.objects.filter(is_active=True)
        images = GalleryImage.objects.filter(is_active=True, gallery__is_active=True)
        
        return {
            'total_galleries': galleries.count(),
            'total_images': images.count(),
            'galleries_with_images': galleries.filter(images__is_active=True).distinct().count(),
        }
    
    return get_or_set_cache(
        make_cache_key('stats'),
        compute_stats,
        CACHE_TIMEOUT_GALLERY_STATS
    )


def get_cached_gallery_detail(gallery_id: int):
    """
    Get cached gallery detail.
    
    Args:
        gallery_id: Gallery ID
        
    Returns:
        Gallery data dict or None
    """
    from .models import Gallery
    from .serializers import GallerySerializer
    
    cache_key = make_cache_key('detail', gallery_id)
    
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        gallery = Gallery.objects.filter(
            id=gallery_id,
            is_active=True
        ).select_related('created_by').prefetch_related('images').first()
        
        if gallery:
            serializer = GallerySerializer(gallery)
            data = serializer.data
            cache.set(cache_key, data, CACHE_TIMEOUT_GALLERY_DETAIL)
            return data
    except Exception as e:
        logger.error(f"Error fetching gallery {gallery_id}: {e}")
    
    return None