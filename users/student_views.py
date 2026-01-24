# import csv
# import io
# import logging
# from datetime import datetime

# from django.http import HttpResponse
# from django_filters.rest_framework import DjangoFilterBackend
# from rest_framework import filters, status, viewsets
# from rest_framework.decorators import action
# from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
# from rest_framework.permissions import AllowAny, IsAuthenticated
# from rest_framework.response import Response
# from rest_framework.views import APIView

# from .models import (
#     AcademicSession,
#     ActiveStudent,
#     CAScore,
#     ClassLevel,
#     ExamResult,
#     Subject,
#     Term,
# )
# from .permissions import IsAdminOrSuperAdmin
# from .serializers import (
#     AcademicSessionSerializer,
#     ActiveStudentSerializer,
#     ActiveStudentWriteSerializer,
#     CAScoreBulkUploadSerializer,
#     CAScoreSerializer,
#     ClassLevelSerializer,
#     ExamResultBulkUploadSerializer,
#     ExamResultSerializer,
#     StudentBulkUploadSerializer,
#     StudentCredentialsSerializer,
#     StudentLoginSerializer,
#     StudentProfileUpdateSerializer,
#     SubjectSerializer,
#     TermSerializer,
# )
# from .utils import calculate_grade, calculate_position_and_stats

# logger = logging.getLogger(__name__)


# # ============================================================
# # ACADEMIC MANAGEMENTT VIEWS
# # ============================================================


# class AcademicSessionViewSet(viewsets.ModelViewSet):
#     """CRUD for academic sessions"""

#     queryset = AcademicSession.objects.all()
#     serializer_class = AcademicSessionSerializer
#     permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
#     ordering = ["-start_date"]

#     @action(detail=True, methods=["post"], url_path="set-active")
#     def set_active(self, request, pk=None):
#         """Set this session as current"""
#         session = self.get_object()
#         AcademicSession.objects.all().update(is_current=False)
#         session.is_current = True
#         session.save()
#         return Response({"detail": "Session set as current"})


# class TermViewSet(viewsets.ModelViewSet):
#     """CRUD for terms"""

#     queryset = Term.objects.all()
#     serializer_class = TermSerializer
#     permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
#     filter_backends = [DjangoFilterBackend]
#     filterset_fields = ["session"]
#     ordering = ["session", "name"]

#     @action(detail=True, methods=["post"], url_path="set-active")
#     def set_active(self, request, pk=None):
#         """Set this term as current within its session"""
#         term = self.get_object()
#         Term.objects.filter(session=term.session).update(is_current=False)
#         term.is_current = True
#         term.save()
#         return Response({"detail": "Term set as current"})


# class ClassLevelViewSet(viewsets.ModelViewSet):
#     """CRUD for class levels"""

#     queryset = ClassLevel.objects.all()
#     serializer_class = ClassLevelSerializer
#     permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
#     ordering = ["order"]


# class SubjectViewSet(viewsets.ModelViewSet):
#     """CRUD for subjects"""

#     queryset = Subject.objects.all()
#     serializer_class = SubjectSerializer
#     permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
#     filter_backends = [filters.SearchFilter, DjangoFilterBackend]
#     search_fields = ["name", "code"]
#     filterset_fields = ["is_active"]


# # ============================================================
# # STUDENT MANAGEMENT VIEWS
# # ============================================================


# class ActiveStudentViewSet(viewsets.ModelViewSet):
#     """
#     CRUD for students with passport photo upload support.

#     Uses different serializers for read vs write operations:
#     - ActiveStudentSerializer for reading (returns passport URL)
#     - ActiveStudentWriteSerializer for creating/updating (accepts file uploads)
#     """

#     queryset = ActiveStudent.objects.all()
#     permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
#     parser_classes = [MultiPartParser, FormParser, JSONParser]
#     filter_backends = [
#         filters.SearchFilter,
#         DjangoFilterBackend,
#         filters.OrderingFilter,
#     ]
#     search_fields = ["admission_number", "first_name", "last_name", "email"]
#     filterset_fields = ["class_level", "gender", "is_active"]
#     ordering_fields = ["admission_number", "first_name", "created_at"]
#     ordering = ["admission_number"]

#     def get_serializer_class(self):
#         """
#         Switch serializer based on action:
#         - create/update/partial_update: use write serializer (accepts file uploads)
#         - list/retrieve: use read serializer (returns passport URL)
#         """
#         if self.action in ["create", "update", "partial_update"]:
#             return ActiveStudentWriteSerializer
#         return ActiveStudentSerializer

#     def create(self, request, *args, **kwargs):
#         """Create student with file upload support"""
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         instance = serializer.save(created_by=request.user)

#         # Return response using read serializer (includes passport URL)
#         read_serializer = ActiveStudentSerializer(instance)
#         return Response(read_serializer.data, status=status.HTTP_201_CREATED)

#     def update(self, request, *args, **kwargs):
#         """Update student with file upload support"""
#         partial = kwargs.pop("partial", False)
#         instance = self.get_object()
#         serializer = self.get_serializer(instance, data=request.data, partial=partial)
#         serializer.is_valid(raise_exception=True)
#         instance = serializer.save()

#         # Return response using read serializer (includes passport URL)
#         read_serializer = ActiveStudentSerializer(instance)
#         return Response(read_serializer.data)

#     def perform_create(self, serializer):
#         serializer.save(created_by=self.request.user)

#     @action(detail=False, methods=["get"])
#     def stats(self, request):
#         """Get student statistics"""
#         total = ActiveStudent.objects.count()
#         active = ActiveStudent.objects.filter(is_active=True).count()
#         inactive = total - active

#         return Response({"total": total, "active": active, "inactive": inactive})

#     @action(detail=False, methods=["post"], url_path="bulk-upload")
#     def bulk_upload(self, request):
#         """Bulk upload students via CSV"""
#         if "file" not in request.FILES:
#             return Response(
#                 {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         csv_file = request.FILES["file"]

#         try:
#             decoded_file = csv_file.read().decode("utf-8")
#         except UnicodeDecodeError:
#             return Response(
#                 {"error": "Invalid file encoding. Please save CSV as UTF-8."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         io_string = io.StringIO(decoded_file)
#         reader = csv.DictReader(io_string)

#         created_students = []
#         errors = []
#         row_num = 1

#         for row in reader:
#             row_num += 1
#             try:
#                 serializer = StudentBulkUploadSerializer(data=row)
#                 if not serializer.is_valid():
#                     errors.append(
#                         {
#                             "row": row_num,
#                             "error": f"Validation failed: {serializer.errors}",
#                         }
#                     )
#                     continue

#                 session = AcademicSession.objects.filter(is_current=True).first()
#                 if not session:
#                     errors.append(
#                         {"row": row_num, "error": "No current academic session set."}
#                     )
#                     continue

#                 class_level_name = serializer.validated_data["class_level"].upper()
#                 try:
#                     class_level = ClassLevel.objects.get(name=class_level_name)
#                 except ClassLevel.DoesNotExist:
#                     errors.append(
#                         {
#                             "row": row_num,
#                             "error": f"Invalid class level '{class_level_name}'",
#                         }
#                     )
#                     continue

#                 student = ActiveStudent(
#                     first_name=serializer.validated_data["first_name"].strip(),
#                     middle_name=serializer.validated_data.get("middle_name", "").strip()
#                     or None,
#                     last_name=serializer.validated_data["last_name"].strip(),
#                     date_of_birth=serializer.validated_data["date_of_birth"],
#                     gender=serializer.validated_data["gender"],
#                     class_level=class_level,
#                     enrollment_session=session,
#                     email=serializer.validated_data.get("email"),
#                     phone_number=serializer.validated_data.get(
#                         "phone_number", ""
#                     ).strip()
#                     or None,
#                     parent_name=serializer.validated_data.get("parent_name", "").strip()
#                     or None,
#                     parent_email=serializer.validated_data.get(
#                         "parent_email", ""
#                     ).strip()
#                     or None,
#                     parent_phone=serializer.validated_data.get(
#                         "parent_phone", ""
#                     ).strip()
#                     or None,
#                     address=serializer.validated_data.get("address", "").strip()
#                     or None,
#                     state_of_origin=serializer.validated_data.get(
#                         "state_of_origin", ""
#                     ).strip()
#                     or None,
#                     local_govt_area=serializer.validated_data.get(
#                         "local_govt_area", ""
#                     ).strip()
#                     or None,
#                     is_active=True,
#                     created_by=request.user,
#                 )
#                 student.save()
#                 created_students.append(student.admission_number)

#             except Exception as e:
#                 errors.append({"row": row_num, "error": str(e)})

#         return Response(
#             {
#                 "created": len(created_students),
#                 "students": created_students,
#                 "errors": errors[:10] if errors else [],
#                 "total_errors": len(errors),
#             }
#         )

#     @action(detail=False, methods=["get"], url_path="export-csv")
#     def export_csv(self, request):
#         """Export all students as CSV"""
#         response = HttpResponse(content_type="text/csv")
#         response["Content-Disposition"] = 'attachment; filename="students_export.csv"'

#         writer = csv.writer(response)
#         writer.writerow(
#             [
#                 "admission_number",
#                 "first_name",
#                 "middle_name",
#                 "last_name",
#                 "date_of_birth",
#                 "gender",
#                 "email",
#                 "phone_number",
#                 "class_level",
#                 "enrollment_session",
#                 "is_active",
#                 "parent_name",
#                 "parent_email",
#                 "parent_phone",
#                 "address",
#                 "state_of_origin",
#                 "local_govt_area",
#             ]
#         )

#         students = ActiveStudent.objects.all().select_related(
#             "class_level", "enrollment_session"
#         )
#         for student in students:
#             writer.writerow(
#                 [
#                     student.admission_number,
#                     student.first_name,
#                     student.middle_name or "",
#                     student.last_name,
#                     student.date_of_birth,
#                     student.gender,
#                     student.email or "",
#                     student.phone_number or "",
#                     student.class_level.name if student.class_level else "",
#                     student.enrollment_session.name
#                     if student.enrollment_session
#                     else "",
#                     "Yes" if student.is_active else "No",
#                     student.parent_name or "",
#                     student.parent_email or "",
#                     student.parent_phone or "",
#                     student.address or "",
#                     student.state_of_origin or "",
#                     student.local_govt_area or "",
#                 ]
#             )

#         return response

#     @action(detail=False, methods=["get"], url_path="export-for-cbt")
#     def export_for_cbt(self, request):
#         """
#         Export students in CBT format.
#         Format: admission_number, first_name, middle_name, last_name, class_level, password_plain
#         """
#         response = HttpResponse(content_type="text/csv")
#         response["Content-Disposition"] = 'attachment; filename="students_for_cbt.csv"'

#         writer = csv.writer(response)
#         writer.writerow(
#             [
#                 "admission_number",
#                 "first_name",
#                 "middle_name",
#                 "last_name",
#                 "class_level",
#                 "password_plain",
#             ]
#         )

#         students = ActiveStudent.objects.filter(is_active=True).select_related(
#             "class_level"
#         )
#         for student in students:
#             writer.writerow(
#                 [
#                     student.admission_number,
#                     student.first_name,
#                     student.middle_name or "",
#                     student.last_name,
#                     student.class_level.name if student.class_level else "",
#                     student.password_plain or "",
#                 ]
#             )

#         return response

#     @action(detail=False, methods=["post"])
#     def promote(self, request):
#         """Promote students to next class level"""
#         student_ids = request.data.get("student_ids", [])

#         if not student_ids:
#             return Response(
#                 {"error": "No students selected"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         promoted = 0
#         graduated = 0
#         errors = []

#         for student_id in student_ids:
#             try:
#                 student = ActiveStudent.objects.get(id=student_id)
#                 current_order = student.class_level.order if student.class_level else 0

#                 if current_order >= 6:  # SS3
#                     student.is_active = False
#                     student.graduation_date = datetime.now().date()
#                     student.save()
#                     graduated += 1
#                 else:
#                     next_class = ClassLevel.objects.filter(
#                         order=current_order + 1
#                     ).first()
#                     if next_class:
#                         student.class_level = next_class
#                         student.save()
#                         promoted += 1
#                     else:
#                         errors.append(
#                             f"No next class level for student {student.admission_number}"
#                         )
#             except ActiveStudent.DoesNotExist:
#                 errors.append(f"Student with ID {student_id} not found")
#             except Exception as e:
#                 errors.append(str(e))

#         return Response(
#             {"promoted": promoted, "graduated": graduated, "errors": errors}
#         )


# # ============================================================
# # CA SCORE MANAGEMENT VIEWS
# # ============================================================


# class CAScoreViewSet(viewsets.ModelViewSet):
#     """CRUD for CA scores"""

#     queryset = CAScore.objects.all()
#     serializer_class = CAScoreSerializer
#     permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
#     filter_backends = [DjangoFilterBackend]
#     filterset_fields = ["student", "subject", "session", "term"]

#     @action(detail=False, methods=["post"], url_path="bulk-upload")
#     def bulk_upload(self, request):
#         """
#         Bulk upload CA scores via CSV.
#         Expected columns: admission_number, subject_code, subject_name, ca_score
#         """
#         if "file" not in request.FILES:
#             return Response(
#                 {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         session_id = request.data.get("session")
#         term_id = request.data.get("term")

#         if not session_id or not term_id:
#             return Response(
#                 {"error": "Session and term are required"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             session = AcademicSession.objects.get(id=session_id)
#             term = Term.objects.get(id=term_id)
#         except (AcademicSession.DoesNotExist, Term.DoesNotExist):
#             return Response(
#                 {"error": "Invalid session or term"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         csv_file = request.FILES["file"]

#         try:
#             decoded_file = csv_file.read().decode("utf-8")
#         except UnicodeDecodeError:
#             return Response(
#                 {"error": "Invalid file encoding. Please save CSV as UTF-8."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         io_string = io.StringIO(decoded_file)
#         reader = csv.DictReader(io_string)

#         created = 0
#         updated = 0
#         subjects_created = 0
#         errors = []
#         row_num = 1

#         for row in reader:
#             row_num += 1
#             try:
#                 serializer = CAScoreBulkUploadSerializer(data=row)
#                 if not serializer.is_valid():
#                     errors.append(
#                         {
#                             "row": row_num,
#                             "error": f"Validation failed: {serializer.errors}",
#                         }
#                     )
#                     continue

#                 admission_number = serializer.validated_data["admission_number"].upper()
#                 subject_code = serializer.validated_data["subject_code"].upper()
#                 subject_name = serializer.validated_data.get(
#                     "subject_name", subject_code
#                 )
#                 ca_score = serializer.validated_data["ca_score"]

#                 # Validate CA score
#                 if ca_score > 30:
#                     errors.append(
#                         {
#                             "row": row_num,
#                             "error": f"CA score {ca_score} exceeds maximum of 30",
#                         }
#                     )
#                     continue

#                 # Get student
#                 try:
#                     student = ActiveStudent.objects.get(
#                         admission_number=admission_number, is_active=True
#                     )
#                 except ActiveStudent.DoesNotExist:
#                     errors.append(
#                         {
#                             "row": row_num,
#                             "error": f"Student {admission_number} not found",
#                         }
#                     )
#                     continue

#                 # Get or create subject
#                 subject, subject_is_new = Subject.objects.get_or_create(
#                     code=subject_code,
#                     defaults={"name": subject_name, "is_active": True},
#                 )
#                 if subject_is_new:
#                     subjects_created += 1

#                 # Create or update CA score
#                 ca_obj, is_new = CAScore.objects.update_or_create(
#                     student=student,
#                     subject=subject,
#                     session=session,
#                     term=term,
#                     defaults={"score": ca_score, "uploaded_by": request.user},
#                 )

#                 if is_new:
#                     created += 1
#                 else:
#                     updated += 1

#             except Exception as e:
#                 errors.append({"row": row_num, "error": str(e)})

#         return Response(
#             {
#                 "created": created,
#                 "updated": updated,
#                 "subjects_created": subjects_created,
#                 "failed": len(errors),
#                 "errors": errors[:10],
#             }
#         )

#     @action(detail=False, methods=["get"], url_path="export-template")
#     def export_template(self, request):
#         """Export CA scores template CSV"""
#         response = HttpResponse(content_type="text/csv")
#         response["Content-Disposition"] = (
#             'attachment; filename="ca_scores_template.csv"'
#         )

#         writer = csv.writer(response)
#         writer.writerow(
#             ["admission_number", "subject_code", "subject_name", "ca_score"]
#         )
#         writer.writerow(["MOL/2026/001", "GNS101", "General Studies", "25"])
#         writer.writerow(["MOL/2026/002", "GNS101", "General Studies", "28"])

#         return response


# # ============================================================
# # EXAM RESULT MANAGEMENT VIEWS
# # ============================================================


# class ExamResultViewSet(viewsets.ModelViewSet):
#     """CRUD for exam results"""

#     queryset = ExamResult.objects.all()
#     serializer_class = ExamResultSerializer
#     permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
#     filter_backends = [DjangoFilterBackend]
#     filterset_fields = ["student", "subject", "session", "term"]

#     @action(detail=False, methods=["post"], url_path="bulk-import")
#     def bulk_import(self, request):
#         """
#         Bulk import exam results from CBT CSV.
#         Expected columns: admission_number, subject_code, subject_name, exam_score, submitted_at
#         """
#         if "file" not in request.FILES:
#             return Response(
#                 {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         session_id = request.data.get("session")
#         term_id = request.data.get("term")

#         if not session_id or not term_id:
#             return Response(
#                 {"error": "Session and term are required"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             session = AcademicSession.objects.get(id=session_id)
#             term = Term.objects.get(id=term_id)
#         except (AcademicSession.DoesNotExist, Term.DoesNotExist):
#             return Response(
#                 {"error": "Invalid session or term"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         csv_file = request.FILES["file"]

#         try:
#             decoded_file = csv_file.read().decode("utf-8")
#         except UnicodeDecodeError:
#             return Response(
#                 {"error": "Invalid file encoding. Please save CSV as UTF-8."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         io_string = io.StringIO(decoded_file)
#         reader = csv.DictReader(io_string)

#         created = 0
#         updated = 0
#         subjects_created = 0
#         errors = []
#         row_num = 1

#         for row in reader:
#             row_num += 1
#             try:
#                 serializer = ExamResultBulkUploadSerializer(data=row)
#                 if not serializer.is_valid():
#                     errors.append(
#                         {
#                             "row": row_num,
#                             "error": f"Validation failed: {serializer.errors}",
#                         }
#                     )
#                     continue

#                 admission_number = serializer.validated_data["admission_number"].upper()
#                 subject_code = serializer.validated_data["subject_code"].upper()
#                 subject_name = serializer.validated_data.get(
#                     "subject_name", subject_code
#                 )
#                 exam_score = serializer.validated_data["exam_score"]
#                 submitted_at = serializer.validated_data.get("submitted_at")

#                 # Validate exam score
#                 if exam_score > 70:
#                     errors.append(
#                         {
#                             "row": row_num,
#                             "error": f"Exam score {exam_score} exceeds maximum of 70",
#                         }
#                     )
#                     continue

#                 # Get student
#                 try:
#                     student = ActiveStudent.objects.get(
#                         admission_number=admission_number, is_active=True
#                     )
#                 except ActiveStudent.DoesNotExist:
#                     errors.append(
#                         {
#                             "row": row_num,
#                             "error": f"Student {admission_number} not found",
#                         }
#                     )
#                     continue

#                 # Get or create subject
#                 subject, subject_is_new = Subject.objects.get_or_create(
#                     code=subject_code,
#                     defaults={"name": subject_name, "is_active": True},
#                 )
#                 if subject_is_new:
#                     subjects_created += 1

#                 # Get CA score if exists
#                 ca_score = 0
#                 try:
#                     ca_obj = CAScore.objects.get(
#                         student=student, subject=subject, session=session, term=term
#                     )
#                     ca_score = ca_obj.score
#                 except CAScore.DoesNotExist:
#                     pass

#                 # Calculate totals
#                 total_score = ca_score + exam_score
#                 percentage = round((total_score / 100) * 100, 2)
#                 grade = calculate_grade(percentage)

#                 # Create or update exam result
#                 result, is_new = ExamResult.objects.update_or_create(
#                     student=student,
#                     subject=subject,
#                     session=session,
#                     term=term,
#                     defaults={
#                         "ca_score": ca_score,
#                         "exam_score": exam_score,
#                         "total_score": total_score,
#                         "percentage": percentage,
#                         "grade": grade,
#                         "submitted_at": submitted_at,
#                     },
#                 )

#                 if is_new:
#                     created += 1
#                 else:
#                     updated += 1

#             except Exception as e:
#                 errors.append({"row": row_num, "error": str(e)})

#         # After import, calculate positions for each subject
#         try:
#             calculate_position_and_stats(session, term)
#         except Exception as e:
#             logger.error(f"Failed to calculate positions: {e}")

#         return Response(
#             {
#                 "created": created,
#                 "updated": updated,
#                 "subjects_created": subjects_created,
#                 "failed": len(errors),
#                 "errors": errors[:10],
#             }
#         )


# # ============================================================
# # STUDENT PORTAL VIEWS
# # ============================================================


# class StudentLoginView(APIView):
#     """Student portal login"""

#     permission_classes = [AllowAny]

#     def post(self, request):
#         serializer = StudentLoginSerializer(data=request.data)
#         if serializer.is_valid():
#             student = serializer.validated_data["student"]
#             return Response(
#                 {
#                     "message": "Login successful",
#                     "student": ActiveStudentSerializer(student).data,
#                 }
#             )
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class StudentProfileView(APIView):
#     """Get/update student profile"""

#     permission_classes = [AllowAny]
#     parser_classes = [MultiPartParser, FormParser, JSONParser]

#     def get(self, request):
#         """Get student profile by admission number"""
#         admission_number = request.query_params.get("admission_number")
#         if not admission_number:
#             return Response(
#                 {"error": "Admission number required"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             student = ActiveStudent.objects.get(
#                 admission_number=admission_number.upper(), is_active=True
#             )
#         except ActiveStudent.DoesNotExist:
#             return Response(
#                 {"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND
#             )

#         return Response({"student": ActiveStudentSerializer(student).data})

#     def put(self, request):
#         """Update student profile"""
#         admission_number = request.data.get("admission_number")
#         if not admission_number:
#             return Response(
#                 {"error": "Admission number required"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             student = ActiveStudent.objects.get(
#                 admission_number=admission_number.upper(), is_active=True
#             )
#         except ActiveStudent.DoesNotExist:
#             return Response(
#                 {"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND
#             )

#         # Use StudentProfileUpdateSerializer for controlled updates
#         serializer = StudentProfileUpdateSerializer(
#             student, data=request.data, partial=True
#         )
#         if serializer.is_valid():
#             # Handle passport file upload separately
#             if "passport" in request.FILES:
#                 student.passport = request.FILES["passport"]

#             serializer.save()

#             # Return with full data including passport URL
#             return Response(
#                 {
#                     "message": "Profile updated successfully",
#                     "student": ActiveStudentSerializer(student).data,
#                 }
#             )

#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class StudentChangePasswordView(APIView):
#     """Change student password"""

#     permission_classes = [AllowAny]

#     def post(self, request):
#         from django.contrib.auth.hashers import check_password, make_password

#         admission_number = request.data.get("admission_number")
#         old_password = request.data.get("old_password")
#         new_password = request.data.get("new_password")

#         if not all([admission_number, old_password, new_password]):
#             return Response(
#                 {"error": "All fields required"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         try:
#             student = ActiveStudent.objects.get(
#                 admission_number=admission_number.upper(), is_active=True
#             )
#         except ActiveStudent.DoesNotExist:
#             return Response(
#                 {"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND
#             )

#         if not check_password(old_password, student.password_hash):
#             return Response(
#                 {"error": "Current password is incorrect"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         student.password_plain = new_password
#         student.password_hash = make_password(new_password)
#         student.save()

#         return Response(
#             {"message": "Password changed successfully"}, status=status.HTTP_200_OK
#         )


# class StudentGradesView(APIView):
#     """Get all grades for a student"""

#     permission_classes = [AllowAny]

#     def get(self, request):
#         admission_number = request.query_params.get("admission_number")
#         if not admission_number:
#             return Response(
#                 {"error": "Admission number required"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             student = ActiveStudent.objects.get(
#                 admission_number=admission_number.upper(), is_active=True
#             )
#         except ActiveStudent.DoesNotExist:
#             return Response(
#                 {"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND
#             )

#         results = (
#             ExamResult.objects.filter(student=student)
#             .select_related("subject", "session", "term")
#             .order_by("-session__start_date", "term__name")
#         )

#         return Response({"grades": ExamResultSerializer(results, many=True).data})


# class StudentCAScoresView(APIView):
#     """Get CA scores for a student"""

#     permission_classes = [AllowAny]

#     def get(self, request):
#         admission_number = request.query_params.get("admission_number")
#         session_id = request.query_params.get("session")
#         term_id = request.query_params.get("term")

#         if not admission_number:
#             return Response(
#                 {"error": "Admission number required"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             student = ActiveStudent.objects.get(
#                 admission_number=admission_number.upper(), is_active=True
#             )
#         except ActiveStudent.DoesNotExist:
#             return Response(
#                 {"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND
#             )

#         ca_scores = CAScore.objects.filter(student=student)
#         if session_id:
#             ca_scores = ca_scores.filter(session_id=session_id)
#         if term_id:
#             ca_scores = ca_scores.filter(term_id=term_id)

#         ca_scores = ca_scores.select_related("subject", "session", "term").order_by(
#             "-session__start_date"
#         )

#         return Response({"ca_scores": CAScoreSerializer(ca_scores, many=True).data})


# class StudentExamResultsView(APIView):
#     """Get exam results for a student"""

#     permission_classes = [AllowAny]

#     def get(self, request):
#         admission_number = request.query_params.get("admission_number")
#         session_id = request.query_params.get("session")
#         term_id = request.query_params.get("term")

#         if not admission_number:
#             return Response(
#                 {"error": "Admission number required"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             student = ActiveStudent.objects.get(
#                 admission_number=admission_number.upper(), is_active=True
#             )
#         except ActiveStudent.DoesNotExist:
#             return Response(
#                 {"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND
#             )

#         results = ExamResult.objects.filter(student=student)
#         if session_id:
#             results = results.filter(session_id=session_id)
#         if term_id:
#             results = results.filter(term_id=term_id)

#         results = results.select_related("subject", "session", "term").order_by(
#             "-session__start_date"
#         )

#         return Response({"exam_results": ExamResultSerializer(results, many=True).data})


# class StudentReportCardView(APIView):
#     """Get comprehensive report card"""

#     permission_classes = [AllowAny]

#     def get(self, request):
#         admission_number = request.query_params.get("admission_number")
#         session_id = request.query_params.get("session")
#         term_id = request.query_params.get("term")

#         if not all([admission_number, session_id, term_id]):
#             return Response(
#                 {"error": "Admission number, session, and term required"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             student = ActiveStudent.objects.get(
#                 admission_number=admission_number.upper(), is_active=True
#             )
#             session = AcademicSession.objects.get(id=session_id)
#             term = Term.objects.get(id=term_id)
#         except (
#             ActiveStudent.DoesNotExist,
#             AcademicSession.DoesNotExist,
#             Term.DoesNotExist,
#         ):
#             return Response(
#                 {"error": "Invalid parameters"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         results = ExamResult.objects.filter(
#             student=student, session=session, term=term
#         ).select_related("subject")

#         if not results.exists():
#             return Response(
#                 {
#                     "session": session.name,
#                     "term": term.name,
#                     "student_class": student.class_level.name
#                     if student.class_level
#                     else "",
#                     "results": [],
#                     "total_score": 0,
#                     "average_percentage": 0,
#                 }
#             )

#         total_score = sum(r.total_score for r in results)
#         average = round(total_score / len(results), 2)

#         return Response(
#             {
#                 "session": session.name,
#                 "term": term.name,
#                 "student_class": student.class_level.name
#                 if student.class_level
#                 else "",
#                 "results": ExamResultSerializer(results, many=True).data,
#                 "total_score": total_score,
#                 "average_percentage": average,
#             }
#         )


# class StudentSessionsView(APIView):
#     """Get all academic sessions"""

#     permission_classes = [AllowAny]

#     def get(self, request):
#         sessions = AcademicSession.objects.all().order_by("-start_date")
#         return Response(
#             {"sessions": AcademicSessionSerializer(sessions, many=True).data}
#         )


# class StudentTermsView(APIView):
#     """Get all terms"""

#     permission_classes = [AllowAny]

#     def get(self, request):
#         terms = (
#             Term.objects.all()
#             .select_related("session")
#             .order_by("-session__start_date", "name")
#         )
#         return Response({"terms": TermSerializer(terms, many=True).data})
