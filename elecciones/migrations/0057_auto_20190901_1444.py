# Generated by Django 2.2.2 on 2019-09-01 17:44

from django.db import migrations, models
import django.db.models.deletion


def invalidar_firmas(apps, schema_editor):
    """
    Recalcula las firmas de las cargas, que ahora se basan en id en lugar de orden.
    """

    Carga = apps.get_model("elecciones", "Carga")
    for carga in Carga.objects.all():
        carga.firma = None
        carga.save(update_fields=['firma'])

def pasar_orden_a_categoriaopcion(apps, schema_editor):
    """
    Pasa el orden que antes estaba en las opciones a las categoría-opción.
    """

    CategoriaOpcion = apps.get_model("elecciones", "CategoriaOpcion")
    Opcion = apps.get_model("elecciones", "Opcion")
    for opcion in Opcion.objects.all():
        orden = opcion.orden
        for categoriaopcion in CategoriaOpcion.objects.filter(opcion=opcion):
            categoriaopcion.orden = orden
            categoriaopcion.save(update_fields=['orden'])

def agregar_categoria_general(apps, schema_editor):
    """
    Agrega una categoría general default.
    """
    CategoriaGeneral = apps.get_model("elecciones", "CategoriaGeneral")

    cg = CategoriaGeneral.objects.update_or_create(
        nombre='Default',
        slug='default',
        id=1
    )


class Migration(migrations.Migration):

    dependencies = [
        ('elecciones', '0056_merge_20190830_1039'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='opcion',
            options={'ordering': ['partido', 'nombre_corto'], 'verbose_name': 'Opción', 'verbose_name_plural': 'Opciones'},
        ),
        migrations.AddField(
            model_name='categoriaopcion',
            name='orden',
            field=models.PositiveIntegerField(blank=True, help_text='Orden en el acta', null=True),
        ),
        migrations.RunPython(pasar_orden_a_categoriaopcion, atomic=True),
        migrations.RemoveField(
            model_name='opcion',
            name='orden',
        ),
        migrations.RemoveField(
            model_name='partido',
            name='orden',
        ),
        migrations.AddField(
            model_name='categoria',
            name='distrito',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='elecciones.Distrito'),
        ),
        migrations.AddField(
            model_name='categoria',
            name='seccion',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='elecciones.Seccion'),
        ),
        migrations.CreateModel(
            name='CategoriaGeneral',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('nombre', models.CharField(max_length=100, unique=True)),
                ('eleccion', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='elecciones.Eleccion')),
            ],
        ),
        migrations.RunPython(agregar_categoria_general, atomic=True),
        migrations.AddField(
            model_name='categoria',
            name='categoria_general',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='categorias', to='elecciones.CategoriaGeneral'),
            preserve_default=False,
        ),
        migrations.RunPython(invalidar_firmas, atomic=True),
    ]