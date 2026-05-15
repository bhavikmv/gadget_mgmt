from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from gadgets.models import Request
from notifications.tasks import send_notification_email_task


class Command(BaseCommand):
    help = 'Sends return reminders for issued gadgets due in 3 days and 1 day.'

    def handle(self, *args, **options):
        today = timezone.now().date()

        # 3-day reminders
        date_3day = today + timedelta(days=3)
        reqs_3day = Request.objects.filter(
            expected_return_date=date_3day,
            status='issued'
        ).select_related('student')

        count_3 = 0
        for req in reqs_3day:
            send_notification_email_task.delay(req.id, 'reminder')
            count_3 += 1
            self.stdout.write(self.style.SUCCESS(
                f'[3-day] Queued reminder for {req.student.email} (Request #{req.id})'
            ))

        # 1-day reminders
        date_1day = today + timedelta(days=1)
        reqs_1day = Request.objects.filter(
            expected_return_date=date_1day,
            status='issued'
        ).select_related('student')

        count_1 = 0
        for req in reqs_1day:
            send_notification_email_task.delay(req.id, 'reminder_1day')
            count_1 += 1
            self.stdout.write(self.style.SUCCESS(
                f'[1-day] Queued reminder for {req.student.email} (Request #{req.id})'
            ))

        self.stdout.write(self.style.SUCCESS(
            f'Done. Queued {count_3} three-day reminder(s) and {count_1} one-day reminder(s).'
        ))
