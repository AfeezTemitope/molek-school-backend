# users/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Student
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Student)
def send_student_credentials_to_parent(sender, instance, created, **kwargs):
    if created:
        raw_password = instance.raw_password
        if not raw_password:
            logger.error("No raw password found for student. This should not happen!")
            return

        message = (
            f"Dear Parent, your child {instance.first_name} {instance.last_name} "
            f"has been enrolled.\n"
            f"Admission No: {instance.admission_number}\n"
            f"Password: {raw_password}\n"
            f"Login: https://student.edumanage.ng"
        )

        logger.info(f"[SMS MOCK] To: {instance.parent_phone}\n{message}")
        print(f"[SMS MOCK] To: {instance.parent_phone}\n{message}")

        # ✅ Clear temp password after use
        instance._raw_password = None