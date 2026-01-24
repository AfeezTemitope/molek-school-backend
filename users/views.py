# from django.utils import timezone
# from rest_framework import status, viewsets
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated

# from rest_framework.views import APIView
# from rest_framework.decorators import action, permission_classes, api_view
# from rest_framework_simplejwt.views import TokenObtainPairView
# from django.core.cache import cache
# from rest_framework import filters
# from django_filters.rest_framework import DjangoFilterBackend
# import logging
# from django.db import transaction
# from django.db.models import Avg, F
# from decimal import Decimal
# import csv
# import io

# from .models import UserProfile, ExamResult, CAScore, ActiveStudent, ClassLevel, Term, AcademicSession, Subject
# from .serializers import (
#     CustomTokenObtainPairSerializer,
#     AdminProfileSerializer,
#     ChangePasswordSerializer,
#     ProfileUpdateSerializer, ExamResultSerializer, CAScoreSerializer, BulkPromotionSerializer,
#     ExamResultUploadSerializer, CAScoreUploadSerializer
# )
# from .permissions import IsAdminOrSuperAdmin

# logger = logging.getLogger(__name__)


# # ==============================
# # AUTHENTICATION VIEWS
# # ==============================
# class CustomTokenObtainPairView(TokenObtainPairView):
#     """Custom JWT authentication for admin users"""
#     serializer_class = CustomTokenObtainPairSerializer


# # ==============================
# # ADMIN MANAGEMENT VIEWSET
# # ==============================
# class AdminViewSet(viewsets.ModelViewSet):
#     """ViewSet for managing admin users"""
#     serializer_class = AdminProfileSerializer
#     permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
#     filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
#     search_fields = ['username', 'email', 'first_name', 'last_name']
#     filterset_fields = ['role', 'is_active']
#     ordering_fields = ['created_at', 'username', 'email']
#     ordering = ['-created_at']

#     def get_queryset(self):
#         return UserProfile.objects.filter(
#             is_active=True,
#             role__in=['admin', 'superadmin']
#         ).only(
#             'id', 'username', 'email', 'first_name', 'last_name',
#             'role', 'phone_number', 'is_active', 'created_at'
#         )

#     def perform_create(self, serializer):
#         serializer.save()
#         logger.info(f"Admin user created: {serializer.instance.username} by {self.request.user.username}")

#     def perform_update(self, serializer):
#         serializer.save()
#         cache_key = f'admin_{serializer.instance.id}'
#         cache.delete(cache_key)
#         logger.info(f"Admin user updated: {serializer.instance.username} by {self.request.user.username}")

#     def perform_destroy(self, instance):
#         instance.is_active = False
#         instance.save(update_fields=['is_active'])
#         logger.info(f"Admin user deactivated: {instance.username} by {self.request.user.username}")

#     @action(detail=False, methods=['get'])
#     def stats(self, request):
#         """Get admin statistics"""
#         queryset = self.get_queryset()
#         return Response({
#             'total_admins': queryset.filter(role='admin').count(),
#             'total_superadmins': queryset.filter(role='superadmin').count(),
#             'total': queryset.count()
#         })


# # ==============================
# # PROFILE MANAGEMENT VIEWS
# # ==============================
# class ProfileView(APIView):
#     """Get and update current user's profile"""
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         serializer = AdminProfileSerializer(request.user)
#         return Response(serializer.data, status=status.HTTP_200_OK)

#     def put(self, request):
#         serializer = ProfileUpdateSerializer(
#             request.user,
#             data=request.data,
#             partial=False,
#             context={'request': request}
#         )
#         if serializer.is_valid():
#             serializer.save()
#             cache_key = f'profile_{request.user.id}'
#             cache.delete(cache_key)
#             return Response(serializer.data, status=status.HTTP_200_OK)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     def patch(self, request):
#         serializer = ProfileUpdateSerializer(
#             request.user,
#             data=request.data,
#             partial=True,
#             context={'request': request}
#         )
#         if serializer.is_valid():
#             serializer.save()
#             cache_key = f'profile_{request.user.id}'
#             cache.delete(cache_key)
#             return Response(serializer.data, status=status.HTTP_200_OK)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class ChangePasswordView(APIView):
#     """Change current user's password"""
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         serializer = ChangePasswordSerializer(
#             data=request.data,
#             context={'request': request}
#         )
#         if serializer.is_valid():
#             user = request.user
#             user.set_password(serializer.validated_data['new_password'])
#             user.save()
#             logger.info(f"Password changed for user: {user.username}")
#             return Response({
#                 'detail': 'Password changed successfully'
#             }, status=status.HTTP_200_OK)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# # ============================================
# # CA + THEORY SCORE BULK UPLOAD
# # ============================================

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def bulk_upload_ca_scores(request):
#     """
#     Bulk upload CA + Theory scores from CSV

#     CSV Format:
#     admission_number,subject,ca_score,theory_score
#     MOL/2026/001,Mathematics,25,18
#     MOL/2026/002,Mathematics,22,20
#     """
#     if 'file' not in request.FILES:
#         return Response(
#             {'error': 'No file provided'},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     csv_file = request.FILES['file']
#     session_id = request.data.get('session_id')
#     term_id = request.data.get('term_id')

#     if not session_id or not term_id:
#         return Response(
#             {'error': 'session_id and term_id are required'},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     try:
#         session = AcademicSession.objects.get(id=session_id)
#         term = Term.objects.get(id=term_id)
#     except (AcademicSession.DoesNotExist, Term.DoesNotExist):
#         return Response(
#             {'error': 'Invalid session or term'},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     # Parse CSV
#     try:
#         decoded_file = csv_file.read().decode('utf-8')
#         reader = csv.DictReader(io.StringIO(decoded_file))
#         rows = list(reader)
#     except Exception as e:
#         return Response(
#             {'error': f'Failed to parse CSV: {str(e)}'},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     if not rows:
#         return Response(
#             {'error': 'CSV file is empty'},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     # Validate and process
#     created_count = 0
#     updated_count = 0
#     errors = []

#     with transaction.atomic():
#         for idx, row in enumerate(rows, start=2):  # Start at 2 (header is row 1)
#             serializer = CAScoreUploadSerializer(data=row)

#             if not serializer.is_valid():
#                 errors.append({
#                     'row': idx,
#                     'admission_number': row.get('admission_number', 'N/A'),
#                     'errors': serializer.errors
#                 })
#                 continue

#             data = serializer.validated_data

#             try:
#                 student = ActiveStudent.objects.get(
#                     admission_number=data['admission_number']
#                 )
#                 subject = Subject.objects.get(name__iexact=data['subject'])

#                 # Create or update CA score
#                 ca_score, created = CAScore.objects.update_or_create(
#                     student=student,
#                     subject=subject,
#                     session=session,
#                     term=term,
#                     defaults={
#                         'ca_score': data['ca_score'],
#                         'theory_score': data['theory_score'],
#                         'uploaded_by': request.user.userprofile
#                     }
#                 )

#                 if created:
#                     created_count += 1
#                 else:
#                     updated_count += 1

#             except Exception as e:
#                 errors.append({
#                     'row': idx,
#                     'admission_number': row.get('admission_number', 'N/A'),
#                     'errors': str(e)
#                 })

#     return Response({
#         'success': True,
#         'message': f'Processed {len(rows)} records',
#         'created': created_count,
#         'updated': updated_count,
#         'errors': errors if errors else None,
#         'total_processed': created_count + updated_count
#     })


# # ============================================
# # CBT EXAM RESULTS UPLOAD
# # ============================================

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def bulk_upload_exam_results(request):
#     """
#     Bulk upload CBT exam results and combine with CA scores

#     CSV Format from CBT:
#     admission_number,subject,exam_score,total_questions,submitted_at
#     MOL/2026/001,Mathematics,35,40,2026-01-19 13:30:55

#     This will:
#     1. Find matching CA score for the student/subject
#     2. Combine CA + Theory + Exam = Total
#     3. Calculate grade
#     4. Save ExamResult
#     """
#     if 'file' not in request.FILES:
#         return Response(
#             {'error': 'No file provided'},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     csv_file = request.FILES['file']
#     session_id = request.data.get('session_id')
#     term_id = request.data.get('term_id')

#     if not session_id or not term_id:
#         return Response(
#             {'error': 'session_id and term_id are required'},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     try:
#         session = AcademicSession.objects.get(id=session_id)
#         term = Term.objects.get(id=term_id)
#     except (AcademicSession.DoesNotExist, Term.DoesNotExist):
#         return Response(
#             {'error': 'Invalid session or term'},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     # Parse CSV
#     try:
#         decoded_file = csv_file.read().decode('utf-8')
#         reader = csv.DictReader(io.StringIO(decoded_file))
#         rows = list(reader)
#     except Exception as e:
#         return Response(
#             {'error': f'Failed to parse CSV: {str(e)}'},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     if not rows:
#         return Response(
#             {'error': 'CSV file is empty'},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     # Process results
#     created_count = 0
#     updated_count = 0
#     missing_ca_scores = []
#     errors = []

#     with transaction.atomic():
#         for idx, row in enumerate(rows, start=2):
#             serializer = ExamResultUploadSerializer(data=row)

#             if not serializer.is_valid():
#                 errors.append({
#                     'row': idx,
#                     'admission_number': row.get('admission_number', 'N/A'),
#                     'errors': serializer.errors
#                 })
#                 continue

#             data = serializer.validated_data

#             try:
#                 student = ActiveStudent.objects.get(
#                     admission_number=data['admission_number']
#                 )
#                 subject = Subject.objects.get(name__iexact=data['subject'])

#                 # Find CA score for this student/subject
#                 try:
#                     ca_score_obj = CAScore.objects.get(
#                         student=student,
#                         subject=subject,
#                         session=session,
#                         term=term
#                     )
#                     ca_score = ca_score_obj.ca_score
#                     theory_score = ca_score_obj.theory_score
#                 except CAScore.DoesNotExist:
#                     missing_ca_scores.append({
#                         'admission_number': data['admission_number'],
#                         'subject': data['subject']
#                     })
#                     # Use default values if CA not found
#                     ca_score = Decimal('0')
#                     theory_score = Decimal('0')

#                 # Create or update exam result
#                 exam_result, created = ExamResult.objects.update_or_create(
#                     student=student,
#                     subject=subject,
#                     session=session,
#                     term=term,
#                     defaults={
#                         'ca_score': ca_score,
#                         'theory_score': theory_score,
#                         'exam_score': Decimal(str(data['exam_score'])),
#                         'total_exam_questions': data['total_questions'],
#                         'submitted_at': data.get('submitted_at'),
#                         'uploaded_by': request.user.userprofile
#                     }
#                 )

#                 if created:
#                     created_count += 1
#                 else:
#                     updated_count += 1

#             except Exception as e:
#                 errors.append({
#                     'row': idx,
#                     'admission_number': row.get('admission_number', 'N/A'),
#                     'errors': str(e)
#                 })

#     # Calculate positions after all results are uploaded
#     _calculate_class_positions(session, term)

#     return Response({
#         'success': True,
#         'message': f'Processed {len(rows)} results',
#         'created': created_count,
#         'updated': updated_count,
#         'missing_ca_scores': missing_ca_scores if missing_ca_scores else None,
#         'errors': errors if errors else None
#     })


# def _calculate_class_positions(session, term):
#     """Calculate positions within each class/subject"""
#     # Get all results for this session/term
#     results = ExamResult.objects.filter(session=session, term=term)

#     # Group by class and subject
#     class_subject_groups = {}
#     for result in results:
#         key = (result.student.class_level_id, result.subject_id)
#         if key not in class_subject_groups:
#             class_subject_groups[key] = []
#         class_subject_groups[key].append(result)

#     # Calculate positions for each group
#     for key, group_results in class_subject_groups.items():
#         # Sort by total score descending
#         sorted_results = sorted(group_results, key=lambda x: x.total_score, reverse=True)

#         total_students = len(sorted_results)
#         scores = [r.total_score for r in sorted_results]
#         avg_score = sum(scores) / total_students if total_students > 0 else 0
#         highest = max(scores) if scores else 0
#         lowest = min(scores) if scores else 0

#         # Assign positions
#         for position, result in enumerate(sorted_results, start=1):
#             result.position = position
#             result.class_average = avg_score
#             result.total_students = total_students
#             result.highest_score = highest
#             result.lowest_score = lowest
#             result.save()


# # ============================================
# # STUDENT PROMOTION SYSTEM
# # ============================================

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def get_promotion_data(request):
#     """
#     Get students eligible for promotion with their cumulative averages

#     Query params:
#     - class_level: Current class (e.g., 'JSS1')
#     - session_id: Academic session ID
#     """
#     class_level_name = request.query_params.get('class_level')
#     session_id = request.query_params.get('session_id')

#     if not class_level_name or not session_id:
#         return Response(
#             {'error': 'class_level and session_id are required'},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     try:
#         class_level = ClassLevel.objects.get(name=class_level_name)
#         session = AcademicSession.objects.get(id=session_id)
#     except (ClassLevel.DoesNotExist, AcademicSession.DoesNotExist):
#         return Response(
#             {'error': 'Invalid class_level or session'},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     # Get all students in this class
#     students = ActiveStudent.objects.filter(
#         class_level=class_level,
#         is_active=True
#     )

#     # Get all terms for this session
#     terms = Term.objects.filter(session=session).order_by('id')

#     promotion_data = []

#     for student in students:
#         # Get results for each term
#         term_averages = []
#         all_scores = []
#         subjects_count = 0

#         for term in terms:
#             results = ExamResult.objects.filter(
#                 student=student,
#                 session=session,
#                 term=term
#             )

#             if results.exists():
#                 term_avg = results.aggregate(avg=Avg('total_score'))['avg']
#                 term_averages.append(term_avg)
#                 all_scores.extend([r.total_score for r in results])
#                 subjects_count = max(subjects_count, results.count())

#         # Calculate cumulative average
#         cumulative_avg = sum(all_scores) / len(all_scores) if all_scores else 0

#         # Determine if passed (average >= 50)
#         passed = cumulative_avg >= 50

#         promotion_data.append({
#             'student_id': student.id,
#             'admission_number': student.admission_number,
#             'full_name': f"{student.first_name} {student.last_name}",
#             'current_class': class_level_name,
#             'term1_average': term_averages[0] if len(term_averages) > 0 else None,
#             'term2_average': term_averages[1] if len(term_averages) > 1 else None,
#             'term3_average': term_averages[2] if len(term_averages) > 2 else None,
#             'cumulative_average': round(cumulative_avg, 2),
#             'passed': passed,
#             'subjects_count': subjects_count
#         })

#     # Sort by cumulative average descending
#     promotion_data.sort(key=lambda x: x['cumulative_average'], reverse=True)

#     # Get next class level
#     next_class = _get_next_class_level(class_level_name)

#     return Response({
#         'success': True,
#         'class_level': class_level_name,
#         'next_class': next_class,
#         'session': session.name,
#         'total_students': len(promotion_data),
#         'passed_count': sum(1 for s in promotion_data if s['passed']),
#         'failed_count': sum(1 for s in promotion_data if not s['passed']),
#         'students': promotion_data
#     })


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def promote_students(request):
#     """
#     Bulk promote selected students to next class

#     POST data:
#     {
#         "student_ids": [1, 2, 3, 5],
#         "from_class": "JSS1",
#         "to_class": "JSS2",
#         "session_id": 1
#     }
#     """
#     serializer = BulkPromotionSerializer(data=request.data)

#     if not serializer.is_valid():
#         return Response(
#             {'error': 'Invalid data', 'details': serializer.errors},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     data = serializer.validated_data

#     try:
#         from_class = ClassLevel.objects.get(name=data['from_class'])
#         to_class = ClassLevel.objects.get(name=data['to_class'])
#     except ClassLevel.DoesNotExist:
#         return Response(
#             {'error': 'Invalid class level'},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     # Validate class progression
#     valid_progressions = {
#         'JSS1': 'JSS2',
#         'JSS2': 'JSS3',
#         'JSS3': 'SS1',
#         'SS1': 'SS2',
#         'SS2': 'SS3',
#         'SS3': 'GRADUATED'
#     }

#     if valid_progressions.get(data['from_class']) != data['to_class']:
#         return Response(
#             {'error': f"Invalid progression: {data['from_class']} -> {data['to_class']}"},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     # Promote students
#     promoted_count = 0
#     graduated_count = 0
#     errors = []

#     with transaction.atomic():
#         for student_id in data['student_ids']:
#             try:
#                 student = ActiveStudent.objects.get(
#                     id=student_id,
#                     class_level=from_class,
#                     is_active=True
#                 )

#                 if data['to_class'] == 'GRADUATED':
#                     # Mark as graduated
#                     student.is_active = False
#                     student.graduation_date = timezone.now().date()
#                     student.save()
#                     graduated_count += 1
#                 else:
#                     # Promote to next class
#                     student.class_level = to_class
#                     student.save()
#                     promoted_count += 1

#             except ActiveStudent.DoesNotExist:
#                 errors.append({
#                     'student_id': student_id,
#                     'error': 'Student not found or not in expected class'
#                 })

#     return Response({
#         'success': True,
#         'message': f'Promotion complete',
#         'promoted': promoted_count,
#         'graduated': graduated_count,
#         'errors': errors if errors else None
#     })


# def _get_next_class_level(current_class):
#     """Get the next class level for promotion"""
#     progression = {
#         'JSS1': 'JSS2',
#         'JSS2': 'JSS3',
#         'JSS3': 'SS1',
#         'SS1': 'SS2',
#         'SS2': 'SS3',
#         'SS3': 'GRADUATED'
#     }
#     return progression.get(current_class, 'UNKNOWN')


# # ============================================
# # GET CA SCORES
# # ============================================

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def get_ca_scores(request):
#     """Get CA scores with filters"""
#     session_id = request.query_params.get('session_id')
#     term_id = request.query_params.get('term_id')
#     class_level = request.query_params.get('class_level')
#     subject_id = request.query_params.get('subject_id')

#     queryset = CAScore.objects.select_related(
#         'student', 'subject', 'session', 'term'
#     ).all()

#     if session_id:
#         queryset = queryset.filter(session_id=session_id)
#     if term_id:
#         queryset = queryset.filter(term_id=term_id)
#     if class_level:
#         queryset = queryset.filter(student__class_level__name=class_level)
#     if subject_id:
#         queryset = queryset.filter(subject_id=subject_id)

#     serializer = CAScoreSerializer(queryset, many=True)

#     return Response({
#         'success': True,
#         'count': queryset.count(),
#         'ca_scores': serializer.data
#     })


# # ============================================
# # GET EXAM RESULTS
# # ============================================

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def get_exam_results(request):
#     """Get exam results with filters"""
#     session_id = request.query_params.get('session_id')
#     term_id = request.query_params.get('term_id')
#     class_level = request.query_params.get('class_level')
#     subject_id = request.query_params.get('subject_id')

#     queryset = ExamResult.objects.select_related(
#         'student', 'subject', 'session', 'term'
#     ).all()

#     if session_id:
#         queryset = queryset.filter(session_id=session_id)
#     if term_id:
#         queryset = queryset.filter(term_id=term_id)
#     if class_level:
#         queryset = queryset.filter(student__class_level__name=class_level)
#     if subject_id:
#         queryset = queryset.filter(subject_id=subject_id)

#     serializer = ExamResultSerializer(queryset, many=True)

#     return Response({
#         'success': True,
#         'count': queryset.count(),
#         'results': serializer.data
#     })