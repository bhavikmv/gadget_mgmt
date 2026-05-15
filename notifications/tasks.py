from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from gadgets.models import Request
from datetime import timedelta, date

import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_email_task(self, request_id, email_type):
    try:
        logger.info(f"Starting email task for request {request_id}, type {email_type}")
        req = Request.objects.select_related('student').prefetch_related('items__gadget').get(id=request_id)
        
        templates = {
            'placed': ('Gadget Request Placed Successfully', 'notifications/emails/request_placed.html'),
            'approved': ('Gadget Request Approved', 'notifications/emails/request_approved.html'),
            'returned': ('Gadget Returned Successfully', 'notifications/emails/gadget_returned.html'),
            'reminder': ('Reminder: 3 Days Left to Return Your Gadget', 'notifications/emails/return_reminder.html'),
            'reminder_1day': ('Urgent: 1 Day Left to Return Your Gadget', 'notifications/emails/return_reminder.html'),
        }

        if email_type not in templates:
            return f"Unknown email type: {email_type}"

        subject, template_name = templates[email_type]
        
        context = {'req': req}
        if email_type in ('reminder', 'reminder_1day'):
            today = date.today()
            remaining = (req.expected_return_date - today).days if req.expected_return_date else 0
            context['remaining_days'] = remaining

        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)
        
        logger.info(f"Sending email to {req.student.email} via Brevo Anymail")
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [req.student.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Email {email_type} sent successfully to {req.student.email}")
        return f"Email {email_type} sent to {req.student.email}"

    except Request.DoesNotExist:
        logger.error(f"Request {request_id} not found")
        return f"Request {request_id} not found"
    except Exception as exc:
        logger.error(f"Error sending email: {exc}")
        if self.request.is_eager:
            logger.warning("Eager mode detected, skipping retry to avoid blocking.")
            return f"Failed to send email in eager mode: {exc}"
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_otp_email_task(self, email, otp):
    try:
        logger.info(f"Sending OTP to {email}")
        subject = 'Verify Your Account - OTP'
        context = {'otp': otp}
        html_message = render_to_string('notifications/emails/otp_email.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"OTP sent successfully to {email}")
        return f"OTP sent to {email}"
    except Exception as exc:
        logger.error(f"Error sending OTP email: {exc}")
        if self.request.is_eager:
            logger.warning("Eager mode detected, skipping retry to avoid blocking.")
            return f"Failed to send email in eager mode: {exc}"
        raise self.retry(exc=exc)

@shared_task
def send_return_reminders_task():
    try:
        logger.info("Starting return reminders task")
        target_date = date.today() + timedelta(days=3)
        requests_list = Request.objects.filter(status='issued', expected_return_date=target_date)
        
        count = 0
        for req in requests_list:
            send_notification_email_task.delay(req.id, 'reminder')
            count += 1
            
        logger.info(f"Queued {count} reminder emails")
        return f"Queued {count} reminders"
    except Exception as exc:
        logger.error(f"Error in send_return_reminders_task: {exc}")
        return str(exc)
