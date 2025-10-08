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
    CLASS_CHOICES=[
        ('JSS1', 'JSS1'),
        ('JSS2', 'JSS2'),
        ('JSS3', 'JSS3'),
        ('SS1 Science', 'SS1 Science'),
        ('SS1 Commercial', 'SS1 Commercial'),
        ('SS1 Art', 'SS1 Art'),
        ('SS2 Science', 'SS2 Science'),
        ('SS2 Commercial', 'SS2 Commercial'),
        ('SS2 Art', 'SS2 Art'),
        ('SS3 Science', 'SS3 Science'),
        ('SS3 Commercial', 'SS3 Commercial'),
        ('SS3 Art', 'SS3 Art'),
    ]

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')])
    age = models.PositiveIntegerField(help_text="Age in years")
    address = models.TextField()
    class_name = models.CharField(max_length=20, choices=CLASS_CHOICES, help_text="e.g., SS2 Science")
    parent_phone = models.CharField(max_length=15, help_text="e.g., +2348012345678")
    parent_email = models.EmailField(unique=False, blank=True, null=True)

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
        return f"{self.admission_number} - {self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        if not self.pk:  # Only on creation
            year = timezone.now().year
            class_name = self.class_name.strip()

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

            # Use last name as password
            raw_password = self.last_name

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

    class Meta:
        indexes = [
            models.Index(fields=['admission_number']),
            models.Index(fields=['class_name', 'is_active']),
        ]

class TeacherAssignment(models.Model):
    """
    Assigns a teacher to a class.
    e.g., Mr. Ade → SS2 Science
    """
    CLASS_CHOICES = [
        ('JSS1', 'JSS1'),
        ('JSS2', 'JSS2'),
        ('JSS3', 'JSS3'),
        ('SS1 Science', 'SS1 - Science'),
        ('SS1 Commercial', 'SS1 - Commercial'),
        ('SS1 Art', 'SS1 - Art'),
        ('SS2 Science', 'SS2 - Science'),
        ('SS2 Commercial', 'SS2 - Commercial'),
        ('SS2 Art', 'SS2 - Art'),
        ('SS3 Science', 'SS3 - Science'),
        ('SS3 Commercial', 'SS3 - Commercial'),
        ('SS3 Art', 'SS3 - Art'),
    ]

    teacher = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'teacher'}
    )
    class_name = models.CharField(max_length=50, choices=CLASS_CHOICES)
    session_year = models.CharField(max_length=9, default="2025/2026")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.teacher.username} → {self.class_name}"

    class Meta:
        verbose_name = "Teacher Assignment"
        verbose_name_plural = "Teacher Assignments"
        unique_together = ['teacher', 'class_name']  # One teacher per class