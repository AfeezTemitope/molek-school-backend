import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "molekSchool.settings")
django.setup()

from django.contrib.auth import get_user_model

def main():
    if os.environ.get("DJANGO_ENV") != "prod":
        print("🚫 Skipping superuser creation: Not in production environment.")
        return

    User = get_user_model()
    username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
    email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

    if not all([username, email, password]):
        print("⚠️ Missing environment variables for superuser creation.")
        return

    if User.objects.filter(username=username).exists():
        print(f"✅ Superuser '{username}' already exists. Skipping creation.")
    else:
        print(f"🛠️ Creating superuser '{username}'...")
        User.objects.create_superuser(username=username, email=email, password=password)
        print("🎉 Superuser created successfully.")

if __name__ == "__main__":
    main()
