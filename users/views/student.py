"""
MOLEK School - Student Management Views
ViewSet for student CRUD, bulk upload, and export operations
"""
import csv
import io
import logging
from datetime import datetime

from django.http import HttpResponse
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from ..models import ActiveStudent, AcademicSession, ClassLevel
from ..serializers import (
    ActiveStudentSerializer,
    ActiveStudentWriteSerializer,
    StudentBulkUploadSerializer,
)
from ..permissions import IsAdminOrSuperAdmin
from ..cache_utils import (
    make_cache_key,
    make_list_cache_key,
    get_or_set_cache,
    invalidate_cache,
    invalidate_student_cache,
    CACHE_TIMEOUT_STUDENT,
)

logger = logging.getLogger(__name__)


class ActiveStudentViewSet(viewsets.ModelViewSet):
    """
    CRUD for students with passport photo upload support.
    
    Features:
    - List students with caching (5 minutes)
    - Search by admission_number, first_name, last_name, email
    - Filter by class_level, gender, is_active
    - Bulk upload via CSV
    - Export to CSV (full data or CBT format)
    - Promote students to next class
    
    Uses different serializers for read vs write operations:
    - ActiveStudentSerializer for reading (returns passport URL)
    - ActiveStudentWriteSerializer for creating/updating (accepts file uploads)
    """
    queryset = ActiveStudent.objects.all()
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['admission_number', 'first_name', 'last_name', 'email']
    filterset_fields = ['class_level', 'gender', 'is_active']
    ordering_fields = ['admission_number', 'first_name', 'created_at']
    ordering = ['admission_number']
    
    def get_serializer_class(self):
        """Switch serializer based on action"""
        if self.action in ['create', 'update', 'partial_update']:
            return ActiveStudentWriteSerializer
        return ActiveStudentSerializer
    
    def get_queryset(self):
        """Optimized queryset with select_related"""
        return ActiveStudent.objects.select_related(
            'class_level', 'enrollment_session', 'created_by'
        ).prefetch_related('subjects')
    
    def list(self, request, *args, **kwargs):
        """Return cached list of students"""
        # Build cache key from query params
        cache_key = make_list_cache_key(
            'students',
            class_level=request.query_params.get('class_level'),
            is_active=request.query_params.get('is_active'),
            gender=request.query_params.get('gender'),
            search=request.query_params.get('search'),
            page=request.query_params.get('page', 1),
        )
        
        # Use default list behavior but with caching consideration
        # For paginated results, we skip caching to avoid stale pagination
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Return cached student detail"""
        pk = kwargs.get('pk')
        cache_key = make_cache_key('student', pk)
        
        def get_student():
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return serializer.data
        
        data = get_or_set_cache(cache_key, get_student, timeout=CACHE_TIMEOUT_STUDENT)
        return Response(data)
    
    def create(self, request, *args, **kwargs):
        """Create student with file upload support"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(created_by=request.user)
        
        # Invalidate caches
        invalidate_student_cache(class_level=instance.class_level_id)
        
        # Return response using read serializer (includes passport URL)
        read_serializer = ActiveStudentSerializer(instance)
        logger.info(f"Student created: {instance.admission_number} by {request.user.username}")
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update student with file upload support"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_class_level = instance.class_level_id
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        # Invalidate caches
        invalidate_student_cache(
            student_id=instance.id,
            class_level=old_class_level
        )
        if instance.class_level_id != old_class_level:
            invalidate_student_cache(class_level=instance.class_level_id)
        
        # Return response using read serializer
        read_serializer = ActiveStudentSerializer(instance)
        logger.info(f"Student updated: {instance.admission_number} by {request.user.username}")
        return Response(read_serializer.data)
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete student"""
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        
        invalidate_student_cache(
            student_id=instance.id,
            class_level=instance.class_level_id
        )
        
        logger.info(f"Student deactivated: {instance.admission_number} by {request.user.username}")
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get student statistics.
        
        Returns:
            - total: Total student count
            - active: Active student count
            - inactive: Inactive student count
        """
        cache_key = make_cache_key('student_stats')
        
        def get_stats():
            total = ActiveStudent.objects.count()
            active = ActiveStudent.objects.filter(is_active=True).count()
            return {
                'total': total,
                'active': active,
                'inactive': total - active
            }
        
        stats = get_or_set_cache(cache_key, get_stats, timeout=CACHE_TIMEOUT_STUDENT)
        return Response(stats)
    
    @action(detail=False, methods=['post'], url_path='bulk-upload')
    def bulk_upload(self, request):
        """
        Bulk upload students via CSV.
        
        Expected CSV columns:
        - first_name (required)
        - last_name (required)
        - date_of_birth (YYYY-MM-DD)
        - gender (M/F)
        - class_level (JSS1-SS3)
        - email
        - phone_number
        - parent_name
        - parent_email
        - parent_phone
        - address
        - state_of_origin
        - local_govt_area
        """
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        csv_file = request.FILES['file']
        
        try:
            decoded_file = csv_file.read().decode('utf-8')
        except UnicodeDecodeError:
            return Response(
                {'error': 'Invalid file encoding. Please save CSV as UTF-8.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        
        created_students = []
        errors = []
        row_num = 1
        
        # Get current session
        session = AcademicSession.objects.filter(is_current=True).first()
        if not session:
            return Response(
                {'error': 'No current academic session set.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        for row in reader:
            row_num += 1
            try:
                serializer = StudentBulkUploadSerializer(data=row)
                if not serializer.is_valid():
                    errors.append({
                        'row': row_num,
                        'error': f"Validation failed: {serializer.errors}"
                    })
                    continue
                
                class_level_name = serializer.validated_data['class_level'].upper()
                try:
                    class_level = ClassLevel.objects.get(name=class_level_name)
                except ClassLevel.DoesNotExist:
                    errors.append({
                        'row': row_num,
                        'error': f"Invalid class level '{class_level_name}'"
                    })
                    continue
                
                student = ActiveStudent(
                    first_name=serializer.validated_data['first_name'].strip(),
                    middle_name=serializer.validated_data.get('middle_name', '').strip() or None,
                    last_name=serializer.validated_data['last_name'].strip(),
                    date_of_birth=serializer.validated_data.get('date_of_birth'),
                    gender=serializer.validated_data['gender'],
                    class_level=class_level,
                    enrollment_session=session,
                    email=serializer.validated_data.get('email'),
                    phone_number=serializer.validated_data.get('phone_number', '').strip() or None,
                    parent_name=serializer.validated_data.get('parent_name', '').strip() or None,
                    parent_email=serializer.validated_data.get('parent_email', '').strip() or None,
                    parent_phone=serializer.validated_data.get('parent_phone', '').strip() or None,
                    address=serializer.validated_data.get('address', '').strip() or None,
                    state_of_origin=serializer.validated_data.get('state_of_origin', '').strip() or None,
                    local_govt_area=serializer.validated_data.get('local_govt_area', '').strip() or None,
                    is_active=True,
                    created_by=request.user,
                )
                student.save()
                created_students.append(student.admission_number)
                
            except Exception as e:
                errors.append({'row': row_num, 'error': str(e)})
        
        # Invalidate student cache
        invalidate_student_cache()
        
        logger.info(f"Bulk upload: {len(created_students)} students created by {request.user.username}")
        
        return Response({
            'created': len(created_students),
            'students': created_students,
            'errors': errors[:10] if errors else [],
            'total_errors': len(errors),
        })
    
    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        """Export all students as CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="students_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'admission_number', 'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'gender', 'email', 'phone_number', 'class_level',
            'enrollment_session', 'is_active', 'parent_name', 'parent_email',
            'parent_phone', 'address', 'state_of_origin', 'local_govt_area'
        ])
        
        students = ActiveStudent.objects.select_related(
            'class_level', 'enrollment_session'
        ).all()
        
        for student in students:
            writer.writerow([
                student.admission_number,
                student.first_name,
                student.middle_name or '',
                student.last_name,
                student.date_of_birth,
                student.gender,
                student.email or '',
                student.phone_number or '',
                student.class_level.name if student.class_level else '',
                student.enrollment_session.name if student.enrollment_session else '',
                'Yes' if student.is_active else 'No',
                student.parent_name or '',
                student.parent_email or '',
                student.parent_phone or '',
                student.address or '',
                student.state_of_origin or '',
                student.local_govt_area or '',
            ])
        
        return response
    
    @action(detail=False, methods=['get'], url_path='export-for-cbt')
    def export_for_cbt(self, request):
        """
        Export students in CBT format.
        
        Format: admission_number, first_name, middle_name, last_name, class_level, password_plain
        """
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="students_for_cbt.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'admission_number', 'first_name', 'middle_name', 'last_name',
            'class_level', 'password_plain'
        ])
        
        students = ActiveStudent.objects.filter(is_active=True).select_related('class_level')
        
        for student in students:
            writer.writerow([
                student.admission_number,
                student.first_name,
                student.middle_name or '',
                student.last_name,
                student.class_level.name if student.class_level else '',
                student.password_plain or '',
            ])
        
        return response
    
    @action(detail=False, methods=['post'])
    def promote(self, request):
        """
        Promote students to next class level.
        
        Request body:
        {
            "student_ids": [1, 2, 3, ...]
        }
        """
        student_ids = request.data.get('student_ids', [])
        
        if not student_ids:
            return Response(
                {'error': 'No students selected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        promoted = 0
        graduated = 0
        errors = []
        
        for student_id in student_ids:
            try:
                student = ActiveStudent.objects.get(id=student_id)
                current_order = student.class_level.order if student.class_level else 0
                
                if current_order >= 6:  # SS3
                    student.is_active = False
                    student.graduation_date = datetime.now().date()
                    student.save()
                    graduated += 1
                else:
                    next_class = ClassLevel.objects.filter(order=current_order + 1).first()
                    if next_class:
                        student.class_level = next_class
                        student.save()
                        promoted += 1
                    else:
                        errors.append(f"No next class level for student {student.admission_number}")
            except ActiveStudent.DoesNotExist:
                errors.append(f"Student with ID {student_id} not found")
            except Exception as e:
                errors.append(str(e))
        
        # Invalidate student cache
        invalidate_student_cache()
        
        logger.info(f"Promotion: {promoted} promoted, {graduated} graduated by {request.user.username}")
        
        return Response({
            'promoted': promoted,
            'graduated': graduated,
            'errors': errors
        })