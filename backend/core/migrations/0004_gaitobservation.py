from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_mealtime_incident_meal_notification'),
    ]

    operations = [
        migrations.CreateModel(
            name='GaitObservation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(choices=[('normal', 'Normal'), ('abnormal', 'Abnormal')], max_length=20)),
                ('confidence', models.FloatField()),
                ('stride_length', models.FloatField(default=0)),
                ('walking_speed', models.FloatField(default=0)),
                ('arm_swing', models.FloatField(default=0)),
                ('step_variability', models.FloatField(default=0)),
                ('cadence', models.FloatField(default=0)),
                ('height_ratio', models.FloatField(default=0)),
                ('recorded_at', models.DateTimeField(auto_now_add=True)),
                ('alert_triggered', models.BooleanField(default=False)),
                ('snapshot', models.ImageField(blank=True, null=True, upload_to='gait_snapshots/')),
                ('resident', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='gait_observations', to='core.resident')),
                ('zone', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='gait_observations', to='core.zone')),
            ],
            options={
                'ordering': ['-recorded_at'],
            },
        ),
    ]
