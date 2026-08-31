from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="WorkshopSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "reception_can_create_mechanic",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Quando ativo, usuários de recepção também podem criar "
                            "mecânicos pelo cadastro rápido e pela aba Configurações."
                        ),
                        verbose_name="recepção pode cadastrar mecânicos",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="atualizado em"),
                ),
            ],
            options={
                "verbose_name": "configuração da oficina",
                "verbose_name_plural": "configurações da oficina",
            },
        ),
    ]
