from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'
from django.contrib.auth import get_user_model

User = get_user_model()

if not User.objects.filter(username='bhavik').exists():
    User.objects.create_superuser(
        fristname='bhavik',
        lastname='vasavada',
        email='bhavikmv5@gmail.com',
        password='bhavik@123'
    )
