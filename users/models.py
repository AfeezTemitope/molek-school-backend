"""
MOLEK School - Database Models
Updated with Nigerian Secondary School Grading Structure:
- CA1: 15 marks (manual)
- CA2: 15 marks (manual)
- OBJ/CBT: 30 marks (from CBT system)
- Theory: 40 marks (manual)
- Total: 100 marks
"""
from datetime import datetime
from django.contrib.auth.hashers import make_password
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from cloudinary.models import CloudinaryField
from django.core.validators import MinValueValidator, MaxValueValidator


# ==============================================================================
# USER PROFILE (ADMIN/SUPERADMIN)
# ==============================================================================

class UserProfileManager(BaseUserManager):
    """Custom manager for UserProfile model"""
    
    def create_user(self, username, email, first_name, last_name, role='admin', phone_number=None, password=None):
        if not username:
            raise ValueError('Username is required')
        if role not in ['admin', 'superadmin']:
            raise ValueError('Role must be admin or superadmin')
        
        email = self.normalize_email(email)
        user = self.model(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            phone_number=phone_number
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, username, email, first_name, last_name, password, role='superadmin', phone_number=None):
        user = self.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            phone_number=phone_number,
            password=password
        )
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class UserProfile(AbstractBaseUser, PermissionsMixin):
    """Admin/SuperAdmin user model"""
    
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('superadmin', 'Superadmin'),
    )
    SEX_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
    )
    
    username = models.CharField(max_length=150, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    age = models.PositiveIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES, null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    state_of_origin = models.CharField(max_length=100, blank=True, null=True)
    local_govt_area = models.CharField(max_length=100, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin', db_index=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserProfileManager()
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']
    
    class Meta:
        indexes = [
            models.Index(fields=['role', 'is_active'], name='userprofile_role_active_idx'),
            models.Index(fields=['created_at'], name='userprofile_created_idx'),
        ]
        verbose_name = "Admin User"
        verbose_name_plural = "Admin Users"
    
    def __str__(self):
        return f"{self.full_name} ({self.role})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


# ==============================================================================
# LEGACY STUDENT MODEL - DO NOT USE
# ==============================================================================

class Student(models.Model):
    """DEPRECATED - Preserved for database compatibility only"""
    
    CLASS_LEVEL_CHOICES = (
        ('JSS1', 'Junior Secondary 1'),
        ('JSS2', 'Junior Secondary 2'),
        ('JSS3', 'Junior Secondary 3'),
        ('SS1', 'Senior Secondary 1'),
        ('SS2', 'Senior Secondary 2'),
        ('SS3', 'Senior Secondary 3'),
    )
    STREAM_CHOICES = (
        ('Science', 'Science'),
        ('Commercial', 'Commercial'),
        ('Art', 'Art'),
        ('General', 'General'),
    )
    SECTION_CHOICES = (
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
    )
    SEX_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
    )
    
    first_name = models.CharField(max_length=150, null=True)
    last_name = models.CharField(max_length=150, null=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES, null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    state_of_origin = models.CharField(max_length=100, blank=True, null=True)
    local_govt_area = models.CharField(max_length=100, blank=True, null=True)
    admission_number = models.CharField(max_length=50, unique=True)
    class_level = models.CharField(max_length=10, choices=CLASS_LEVEL_CHOICES)
    stream = models.CharField(max_length=20, choices=STREAM_CHOICES, blank=True, null=True)
    section = models.CharField(max_length=1, choices=SECTION_CHOICES, blank=True, null=True)
    parent_email = models.EmailField(blank=True, null=True)
    parent_phone_number = models.CharField(max_length=15, blank=True, null=True)
    passport = CloudinaryField('image', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    user = models.OneToOneField(
        UserProfile, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='student_profile'
    )
    created_by = models.ForeignKey(
        UserProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='students_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        managed = False
        db_table = 'users_student'
    
    def __str__(self):
        return f"{self.full_name} ({self.admission_number})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


# ==============================================================================
# CBT INTEGRATION MODELS - MOLEK SCHOOL
# ==============================================================================

class AcademicSession(models.Model):
    """Academic year (e.g., 2024/2025)"""
    
    name = models.CharField(max_length=20, unique=True, db_index=True)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['is_current', 'start_date'], name='session_current_start_idx'),
        ]
        verbose_name = "Academic Session"
        verbose_name_plural = "Academic Sessions"
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicSession.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)


class Term(models.Model):
    """School terms within an academic session"""
    
    TERM_CHOICES = [
        ('First Term', 'First Term'),
        ('Second Term', 'Second Term'),
        ('Third Term', 'Third Term'),
    ]
    
    session = models.ForeignKey(
        AcademicSession, 
        on_delete=models.CASCADE, 
        related_name='terms',
        db_index=True
    )
    name = models.CharField(max_length=20, choices=TERM_CHOICES, db_index=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['session', 'name']
        unique_together = ['session', 'name']
        indexes = [
            models.Index(fields=['session', 'is_current'], name='term_session_current_idx'),
        ]
        verbose_name = "Term"
        verbose_name_plural = "Terms"
    
    def __str__(self):
        return f"{self.session.name} - {self.name}"
    
    def save(self, *args, **kwargs):
        if self.is_current:
            Term.objects.filter(session=self.session, is_current=True).update(is_current=False)
        super().save(*args, **kwargs)
    
    @property
    def term_number(self):
        """Return term number (1, 2, or 3)"""
        term_map = {
            'First Term': 1,
            'Second Term': 2,
            'Third Term': 3
        }
        return term_map.get(self.name, 0)


class ClassLevel(models.Model):
    """Class levels (JSS1-SS3)"""
    
    CLASS_CHOICES = [
        ('JSS1', 'Junior Secondary 1'),
        ('JSS2', 'Junior Secondary 2'),
        ('JSS3', 'Junior Secondary 3'),
        ('SS1', 'Senior Secondary 1'),
        ('SS2', 'Senior Secondary 2'),
        ('SS3', 'Senior Secondary 3'),
    ]
    
    name = models.CharField(max_length=10, choices=CLASS_CHOICES, unique=True, db_index=True)
    order = models.IntegerField(unique=True, db_index=True)
    description = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['order']
        verbose_name = "Class Level"
        verbose_name_plural = "Class Levels"
    
    def __str__(self):
        return self.name


class Subject(models.Model):
    """School subjects"""
    
    name = models.CharField(max_length=100, db_index=True)
    code = models.CharField(max_length=20, unique=True, db_index=True)
    description = models.TextField(blank=True)
    class_levels = models.ManyToManyField(ClassLevel, related_name='subjects', blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'name'], name='subject_active_name_idx'),
        ]
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class ActiveStudent(models.Model):
    """
    Active Student Model for CBT Integration
    
    This is the main student model used by the CBT system.
    """
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]
    
    # Basic Information
    admission_number = models.CharField(max_length=50, unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    
    # Authentication
    password_plain = models.CharField(max_length=20, blank=True)
    password_hash = models.CharField(max_length=128, blank=True)
    
    # Demographics
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    
    # Contact
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    state_of_origin = models.CharField(max_length=100, blank=True, null=True)
    local_govt_area = models.CharField(max_length=100, blank=True, null=True)
    
    # Academic
    class_level = models.ForeignKey(
        ClassLevel, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='students',
        db_index=True
    )
    subjects = models.ManyToManyField(Subject, related_name='students', blank=True)
    enrollment_session = models.ForeignKey(
        AcademicSession, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='enrolled_students'
    )
    
    # Parent/Guardian
    parent_name = models.CharField(max_length=200, blank=True, null=True)
    parent_email = models.EmailField(blank=True, null=True)
    parent_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Photo
    passport = CloudinaryField('image', blank=True, null=True)
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    graduation_date = models.DateField(null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        UserProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='students_enrolled'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['admission_number']
        indexes = [
            models.Index(fields=['class_level', 'is_active'], name='student_class_active_idx'),
            models.Index(fields=['is_active', 'created_at'], name='student_active_created_idx'),
            models.Index(fields=['first_name', 'last_name'], name='student_name_idx'),
        ]
        verbose_name = "Student"
        verbose_name_plural = "Students"
    
    def __str__(self):
        return f"{self.full_name} ({self.admission_number})"
    
    @property
    def full_name(self):
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return ' '.join(parts)
    
    def save(self, *args, **kwargs):
        if not self.admission_number:
            from .utils import generate_admission_number, generate_password
            
            self.admission_number = generate_admission_number()
            
            if not self.password_plain:
                self.password_plain = generate_password()
            
            self.password_hash = make_password(self.password_plain)
        
        super().save(*args, **kwargs)


# ==============================================================================
# FLEXIBLE GRADING MODELS
# CA1 + CA2 + OBJ/CBT (RAW) + Theory = Total
# Admin configures max marks for each component
# ==============================================================================

class CAScore(models.Model):
    """
    Continuous Assessment Score Model (CA1 + CA2)
    
    Flexible Grading - Admin configures max marks:
    - CA1: Flexible marks (e.g., 15 marks - manual entry)
    - CA2: Flexible marks (e.g., 15 marks - manual entry)
    - Can also be used for CBT-based CA if needed
    """
    
    student = models.ForeignKey(
        ActiveStudent,
        on_delete=models.CASCADE,
        related_name='ca_scores',
        db_index=True
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='ca_scores',
        db_index=True
    )
    session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name='ca_scores',
        db_index=True
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        related_name='ca_scores',
        db_index=True
    )
    
    # CA1 Score (flexible marks, e.g., 15)
    ca1_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="First Continuous Assessment score (flexible marks)",
        default=0
    )
    
    # CA2 Score (flexible marks, e.g., 15)
    ca2_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Second Continuous Assessment score (flexible marks)",
        default=0
    )
    
    uploaded_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_ca_scores'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'subject', 'session', 'term')
        indexes = [
            models.Index(fields=['session', 'term'], name='cascore_session_term_idx'),
            models.Index(fields=['student', 'session'], name='cascore_student_session_idx'),
        ]
        verbose_name = 'CA Score (CA1 + CA2)'
        verbose_name_plural = 'CA Scores'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.student.admission_number} - {self.subject.name}: CA1={self.ca1_score}, CA2={self.ca2_score}"
    
    @property
    def total_ca_score(self):
        """CA1 + CA2 combined score (max 30)"""
        return (self.ca1_score or 0) + (self.ca2_score or 0)


class ExamResult(models.Model):
    """
    Final Exam Result Model
    
    Flexible Grading Structure - Admin configures max marks:
    - CA1: Flexible marks (from CAScore model)
    - CA2: Flexible marks (from CAScore model)
    - OBJ/CBT: RAW score from CBT (no max - equals correct answers)
    - Theory: Flexible marks (manual entry by teacher)
    - Total: Sum of all components
    
    OBJ Score Example:
    - 20 questions, student gets 15 correct → obj_score = 15
    - total_obj_questions = 20 (for reference)
    
    Grading Scale (applied to total):
    - A: 75-100 (Excellent)
    - B: 70-74 (Very Good)
    - C: 60-69 (Good)
    - D: 50-59 (Pass)
    - E: 45-49 (Fair)
    - F: 0-44 (Fail)
    """
    
    student = models.ForeignKey(
        ActiveStudent,
        on_delete=models.CASCADE,
        related_name='exam_results',
        db_index=True
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='exam_results',
        db_index=True
    )
    session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name='exam_results',
        db_index=True
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        related_name='exam_results',
        db_index=True
    )
    
    # =====================
    # SCORE COMPONENTS (All flexible - admin decides max values)
    # =====================
    
    # CA1 Score - copied from CAScore (flexible, e.g., 15 marks)
    ca1_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="First Continuous Assessment (flexible marks)",
        default=0
    )
    
    # CA2 Score - copied from CAScore (flexible, e.g., 15 marks)
    ca2_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Second Continuous Assessment (flexible marks)",
        default=0
    )
    
    # OBJ/CBT Score - RAW score from CBT (no max limit)
    # Score = number of correct answers (e.g., 15 out of 20 questions = 15)
    obj_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Objective/CBT RAW score (equals correct answers, no scaling)",
        default=0
    )
    
    # Theory Score - manual entry (flexible, e.g., 40 marks)
    theory_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Theory/Essay score (flexible marks)",
        default=0
    )
    
    # CBT metadata - tracks how many questions were in the exam
    total_obj_questions = models.IntegerField(
        default=0,
        help_text="Total MCQ questions in the CBT exam"
    )
    
    # =====================
    # CALCULATED FIELDS
    # =====================
    
    # Total Score (CA1 + CA2 + OBJ + Theory = 100)
    total_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="CA1 + CA2 + OBJ + Theory (max 100)",
        default=0
    )
    
    # Grade (A, B, C, D, E, F)
    grade = models.CharField(
        max_length=2,
        help_text="Grade based on Nigerian grading scale",
        db_index=True,
        default='F'
    )
    
    # Grade Remark
    remark = models.CharField(
        max_length=20,
        help_text="Grade remark (Excellent, Very Good, Good, Pass, Fair, Fail)",
        default='Fail'
    )
    
    # =====================
    # CLASS STATISTICS
    # =====================
    
    position = models.IntegerField(null=True, blank=True, help_text="Position in class for this subject")
    class_average = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_students = models.IntegerField(null=True, blank=True)
    highest_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    lowest_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # =====================
    # CUMULATIVE SCORES (for report cards)
    # =====================
    
    # Store previous term totals for cumulative calculation
    first_term_total = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="First term total (for cumulative calculation)"
    )
    second_term_total = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Second term total (for cumulative calculation)"
    )
    third_term_total = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Third term total (for cumulative calculation)"
    )
    
    # Cumulative score (average of available terms)
    cumulative_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cumulative average across terms"
    )
    cumulative_grade = models.CharField(
        max_length=2,
        blank=True,
        null=True,
        help_text="Grade based on cumulative score"
    )
    
    # =====================
    # METADATA
    # =====================
    
    submitted_at = models.DateTimeField(null=True, blank=True, help_text="CBT submission timestamp")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    uploaded_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True
    )
    
    class Meta:
        unique_together = ('student', 'subject', 'session', 'term')
        indexes = [
            models.Index(fields=['session', 'term'], name='examresult_session_term_idx'),
            models.Index(fields=['student', 'session'], name='examresult_student_session_idx'),
            models.Index(fields=['session', 'term', 'grade'], name='examresult_grade_idx'),
        ]
        verbose_name = 'Exam Result'
        verbose_name_plural = 'Exam Results'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.student.admission_number} - {self.subject.name}: {self.total_score} ({self.grade})"
    
    def save(self, *args, **kwargs):
        # Auto-calculate total score
        self.total_score = (
            (self.ca1_score or 0) +
            (self.ca2_score or 0) +
            (self.obj_score or 0) +
            (self.theory_score or 0)
        )
        
        # Auto-calculate grade and remark
        self.grade, self.remark = self.calculate_grade(self.total_score)
        
        # Calculate cumulative score if we have term data
        self._calculate_cumulative()
        
        super().save(*args, **kwargs)
    
    def _calculate_cumulative(self):
        """
        Calculate cumulative score based on all term totals within the same session.
        
        Logic per the spec:
        - First Term:  cumulative = Term1 total (out of 100)
        - Second Term: cumulative = (Term1 + Term2) / 2
        - Third Term:  cumulative = (Term1 + Term2 + Term3) / 3
        
        This method queries the database for prior term results
        to ensure accuracy even when saving a new term's result.
        """
        from .models import ExamResult, Term  # Local import to avoid circular
    
        term_name = self.term.name if self.term else ''
        current_total = float(self.total_score)
    
        # Always reset term total fields based on current term
        if term_name == 'First Term':
            self.first_term_total = self.total_score
        elif term_name == 'Second Term':
            self.second_term_total = self.total_score
        elif term_name == 'Third Term':
            self.third_term_total = self.total_score
    
        # Query database for other terms' results in the same session
        # for the same student and subject
        if self.student_id and self.subject_id and self.session_id:
            other_results = ExamResult.objects.filter(
                student_id=self.student_id,
                subject_id=self.subject_id,
                session_id=self.session_id,
            ).exclude(
                pk=self.pk  # Exclude current record (may not exist yet if creating)
            ).select_related('term')
    
            for result in other_results:
                if result.term.name == 'First Term':
                    self.first_term_total = result.total_score
                elif result.term.name == 'Second Term':
                    self.second_term_total = result.total_score
                elif result.term.name == 'Third Term':
                    self.third_term_total = result.total_score
    
        # Collect all available term scores
        term_scores = []
        if self.first_term_total is not None:
            term_scores.append(float(self.first_term_total))
        if self.second_term_total is not None:
            term_scores.append(float(self.second_term_total))
        if self.third_term_total is not None:
            term_scores.append(float(self.third_term_total))
    
        # Calculate cumulative as AVERAGE of available terms
        if term_scores:
            self.cumulative_score = sum(term_scores) / len(term_scores)
            self.cumulative_grade, _ = self.calculate_grade(self.cumulative_score)
        else:
            self.cumulative_score = current_total
            self.cumulative_grade, _ = self.calculate_grade(current_total)
    
    @staticmethod
    def calculate_grade(score):
        """
        Calculate grade based on Nigerian Secondary School grading scale
        
        Returns: (grade, remark) tuple
        """
        score = float(score) if score else 0
        
        if score >= 75:
            return ('A', 'Excellent')
        elif score >= 70:
            return ('B', 'Very Good')
        elif score >= 60:
            return ('C', 'Good')
        elif score >= 50:
            return ('D', 'Pass')
        elif score >= 45:
            return ('E', 'Fair')
        else:
            return ('F', 'Fail')
    
    @property
    def total_ca(self):
        """Combined CA score (CA1 + CA2)"""
        return (self.ca1_score or 0) + (self.ca2_score or 0)
    
    @property
    def exam_total(self):
        """Combined exam score (OBJ + Theory)"""
        return (self.obj_score or 0) + (self.theory_score or 0)


# ==============================================================================
# PROMOTION RULES (CONFIGURABLE)
# ==============================================================================

class PromotionRule(models.Model):
    """
    Configurable promotion rules for Nigerian Secondary Schools
    
    Default: Student must pass Math + English + 5 other subjects with >= 50%
    """
    
    PROMOTION_MODE_CHOICES = [
        ('auto', 'Automatic (system decides)'),
        ('recommend', 'Recommend (admin approves)'),
        ('manual', 'Manual (admin decides)'),
    ]
    
    session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name='promotion_rules'
    )
    
    # Class level (NULL = applies to all classes)
    class_level = models.ForeignKey(
        ClassLevel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Leave blank to apply to all classes"
    )
    
    # Pass mark configuration
    pass_mark_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=50.00,
        help_text="Minimum cumulative score to pass (default 50%)"
    )
    
    # Compulsory subjects (stored as JSON array of subject IDs)
    compulsory_subject_ids = models.JSONField(
        default=list,
        help_text="List of subject IDs that must be passed (e.g., Math, English)"
    )
    
    # Additional subjects requirement
    minimum_additional_subjects = models.IntegerField(
        default=5,
        help_text="Minimum number of other subjects to pass (default 5)"
    )
    
    # Promotion mode
    promotion_mode = models.CharField(
        max_length=20,
        choices=PROMOTION_MODE_CHOICES,
        default='recommend'
    )
    
    # Carryover settings
    allow_carryover = models.BooleanField(
        default=False,
        help_text="Allow students to be promoted with failed subjects"
    )
    max_carryover_subjects = models.IntegerField(
        default=2,
        help_text="Maximum failed subjects allowed for carryover"
    )
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('session', 'class_level')
        verbose_name = "Promotion Rule"
        verbose_name_plural = "Promotion Rules"
    
    def __str__(self):
        class_str = self.class_level.name if self.class_level else "All Classes"
        return f"{self.session.name} - {class_str}: {self.pass_mark_percentage}%"
    
    @property
    def total_minimum_subjects(self):
        """Total subjects needed to pass = compulsory + additional"""
        return len(self.compulsory_subject_ids) + self.minimum_additional_subjects 