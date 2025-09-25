# import os
# from django.contrib.auth import get_user_model
# from django.db.models.signals import post_migrate
# from django.dispatch import receiver
#
# @receiver(post_migrate)
# def create_superuser(sender, **kwargs):
#     """
#     Auto-create a superuser after migrations are applied.
#     Uses environment variables for credentials.
#     """
#     User = get_user_model()
#     username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
#     email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
#     password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
#
#     if username and email and password:
#         if not User.objects.filter(username=username).exists():
#             User.objects.create_superuser(
#                 username=username,
#                 email=email,
#                 password=password
#             )
#             print(f"✅ Superuser '{username}' created successfully.")
#         else:
#             print(f"ℹ️ Superuser '{username}' already exists.")
#     else:
#         print("⚠️ Superuser env vars not set, skipping creation.")
