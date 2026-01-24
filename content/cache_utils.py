"""
Cache utilities for the content app.
Provides centralized cache management for content items.
"""
from django.core.cache import cache
from django.conf import settings
import hashlib
import logging

logger = logging.getLogger(__name__)

# Cache timeout constants (in seconds)
CACHE_TIMEOUT_PUBLIC = getattr(settings, 'CACHE_TIMEOUT_PUBLIC', 300)  # 5 minutes for public content
CACHE_TIMEOUT_STATS = getattr(settings, 'CACHE_TIMEOUT_STATS', 120)  # 2 minutes for stats
CACHE_TIMEOUT_DETAIL = getattr(settings, 'CACHE_TIMEOUT_DETAIL', 180)  # 3 minutes for detail views

# Cache key prefixes
CONTENT_CACHE_PREFIX = 'content'


def make_cache_key(prefix: str, *args) -> str:
    """
    Generate a cache key from prefix and arguments.
    
    Args:
        prefix: Cache key prefix
        *args: Additional arguments to include in key
        
    Returns:
        Cache key string
    """
    key_parts = [CONTENT_CACHE_PREFIX, prefix] + [str(arg) for arg in args if arg is not None]
    key = ':'.join(key_parts)
    
    # Hash if key is too long
    if len(key) > 200:
        key = f"{CONTENT_CACHE_PREFIX}:{prefix}:{hashlib.md5(key.encode()).hexdigest()}"
    
    return key


def make_list_cache_key(prefix: str, query_params: dict) -> str:
    """
    Generate cache key for list views based on query parameters.
    
    Args:
        prefix: Cache key prefix
        query_params: Request query parameters
        
    Returns:
        Cache key string
    """
    # Sort and filter relevant params
    relevant_params = ['content_type', 'published', 'is_active', 'search', 'ordering', 'page', 'page_size']
    params_str = '&'.join(
        f"{k}={query_params.get(k, '')}"
        for k in sorted(relevant_params)
        if query_params.get(k)
    )
    
    return make_cache_key(prefix, 'list', params_str or 'all')


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
            timeout = CACHE_TIMEOUT_PUBLIC
        cache.set(key, value, timeout)
        logger.debug(f"Cache MISS: {key}")
    else:
        logger.debug(f"Cache HIT: {key}")
    
    return value


def invalidate_content_cache(content_id: int = None, content_type: str = None):
    """
    Invalidate content-related cache entries.
    
    Args:
        content_id: Specific content ID to invalidate
        content_type: Content type to invalidate (image, video, news)
    """
    keys_to_delete = []
    
    # Always invalidate list caches
    keys_to_delete.extend([
        make_cache_key('public', 'list', 'all'),
        make_cache_key('stats'),
    ])
    
    # Invalidate specific content
    if content_id:
        keys_to_delete.append(make_cache_key('detail', content_id))
    
    # Invalidate by content type
    if content_type:
        keys_to_delete.append(make_cache_key('public', 'list', f'content_type={content_type}'))
    
    for key in keys_to_delete:
        cache.delete(key)
        logger.debug(f"Cache invalidated: {key}")


def get_cached_content_stats():
    """
    Get cached content statistics.
    
    Returns:
        Dictionary with content statistics
    """
    from .models import ContentItem
    
    def compute_stats():
        queryset = ContentItem.objects.filter(is_active=True)
        return {
            'total_content': queryset.count(),
            'total_images': queryset.filter(content_type='image').count(),
            'total_videos': queryset.filter(content_type='video').count(),
            'total_news': queryset.filter(content_type='news').count(),
            'published_content': queryset.filter(published=True).count(),
        }
    
    return get_or_set_cache(
        make_cache_key('stats'),
        compute_stats,
        CACHE_TIMEOUT_STATS
    )


def get_cached_public_content(content_type: str = None, search: str = None):
    """
    Get cached public content list.
    
    Args:
        content_type: Filter by content type
        search: Search term
        
    Returns:
        QuerySet of content items
    """
    from .models import ContentItem
    
    # Build cache key
    params = {}
    if content_type:
        params['content_type'] = content_type
    if search:
        params['search'] = search
    
    cache_key = make_list_cache_key('public', params)
    
    def get_content():
        queryset = ContentItem.objects.filter(
            is_active=True,
            published=True
        ).select_related('created_by').only(
            'id', 'title', 'description', 'content_type', 'media',
            'slug', 'published', 'publish_date', 'updated_at', 'is_active',
            'created_by__id', 'created_by__first_name', 'created_by__last_name', 'created_by__username'
        )
        
        if content_type:
            queryset = queryset.filter(content_type=content_type)
        
        if search:
            queryset = queryset.filter(title__icontains=search) | queryset.filter(description__icontains=search)
        
        return list(queryset.values(
            'id', 'title', 'description', 'content_type', 'slug',
            'published', 'publish_date', 'updated_at'
        ))
    
    return get_or_set_cache(cache_key, get_content, CACHE_TIMEOUT_PUBLIC)