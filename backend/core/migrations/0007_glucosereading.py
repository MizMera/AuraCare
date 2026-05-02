from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_resident_photo_faceencoding'),
    ]

    operations = [
        migrations.CreateModel(
            name='GlucoseReading',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('blood_glucose', models.FloatField(
                    help_text='Glycémie en mg/dL'
                )),
                ('glucose_class', models.IntegerField(
                    choices=[(0, 'Hypoglycémie'), (1, 'Normale'), (2, 'Pré-Hyperglycémie'), (3, 'Hyperglycémie')],
                    default=1,
                )),
                ('HbA1c_level', models.FloatField(null=True, blank=True, help_text='HbA1c en %')),
                ('bmi', models.FloatField(null=True, blank=True, help_text='IMC kg/m²')),
                ('notes', models.TextField(blank=True, default='')),
                ('measured_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('created_by', models.CharField(max_length=100, blank=True, default='')),
                ('resident', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='glucose_readings',
                    to='core.resident',
                )),
            ],
            options={
                'verbose_name': 'Glucose Reading',
                'verbose_name_plural': 'Glucose Readings',
                'ordering': ['-measured_at'],
            },
        ),
    ]
