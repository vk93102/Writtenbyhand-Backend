"""
Django migration for Razorpay payment fields
Auto-generated migration for Payment model updates
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('question_solver', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='razorpay_order_id',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='razorpay_payment_id',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='razorpay_signature',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
