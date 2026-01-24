"""
MOLEK School - Database Models
Enhanced with proper indexing and query optimization
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


class CAScore(models.Model):
    """
    Continuous Assessment + Theory Score Model
    
    Grading Formula: CA (30) + Theory (varies) + Exam (varies) = 100
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
    
    # CA Score (max 30)
    ca_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(30)],
        help_text="Continuous Assessment score (max 30)"
    )
    
    # Theory Score (varies based on teacher's discretion)
    theory_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Theory/essay score (varies by exam)",
        default=0
    )
    
    # Maximum possible theory score for this subject/exam
    max_theory_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=30,
        help_text="Maximum possible theory score"
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
        verbose_name = 'CA & Theory Score'
        verbose_name_plural = 'CA & Theory Scores'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.student.admission_number} - {self.subject.name}: CA={self.ca_score}, Theory={self.theory_score}"
    
    @property
    def total_non_exam_score(self):
        """CA + Theory combined score"""
        return self.ca_score + self.theory_score


class ExamResult(models.Model):
    """
    Final Exam Result Model
    
    Combines:
    - CA Score (from CAScore model, max 30)
    - Theory Score (from CAScore model, varies)
    - Exam Score (from CBT, varies)
    
    Total = CA + Theory + Exam = 100
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
    
    # Scores
    ca_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="CA score (from CAScore, max 30)"
    )
    theory_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Theory score (from CAScore)",
        default=0
    )
    exam_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Exam score (from CBT)"
    )
    total_exam_questions = models.IntegerField(
        default=0,
        help_text="Total MCQ questions in the exam"
    )
    
    # Calculated fields
    total_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="CA + Theory + Exam (should = 100)"
    )
    grade = models.CharField(
        max_length=2,
        help_text="Grade (A, B, C, D, F)",
        db_index=True
    )
    
    # Class statistics
    position = models.IntegerField(null=True, blank=True)
    class_average = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_students = models.IntegerField(null=True, blank=True)
    highest_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    lowest_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Metadata
    submitted_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
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
        # Auto-calculate total and grade
        self.total_score = self.ca_score + self.theory_score + self.exam_score
        self.grade = self.calculate_grade(self.total_score)
        super().save(*args, **kwargs)
    
    @staticmethod
    def calculate_grade(total_score):
        """Calculate grade based on total score (out of 100)"""
        if total_score >= 70:
            return 'A'
        elif total_score >= 60:
            return 'B'
        elif total_score >= 50:
            return 'C'
        elif total_score >= 40:
            return 'D'
        else:
            return 'F'