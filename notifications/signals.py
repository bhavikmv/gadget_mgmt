from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import Booking
from .tasks import send_notification_email_task

@receiver(post_save, sender=Booking)
def send_booking_notification(sender, instance, created, **kwargs):
    """
    Trigger background email tasks via Celery.
    This ensures the web request returns instantly (under 200ms).
    """
    if created:
        send_notification_email_task.delay(instance.id, 'placed')
    else:
        # Check status changes
        if instance.status == 'approved':
            send_notification_email_task.delay(instance.id, 'approved')
        elif instance.status == 'returned':
            send_notification_email_task.delay(instance.id, 'returned')
