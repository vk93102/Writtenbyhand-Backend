# Generated migration for PairQuizSession model
# Run: python manage.py makemigrations && python manage.py migrate

from django.db import migrations, models
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('question_solver', '0006_rename_question_so_token_idx_question_so_token_f3cb3a_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PairQuizSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('session_code', models.CharField(db_index=True, max_length=10, unique=True)),
                ('host_user_id', models.CharField(max_length=255)),
                ('partner_user_id', models.CharField(blank=True, max_length=255, null=True)),
                ('quiz_config', models.JSONField(default=dict)),
                ('questions', models.JSONField(default=list)),
                ('status', models.CharField(choices=[('waiting', 'Waiting for Partner'), ('active', 'Active'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='waiting', max_length=20)),
                ('current_question_index', models.IntegerField(default=0)),
                ('host_answers', models.JSONField(default=dict)),
                ('partner_answers', models.JSONField(default=dict)),
                ('timer_seconds', models.IntegerField(default=0)),
                ('host_time_taken', models.IntegerField(default=0)),
                ('partner_time_taken', models.IntegerField(default=0)),
                ('host_score', models.FloatField(blank=True, null=True)),
                ('partner_score', models.FloatField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField()),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='pairquizsession',
            index=models.Index(fields=['session_code'], name='question_so_session_b3c4f1_idx'),
        ),
        migrations.AddIndex(
            model_name='pairquizsession',
            index=models.Index(fields=['status', '-created_at'], name='question_so_status_a7e2d9_idx'),
        ),
        migrations.AddIndex(
            model_name='pairquizsession',
            index=models.Index(fields=['host_user_id'], name='question_so_host_us_c8f3a1_idx'),
        ),
    ]
