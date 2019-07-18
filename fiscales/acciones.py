from django.shortcuts import redirect, render

from adjuntos.models import Attachment
from elecciones.models import MesaCategoria


def siguiente_accion(request):
    """
    Elige la siguiente acción a ejecutarse
    - si hay actas en el queryset :meth:`Attachment.sin asignar`,
      entonces la accion es identificar una al azar
    - si hay mesas con carga pendiente (es decir, que tienen categorias sin cargar),
      se elige una por orden de prioridad y tamaño del circuito
    - caso contrario, no hay nada para hacer
    """
    accion = None

    if accion is None:
        foto = foto_a_identificar(request.user.fiscal)
        if foto is not None:
            accion = IdentificacionDeFoto(request, foto)

    if accion is None:
        mesacategoria = MesaCategoria.objects.siguiente()
        if mesacategoria:
            accion = CargaCategoriaEnActa(request, mesacategoria)

    if accion is None:
        accion = NoHayAccion(request)

    return accion


def foto_a_identificar(fiscal):
    attachments = Attachment.sin_identificar(fiscal)
    if attachments.exists():
        return attachments.order_by('?').first()
    return None


class IdentificacionDeFoto():
    """
    Accion sobre una foto (attachment):
    estampa el tiempo de "asignación" para que se excluya durante el periodo
    de guarda y redirige a la vista para su clasificación
    """

    def __init__(self, _request, _attachment):
        self.attachment = _attachment

    def ejecutar(self):
        # Se marca el adjunto
        self.attachment.take()
        # Se realiza el redirect
        return redirect('asignar-mesa', attachment_id=self.attachment.id)


class CargaCategoriaEnActa():
    """
    Acción sobre una mesa-categoría:
    estampa en la mesa el tiempo de "asignación" para que se excluya durante el periodo
    de guarda y redirige a la vista para la carga de la mesa/categoría dependiendo
    de la configuracion de la categoria
    """

    def __init__(self, _request, mc):
        self.mc = mc

    def ejecutar(self):
        # Se marca que se inicia una carga
        self.mc.take()
        if (self.mc.categoria.requiere_cargas_parciales and
                self.mc.status != MesaCategoria.STATUS.parcial_consolidada_dc):
            # solo si la categoria requiere parciales y las parciales no estan consolidada
            return redirect('mesa-cargar-resultados-parciales', mesacategoria_id=self.mc.id)
        return redirect('mesa-cargar-resultados', mesacategoria_id=self.mc.id)


class NoHayAccion():

    def __init__(self, _request):
        self.request = _request

    def ejecutar(self):
        return render(self.request, 'fiscales/sin-actas.html')


