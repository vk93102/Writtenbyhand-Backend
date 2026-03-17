# Generated migration to refactor CoinWithdrawal for UPI-only payouts
# Removes bank account fields, updates status choices

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('question_solver', '0015_remove_usersubscription_auto_pay_enabled_and_more'),
    ]

    operations = [
        # Remove bank account fields
        migrations.RemoveField(
            model_name='coinwithdrawal',
            name='account_number',
        ),
        migrations.RemoveField(
            model_name='coinwithdrawal',
            name='ifsc_code',
        ),
        migrations.RemoveField(
            model_name='coinwithdrawal',
            name='account_holder_name',
        ),
        migrations.RemoveField(
            model_name='coinwithdrawal',
            name='payout_method',
        ),
        migrations.RemoveField(
            model_name='coinwithdrawal',
            name='payout_amount',
        ),
        
        # Update status field choices
        migrations.AlterField(
            model_name='coinwithdrawal',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('processing', 'Processing'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                ],
                default='pending',
                max_length=20
            ),
        ),
        
        # Make upi_id required (not null)
        migrations.AlterField(
            model_name='coinwithdrawal',
            name='upi_id',
            field=models.CharField(max_length=100, help_text='UPI ID for payout (e.g., user@paytm)'),
        ),
    ]
