from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_merge_20260502_1522'),
    ]

    operations = [
        migrations.CreateModel(
            name='WanderingDetection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('risk_score', models.FloatField()),
                ('risk_level', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], max_length=20)),
                ('tortuosity', models.FloatField(blank=True, null=True)),
                ('turn_rate_per_min', models.FloatField(blank=True, null=True)),
                ('revisit_ratio', models.FloatField(blank=True, null=True)),
                ('speed_mean', models.FloatField(blank=True, null=True)),
                ('speed_std', models.FloatField(blank=True, null=True)),
                ('displacement', models.FloatField(blank=True, null=True)),
                ('idle_ratio', models.FloatField(blank=True, null=True)),
                ('max_speed', models.FloatField(blank=True, null=True)),
                ('trajectory_points', models.JSONField(blank=True, default=list)),
                ('feature_importance', models.JSONField(blank=True, default=dict)),
                ('explanation', models.TextField(blank=True)),
                ('resident', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='wandering_detections', to='core.resident')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='WanderingAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_level', models.CharField(choices=[('info', 'Info'), ('warning', 'Warning'), ('alert', 'Alert'), ('critical', 'Critical')], max_length=20)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('acknowledged', models.BooleanField(default=False)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('acknowledged_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='wandering_alerts_acknowledged', to='core.customuser')),
                ('detection', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='alert', to='core.wanderingdetection')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='wanderingdetection',
            index=models.Index(fields=['resident', '-timestamp'], name='core_wander_resident_idx'),
        ),
        migrations.AddIndex(
            model_name='wanderingdetection',
            index=models.Index(fields=['risk_level'], name='core_wander_risk_level_idx'),
        ),
    ]