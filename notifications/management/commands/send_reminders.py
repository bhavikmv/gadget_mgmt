from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import Booking
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from notifications.tasks import send_notification_email_task

class Command(BaseCommand):
    help = 'Sends reminders for bookings that are 3 days away from the submission date.'

    def handle(self, *args, **options):
        today = timezone.now().date()
        reminder_date = today + timedelta(days=3)
        
        # Find bookings ending in exactly 3 days
        bookings_to_remind = Booking.objects.filter(
            end_date=reminder_date,
            status='approved'
        )
        
        self.stdout.write(f"Found {bookings_to_remind.count()} bookings for reminder.")

        for booking in bookings_to_remind:
            send_notification_email_task.delay(booking.id, 'reminder')
            self.stdout.write(self.style.SUCCESS(f'Queued reminder for {booking.student.email}'))
