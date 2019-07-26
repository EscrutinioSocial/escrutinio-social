# Generated by Django 2.2.2 on 2019-07-25 00:43

from django.db import migrations, models
from fiscales.views import generar_codigo_confirmacion


def actulizar_codigo_referido(apps, schema_editor):
    Fiscal = apps.get_model("fiscales", "Fiscal")
    fiscales = Fiscal.objects.all()
    for fiscal in fiscales:
        codigo = generar_codigo_confirmacion()
        fiscal.referido_codigo = codigo
        fiscal.save(update_fields=['referido_codigo'])


class Migration(migrations.Migration):

    dependencies = [
        ('fiscales', '0003_auto_20190723_1559'),
    ]

    operations = [
        migrations.RunSQL('SET CONSTRAINTS ALL IMMEDIATE', reverse_sql=migrations.RunSQL.noop),

        migrations.AddField(
            model_name='fiscal',
            name='referido_por_apellido',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),

        migrations.AlterField(
            model_name='fiscal',
            name='referido_codigo',
            field=models.CharField(blank=True, max_length=4, null=True, unique=False),
        ),
        migrations.RunPython(actulizar_codigo_referido, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='fiscal',
            name='referido_codigo',
            field=models.CharField(blank=True, max_length=4, null=False, unique=True),
        ),
        migrations.AlterField(
            model_name='fiscal',
            name='referido_por_codigo',
            field=models.CharField(blank=True, max_length=4, null=True),
        ),
        migrations.RunSQL(migrations.RunSQL.noop, reverse_sql='SET CONSTRAINTS ALL IMMEDIATE'),
    ]
