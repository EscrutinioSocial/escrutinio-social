from django.shortcuts import redirect, render
from django.db import transaction
from constance import config

from adjuntos.models import Attachment
from elecciones.models import MesaCategoria


@transaction.atomic
def siguiente_accion(request):
    """
    Elige la siguiente acción a ejecutarse

    - si sólo hay actas sin cargar la accion será identificar una de ellas al azar

    - si sólo hay mesas con carga pendiente (es decir, que tienen categorias sin cargar),
      se elige una por orden de prioridad

    - si hay tanto mesas como actas pendientes, se elige identicar
      si el tamaño de la cola de identificaciones pendientes es X veces el tamaño de la
      cola de carga (siendo X la variable config.COEFICIENTE_IDENTIFICACION_VS_CARGA).
    - caso contrario, no hay nada para hacer
    """
    attachments = Attachment.sin_identificar(request.user.fiscal)
    con_carga_pendiente = MesaCategoria.objects.con_carga_pendiente()

    cant_fotos = attachments.count()
    cant_cargas = con_carga_pendiente.count()

    if (cant_fotos and not cant_cargas or
            cant_fotos >= cant_cargas * config.COEFICIENTE_IDENTIFICACION_VS_CARGA):
        foto = attachments.order_by('?').first()
        if foto:
            return IdentificacionDeFoto(request, foto)
    elif cant_cargas:
        mesacategoria = con_carga_pendiente.mas_prioritaria()
        if mesacategoria:
            return CargaCategoriaEnActa(request, mesacategoria)
    return NoHayAccion(request)


class IdentificacionDeFoto():
    """
    Acción sobre una foto (attachment):
    estampa el tiempo de "asignación" para que se excluya durante el periodo
    de guarda y redirige a la vista para su clasificación.
    """

    def __init__(self, request, attachment):
        self.request = request
        self.attachment = attachment

    def ejecutar(self):
        # Se marca el adjunto
        self.attachment.take(self.request.user.fiscal)
        # Se realiza el redirect
        return redirect('asignar-mesa', attachment_id=self.attachment.id)


class CargaCategoriaEnActa():
    """
    Acción sobre una mesa-categoría:
    estampa en la mesa el tiempo de "asignación" para que se excluya durante el periodo
    de guarda y redirige a la vista para la carga de la mesa/categoría dependiendo
    de la configuracion de la categoría.
    """

    def __init__(self, request, mc):
        self.request = request
        self.mc = mc

    def ejecutar(self):
        # Se marca que se inicia una carga
        self.mc.take(self.request.user.fiscal)
        if (self.mc.categoria.requiere_cargas_parciales and
                self.mc.status[:2] < MesaCategoria.STATUS.parcial_consolidada_dc[:2]):
            # solo si la categoria requiere parciales y las parciales no estan consolidadas
            return redirect('carga-parcial', mesacategoria_id=self.mc.id)
        return redirect('carga-total', mesacategoria_id=self.mc.id)


class NoHayAccion():

    def __init__(self, request):
        self.request = request

    def ejecutar(self):
        return render(self.request, 'fiscales/sin-actas.html')
