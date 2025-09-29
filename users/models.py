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

    # Allow blank/null email since it's not required for login
    email = models.EmailField(unique=False, blank=True, null=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
        ordering = ['-created_at']

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

class Student(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')])
    age = models.PositiveIntegerField(help_text="Age in years")
    address = models.TextField()
    class_name = models.CharField(max_length=20, help_text="e.g., SS1, JSS2, Nursery")
    parent_phone = models.CharField(max_length=15, help_text="e.g., +2348012345678")
    parent_email = models.EmailField(unique=False, blank=True, null=True)

    admission_number = models.CharField(max_length=20, unique=True, editable=False)
    passport_url = CloudinaryField('passport', blank=True, null=True, folder='students/passports')

    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='student_profile')
    created_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, related_name='created_students', default=get_default_staff)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.admission_number} - {self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        if not self.pk:  # Only on creation
            year = timezone.now().year
            class_name = self.class_name.strip().upper()

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

            # ✅ USE LAST NAME AS PASSWORD
            raw_password = self.last_name  # ← This is now the password

            # ✅ Create user with admission_number as username
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
            self._raw_password = raw_password  # For signal (if needed later)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Soft delete
        self.is_active = False
        self.save(update_fields=['is_active'])

    @property
    def raw_password(self):
        return getattr(self, '_raw_password', None)

    @raw_password.setter
    def raw_password(self, value):
        raise AttributeError("Cannot set raw_password directly")