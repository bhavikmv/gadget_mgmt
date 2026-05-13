# Generated manually

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('gadgets', '0002_request_requestitem_waitingqueue_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='request',
            name='issue_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='request',
            name='return_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
