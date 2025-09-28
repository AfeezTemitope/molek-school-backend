from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Student
import logging
from decouple import config

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

@receiver(post_migrate)
def create_superuser(sender, **kwargs):
    if sender.name != "django.contrib.auth":
        return
    if config("DJANGO_ENV") != "prod":
        logger.info("Skipping superuser creation (not production).")
        return
    User = get_user_model()
    username = config("DJANGO_SUPERUSER_USERNAME")
    email = config("DJANGO_SUPERUSER_EMAIL")
    password = config("DJANGO_SUPERUSER_PASSWORD")

    if username and email and password:
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            logger.info(f"✅ Superuser '{username}' created successfully.")
        else:
            logger.info(f"ℹ️ Superuser '{username}' already exists.")
    else:
        logger.warning("⚠️ Superuser env vars not set, skipping creation.")