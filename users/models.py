from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from cloudinary.models import CloudinaryField

class UserProfileManager(BaseUserManager):
    def create_user(self, username, email, first_name, last_name, role='student', phone_number=None, password=None):
        if not username:
            raise ValueError('Username is required')
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
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
        ('superadmin', 'Superadmin'),
    )

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='users_created')
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

    def __str__(self):
        return self.username

class Student(models.Model):
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

    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='student_profile')
    admission_number = models.CharField(max_length=50, unique=True)
    class_level = models.CharField(max_length=10, choices=CLASS_LEVEL_CHOICES)
    stream = models.CharField(max_length=20, choices=STREAM_CHOICES, blank=True, null=True)
    section = models.CharField(max_length=1, choices=SECTION_CHOICES, blank=True, null=True)
    passport = CloudinaryField('image', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='students_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['admission_number']),
            models.Index(fields=['class_level']),
            models.Index(fields=['stream']),
            models.Index(fields=['section']),
            models.Index(fields=['is_active']),
        ]

    def save(self, *args, **kwargs):
        if not self.admission_number:
            year = '2025'  # Adjust as needed
            class_level = self.class_level
            stream = self.stream or 'GENERAL'
            section = self.section or 'A'
            count = Student.objects.filter(class_level=class_level, stream=stream, section=section).count() + 1
            self.admission_number = f'{year}/{class_level}/{stream.upper()}/{section}/{count:03d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} ({self.admission_number})"