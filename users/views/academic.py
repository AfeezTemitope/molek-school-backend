"""
MOLEK School - Academic Management Views
ViewSets for academic sessions, terms, class levels, and subjects
"""
import logging
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from ..models import AcademicSession, Term, ClassLevel, Subject
from ..serializers import (
    AcademicSessionSerializer,
    TermSerializer,
    ClassLevelSerializer,
    SubjectSerializer,
)
from ..permissions import IsAdminOrSuperAdmin
from ..cache_utils import (
    get_cached_sessions,
    get_cached_terms,
    get_cached_class_levels,
    get_cached_subjects,
    invalidate_session_cache,
    invalidate_term_cache,
    invalidate_class_level_cache,
    invalidate_subject_cache,
    CACHE_TIMEOUT_ACADEMIC,
    CACHE_TIMEOUT_STATIC,
)

logger = logging.getLogger(__name__)


class AcademicSessionViewSet(viewsets.ModelViewSet):
    """
    CRUD for academic sessions.
    
    Features:
    - List all sessions (cached for 30 minutes)
    - Create/Update/Delete sessions
    - Set a session as current (deactivates others)
    """
    queryset = AcademicSession.objects.all()
    serializer_class = AcademicSessionSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    ordering = ['-start_date']
    
    def list(self, request, *args, **kwargs):
        """Return cached list of sessions"""
        sessions = get_cached_sessions()
        serializer = self.get_serializer(sessions, many=True)
        return Response(serializer.data)
    
    def perform_create(self, serializer):
        serializer.save()
        invalidate_session_cache()
        logger.info(f"Academic session created: {serializer.instance.name}")
    
    def perform_update(self, serializer):
        serializer.save()
        invalidate_session_cache()
        logger.info(f"Academic session updated: {serializer.instance.name}")
    
    def perform_destroy(self, instance):
        name = instance.name
        instance.delete()
        invalidate_session_cache()
        logger.info(f"Academic session deleted: {name}")
    
    @action(detail=True, methods=['post'], url_path='set-active')
    def set_active(self, request, pk=None):
        """
        Set this session as current.
        
        This will:
        1. Deactivate all other sessions
        2. Activate this session
        3. Invalidate session cache
        """
        session = self.get_object()
        AcademicSession.objects.exclude(pk=pk).update(is_current=False)
        session.is_current = True
        session.save()
        invalidate_session_cache()
        logger.info(f"Academic session set as current: {session.name}")
        return Response({'detail': 'Session set as current'})


class TermViewSet(viewsets.ModelViewSet):
    """
    CRUD for terms.
    
    Features:
    - List all terms (cached for 30 minutes)
    - Filter by session
    - Set a term as current within its session
    """
    queryset = Term.objects.select_related('session').all()
    serializer_class = TermSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['session']
    ordering = ['session', 'name']
    
    def get_queryset(self):
        """Optimized queryset with select_related"""
        return Term.objects.select_related('session').all()
    
    def list(self, request, *args, **kwargs):
        """Return cached list of terms"""
        session_id = request.query_params.get('session')
        terms = get_cached_terms(session_id)
        serializer = self.get_serializer(terms, many=True)
        return Response(serializer.data)
    
    def perform_create(self, serializer):
        serializer.save()
        invalidate_term_cache(serializer.instance.session_id)
        logger.info(f"Term created: {serializer.instance}")
    
    def perform_update(self, serializer):
        serializer.save()
        invalidate_term_cache(serializer.instance.session_id)
        logger.info(f"Term updated: {serializer.instance}")
    
    def perform_destroy(self, instance):
        session_id = instance.session_id
        name = str(instance)
        instance.delete()
        invalidate_term_cache(session_id)
        logger.info(f"Term deleted: {name}")
    
    @action(detail=True, methods=['post'], url_path='set-active')
    def set_active(self, request, pk=None):
        """
        Set this term as current within its session.
        
        This will:
        1. Deactivate all other terms in the same session
        2. Activate this term
        3. Invalidate term cache
        """
        term = self.get_object()
        Term.objects.filter(session=term.session).exclude(pk=pk).update(is_current=False)
        term.is_current = True
        term.save()
        invalidate_term_cache(term.session_id)
        logger.info(f"Term set as current: {term}")
        return Response({'detail': 'Term set as current'})


class ClassLevelViewSet(viewsets.ModelViewSet):
    """
    CRUD for class levels (JSS1-SS3).
    
    Features:
    - List all class levels (cached for 1 hour - rarely changes)
    - Ordered by class order
    """
    queryset = ClassLevel.objects.all()
    serializer_class = ClassLevelSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    ordering = ['order']
    
    def list(self, request, *args, **kwargs):
        """Return cached list of class levels"""
        class_levels = get_cached_class_levels()
        serializer = self.get_serializer(class_levels, many=True)
        return Response(serializer.data)
    
    def perform_create(self, serializer):
        serializer.save()
        invalidate_class_level_cache()
        logger.info(f"Class level created: {serializer.instance.name}")
    
    def perform_update(self, serializer):
        serializer.save()
        invalidate_class_level_cache()
        logger.info(f"Class level updated: {serializer.instance.name}")
    
    def perform_destroy(self, instance):
        name = instance.name
        instance.delete()
        invalidate_class_level_cache()
        logger.info(f"Class level deleted: {name}")


class SubjectViewSet(viewsets.ModelViewSet):
    """
    CRUD for subjects.
    
    Features:
    - List all subjects (cached for 30 minutes)
    - Search by name, code
    - Filter by is_active
    """
    queryset = Subject.objects.prefetch_related('class_levels').all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'code']
    filterset_fields = ['is_active']
    
    def get_queryset(self):
        """Optimized queryset with prefetch_related"""
        return Subject.objects.prefetch_related('class_levels').all()
    
    def list(self, request, *args, **kwargs):
        """Return cached list of subjects"""
        is_active = request.query_params.get('is_active', 'true').lower() == 'true'
        subjects = get_cached_subjects(is_active)
        serializer = self.get_serializer(subjects, many=True)
        return Response(serializer.data)
    
    def perform_create(self, serializer):
        serializer.save()
        invalidate_subject_cache()
        logger.info(f"Subject created: {serializer.instance.name}")
    
    def perform_update(self, serializer):
        serializer.save()
        invalidate_subject_cache()
        logger.info(f"Subject updated: {serializer.instance.name}")
    
    def perform_destroy(self, instance):
        name = instance.name
        instance.delete()
        invalidate_subject_cache()
        logger.info(f"Subject deleted: {name}")