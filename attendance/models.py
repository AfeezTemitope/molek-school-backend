from django.db import models
from users.models import Student, UserProfile


class Class(models.Model):
    CLASS_CHOICES = [
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

    name = models.CharField(max_length=30, choices=CLASS_CHOICES, unique=True)
    teacher = models.ForeignKey(UserProfile, on_delete=models.CASCADE, limit_choices_to={'role': 'teacher'})
    session_year = models.CharField(max_length=9, default="2025/2026")

    def __str__(self):
        return f"{self.name} ({self.session_year})"


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused')
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    recorded_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ['student', 'date', 'class_obj']

    def __str__(self):
        return f"{self.student.admission_number} - {self.status}"