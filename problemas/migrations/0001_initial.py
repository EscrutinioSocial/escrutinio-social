# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-05-01 14:07
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('fiscales', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('elecciones', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Problema',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('problema', models.CharField(blank=True, choices=[('Foto/s no válidas', 'Foto/s no válidas'), ('Total incorrecto', 'Total incorrecto'), ('Otro', 'Otro')], max_length=100, null=True)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('estado', models.CharField(blank=True, choices=[('pendiente', 'pendiente'), ('en curso', 'en curso'), ('resuelto', 'resuelto')], max_length=100, null=True)),
                ('mesa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='problemas', to='elecciones.Mesa')),
                ('reportado_por', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='fiscales.Fiscal')),
                ('resuelto_por', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
