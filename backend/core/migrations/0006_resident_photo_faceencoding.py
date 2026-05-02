from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_alter_incident_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='resident',
            name='photo',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='resident_photos/',
                help_text='Photo du résident utilisée pour la reconnaissance faciale',
            ),
        ),
        migrations.CreateModel(
            name='FaceEncoding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('encoding_json', models.TextField(
                    help_text='Encodage facial sérialisé en JSON (vecteur 128-dim face_recognition)'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('resident', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='face_encoding',
                    to='core.resident',
                )),
            ],
            options={
                'verbose_name': 'Face Encoding',
                'verbose_name_plural': 'Face Encodings',
            },
        ),
    ]
