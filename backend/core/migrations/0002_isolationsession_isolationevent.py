import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='IsolationSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.CharField(max_length=255)),
                ('source', models.CharField(max_length=20, choices=[('upload','Video Upload'),('webcam','Webcam Live')], default='upload')),
                ('video_file', models.FileField(blank=True, null=True, upload_to='isolation_videos/')),
                ('uploaded_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('duration_seconds', models.PositiveIntegerField(default=0)),
                ('total_frames', models.PositiveIntegerField(default=0)),
                ('persons_detected', models.PositiveIntegerField(default=0)),
                ('frames_actif', models.PositiveIntegerField(default=0)),
                ('frames_vigilance', models.PositiveIntegerField(default=0)),
                ('frames_isole', models.PositiveIntegerField(default=0)),
                ('isolation_score', models.FloatField(default=0.0)),
                ('status', models.CharField(max_length=20, choices=[('pending','Pending'),('analysed','Analysed'),('error','Error')], default='pending')),
                ('weekly_scores_json', models.TextField(default='[]')),
                ('notes', models.TextField(blank=True)),
                ('resident', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='isolation_sessions',
                    to='core.resident',
                )),
            ],
            options={'ordering': ['-uploaded_at']},
        ),
        migrations.CreateModel(
            name='IsolationEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('track_id', models.CharField(max_length=50)),
                ('event_type', models.CharField(max_length=20, choices=[('isole','Isolé'),('vigilance','Vigilance'),('actif','Actif')], default='isole')),
                ('confidence', models.FloatField(default=0.0)),
                ('timestamp_seconds', models.FloatField(default=0.0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='events',
                    to='core.isolationsession',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
