import random
import string

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from cloudinary.models import CloudinaryField

def get_default_staff():
    return UserProfile.objects.filter(role__in=['staff', 'superadmin', 'teacher']).first().id

class UserProfile(AbstractUser):
    ROLE_CHOICES = [
        ('superadmin', 'Super Admin'),
        ('staff', 'Staff'),
        ('teacher', 'Teacher'),
    ]

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='staff')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    email = models.EmailField(unique=False, blank=True, null=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['role', 'is_active']),
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

class ClassCounter(models.Model):
    class_name = models.CharField(max_length=20, unique=True)
    count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.class_name}: {self.count}"

    class Meta:
        verbose_name = "Class Counter"
        verbose_name_plural = "Class Counters"
        indexes = [
            models.Index(fields=['class_name']),
        ]

class Student(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other')
    ]

    # ✅ Dropdown for class level
    CLASS_LEVEL_CHOICES = [
        ('JSS1', 'JSS1'),
        ('JSS2', 'JSS2'),
        ('JSS3', 'JSS3'),
        ('SS1', 'SS1'),
        ('SS2', 'SS2'),
        ('SS3', 'SS3'),
    ]

    # ✅ Dropdown for stream (depends on class)
    STREAM_CHOICES = [
        ('Science', 'Science'),
        ('Commercial', 'Commercial'),
        ('Art', 'Art'),
        ('General', 'General'),  # For JSS levels
    ]

    # ✅ Dropdown for section
    SECTION_CHOICES = [
        ('A', 'Section A'),
        ('B', 'Section B'),
        ('C', 'Section C'),
    ]

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    age = models.PositiveIntegerField(help_text="Age in years")
    address = models.TextField()

    # ✅ New fields with dropdowns
    class_level = models.CharField(max_length=10, choices=CLASS_LEVEL_CHOICES, help_text="e.g., SS1, JSS2")
    stream = models.CharField(max_length=15, choices=STREAM_CHOICES, blank=True, null=True)
    section = models.CharField(max_length=1, choices=SECTION_CHOICES, blank=True, null=True)

    parent_phone = models.CharField(max_length=15, help_text="e.g., +23480...")
    parent_email = models.EmailField(blank=True, null=True)

    admission_number = models.CharField(max_length=20, unique=True, editable=False)
    passport_url = CloudinaryField(
        'image',
        folder='students/passports',
        resource_type='image',
        format='webp',
        transformation={
            'fetch_format': 'auto',
            'quality': 'auto',
            'secure': True,
        },
        blank=True,
        null=True
    )

    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='student_profile')
    created_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, related_name='created_students')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        stream_part = f" {self.stream}" if self.stream else ""
        section_part = f" {self.section}" if self.section else ""
        return f"{self.admission_number} - {self.first_name} {self.last_name}{stream_part}{section_part}"

    def save(self, *args, **kwargs):
        if not self.pk:  # Only on creation
            year = timezone.now().year
            class_name = self.class_level.strip().upper()

            # Get or create class counter
            class_counter, created = ClassCounter.objects.get_or_create(class_name=class_name)
            class_sn = class_counter.count + 1
            global_sn = Student.objects.count() + 1
            global_sn_padded = str(global_sn).zfill(3)

            # Generate admission number
            self.admission_number = f"{year}/{class_sn}/{global_sn_padded}"

            # Increment class counter
            class_counter.count += 1
            class_counter.save()

            # Generate 6-digit alphanumeric password
            chars = string.ascii_uppercase + string.digits
            raw_password = ''.join(random.choice(chars) for _ in range(6))

            # Create user with admission_number as username
            user = UserProfile.objects.create_user(
                username=self.admission_number,
                first_name=self.first_name,
                last_name=self.last_name,
                email=self.parent_email or None,
                password=raw_password,
                role='student',
                is_active=True,
            )

            self.user = user
            self._raw_password = raw_password

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.save(update_fields=['is_active'])

    @property
    def raw_password(self):
        return getattr(self, '_raw_password', None)

    @raw_password.setter
    def raw_password(self, value):
        raise AttributeError("Cannot set raw_password directly")

class TeacherAssignment(models.Model):
    LEVEL_CHOICES = [
        ('JSS1', 'JSS1'),
        ('JSS2', 'JSS2'),
        ('JSS3', 'JSS3'),
        ('SS1', 'SS1'),
        ('SS2', 'SS2'),
        ('SS3', 'SS3'),
    ]
    STREAM_CHOICES = [
        ('Science', 'Science'),
        ('Commercial', 'Commercial'),
        ('Art', 'Art'),
        ('General', 'General'),  # For JSS
    ]

    teacher = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'teacher'},
        related_name='assigned_classes'
    )
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    stream = models.CharField(max_length=15, choices=STREAM_CHOICES, blank=True, null=True)
    section = models.CharField(max_length=1, choices=[
        ('A', 'A'), ('B', 'B'), ('C', 'C')
    ])
    session_year = models.CharField(max_length=9, default="2025/2026")

    class Meta:
        unique_together = ['teacher', 'level', 'stream', 'section']
        verbose_name = "Class Assignment"
        verbose_name_plural = "Class Assignments"

    def __str__(self):
        if self.stream:
            return f"{self.level} {self.stream} - Section {self.section}"
        return f"{self.level} - Section {self.section}"

    @property
    def class_name(self):
        if self.stream:
            return f"{self.level} {self.stream} {self.section}"
        return f"{self.level} {self.section}"