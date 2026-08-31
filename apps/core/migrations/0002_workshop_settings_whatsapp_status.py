from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_workshop_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="workshopsettings",
            name="auto_whatsapp_status_notify",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Ao mudar o status da OS, abre o WhatsApp Web/app com mensagem "
                    "pronta para o cliente (wa.me — sem API)."
                ),
                verbose_name="avisar cliente no WhatsApp ao mudar status",
            ),
        ),
    ]
