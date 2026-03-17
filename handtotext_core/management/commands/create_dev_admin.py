from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
import os
import secrets


class Command(BaseCommand):
    help = 'Create a development superuser (optional: set via DEV_SUPERUSER_* env vars)'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Username for superuser')
        parser.add_argument('--email', type=str, help='Email for superuser')
        parser.add_argument('--password', type=str, help='Password for superuser')
        parser.add_argument('--noinput', action='store_true', help='Do not prompt for input')

    def handle(self, *args, **options):
        User = get_user_model()
        username = options.get('username') or os.getenv('DEV_SUPERUSER_NAME') or 'devadmin'
        email = options.get('email') or os.getenv('DEV_SUPERUSER_EMAIL') or 'devadmin@example.com'
        password = options.get('password') or os.getenv('DEV_SUPERUSER_PASSWORD')

        if not password:
            # generate a random password if not provided
            password = secrets.token_urlsafe(12)

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f"Superuser '{username}' already exists. Updating password."))
            user = User.objects.get(username=username)
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()
        else:
            if options.get('noinput'):
                # Create without interactive prompts
                user = User.objects.create_superuser(username=username, email=email, password=password)
            else:
                # Interactive fallback, ask user for password confirmation
                try:
                    user = User.objects.create_superuser(username=username, email=email)
                    user.set_password(password)
                    user.is_staff = True
                    user.is_superuser = True
                    user.save()
                except Exception as e:
                    raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS("Superuser created or updated successfully."))
        self.stdout.write(self.style.SUCCESS(f"Username: {username}"))
        self.stdout.write(self.style.SUCCESS(f"Password: {password}"))
*** End Patch