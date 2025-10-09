from django.db import models
from users.models import Student, UserProfile


class TeacherAssignment(models.Model):
    CLASS_LEVELS = [
        'JSS1', 'JSS2', 'JSS3',
        'SS1', 'SS2', 'SS3',
    ]
    STREAMS = [
        ('Science', 'Science'),
        ('Commercial', 'Commercial'),
        ('Art', 'Art'),
        ('General', 'General'),  # For JSS
    ]

    teacher = models.ForeignKey(UserProfile, on_delete=models.CASCADE, limit_choices_to={'role': 'teacher'})
    level = models.CharField(max_length=10)  # JSS1, SS2
    stream = models.CharField(max_length=15, choices=STREAMS, blank=True, null=True)
    section = models.CharField(max_length=1, choices=[
        ('A', 'A'), ('B', 'B'), ('C', 'C')
    ])
    session_year = models.CharField(max_length=9, default="2025/2026")

    class Meta:
        unique_together = ['teacher', 'level', 'stream', 'section']
        verbose_name = "Teacher Assignment"
        verbose_name_plural = "Teacher Assignments"

    def __str__(self):
        if self.stream:
            return f"{self.level} {self.stream} {self.section}"
        return f"{self.level} {self.section}"


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused')
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    recorded_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ['student', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.student.admission_number} - {self.date} ({self.status})"