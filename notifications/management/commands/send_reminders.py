from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from gadgets.models import Request
from notifications.tasks import send_notification_email_task

class Command(BaseCommand):
    help = 'Sends reminders for issued gadgets that are 3 days away from the expected return date.'

    def handle(self, *args, **options):
        today = timezone.now().date()
        reminder_date = today + timedelta(days=3)
        
        # Find requests expected to return in exactly 3 days
        requests_to_remind = Request.objects.filter(
            expected_return_date=reminder_date,
            status='issued'
        )
        
        self.stdout.write(f"Found {requests_to_remind.count()} requests for reminder.")

        for req in requests_to_remind:
            send_notification_email_task.delay(req.id, 'reminder')
            self.stdout.write(self.style.SUCCESS(f'Queued reminder for {req.student.email}'))
