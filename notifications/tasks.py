from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from core.models import Booking

import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_email_task(self, booking_id, email_type):
    try:
        logger.info(f"Starting email task for booking {booking_id}, type {email_type}")
        booking = Booking.objects.select_related('student', 'gadget', 'approved_by').get(id=booking_id)
        
        templates = {
            'placed': ('Gadget Request Placed Successfully', 'notifications/emails/request_placed.html'),
            'approved': ('Gadget Request Approved', 'notifications/emails/request_approved.html'),
            'returned': ('Gadget Returned Successfully', 'notifications/emails/gadget_returned.html'),
            'reminder': ('Official Reminder: 3 Days Left for Gadget Return', 'notifications/emails/return_reminder.html')
        }

        if email_type not in templates:
            return f"Unknown email type: {email_type}"

        subject, template_name = templates[email_type]
        
        context = {'booking': booking}
        if email_type == 'reminder':
            context['remaining_days'] = 3
            context['submit_date'] = booking.end_date

        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)
        
        logger.info(f"Sending email to {booking.student.email} via {settings.EMAIL_HOST}")
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [booking.student.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Email {email_type} sent successfully to {booking.student.email}")
        return f"Email {email_type} sent to {booking.student.email}"

    except Booking.DoesNotExist:
        logger.error(f"Booking {booking_id} not found")
        return f"Booking {booking_id} not found"
    except Exception as exc:
        logger.error(f"Error sending email: {exc}")
        # If in eager mode (synchronous), don't retry as it blocks the web worker
        if self.request.is_eager:
            logger.warning("Eager mode detected, skipping retry to avoid blocking.")
            return f"Failed to send email in eager mode: {exc}"
        
        # Retry for network errors in background worker
        raise self.retry(exc=exc)
