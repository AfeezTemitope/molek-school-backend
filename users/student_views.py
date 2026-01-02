from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
import csv
import io
from datetime import datetime
import logging

from .models import (
    AcademicSession,
    Term,
    ClassLevel,
    Subject,
    ActiveStudent,
    CAScore,
    ExamResult
)
from .serializers import (
    AcademicSessionSerializer,
    TermSerializer,
    ClassLevelSerializer,
    SubjectSerializer,
    ActiveStudentSerializer,
    StudentBulkUploadSerializer,
    StudentCredentialsSerializer,
    CAScoreSerializer,
    CAScoreBulkUploadSerializer,
    ExamResultSerializer,
    ExamResultBulkUploadSerializer,
    StudentLoginSerializer,
)
from .permissions import IsAdminOrSuperAdmin
from .utils import calculate_grade, calculate_position_and_stats

logger = logging.getLogger(__name__)


# ============================================================
# ACADEMIC MANAGEMENT VIEWS
# ============================================================

class AcademicSessionViewSet(viewsets.ModelViewSet):
    """CRUD for academic sessions"""
    queryset = AcademicSession.objects.all()
    serializer_class = AcademicSessionSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    ordering = ['-start_date']

    @action(detail=True, methods=['post'], url_path='set-active')
    def set_active(self, request, pk=None):
        """Set this session as current"""
        session = self.get_object()
        AcademicSession.objects.all().update(is_current=False)
        session.is_current = True
        session.save()
        return Response({'detail': 'Session set as current'})

class TermViewSet(viewsets.ModelViewSet):
    """CRUD for terms"""
    queryset = Term.objects.all()
    serializer_class = TermSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['session']
    ordering = ['session', 'name']

    @action(detail=True, methods=['post'], url_path='set-active')
    def set_active(self, request, pk=None):
        """Set this term as current within its session"""
        term = self.get_object()
        Term.objects.filter(session=term.session).update(is_current=False)
        term.is_current = True
        term.save()
        return Response({'detail': 'Term set as current'})

class ClassLevelViewSet(viewsets.ModelViewSet):
    """CRUD for class levels"""
    queryset = ClassLevel.objects.all()
    serializer_class = ClassLevelSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    ordering = ['order']

class SubjectViewSet(viewsets.ModelViewSet):
    """CRUD for subjects"""
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'code']
    filterset_fields = ['is_active']


# ============================================================
# STUDENT MANAGEMENT VIEWS
# ============================================================

class ActiveStudentViewSet(viewsets.ModelViewSet):
    """CRUD for students"""
    queryset = ActiveStudent.objects.all()
    serializer_class = ActiveStudentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['admission_number', 'first_name', 'last_name', 'email']
    filterset_fields = ['class_level', 'gender', 'is_active']
    ordering_fields = ['admission_number', 'first_name', 'created_at']
    ordering = ['admission_number']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    # @action(detail=False, methods=['post'], url_path='bulk-upload')
    @action(detail=False, methods=['post'], url_path='bulk-upload')
    def bulk_upload(self, request):
        """Bulk upload students via CSV"""
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        csv_file = request.FILES['file']

        try:
            decoded_file = csv_file.read().decode('utf-8')
        except UnicodeDecodeError:
            return Response({
                'error': 'Invalid file encoding. Please save CSV as UTF-8.'
            }, status=status.HTTP_400_BAD_REQUEST)

        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)

        created_students = []
        errors = []
        row_num = 1  # Start at 1 for header

        for row in reader:
            row_num += 1
            try:
                # Validate CSV data
                serializer = StudentBulkUploadSerializer(data=row)
                if not serializer.is_valid():
                    errors.append({
                        'row': row_num,
                        'error': f"Validation failed: {serializer.errors}"
                    })
                    continue

                # Get current session
                session = AcademicSession.objects.filter(is_current=True).first()
                if not session:
                    errors.append({
                        'row': row_num,
                        'error': 'No current academic session set. Please set a current session first.'
                    })
                    continue

                # Get class level
                class_level_name = serializer.validated_data['class_level'].upper()
                try:
                    class_level = ClassLevel.objects.get(name=class_level_name)
                except ClassLevel.DoesNotExist:
                    errors.append({
                        'row': row_num,
                        'error': f"Invalid class level '{class_level_name}'. Must be one of: JSS1, JSS2, JSS3, SS1, SS2, SS3"
                    })
                    continue

                # Get email
                email = serializer.validated_data.get('email')

                # Create student object
                student = ActiveStudent(
                    first_name=serializer.validated_data['first_name'].strip(),
                    middle_name=serializer.validated_data.get('middle_name', '').strip() or None,
                    last_name=serializer.validated_data['last_name'].strip(),
                    date_of_birth=serializer.validated_data['date_of_birth'],
                    gender=serializer.validated_data['gender'],
                    class_level=class_level,
                    enrollment_session=session,
                    email=email,
                    phone_number=serializer.validated_data.get('phone_number', '').strip() or None,
                    parent_name=serializer.validated_data.get('parent_name', '').strip() or None,
                    parent_email=serializer.validated_data.get('parent_email', '').strip() or None,
                    parent_phone=serializer.validated_data.get('parent_phone', '').strip() or None,
                    address=serializer.validated_data.get('address', '').strip() or None,
                    state_of_origin=serializer.validated_data.get('state_of_origin', '').strip() or None,
                    local_govt_area=serializer.validated_data.get('local_govt_area', '').strip() or None,
                    is_active=True,
                    created_by=request.user
                )

                # Save student (triggers auto-generation of admission_number and password)
                student.save()

                created_students.append({
                    'admission_number': student.admission_number,
                    'full_name': student.full_name,
                    'password': student.password_plain,
                    'class_level': class_level.get_name_display()
                })

                logger.info(f"Created student: {student.admission_number} - {student.full_name}")

            except Exception as e:
                logger.error(f"Error processing row {row_num}: {str(e)}")
                errors.append({
                    'row': row_num,
                    'error': f"Unexpected error: {str(e)}"
                })

        # Return response
        return Response({
            'created': len(created_students),
            'updated': 0,
            'failed': len(errors),
            'created_students': created_students,
            'errors': errors if errors else []
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        """Export students to CSV"""
        students = self.filter_queryset(self.get_queryset())

        response = Response()
        response['Content-Type'] = 'text/csv'
        response['Content-Disposition'] = 'attachment; filename="students_export.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Admission Number', 'First Name', 'Middle Name', 'Last Name',
            'Date of Birth', 'Gender', 'Email', 'Phone Number',
            'Class Level', 'Session', 'Parent Name', 'Parent Email',
            'Parent Phone', 'Address', 'State', 'LGA', 'Status'
        ])

        for student in students:
            writer.writerow([
                student.admission_number,
                student.first_name,
                student.middle_name or '',
                student.last_name,
                student.date_of_birth.strftime('%Y-%m-%d'),
                student.get_gender_display(),
                student.email or '',
                student.phone_number or '',
                student.class_level.get_name_display(),
                student.enrollment_session.name,
                student.parent_name or '',
                student.parent_email or '',
                student.parent_phone or '',
                student.address or '',
                student.state_of_origin or '',
                student.local_govt_area or '',
                'Active' if student.is_active else 'Inactive'
            ])

        return response

    @action(detail=False, methods=['get'], url_path='export-for-cbt')
    def export_for_cbt(self, request):
        """Export students with credentials for CBT system"""
        class_level = request.query_params.get('class_level')

        students = self.queryset.filter(is_active=True)
        if class_level:
            students = students.filter(class_level__name=class_level)

        serializer = StudentCredentialsSerializer(students, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get student statistics"""
        total = ActiveStudent.objects.count()
        active = ActiveStudent.objects.filter(is_active=True).count()
        inactive = total - active

        return Response({
            'total': total,
            'active': active,
            'inactive': inactive
        })

    @action(detail=False, methods=['post'])
    def promote_class(self, request):
        """Promote students to next class level"""
        from_class = request.data.get('from_class')
        to_class = request.data.get('to_class')

        if not from_class or not to_class:
            return Response(
                {'error': 'from_class and to_class required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from_level = ClassLevel.objects.get(name=from_class)
            to_level = ClassLevel.objects.get(name=to_class)
        except ClassLevel.DoesNotExist:
            return Response(
                {'error': 'Invalid class level'},
                status=status.HTTP_400_BAD_REQUEST
            )

        students = ActiveStudent.objects.filter(
            class_level=from_level,
            is_active=True
        )

        count = students.update(class_level=to_level)

        return Response({
            'promoted': count,
            'from_class': from_class,
            'to_class': to_class
        })

# ============================================================
# CA SCORE MANAGEMENT
# ============================================================

class CAScoreViewSet(viewsets.ModelViewSet):
    """CRUD for CA scores"""
    queryset = CAScore.objects.all()
    serializer_class = CAScoreSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'subject', 'session', 'term']

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='bulk-upload')
    def bulk_upload(self, request):
        """Bulk upload CA scores via CSV"""
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        session_id = request.data.get('session')
        term_id = request.data.get('term')

        if not session_id or not term_id:
            return Response(
                {'error': 'session and term required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            session = AcademicSession.objects.get(id=session_id)
            term = Term.objects.get(id=term_id)
        except (AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response(
                {'error': 'Invalid session or term'},
                status=status.HTTP_400_BAD_REQUEST
            )

        csv_file = request.FILES['file']
        decoded_file = csv_file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)

        created = 0
        updated = 0
        subjects_created = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):
            try:
                serializer = CAScoreBulkUploadSerializer(data=row)
                if serializer.is_valid():
                    student = ActiveStudent.objects.get(
                        admission_number=serializer.validated_data['admission_number'].upper()
                    )

                    # ✅ AUTO-CREATE SUBJECT IF IT DOESN'T EXIST
                    subject_code = serializer.validated_data['subject_code'].upper()
                    subject_name = row.get('subject_name', subject_code)

                    subject, created_now = Subject.objects.get_or_create(
                        code=subject_code,
                        defaults={
                            'name': subject_name,
                            'is_active': True
                        }
                    )

                    if created_now:
                        subjects_created += 1
                        subject.class_levels.add(student.class_level)
                        logger.info(f"Auto-created subject: {subject.name} ({subject.code})")

                    ca_score, was_created = CAScore.objects.update_or_create(
                        student=student,
                        subject=subject,
                        session=session,
                        term=term,
                        defaults={
                            'score': serializer.validated_data['ca_score'],
                            'uploaded_by': request.user
                        }
                    )

                    if was_created:
                        created += 1
                    else:
                        updated += 1
                else:
                    errors.append({'row': row_num, 'errors': serializer.errors})
            except ActiveStudent.DoesNotExist:
                errors.append({
                    'row': row_num,
                    'error': f'Student with admission number {row.get("admission_number")} not found'
                })
            except Exception as e:
                errors.append({'row': row_num, 'error': str(e)})

        return Response({
            'created': created,
            'updated': updated,
            'subjects_created': subjects_created,
            'failed': len(errors),
            'errors': errors[:10]
        })


# ============================================================
# EXAM RESULT MANAGEMENT
# ============================================================

class ExamResultViewSet(viewsets.ModelViewSet):
    """CRUD for exam results"""
    queryset = ExamResult.objects.all()
    serializer_class = ExamResultSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['student', 'subject', 'session', 'term']
    ordering_fields = ['total_score', 'percentage', 'submitted_at']
    ordering = ['-submitted_at']

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='bulk-import')
    def bulk_import(self, request):
        """Bulk import exam results from CBT system"""
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        session_id = request.data.get('session')
        term_id = request.data.get('term')

        if not session_id or not term_id:
            return Response(
                {'error': 'session and term required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            session = AcademicSession.objects.get(id=session_id)
            term = Term.objects.get(id=term_id)
        except (AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response(
                {'error': 'Invalid session or term'},
                status=status.HTTP_400_BAD_REQUEST
            )

        csv_file = request.FILES['file']
        decoded_file = csv_file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)

        created = 0
        updated = 0
        subjects_created = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):
            try:
                serializer = ExamResultBulkUploadSerializer(data=row)
                if serializer.is_valid():
                    student = ActiveStudent.objects.get(
                        admission_number=serializer.validated_data['admission_number'].upper()
                    )

                    # ✅ AUTO-CREATE SUBJECT IF IT DOESN'T EXIST
                    subject_code = serializer.validated_data['subject_code'].upper()
                    subject_name = row.get('subject_name', subject_code)

                    subject, created_now = Subject.objects.get_or_create(
                        code=subject_code,
                        defaults={
                            'name': subject_name,
                            'is_active': True
                        }
                    )

                    if created_now:
                        subjects_created += 1
                        subject.class_levels.add(student.class_level)
                        logger.info(f"Auto-created subject: {subject.name} ({subject.code})")

                    # Get existing CA score
                    try:
                        ca_score_obj = CAScore.objects.get(
                            student=student,
                            subject=subject,
                            session=session,
                            term=term
                        )
                        ca_score = ca_score_obj.score
                    except CAScore.DoesNotExist:
                        ca_score = 0
                        logger.warning(f"No CA score found for {student.admission_number} - {subject.code}")

                    # Calculate total
                    exam_score = serializer.validated_data['exam_score']
                    total_score = ca_score + exam_score
                    percentage = round((total_score / 100) * 100, 2)
                    grade, grade_comment = calculate_grade(percentage)

                    # Create or update
                    exam_result, was_created = ExamResult.objects.update_or_create(
                        student=student,
                        subject=subject,
                        session=session,
                        term=term,
                        defaults={
                            'exam_score': exam_score,
                            'ca_score': ca_score,
                            'total_score': total_score,
                            'percentage': percentage,
                            'grade': grade,
                            'submitted_at': serializer.validated_data.get('submitted_at', datetime.now()),
                            'uploaded_by': request.user
                        }
                    )

                    # Calculate position
                    stats = calculate_position_and_stats(student, subject, session, term)
                    exam_result.position = stats['position']
                    exam_result.total_students = stats['total_students']
                    exam_result.class_average = stats['class_average']
                    exam_result.highest_score = stats['highest_score']
                    exam_result.lowest_score = stats['lowest_score']
                    exam_result.save()

                    if was_created:
                        created += 1
                    else:
                        updated += 1
                else:
                    errors.append({'row': row_num, 'errors': serializer.errors})
            except ActiveStudent.DoesNotExist:
                errors.append({
                    'row': row_num,
                    'error': f'Student with admission number {row.get("admission_number")} not found'
                })
            except Exception as e:
                errors.append({'row': row_num, 'error': str(e)})

        return Response({
            'created': created,
            'updated': updated,
            'subjects_created': subjects_created,
            'failed': len(errors),
            'errors': errors[:10]
        })

    @action(detail=False, methods=['post'])
    def import_from_cbt(self, request):
        """Alias for bulk_import"""
        return self.bulk_import(request)

# ============================================================
# STUDENT PORTAL VIEWS
# ============================================================

class StudentLoginView(APIView):
    """Student portal login"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = StudentLoginSerializer(data=request.data)
        if serializer.is_valid():
            student = serializer.validated_data['student']

            return Response({
                'student': ActiveStudentSerializer(student).data,
                'sessions': AcademicSessionSerializer(
                    AcademicSession.objects.all().order_by('-start_date'),
                    many=True
                ).data
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentResultsView(APIView):
    """View results for student portal"""
    permission_classes = [AllowAny]

    def get(self, request, admission_number):
        session_id = request.query_params.get('session')
        term_id = request.query_params.get('term')

        if not session_id or not term_id:
            return Response(
                {'error': 'session and term required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            student = ActiveStudent.objects.get(
                admission_number=admission_number.upper()
            )
            session = AcademicSession.objects.get(id=session_id)
            term = Term.objects.get(id=term_id)
        except (ActiveStudent.DoesNotExist, AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response(
                {'error': 'Invalid parameters'},
                status=status.HTTP_400_BAD_REQUEST
            )

        results = ExamResult.objects.filter(
            student=student,
            session=session,
            term=term
        ).select_related('subject')

        if not results.exists():
            return Response({
                'session': session.name,
                'term': term.name,
                'student_class': student.class_level.name,
                'results': [],
                'total_score': 0,
                'average_percentage': 0,
                'overall_position': None,
                'total_students': 0
            })

        total_score = sum(r.total_score for r in results)
        average = round(total_score / len(results), 2)

        class_students = ActiveStudent.objects.filter(
            class_level=student.class_level,
            is_active=True
        )

        student_averages = []
        for s in class_students:
            s_results = ExamResult.objects.filter(
                student=s,
                session=session,
                term=term
            )
            if s_results.exists():
                s_avg = sum(r.total_score for r in s_results) / len(s_results)
                student_averages.append((s, s_avg))

        student_averages.sort(key=lambda x: x[1], reverse=True)
        position = next(
            (i + 1 for i, (s, _) in enumerate(student_averages) if s == student),
            None
        )

        return Response({
            'session': session.name,
            'term': term.name,
            'student_class': student.class_level.name,
            'results': ExamResultSerializer(results, many=True).data,
            'total_score': total_score,
            'average_percentage': average,
            'overall_position': position,
            'total_students': len(student_averages)
        })


# ============================================
# ADDITIONAL STUDENT PORTAL VIEWS
# ============================================

class StudentProfileView(APIView):
    """Get and update student profile"""
    permission_classes = [AllowAny]

    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        if not admission_number:
            return Response({'error': 'Admission number required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            student = ActiveStudent.objects.get(admission_number=admission_number.upper(), is_active=True)
            return Response({'student': ActiveStudentSerializer(student).data})
        except ActiveStudent.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request):
        admission_number = request.data.get('admission_number')
        if not admission_number:
            return Response({'error': 'Admission number required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            student = ActiveStudent.objects.get(admission_number=admission_number.upper(), is_active=True)
        except ActiveStudent.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

        # Update allowed fields
        if 'email' in request.data:
            student.email = request.data['email']
        if 'phone_number' in request.data:
            student.phone_number = request.data['phone_number']
        if 'address' in request.data:
            student.address = request.data['address']
        if 'passport' in request.FILES:
            student.passport = request.FILES['passport']

        student.save()
        return Response({
            'message': 'Profile updated successfully',
            'student': ActiveStudentSerializer(student).data
        })


class StudentChangePasswordView(APIView):
    """Change student password"""
    permission_classes = [AllowAny]

    def post(self, request):
        from django.contrib.auth.hashers import check_password, make_password

        admission_number = request.data.get('admission_number')
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not all([admission_number, old_password, new_password]):
            return Response({'error': 'All fields required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            student = ActiveStudent.objects.get(admission_number=admission_number.upper(), is_active=True)
        except ActiveStudent.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

        # Verify old password
        if not check_password(old_password, student.password_hash):
            return Response({'error': 'Current password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)

        # Update password
        student.password_plain = new_password
        student.password_hash = make_password(new_password)
        student.save()

        return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)


class StudentGradesView(APIView):
    """Get all grades for a student"""
    permission_classes = [AllowAny]

    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        if not admission_number:
            return Response({'error': 'Admission number required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            student = ActiveStudent.objects.get(admission_number=admission_number.upper(), is_active=True)
        except ActiveStudent.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

        # Get all exam results
        results = ExamResult.objects.filter(student=student).select_related(
            'subject', 'session', 'term'
        ).order_by('-session__start_date', 'term__name')

        return Response({'grades': ExamResultSerializer(results, many=True).data})


class StudentCAScoresView(APIView):
    """Get CA scores for a student"""
    permission_classes = [AllowAny]

    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        session_id = request.query_params.get('session')
        term_id = request.query_params.get('term')

        if not admission_number:
            return Response({'error': 'Admission number required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            student = ActiveStudent.objects.get(admission_number=admission_number.upper(), is_active=True)
        except ActiveStudent.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

        # Filter CA scores
        ca_scores = CAScore.objects.filter(student=student)
        if session_id:
            ca_scores = ca_scores.filter(session_id=session_id)
        if term_id:
            ca_scores = ca_scores.filter(term_id=term_id)

        ca_scores = ca_scores.select_related('subject', 'session', 'term').order_by('-session__start_date')

        return Response({'ca_scores': CAScoreSerializer(ca_scores, many=True).data})


class StudentExamResultsView(APIView):
    """Get exam results for a student"""
    permission_classes = [AllowAny]

    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        session_id = request.query_params.get('session')
        term_id = request.query_params.get('term')

        if not admission_number:
            return Response({'error': 'Admission number required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            student = ActiveStudent.objects.get(admission_number=admission_number.upper(), is_active=True)
        except ActiveStudent.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)

        # Filter exam results
        results = ExamResult.objects.filter(student=student)
        if session_id:
            results = results.filter(session_id=session_id)
        if term_id:
            results = results.filter(term_id=term_id)

        results = results.select_related('subject', 'session', 'term').order_by('-session__start_date')

        return Response({'exam_results': ExamResultSerializer(results, many=True).data})


class StudentReportCardView(APIView):
    """Get comprehensive report card"""
    permission_classes = [AllowAny]

    def get(self, request):
        admission_number = request.query_params.get('admission_number')
        session_id = request.query_params.get('session')
        term_id = request.query_params.get('term')

        if not all([admission_number, session_id, term_id]):
            return Response({'error': 'Admission number, session, and term required'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            student = ActiveStudent.objects.get(admission_number=admission_number.upper(), is_active=True)
            session = AcademicSession.objects.get(id=session_id)
            term = Term.objects.get(id=term_id)
        except (ActiveStudent.DoesNotExist, AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response({'error': 'Invalid parameters'}, status=status.HTTP_400_BAD_REQUEST)

        # Get results
        results = ExamResult.objects.filter(
            student=student, session=session, term=term
        ).select_related('subject')

        if not results.exists():
            return Response({
                'session': session.name,
                'term': term.name,
                'student_class': student.class_level.get_name_display(),
                'results': [],
                'total_score': 0,
                'average_percentage': 0
            })

        # Calculate stats
        total_score = sum(r.total_score for r in results)
        average = round(total_score / len(results), 2)

        return Response({
            'session': session.name,
            'term': term.name,
            'student_class': student.class_level.get_name_display(),
            'results': ExamResultSerializer(results, many=True).data,
            'total_score': total_score,
            'average_percentage': average
        })


class StudentSessionsView(APIView):
    """Get all academic sessions"""
    permission_classes = [AllowAny]

    def get(self, request):
        sessions = AcademicSession.objects.all().order_by('-start_date')
        return Response({'sessions': AcademicSessionSerializer(sessions, many=True).data})


class StudentTermsView(APIView):
    """Get all terms"""
    permission_classes = [AllowAny]

    def get(self, request):
        terms = Term.objects.all().select_related('session').order_by('-session__start_date', 'name')
        return Response({'terms': TermSerializer(terms, many=True).data})