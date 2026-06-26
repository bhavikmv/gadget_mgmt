from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from gadgets.models import Request
from .tasks import send_notification_email_task

@receiver(post_save, sender=Request)
def send_request_notification(sender, instance, created, **kwargs):
    """
    Trigger background email tasks via Celery.
    This ensures the web request returns instantly (under 200ms).
    """
    if created:
        transaction.on_commit(lambda: send_notification_email_task.delay(instance.id, 'placed'))
    else:
        # Check status changes
        if instance.status == 'approved':
            transaction.on_commit(lambda: send_notification_email_task.delay(instance.id, 'approved'))
        elif instance.status == 'returned':
            transaction.on_commit(lambda: send_notification_email_task.delay(instance.id, 'returned'))
