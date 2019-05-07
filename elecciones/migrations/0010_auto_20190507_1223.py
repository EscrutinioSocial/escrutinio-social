# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-05-07 15:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('elecciones', '0009_auto_20190505_1605'),
    ]

    operations = [
        migrations.AddField(
            model_name='eleccion',
            name='back_color',
            field=models.CharField(default='white', help_text='Color para css (red o #FF0000)', max_length=10),
        ),
        migrations.AddField(
            model_name='eleccion',
            name='color',
            field=models.CharField(default='black', help_text='Color para css (red o #FF0000)', max_length=10),
        ),
    ]