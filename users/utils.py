# users/utils.py

from decouple import config
from twilio.rest import Client
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_credentials(user, password):
    message = f"Your School Portal Login:\nEmail: {user.email}\nPassword: {password}\nLogin at: https://yoursite.com/login"

    # Send SMS if phone exists
    if user.phone:
        try:
            client = Client(config('TWILIO_ACCOUNT_SID'), config('TWILIO_AUTH_TOKEN'))
            client.messages.create(
                body=message,
                from_=config('TWILIO_PHONE_NUMBER'),
                to=user.phone
            )
            logger.info(f"SMS sent to {user.phone}")
        except Exception as e:
            logger.error(f"Failed to send SMS to {user.phone}: {e}")

    # Send Email
    try:
        send_mail(
            subject="Your School Portal Credentials",
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Email sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send email to {user.email}: {e}")