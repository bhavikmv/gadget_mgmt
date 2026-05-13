# Manually written migration for GadgetMS queue system improvements

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gadgets', '0003_request_issue_date_request_return_date'),
    ]

    operations = [
        # Remove the old static expected_return_date from Gadget
        # (now computed dynamically from issued requests via services.py)
        migrations.RemoveField(
            model_name='gadget',
            name='expected_return_date',
        ),

        # Add duration_days to WaitingQueue
        migrations.AddField(
            model_name='waitingqueue',
            name='duration_days',
            field=models.PositiveIntegerField(default=7),
        ),

        # Add estimated_availability_date to WaitingQueue
        migrations.AddField(
            model_name='waitingqueue',
            name='estimated_availability_date',
            field=models.DateField(blank=True, null=True),
        ),

        # Add 'waitlisted' to Request status choices
        migrations.AlterField(
            model_name='request',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending Review'),
                    ('waitlisted', 'Waiting List'),
                    ('approved', 'Approved'),
                    ('ready', 'Ready for Pickup'),
                    ('issued', 'Issued'),
                    ('rejected', 'Rejected'),
                    ('returned', 'Returned'),
                ],
                db_index=True,
                default='pending',
                max_length=20,
            ),
        ),

        # Make expected_return_date nullable on Request (set at creation, but
        # waitlisted requests may not have one yet)
        migrations.AlterField(
            model_name='request',
            name='expected_return_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
