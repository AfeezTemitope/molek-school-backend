from datetime import datetime
from django.contrib.auth.hashers import make_password
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from cloudinary.models import CloudinaryField


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
    """
    Admin/SuperAdmin user model.
    Students and teachers are managed separately via the public portal.
    """
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
# LEGACY MODEL - DO NOT USE IN NEW CODE
# ============================================================
class Student(models.Model):
    """
    DEPRECATED: This model is preserved for database compatibility only.
    Student management has been moved to the public-facing portal.

    This table will NOT be modified by Django migrations (managed=False).
    DO NOT create new students through this model.
    """
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
        managed = False  # 🔑 CRITICAL: Django won't create/modify this table
        db_table = 'users_student'  # Explicitly preserve existing table name
        indexes = [
            models.Index(fields=['admission_number']),
            models.Index(fields=['class_level']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.admission_number})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()