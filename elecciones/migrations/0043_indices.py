# Generated by Django 2.2.2 on 2019-08-02 21:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('elecciones', '0042_auto_20190802_1750'),
    ]

    operations = [
        migrations.AlterField(
            model_name='categoria',
            name='nombre',
            field=models.CharField(db_index=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='circuito',
            name='numero',
            field=models.CharField(db_index=True, max_length=10),
        ),
        migrations.AlterField(
            model_name='distrito',
            name='numero',
            field=models.CharField(db_index=True, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='opcion',
            name='codigo',
            field=models.CharField(blank=True, db_index=True, help_text='Codigo de opción', max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='partido',
            name='codigo',
            field=models.CharField(blank=True, db_index=True, help_text='Codigo de partido', max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='seccion',
            name='numero',
            field=models.CharField(db_index=True, max_length=10, null=True),
        ),
    ]
