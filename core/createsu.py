from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Create superuser automatically'

    def handle(self, *args, **kwargs):
        User = get_user_model()

        if not User.objects.filter(username='bhavik').exists():
            User.objects.create_superuser(
                username='bhavik',
                email='bhavikmv5@gmail.com',
                password='bhavik@123'
            )
            self.stdout.write(self.style.SUCCESS('Superuser created'))
        else:
            self.stdout.write('Superuser already exists')
