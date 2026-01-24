"""
MOLEK School - Cache Utilities
Centralized cache management with proper key generation and invalidation
"""
import hashlib
from functools import wraps
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Cache timeout constants (imported from settings or use defaults)
CACHE_TIMEOUT_STATIC = getattr(settings, 'CACHE_TIMEOUT_STATIC', 3600)
CACHE_TIMEOUT_ACADEMIC = getattr(settings, 'CACHE_TIMEOUT_ACADEMIC', 1800)
CACHE_TIMEOUT_STUDENT = getattr(settings, 'CACHE_TIMEOUT_STUDENT', 300)
CACHE_TIMEOUT_SCORE = getattr(settings, 'CACHE_TIMEOUT_SCORE', 120)
CACHE_TIMEOUT_SHORT = getattr(settings, 'CACHE_TIMEOUT_SHORT', 60)

# Cache key prefixes
PREFIX = getattr(settings, 'CACHE_KEY_PREFIX', 'molek')


def make_cache_key(*args):
    """
    Generate a consistent cache key from arguments.
    
    Usage:
        key = make_cache_key('student', student_id)
        key = make_cache_key('results', session_id, term_id, class_level)
    """
    parts = [PREFIX] + [str(arg) for arg in args if arg is not None]
    return ':'.join(parts)


def make_list_cache_key(prefix, **filters):
    """
    Generate a cache key for list queries with filters.
    
    Usage:
        key = make_list_cache_key('students', class_level='JSS1', is_active=True)
    """
    # Sort filters for consistent key generation
    sorted_filters = sorted(filters.items())
    filter_str = '_'.join(f"{k}={v}" for k, v in sorted_filters if v is not None)
    
    if filter_str:
        return f"{PREFIX}:{prefix}:list:{filter_str}"
    return f"{PREFIX}:{prefix}:list:all"


def get_or_set_cache(key, callback, timeout=CACHE_TIMEOUT_ACADEMIC):
    """
    Get value from cache or set it using callback.
    
    Usage:
        data = get_or_set_cache(
            make_cache_key('sessions'),
            lambda: list(AcademicSession.objects.all()),
            timeout=CACHE_TIMEOUT_ACADEMIC
        )
    """
    data = cache.get(key)
    if data is None:
        data = callback()
        cache.set(key, data, timeout)
        logger.debug(f"Cache MISS: {key}")
    else:
        logger.debug(f"Cache HIT: {key}")
    return data


def invalidate_cache(*keys):
    """
    Invalidate multiple cache keys.
    
    Usage:
        invalidate_cache(
            make_cache_key('student', student_id),
            make_list_cache_key('students')
        )
    """
    for key in keys:
        cache.delete(key)
        logger.debug(f"Cache INVALIDATED: {key}")


def invalidate_pattern(pattern):
    """
    Invalidate all cache keys matching a pattern.
    
    Note: This only works with certain cache backends (Redis, Memcached).
    For locmem cache, we need to track keys manually.
    
    Usage:
        invalidate_pattern('molek:students:*')
    """
    # For database and locmem cache backends, we can't do pattern matching
    # Instead, we'll clear specific known keys
    logger.warning(f"Pattern invalidation requested for {pattern}, but not supported by current cache backend")


def cache_response(timeout=CACHE_TIMEOUT_ACADEMIC, key_func=None):
    """
    Decorator to cache view responses.
    
    Usage:
        @cache_response(timeout=300, key_func=lambda request: f"students:{request.query_params.get('class_level')}")
        def list(self, request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = make_cache_key(key_func(request))
            else:
                # Default key based on view name and query params
                view_name = f"{self.__class__.__name__}.{view_func.__name__}"
                params_hash = hashlib.md5(
                    str(sorted(request.query_params.items())).encode()
                ).hexdigest()[:8]
                cache_key = make_cache_key(view_name, params_hash)
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                logger.debug(f"View cache HIT: {cache_key}")
                return cached_response
            
            # Execute view and cache result
            response = view_func(self, request, *args, **kwargs)
            if response.status_code == 200:
                cache.set(cache_key, response, timeout)
                logger.debug(f"View cache SET: {cache_key}")
            
            return response
        return wrapper
    return decorator


# ==============================================================================
# Specific Cache Helpers
# ==============================================================================

def get_cached_sessions():
    """Get all academic sessions from cache or database"""
    from .models import AcademicSession
    
    key = make_cache_key('sessions', 'all')
    return get_or_set_cache(
        key,
        lambda: list(AcademicSession.objects.all().order_by('-start_date')),
        timeout=CACHE_TIMEOUT_ACADEMIC
    )


def get_cached_current_session():
    """Get current academic session from cache or database"""
    from .models import AcademicSession
    
    key = make_cache_key('sessions', 'current')
    return get_or_set_cache(
        key,
        lambda: AcademicSession.objects.filter(is_current=True).first(),
        timeout=CACHE_TIMEOUT_ACADEMIC
    )


def get_cached_terms(session_id=None):
    """Get terms from cache or database"""
    from .models import Term
    
    key = make_cache_key('terms', session_id or 'all')
    
    def fetch_terms():
        queryset = Term.objects.select_related('session')
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        return list(queryset.order_by('session', 'name'))
    
    return get_or_set_cache(key, fetch_terms, timeout=CACHE_TIMEOUT_ACADEMIC)


def get_cached_class_levels():
    """Get all class levels from cache or database"""
    from .models import ClassLevel
    
    key = make_cache_key('class_levels', 'all')
    return get_or_set_cache(
        key,
        lambda: list(ClassLevel.objects.all().order_by('order')),
        timeout=CACHE_TIMEOUT_STATIC
    )


def get_cached_subjects(is_active=True):
    """Get subjects from cache or database"""
    from .models import Subject
    
    key = make_cache_key('subjects', 'active' if is_active else 'all')
    
    def fetch_subjects():
        queryset = Subject.objects.prefetch_related('class_levels')
        if is_active:
            queryset = queryset.filter(is_active=True)
        return list(queryset.order_by('name'))
    
    return get_or_set_cache(key, fetch_subjects, timeout=CACHE_TIMEOUT_ACADEMIC)


def invalidate_session_cache():
    """Invalidate all session-related cache"""
    invalidate_cache(
        make_cache_key('sessions', 'all'),
        make_cache_key('sessions', 'current'),
    )


def invalidate_term_cache(session_id=None):
    """Invalidate term cache"""
    keys = [make_cache_key('terms', 'all')]
    if session_id:
        keys.append(make_cache_key('terms', session_id))
    invalidate_cache(*keys)


def invalidate_class_level_cache():
    """Invalidate class level cache"""
    invalidate_cache(make_cache_key('class_levels', 'all'))


def invalidate_subject_cache():
    """Invalidate subject cache"""
    invalidate_cache(
        make_cache_key('subjects', 'active'),
        make_cache_key('subjects', 'all'),
    )


def invalidate_student_cache(student_id=None, class_level=None):
    """Invalidate student-related cache"""
    keys = [make_list_cache_key('students')]
    if student_id:
        keys.append(make_cache_key('student', student_id))
    if class_level:
        keys.append(make_list_cache_key('students', class_level=class_level))
    invalidate_cache(*keys)


def invalidate_score_cache(session_id=None, term_id=None, student_id=None):
    """Invalidate score/result cache"""
    keys = []
    if session_id and term_id:
        keys.append(make_cache_key('ca_scores', session_id, term_id))
        keys.append(make_cache_key('exam_results', session_id, term_id))
    if student_id:
        keys.append(make_cache_key('student_grades', student_id))
        keys.append(make_cache_key('student_ca_scores', student_id))
    if keys:
        invalidate_cache(*keys)