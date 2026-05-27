from django.db import migrations, models


def migrate_channel_kind_and_audience(apps, schema_editor):
    Channel = apps.get_model("chat", "Channel")

    for channel in Channel.objects.all():
        if channel.kind == "voice":
            channel.audience = "public"
            channel.kind = "voice"
        elif channel.kind == "group":
            channel.audience = "group"
            channel.kind = "text"
        else:
            channel.audience = "public"
            channel.kind = "text"

        channel.save(update_fields=["kind", "audience"])


def reverse_channel_kind_and_audience(apps, schema_editor):
    Channel = apps.get_model("chat", "Channel")

    for channel in Channel.objects.all():
        if channel.kind == "voice":
            channel.kind = "voice"
        elif channel.audience == "group":
            channel.kind = "group"
        else:
            channel.kind = "public"

        channel.save(update_fields=["kind"])


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="channel",
            name="audience",
            field=models.CharField(
                choices=[("public", "Publiczny"), ("group", "Grupowy")],
                default="public",
                max_length=16,
            ),
        ),
        migrations.RunPython(
            migrate_channel_kind_and_audience,
            reverse_code=reverse_channel_kind_and_audience,
        ),
        migrations.AlterField(
            model_name="channel",
            name="kind",
            field=models.CharField(
                choices=[("text", "Kanał tekstowy"), ("voice", "Kanał głosowy")],
                default="text",
                max_length=16,
            ),
        ),
        migrations.AlterModelOptions(
            name="channel",
            options={"ordering": ("kind", "audience", "name")},
        ),
    ]
