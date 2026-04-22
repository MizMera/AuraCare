import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_gaitobservation'),
        ('core', '0002_isolationsession_isolationevent'),
    ]

    operations = [
        migrations.AddField(
            model_name='isolationevent',
            name='resident',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='isolation_events',
                to='core.resident',
            ),
        ),
    ]
