from datetime import datetime
from django.contrib.auth.hashers import make_password
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from cloudinary.models import CloudinaryField


# ============================================================
# USER PROFILE (ADMIN/SUPERADMIN)
# ============================================================

class UserProfileManager(BaseUserManager):
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

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    age = models.PositiveIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES, null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    state_of_origin = models.CharField(max_length=100, blank=True, null=True)
    local_govt_area = models.CharField(max_length=100, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserProfileManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']

    class Meta:
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['is_active']),
        ]
        verbose_name = "Admin User"
        verbose_name_plural = "Admin Users"

    def __str__(self):
        return f"{self.full_name} ({self.role})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


# ============================================================
# LEGACY STUDENT MODEL - DO NOT USE
# ============================================================

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
    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='student_profile')
    created_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='students_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'users_student'
        indexes = [
            models.Index(fields=['admission_number']),
            models.Index(fields=['class_level']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.admission_number})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


# ============================================================
# CBT INTEGRATION MODELS - MOLEK SCHOOL
# ============================================================

class AcademicSession(models.Model):
    """Academic year (e.g., 2024/2025)"""
    name = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
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

    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='terms')
    name = models.CharField(max_length=20, choices=TERM_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['session', 'name']
        unique_together = ['session', 'name']
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

    name = models.CharField(max_length=10, choices=CLASS_CHOICES, unique=True)
    order = models.IntegerField(unique=True)

    class Meta:
        ordering = ['order']
        verbose_name = "Class Level"
        verbose_name_plural = "Class Levels"

    def __str__(self):
        return self.get_name_display()

    def get_next_class(self):
        """Get the next class level for promotion"""
        try:
            return ClassLevel.objects.get(order=self.order + 1)
        except ClassLevel.DoesNotExist:
            return None


class Subject(models.Model):
    """Subjects taught in the school"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    class_levels = models.ManyToManyField(ClassLevel, related_name='subjects')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"

    def __str__(self):
        return self.name


class ActiveStudent(models.Model):
    """MOLEK SCHOOL STUDENT MODEL"""
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]

    admission_number = models.CharField(max_length=50, unique=True, editable=False)
    first_name = models.CharField(max_length=150)
    middle_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150)

    password_plain = models.CharField(max_length=50)
    password_hash = models.CharField(max_length=128)

    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    address = models.TextField(blank=True, null=True)
    state_of_origin = models.CharField(max_length=100, blank=True, null=True)
    local_govt_area = models.CharField(max_length=100, blank=True, null=True)

    class_level = models.ForeignKey(ClassLevel, on_delete=models.PROTECT, related_name='active_students')
    subjects = models.ManyToManyField(Subject, related_name='students', blank=True)
    enrollment_session = models.ForeignKey(AcademicSession, on_delete=models.PROTECT, related_name='enrolled_students')

    parent_name = models.CharField(max_length=200, blank=True, null=True)
    parent_email = models.EmailField(blank=True, null=True)
    parent_phone = models.CharField(max_length=15, blank=True, null=True)

    passport = CloudinaryField('image', blank=True, null=True)

    is_active = models.BooleanField(default=True)
    graduation_date = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, related_name='students_enrolled')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['admission_number']
        indexes = [
            models.Index(fields=['admission_number']),
            models.Index(fields=['class_level']),
            models.Index(fields=['is_active']),
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
    """Continuous Assessment scores"""
    student = models.ForeignKey(ActiveStudent, on_delete=models.CASCADE, related_name='ca_scores')
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT)
    session = models.ForeignKey(AcademicSession, on_delete=models.PROTECT)
    term = models.ForeignKey(Term, on_delete=models.PROTECT)

    score = models.IntegerField()
    max_score = models.IntegerField(default=30)

    uploaded_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'subject', 'session', 'term']
        indexes = [
            models.Index(fields=['student', 'session', 'term']),
        ]
        verbose_name = "CA Score"
        verbose_name_plural = "CA Scores"

    def __str__(self):
        return f"{self.student.admission_number} - {self.subject.name} - CA: {self.score}"


class ExamResult(models.Model):
    """Exam results from CBT system"""
    GRADE_CHOICES = [
        ('A', 'A - Excellent'),
        ('B', 'B - Very Good'),
        ('C', 'C - Good'),
        ('D', 'D - Fair'),
        ('F', 'F - Fail'),
    ]

    student = models.ForeignKey(ActiveStudent, on_delete=models.CASCADE, related_name='exam_results')
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='exam_results')
    session = models.ForeignKey(AcademicSession, on_delete=models.PROTECT)
    term = models.ForeignKey(Term, on_delete=models.PROTECT)

    ca_score = models.IntegerField()
    exam_score = models.IntegerField()
    total_score = models.IntegerField()
    percentage = models.FloatField()
    grade = models.CharField(max_length=1, choices=GRADE_CHOICES)

    position = models.IntegerField(null=True, blank=True)
    class_average = models.FloatField(null=True, blank=True)
    total_students = models.IntegerField(null=True, blank=True)
    highest_score = models.IntegerField(null=True, blank=True)
    lowest_score = models.IntegerField(null=True, blank=True)

    answers_json = models.JSONField(null=True, blank=True)

    submitted_at = models.DateTimeField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-submitted_at']
        unique_together = ['student', 'subject', 'session', 'term']
        indexes = [
            models.Index(fields=['student', 'session', 'term']),
            models.Index(fields=['subject', 'session', 'term']),
        ]
        verbose_name = "Exam Result"
        verbose_name_plural = "Exam Results"

    def __str__(self):
        return f"{self.student.admission_number} - {self.subject.name} ({self.session.name}/{self.term.name})"

    def save(self, *args, **kwargs):
        self.total_score = self.ca_score + self.exam_score
        self.percentage = round((self.total_score / 100) * 100, 2)

        if self.percentage >= 70:
            self.grade = 'A'
        elif self.percentage >= 60:
            self.grade = 'B'
        elif self.percentage >= 50:
            self.grade = 'C'
        elif self.percentage >= 40:
            self.grade = 'D'
        else:
            self.grade = 'F'

        super().save(*args, **kwargs)