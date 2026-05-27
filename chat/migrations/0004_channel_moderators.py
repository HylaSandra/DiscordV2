from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0003_merge_0002_channel_audience_and_kind_0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="channel",
            name="moderators",
            field=models.ManyToManyField(
                blank=True,
                related_name="moderated_channels",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
