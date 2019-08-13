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
    attachments = Attachment.objects.sin_identificar(request.user.fiscal, for_update=True)
    con_carga_pendiente = MesaCategoria.objects.con_carga_pendiente(for_update=True)

    cant_fotos = attachments.count()
    cant_cargas = con_carga_pendiente.count()

    if (cant_fotos and not cant_cargas or
            cant_fotos >= cant_cargas * config.COEFICIENTE_IDENTIFICACION_VS_CARGA):
        foto = attachments.menos_asignadas().first()
        if foto:
            return IdentificacionDeFoto(request, foto)
    elif cant_cargas:
        mesacategoria = con_carga_pendiente.sin_cargas_del_fiscal(request.user.fiscal).mas_prioritaria()
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
        # Asignamos el attachment al fiscal.
        request.user.fiscal.asignar_attachment(foto)
        # Se registra que fue asignado a un fiscal.
        attachment.asignar_a_fiscal()

    def ejecutar(self):
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
        # Se marca que se inicia una carga.
        request.user.fiscal.asignar_mesa_categoria(mc)
        mesacategoria.asignar_a_fiscal()

    def ejecutar(self):
        if (
            self.mc.categoria.requiere_cargas_parciales and
            self.mc.status in [
                    MesaCategoria.STATUS.sin_cargar,
                    MesaCategoria.STATUS.parcial_sin_consolidar,
                    MesaCategoria.STATUS.parcial_en_conflicto,
                    MesaCategoria.STATUS.parcial_consolidada_csv,
                ]):
            # Sólo si la categoría requiere parciales y las parciales no están consolidadas.
            return redirect('carga-parcial', mesacategoria_id=self.mc.id)
        return redirect('carga-total', mesacategoria_id=self.mc.id)


class NoHayAccion():

    def __init__(self, request):
        self.request = request

    def ejecutar(self):
        return render(self.request, 'fiscales/sin-actas.html')
