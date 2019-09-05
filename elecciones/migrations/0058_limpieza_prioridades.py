# Generated by Django 2.2.2 on 2019-09-05 15:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('elecciones', '0057_auto_20190901_1444'),
    ]

    operations = [
        migrations.RenameField(
            model_name='mesacategoria',
            old_name='orden_de_carga',
            new_name='coeficiente_para_orden_de_carga',
        ),
        migrations.RemoveField(
            model_name='circuito',
            name='prioridad',
        ),
        migrations.RemoveField(
            model_name='distrito',
            name='prioridad',
        ),
        migrations.RemoveField(
            model_name='mesa',
            name='prioridad',
        ),
        migrations.RemoveField(
            model_name='seccion',
            name='prioridad',
        ),
    ]
