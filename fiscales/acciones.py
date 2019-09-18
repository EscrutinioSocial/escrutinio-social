from django.shortcuts import redirect, render
from django.db import transaction
from constance import config

from adjuntos.models import Attachment
from elecciones.models import MesaCategoria
from scheduling.models import ColaCargasPendientes


def siguiente_accion(request):
    return elegir_siguiente_accion_en_el_momento(request)

@transaction.atomic
def elegir_siguiente_accion_en_el_momento(request):
    (mesa_categoria,foto) = ColaCargasPendientes.siguiente_tarea(request.user.fiscal)
    if mesa_categoria:
        return CargaCategoriaEnActa(request, mesa_categoria)
    if foto:
        return IdentificacionDeFoto(request, foto)
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
        request.user.fiscal.asignar_attachment(attachment)
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
        mc.asignar_a_fiscal()

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
