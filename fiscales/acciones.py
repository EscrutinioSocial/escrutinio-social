from django.shortcuts import redirect, render, reverse
from urllib.parse import urlencode
from django.db import transaction
from constance import config

from adjuntos.models import Attachment
from elecciones.models import MesaCategoria
from scheduling.models import ColaCargasPendientes


def siguiente_accion(request):
    # Libero los recursos que tenía tomados el fiscal.
    # Es importante hacerlo en otra transacción para no provocar un deadlock.
    with transaction.atomic():
        request.user.fiscal.limpiar_asignacion_previa()
    # Y ahora comienza otra tr.
    return elegir_siguiente_accion(request)


def elegir_siguiente_accion(request):
    """
    Define la siguiente acción en base a la cola de tareas preexistente.
    """
    modo_ub = request.GET.get('modo_ub') and request.user.fiscal.esta_en_grupo('unidades basicas')
    with transaction.atomic():
        (mesa_categoria, foto) = ColaCargasPendientes.siguiente_tarea(request.user.fiscal, modo_ub)
        if mesa_categoria:
            return CargaCategoriaEnActa(request, mesa_categoria, modo_ub)
        if foto:
            return IdentificacionDeFoto(request, foto, modo_ub)
        siguiente = elegir_siguiente_accion_en_el_momento(request) if config.ASIGNAR_MESA_EN_EL_MOMENTO_SI_NO_HAY_COLA else NoHayAccion(request)
    return siguiente


@transaction.atomic
def elegir_siguiente_accion_en_el_momento(request):
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
    cant_cargas_parcial = MesaCategoria.objects.con_carga_parcial_pendiente().count()

    # Mandamos al usuario a identificar mesas si hay fotos y no hay cargas pendientes
    # o si la cantidad de mesas a identificar supera a la cantidad de cargas pendientes
    # por cierto coeficiente configurable.
    if (cant_fotos and not cant_cargas_parcial or
            cant_fotos >= cant_cargas_parcial * config.COEFICIENTE_IDENTIFICACION_VS_CARGA):
        foto = attachments.priorizadas().first()
        if foto:
            return IdentificacionDeFoto(request, foto)

    mesacategoria = con_carga_pendiente.sin_cargas_del_fiscal(request.user.fiscal).mas_prioritaria()
    if mesacategoria:
        return CargaCategoriaEnActa(request, mesacategoria)

    return NoHayAccion(request)



class IdentificacionDeFoto():
    """
    Acción de identificación de una foto (attachment).
    """

    def __init__(self, request, attachment, modo_ub=False):
        self.request = request
        self.attachment = attachment
        self.modo_ub = modo_ub
        # Asignamos el attachment al fiscal.
        request.user.fiscal.asignar_attachment(attachment)
        # Se registra que fue asignado a un fiscal.
        attachment.asignar_a_fiscal()

    def ejecutar(self):
        # Se realiza el redirect.
        base_url = reverse('asignar-mesa', kwargs={'attachment_id': self.attachment.id})
        return redirect_con_modo_ub_opcional(base_url, self.modo_ub)


def redirect_con_modo_ub_opcional(base_url, modo_ub):
    if not modo_ub:
        return redirect(base_url)
    query_string = urlencode({'modo_ub': modo_ub})
    url = f'{base_url}?{query_string}'
    return redirect(url)


def redirect_siguiente_accion(modo_ub):
    """
    Devuelve un reverse que apunta a siguiente acción con el parámetro modo_ub como corresponde.
    """
    base_url = reverse('siguiente-accion')
    if not modo_ub:
        # Shortcut.
        return base_url
    query_string = urlencode({'modo_ub': modo_ub})
    url = f'{base_url}?{query_string}'
    return url


class CargaCategoriaEnActa():
    """
    Acción de carga de votos en una mesa-categoría.
    Redirige a la vista para la carga de la mesa/categoría dependiendo
    de la configuracion de la categoría.
    """

    def __init__(self, request, mc, modo_ub=False):
        self.request = request
        self.mc = mc
        self.modo_ub = modo_ub
        # Se marca que se inicia una carga.
        request.user.fiscal.asignar_mesa_categoria(mc)
        mc.asignar_a_fiscal()

    def ejecutar(self):
        if (self.mc.categoria.requiere_cargas_parciales and
            self.mc.status in MesaCategoria.status_carga_parcial):
            # Sólo si la categoría requiere parciales y las parciales no están consolidadas.
            url_base = 'carga-parcial'
        else:
            url_base = 'carga-total'

        base_url = reverse(url_base, kwargs={'mesacategoria_id': self.mc.id})
        return redirect_con_modo_ub_opcional(base_url, self.modo_ub)


class NoHayAccion():

    def __init__(self, request):
        self.request = request

    def ejecutar(self):
        return render(self.request, 'fiscales/sin-actas.html')
