"""
define las vistas relacionadas a tareas que realizan los fiscales
como elegir acta a clasificar / a cargar / validar
"""
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, get_object_or_404, render
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.detail import DetailView
from django.utils.safestring import mark_safe
from django.views.generic.edit import UpdateView, CreateView, FormView
from django.views.generic.list import ListView
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import PasswordChangeView
from django.db import transaction
from django.db.models import Q
from django.utils.functional import cached_property
from annoying.functions import get_object_or_None
import structlog
from .models import Fiscal, CodigoReferido
from elecciones.models import (
    Distrito,
    Mesa,
    Carga,
    Seccion,
    Circuito,
    Categoria,
    MesaCategoria,
    VotoMesaReportado
)
from .acciones import siguiente_accion, redirect_siguiente_accion
from adjuntos.consolidacion import consolidar_cargas

from dal import autocomplete

from html2text import html2text
from django.core.mail import send_mail
from sentry_sdk import capture_exception, capture_message
from .forms import (
    MisDatosForm,
    votomesareportadoformset_factory,
    QuieroSerFiscalForm,
    ReferidoForm,
    EnviarEmailForm,
)

from .email_sender import enviar_correo

from contacto.views import ConContactosMixin
from problemas.models import Problema
from problemas.forms import IdentificacionDeProblemaForm

from django.conf import settings
import structlog


NO_PERMISSION_REDIRECT = 'permission-denied'

logger = structlog.get_logger(__name__)


@login_required
def bienvenido(request):
    return render(request, 'fiscales/bienvenido.html')


def choice_home(request):
    """
    redirige a una página en funcion del tipo de usuario
    """
    user = request.user
    if not user.is_authenticated:
        return redirect('login')
    try:
        fiscal = user.fiscal
    except Fiscal.DoesNotExist:
        fiscal = None

    if fiscal and fiscal.esta_en_grupo('validadores'):
        return redirect('siguiente-accion')
    elif user.is_staff:
        return redirect('admin:index')
    return redirect('bienvenido')


def permission_denied(request):
    raise PermissionDenied()


class BaseFiscal(LoginRequiredMixin, DetailView):
    model = Fiscal

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categoria'] = Categoria.objects.first()
        return context

    def get_object(self, *args, **kwargs):
        try:
            return self.request.user.fiscal
        except Fiscal.DoesNotExist:
            raise Http404('no está registrado como fiscal')


class QuieroSerFiscal(FormView):

    title = "Quiero ser validador/a"
    template_name = 'fiscales/quiero-validar.html'
    form_class = QuieroSerFiscalForm

    def get_initial(self):
        initial = super().get_initial()
        initial['referido_por_codigo'] = self.kwargs.get('codigo_ref', None)
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        fiscal = Fiscal(estado='AUTOCONFIRMADO', dni=data['dni'])
        fiscal.nombres = data['nombres']
        fiscal.apellido = data['apellido']
        fiscal.seccion = data['seccion']
        fiscal.referente_nombres = data['referente_nombres']
        fiscal.referente_apellido = data['referente_apellido']
        if data['referido_por_codigo']:
            codigo = data['referido_por_codigo']
            referente, certeza = CodigoReferido.fiscales_para(codigo)[0]
            fiscal.referente = referente
            fiscal.referente_certeza = certeza
            if referente:
                fiscal.referido_por_codigos = f'{referente.referido_por_codigos}-{codigo}'
            else:
                fiscal.referido_por_codigos = codigo
        fiscal.save()
        telefono = data['telefono_area'] + data['telefono_local']
        fiscal.agregar_dato_de_contacto('teléfono', telefono)
        fiscal.agregar_dato_de_contacto('email', data['email'])
        fiscal.user.set_password(data['password'])
        fiscal.user.email = data['email']
        fiscal.user.save()
        self.enviar_correo_confirmacion(fiscal, data['email'])

        # se guarda el fiscal en la sesión para que se consuma en la página de agradecimiento
        self.request.session['fiscal_id'] = fiscal.id
        self.success_url = reverse('quiero-validar-gracias')
        return super().form_valid(form)

    def enviar_correo_confirmacion(self, fiscal, email):
        enviar_correo(
            '[NOREPLY] Recibimos tu inscripción como validador/a.',
            fiscal,
            email
        )


def quiero_validar_gracias(request):
    fiscal = get_object_or_None(Fiscal, id=request.session.get('fiscal_id'))
    return render(request, 'fiscales/quiero-validar-gracias.html', {'fiscal': fiscal})


@login_required
def referidos(request):
    fiscal = request.user.fiscal
    if request.method == 'POST':
        if 'link' in request.POST:
            fiscal.crear_codigo_de_referidos()
        elif 'conozco' in request.POST:
            # TODO ver como dejar traza de esto
            referidos_confirmados = request.POST.getlist('referido')
            fiscal.referidos.filter(id__in=referidos_confirmados).update(referencia_confirmada=True)
            fiscal.referidos.exclude(id__in=referidos_confirmados).update(referencia_confirmada=False)

    form = ReferidoForm(initial={'url': fiscal.ultimo_codigo_url()})
    return render(request, 'fiscales/referidos.html', {'form': form, 'referidos': fiscal.referidos.all()})


def confirmar_email(request, uuid):
    fiscal = get_object_or_None(Fiscal, codigo_confirmacion=uuid)
    if not fiscal:
        texto = mark_safe('El código de confirmación es inválido. '
                          'Por favor copiá y pegá el link que te enviamos'
                          ' por email en la barra de direcciones'
                          'Si seguís con problemas, envía un mail a '
                          '<a href="mailto:{email}">'
                          '{email}</a>'.format(email=settings.DEFAULT_FROM_EMAIL))

    elif fiscal.email_confirmado:
        texto = 'Tu email ya estaba confirmado. Gracias.'
    else:
        fiscal.email_confirmado = True
        fiscal.save(update_fields=['email_confirmado'])
        texto = 'Confirmamos tu email exitosamente. ¡Gracias!'

    return render(
        request, 'fiscales/confirmar_email.html',
        {'texto': texto, 'fiscal': fiscal,
            'email': settings.DEFAULT_FROM_EMAIL,
            'cell_call': settings.DEFAULT_CEL_CALL,
            'cell_local': settings.DEFAULT_CEL_LOCAL,
            'site_url': settings.FULL_SITE_URL}
    )


class MisDatos(BaseFiscal):
    template_name = "fiscales/mis-datos.html"


class MisDatosUpdate(ConContactosMixin, UpdateView, BaseFiscal):
    """muestras los contactos para un fiscal"""
    form_class = MisDatosForm
    template_name = "fiscales/mis-datos-update.html"

    def get_success_url(self):
        return reverse('mis-datos')


@login_required
@user_passes_test(lambda u: u.fiscal.esta_en_algun_grupo(('validadores', 'unidades basicas')),
    login_url=NO_PERMISSION_REDIRECT)
def realizar_siguiente_accion(request):
    """
    Lanza la siguiente acción a realizar, que puede ser
    - identificar una foto (attachment)
    - cargar una mesa/categoría
    Si no hay ninguna acción pendiente, entonces muestra un mensaje al respecto
    """
    return siguiente_accion(request).ejecutar()


@login_required
@user_passes_test(lambda u: u.fiscal.esta_en_grupo('unidades basicas'), login_url=NO_PERMISSION_REDIRECT)
@transaction.atomic
def cargar_desde_ub(request, mesa_id, tipo='total'):
    mesa_existente = get_object_or_404(Mesa, id=mesa_id)

    if request.method == 'GET':
        mesacategoria = MesaCategoria.objects.filter(mesa=mesa_existente).siguiente_para_ub()
        if mesacategoria:
            # Se la asignamos.
            mesacategoria.asignar_a_fiscal()
            request.user.fiscal.asignar_mesa_categoria(mesacategoria)
    else:
        mesa_cat_id = request.session.pop('mesa_categoria_id', None)
        mesacategoria = MesaCategoria.objects.get(id=mesa_cat_id)

    if mesacategoria:
        return carga(request, mesacategoria.id, desde_ub=True)

    # si es None, lo llevamos a subir un adjunto
    return redirect('agregar-adjuntos-ub')


@login_required
@user_passes_test(
    lambda u: u.fiscal.esta_en_algun_grupo(('validadores', 'unidades basicas')),
    login_url=NO_PERMISSION_REDIRECT
)
def carga(request, mesacategoria_id, tipo='total', desde_ub=False):
    """
    Es la vista que muestra y procesa el formset de carga de datos para una categoría-mesa.
    """
    fiscal = request.user.fiscal
    mesa_categoria = get_object_or_404(MesaCategoria, id=mesacategoria_id)
    modo = desde_ub or request.GET.get('modo_ub', False)

    # Sólo el fiscal a quien se le asignó la mesa tiene permiso de cargar esta mc
    if fiscal.mesa_categoria_asignada != mesa_categoria:
        capture_message(
            f"""
            Intento de cargar mesa-categoria {mesa_categoria.id}

        mesa categoría: {mesa_categoria.id}
            fiscal: {fiscal} ({fiscal.id}, tenía asignada: {fiscal.mesa_categoria_asignada})
            """
        )
        # TO DO: quizas sumar puntos al score anti-trolling?
        # Lo mandamos nuevamente a que se le dé algo para hacer.
        return redirect(reverse('siguiente-accion'))

    # En carga parcial sólo se cargan opciones prioritarias.
    solo_prioritarias = tipo == 'parcial'
    mesa = mesa_categoria.mesa
    categoria = mesa_categoria.categoria
    if request.method == 'GET':
        logger.info('Carga inicio', mc=mesa_categoria.id, tipo=tipo)

    # Tenemos la lista de opciones ordenadas como el acta.
    opciones = categoria.opciones_actuales(solo_prioritarias, excluir_optativas=True)

    datos_previos = mesa_categoria.datos_previos(tipo)

    # Obtenemos la clase para el formset seteando tantas filas como opciones
    # existen. Como extra=0, el formset tiene un tamaño fijo
    VotoMesaReportadoFormset = votomesareportadoformset_factory(
        min_num=opciones.count()
    )

    def fix_opciones(formset):
        """
        Función auxiliar que deja sólo la opcion correspondiente a cada fila en los
        choicefields de cada formulario, configura widget readonly necesarios
        y la índice de la navegación con tabs
        """
        first_autofoco = None
        for i, (opcion, form) in enumerate(zip(opciones, formset), 1):
            form.fields['opcion'].choices = [(opcion.id, opcion)]

            # esto hace que la navegacion mediante Tabs priorice los inputs de "votos"
            # por sobre los combo de "opcion"
            form.fields['opcion'].widget.attrs['tabindex'] = 99 + i

            if datos_previos.get(opcion.id):
                # los campos que ya conocemos (metadata o cargas parciales consolidadas)
                # los marcamos como sólo lectura
                form.fields['votos'].widget.attrs['readonly'] = True
            else:
                form.fields['votos'].widget.attrs['tabindex'] = i

                if not first_autofoco:
                    first_autofoco = True
                    form.fields['votos'].widget.attrs['autofocus'] = True

            # Todos los campos son requeridos
            form.fields['votos'].required = True

    data = request.POST if request.method == 'POST' else None

    qs = VotoMesaReportado.objects.none()
    initial = [{'opcion': o, 'votos': datos_previos.get(o.id)} for o in opciones]
    formset = VotoMesaReportadoFormset(
        data, queryset=qs, initial=initial, mesa=mesa, datos_previos=datos_previos
    )
    fix_opciones(formset)

    is_valid = False
    if request.method == 'POST':
        is_valid = formset.is_valid()
        if not is_valid:
            logger.info('carga error', mc=mesa_categoria.id, tipo=tipo, ub=modo_ub)

    if desde_ub:
        request.session['mesa_categoria_id'] = mesa_categoria.id

    if is_valid:
        try:
            with transaction.atomic():
                # Se guardan los datos. El contenedor `carga`
                # y los votos del formset asociados.
                carga = Carga.objects.create(
                    mesa_categoria=mesa_categoria,
                    tipo=tipo,
                    fiscal=fiscal,
                    origen=Carga.SOURCES.web if not modo_ub else Carga.SOURCES.csv
                )
                reportados = []
                for form in formset:
                    vmr = form.save(commit=False)
                    vmr.carga = carga
                    reportados.append(vmr)
                VotoMesaReportado.objects.bulk_create(reportados)

                mesa_categoria.desasignar_a_fiscal()  # Le bajamos la cuenta.
                # Si viene modo_ub, consolidamos la carga.
                if modo_ub:
                    consolidar_cargas(mesa_categoria)

            messages.success(request, f'Carga de {categoria} en mesa {mesa} guardada.')
        except Exception as e:
            # Este catch estaba desde cuando no podía haber múltiples cargas para una
            # misma mesa-categoría.
            # Ahora no podría darte IntegrityError porque esta vista sólo crea objetos
            # y ya no hay constraint.
            # Lo dejamos para enterarnos de algun otro tipo de excepción.
            capture_exception(e)

        if not is_valid:
            logger.info('carga error', mc=mesa_categoria.id, tipo=tipo, ub=modo_ub)

        redirect_to = redirect_siguiente_accion(desde_ub) if not desde_ub else reverse('cargar-desde-ub', args=[mesa.id])

        return redirect(redirect_to)

    # Llega hasta acá si hubo error o viene de un GET
    return render(
        request,
        'fiscales/carga.html' if not desde_ub else 'fiscales/carga_ub.html',
        {
            'formset': formset,
            'categoria': categoria,
            'object': mesa,
            'is_valid': is_valid or request.method == 'GET',
            'recibir_problema': 'problema',
            'dato_id': mesa_categoria.id,
            'form_problema': IdentificacionDeProblemaForm(),
            'action': reverse('cargar-desde-ub', args=[mesa.id]) if desde_ub else None,
        }
    )


class ReporteDeProblemaCreateView(FormView):
    http_method_names = ['post']
    form_class = IdentificacionDeProblemaForm
    template_name = "problemas/problema.html"

    @cached_property
    def mesa_categoria(self):
        return get_object_or_404(
            MesaCategoria, id=self.kwargs['mesacategoria_id']
        )

    def form_invalid(self, form):
        tipo = bool(form.errors.get('tipo_de_problema', False))
        descripcion = bool(form.errors.get('descripcion', False))
        return JsonResponse({'problema_tipo': tipo, 'problema_descripcion': descripcion}, status=500)

    def form_valid(self, form):
        # mismo hack que en la misma vista adjuntos.views.ReporteDeProblemaCreateView
        # FIX ME: no tiene tests
        if self.request.is_ajax():
            fiscal = self.request.user.fiscal
            carga = form.save(commit=False)
            carga.fiscal = fiscal
            carga.status = Carga.TIPOS.problema
            # Lo falso grabo para quedarme con la data de sus campos.
            reporte_de_problema = form.save(commit=False)
            tipo_de_problema = reporte_de_problema.tipo_de_problema
            descripcion = reporte_de_problema.descripcion

            # Creo la carga.
            carga = Carga.objects.create(
                tipo=Carga.TIPOS.problema,
                fiscal=fiscal,
                origen=Carga.SOURCES.web,
                mesa_categoria=self.mesa_categoria
            )

            # Creo el problema asociado.
            Problema.reportar_problema(fiscal, descripcion, tipo_de_problema, carga=carga)
            return JsonResponse({'status': 'hack'})
        messages.info(
            self.request,
            f'Gracias por el reporte. Ahora pasamos a la siguiente acta.',
            extra_tags="problema"
        )
        return redirect('siguiente-accion')


@login_required
@user_passes_test(lambda u: u.fiscal.esta_en_grupo('validadores'), login_url=NO_PERMISSION_REDIRECT)
def detalle_mesa_categoria(request, categoria_id, mesa_numero, carga_id=None):
    """
    Muestra la carga actual de la categoría para la mesa
    """
    mc = get_object_or_404(
        MesaCategoria,
        mesa__numero=mesa_numero,
        categoria__id=categoria_id,
        carga_testigo__isnull=False,
    )
    mesa = mc.mesa
    categoria = mc.categoria
    carga = mc.carga_testigo
    reportados = carga.reportados.order_by('opcion__orden')
    return render(
        request,
        "fiscales/detalle_mesa_categoria.html",
        {
            'reportados': reportados,
            'object': mesa,
            'categoria': categoria
        }
    )


class CambiarPassword(PasswordChangeView):
    template_name = "fiscales/cambiar-contraseña.html"
    success_url = reverse_lazy('mis-datos')

    def form_valid(self, form):
        messages.success(self.request, 'Tu contraseña se cambió correctamente')
        return super().form_valid(form)


@login_required
def confirmar_fiscal(request, fiscal_id):
    """
    cambia el estado del fiscal con el id dado a CONFIRMADO y redirige a
    a la página previa con un mensaje
    """
    fiscal = get_object_or_404(Fiscal, id=fiscal_id, estado='AUTOCONFIRMADO')
    fiscal.estado = 'CONFIRMADO'
    fiscal.save(update_fields=['estado'])
    url = reverse('admin:fiscales_fiscal_change', args=(fiscal_id,))
    msg = f'<a href="{url}">{fiscal}</a> ha sido confirmado'
    messages.info(request, mark_safe(msg))
    return redirect(request.META.get('HTTP_REFERER'))


class EnviarEmail(FormView):
    """
    Permite enviar email a los fiscales seleccionados en admin.
    Usa base_email como template
    """

    form_class = EnviarEmailForm
    template_name = 'fiscales/enviar_email.html'
    success_url = reverse_lazy('admin:fiscales_fiscal_changelist')

    @method_decorator(staff_member_required)
    def dispatch(self, request, *args, **kwargs):
        ids = request.GET.get('ids', '').split(',')
        self.fiscales = Fiscal.objects.filter(
            id__in=ids
        )
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        asunto = self.request.session.get('enviar_email_asunto')
        if asunto:
            initial['asunto'] = asunto
        template = self.request.session.get('enviar_email_template')
        if template:
            initial['template'] = template
        return initial

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['count'] = self.fiscales.count()
        return context

    def form_valid(self, form):
        # guardamos en la session la data del ultimo mail
        # para inicializar el form en el proximo
        self.request.session['enviar_email_template'] = form.data['template']
        self.request.session['enviar_email_asunto'] = form.data['asunto']

        template = form.cleaned_data['template']
        count = 0
        for fiscal in self.fiscales:
            emails = list(fiscal.emails)
            if not emails:
                continue
            context = {
                'fiscal': fiscal,
                'email': settings.DEFAULT_FROM_EMAIL,
                'cell_call': settings.DEFAULT_CEL_CALL,
                'cell_local': settings.DEFAULT_CEL_LOCAL,
                'site_url': settings.FULL_SITE_URL
            }
            body_html = template.render(context, request=self.request)
            body_text = html2text(body_html)
            send_mail(
                form.cleaned_data['asunto'],
                body_text,
                settings.DEFAULT_FROM_EMAIL,
                list(fiscal.emails),
                fail_silently=False,
                html_message=body_html
            )
            count += 1
        messages.success(self.request, f'Email enviado a {count} fiscales')
        return super().form_valid(form)


class AutocompleteBaseListView(ListView):

    def get(self, request, *args, **kwargs):
        try:
            data = {'options': [{'id': o.id, 'text': str(o), 'selected_text': str(o)} for o in self.get_queryset(request)]}
        except:
            return JsonResponse(data={}, status=500)
        return JsonResponse(data, status=200, safe=False)


class DistritoBaseListView(AutocompleteBaseListView):
    model = Distrito

    def get_queryset(self, request):
        qs = Distrito.objects.all()
        if request.GET['id']:
            qs = qs.filter(numero=request.GET['id'])
        return qs


class AjaxListView(autocomplete.Select2QuerySetView):
    def get_result_label(self, item):
        return item.nombre

    def get_selected_result_label(self, item):
        return item.numero


class DistritoSimpleListView(autocomplete.Select2QuerySetView):
    model = Distrito

    def get_queryset(self):
        qs = Distrito.objects.all()
        lookups = Q()
        if self.q:
            lookups &= Q(numero=self.q) | Q(nombre__istartswith=self.q)
        return qs.filter(lookups)


class SeccionSimpleListView(autocomplete.Select2QuerySetView):
    model = Seccion

    def get_queryset(self):
        qs = Seccion.objects.all()
        lookups = Q()
        distrito = self.forwarded.get('distrito', None)
        if distrito:
            lookups &= Q(distrito_id=distrito)
        if self.q:
            lookups &= Q(numero=self.q) | Q(nombre__istartswith=self.q)

        return qs.filter(lookups)


class DistritoListView(AjaxListView):
    model = Distrito

    def get_queryset(self):
        qs = Distrito.objects.all()
        lookups = Q()
        ident = self.request.GET.get('ident', None)
        if ident is not None:
            return qs.filter(id=ident)
        if self.q:
            lookups = Q(numero=self.q) | Q(nombre__istartswith=self.q)
        return qs.filter(lookups)


class SeccionListView(AjaxListView):
    model = Seccion

    def get_queryset(self):
        qs = Seccion.objects.all()
        lookups = Q()
        distrito = self.forwarded.get('distrito', None)
        ident = self.request.GET.get('ident', None)
        if ident is not None:
            return qs.filter(id=ident)
        if self.q:
            lookups = Q(numero__iexact=self.q)
        if distrito:
            lookups &= Q(distrito_id=distrito)
        mesa = self.forwarded.get('mesa', None)
        desdeMesa = self.forwarded.get('desdeMesa', None)
        if mesa and desdeMesa:
            mesas = Mesa.objects.filter(id=mesa).values('circuito__seccion_id')
            lookups &= Q(id__in=mesas)
        return qs.filter(lookups)


class CircuitoListView(AjaxListView):
    model = Circuito

    def get_queryset(self):
        qs = Circuito.objects.all()
        lookups = Q()
        ident = self.request.GET.get('ident', None)
        if ident is not None:
            return qs.filter(id=ident)
        if self.q:
            lookups = Q(numero__iexact=self.q)
        seccion = self.forwarded.get('seccion', None)
        if seccion and seccion != "-1":
            lookups &= Q(seccion_id=seccion)
        distrito = self.forwarded.get('distrito', None)
        if distrito:
            lookups &= Q(seccion__distrito_id=distrito)
        mesa = self.forwarded.get('mesa', None)
        desdeMesa = self.forwarded.get('desdeMesa', None)
        if mesa and desdeMesa:
            mesas = Mesa.objects.filter(id=mesa).values('circuito_id')
            lookups &= Q(id__in=mesas)
        return qs.filter(lookups)


class MesaListView(AjaxListView):
    model = Mesa

    def get_result_label(self, item):
        return item.lugar_votacion.nombre

    def get_selected_result_label(self, item):
        return item.numero

    def get_queryset(self):
        qs = Mesa.objects.all()
        lookups = Q()
        if self.q:
            lookups &= Q(numero__iexact=self.q)
        circuito = self.forwarded.get('circuito',None)
        if circuito and circuito != "-1":
            lookups &= Q(circuito_id=circuito)
        seccion = self.forwarded.get('seccion',None)
        if seccion and seccion != "-1":
            lookups &= Q(circuito__seccion_id=seccion)
        distrito = self.forwarded.get('distrito',None)
        if distrito:
            lookups &= Q(circuito__seccion__distrito_id=distrito)
        return qs.filter(lookups)

