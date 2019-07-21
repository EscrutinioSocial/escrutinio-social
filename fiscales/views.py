"""
define las vistas relacionadas a tareas que realizan los fiscales
como elegir acta a clasificar / a cargar / validar
"""
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.detail import DetailView
from django.utils.safestring import mark_safe
from django.views.generic.edit import UpdateView, CreateView
from django.views.generic.list import ListView
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import PasswordChangeView
from django.db import transaction
from django.utils.functional import cached_property
from annoying.functions import get_object_or_None
from .models import Fiscal
from elecciones.models import (
    Mesa,
    Carga,
    Seccion,
    Circuito,
    Categoria,
    MesaCategoria,
    VotoMesaReportado
)
from .acciones import siguiente_accion

from formtools.wizard.views import SessionWizardView
from django.template.loader import render_to_string
from html2text import html2text
from django.core.mail import send_mail
from sentry_sdk import capture_exception
from .forms import (
    MisDatosForm,
    votomesareportadoformset_factory,
    QuieroSerFiscal1,
    QuieroSerFiscal2,
    QuieroSerFiscal4,
    FiscalxDNI,
)
from contacto.views import ConContactosMixin
from problemas.models import Problema, ReporteDeProblema
from problemas.forms import IdentificacionDeProblemaForm

from django.conf import settings


NO_PERMISSION_REDIRECT = 'permission-denied'


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
    fiscal = get_object_or_404(Fiscal, user=request.user)
    if fiscal.esta_en_grupo('validadores'):
        return redirect('siguiente-accion')

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


class QuieroSerFiscal(SessionWizardView):
    form_list = [
        QuieroSerFiscal1,
        QuieroSerFiscal2,
        #  QuieroSerFiscal3,
        QuieroSerFiscal4
    ]

    def get_form_initial(self, step):
        if step != '0':
            dni = self.get_cleaned_data_for_step('0')['dni']
            email = self.get_cleaned_data_for_step('0')['email']
            fiscal = (get_object_or_None(Fiscal, dni=dni) or
                      get_object_or_None(Fiscal,
                                         datos_de_contacto__valor=email,
                                         datos_de_contacto__tipo='email'))

        if step == '1' and fiscal:
            if self.steps.current == '0':
                # sólo si acaba de llegar al paso '1' muestro mensaje
                messages.info(self.request, 'Ya estás en el sistema. Por favor, confirmá tus datos.')
            return {
                'nombre': fiscal.nombres,
                'apellido': fiscal.apellido,
                'telefono': fiscal.telefonos[0] if fiscal.telefonos else '',
            }

        return self.initial_dict.get(step, {})

    def done(self, form_list, **kwargs):
        data = self.get_all_cleaned_data()
        dni = data['dni']
        email = data['email']
        fiscal = (get_object_or_None(Fiscal, dni=dni) or
                  get_object_or_None(Fiscal,
                                     datos_de_contacto__valor=email,
                                     datos_de_contacto__tipo='email'))
        if fiscal:
            fiscal.estado = 'AUTOCONFIRMADO'
        else:
            fiscal = Fiscal(estado='AUTOCONFIRMADO', dni=dni)

        fiscal.dni = dni
        fiscal.nombres = data['nombre']
        fiscal.apellido = data['apellido']
        # fiscal.escuela_donde_vota = data['escuela']
        fiscal.save()
        fiscal.agregar_dato_de_contacto('teléfono', data['telefono'])
        fiscal.agregar_dato_de_contacto('email', email)

        fiscal.user.set_password(data['new_password1'])
        fiscal.user.save()

        body_html = render_to_string(
            'fiscales/email.html', {
                'fiscal': fiscal,
                'email': settings.DEFAULT_FROM_EMAIL,
                'cell_call': settings.DEFAULT_CEL_CALL,
                'cell_local': settings.DEFAULT_CEL_LOCAL,
                'site_url': settings.FULL_SITE_URL
            }
        )
        body_text = html2text(body_html)

        send_mail(
            '[NOREPLY] Recibimos tu inscripción como validador/a.',
            body_text,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
            html_message=body_html
        )

        return render(self.request, 'formtools/wizard/wizard_done.html', {
            'fiscal': fiscal, 'email': settings.DEFAULT_FROM_EMAIL,
            'cell_call': settings.DEFAULT_CEL_CALL, 'cell_local': settings.DEFAULT_CEL_LOCAL,
            'site_url': settings.FULL_SITE_URL
        })


def confirmar_email(request, uuid):
    fiscal = get_object_or_None(Fiscal, codigo_confirmacion=uuid)
    if not fiscal:
        texto = mark_safe('El código de confirmación es inválido. '
                          'Por favor copiá y pegá el link que te enviamos'
                          ' por email en la barra de direcciones'
                          'Si seguís con problemas, env '
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
@user_passes_test(lambda u: u.fiscal.esta_en_grupo('validadores'), login_url=NO_PERMISSION_REDIRECT)
def realizar_siguiente_accion(request):
    """
    Lanza la siguiente acción a realizar, que puede ser
    - identificar una foto (attachment)
    - cargar una mesa/categoría
    Si no hay ninguna acción pendiente, entonces muestra un mensaje al respecto
    """
    return siguiente_accion(request).ejecutar()


@login_required
@user_passes_test(lambda u: u.fiscal.esta_en_grupo('validadores'), login_url=NO_PERMISSION_REDIRECT)
def carga(request, mesacategoria_id, tipo='total'):
    """
    Es la vista que muestra y procesa el formset de carga de datos para una categoría-mesa.
    """
    fiscal = get_object_or_404(Fiscal, user=request.user)
    mesa_categoria = get_object_or_404(
        MesaCategoria,
        id=mesacategoria_id
    )
    solo_prioritarias = tipo == 'parcial'
    mesa = mesa_categoria.mesa
    categoria = mesa_categoria.categoria
    opciones = categoria.opciones_actuales(solo_prioritarias)

    if tipo == 'total' and mesa_categoria.status == MesaCategoria.STATUS.parcial_consolidada_dc:
        # una carga total con parcial consolidada reutiliza los datos ya cargados
        carga = mesa_categoria.carga_testigo
        votos_para_opcion = dict(carga.opcion_votos())
    else:
        carga = None
        votos_para_opcion = {}

    VotoMesaReportadoFormset = votomesareportadoformset_factory(
        min_num=opciones.count()
    )
    # XXX Crear la carga con el problema asociado si corresponde.

    def fix_opciones(formset):
        # hack para dejar sólo la opcion correspondiente a cada fila en los choicefields
        # se podria hacer "disabled" pero ese caso quita el valor del
        # cleaned_data y luego lo exige por ser requerido.
        first_autofoco = None
        for i, (opcion, form) in enumerate(zip(opciones, formset), 1):
            form.fields['opcion'].choices = [(opcion.id, str(opcion))]

            # esto hace que la navegacion mediante Tabs priorice los inputs de "votos"
            # por sobre los combo de "opcion"
            form.fields['opcion'].widget.attrs['tabindex'] = 99 + i

            if carga and votos_para_opcion.get(opcion.id):
                # los campos previamente cargados son solo lectura
                form.fields['votos'].widget.attrs['readonly'] = True
            else:
                form.fields['votos'].widget.attrs['tabindex'] = i

                if not first_autofoco:
                    first_autofoco = True
                    form.fields['votos'].widget.attrs['autofocus'] = True

            # todos los campos son requeridos
            form.fields['votos'].required = True

    data = request.POST if request.method == 'POST' else None

    qs = VotoMesaReportado.objects.none()
    initial = [{'opcion': o, 'votos': votos_para_opcion.get(o.id)} for o in opciones]
    formset = VotoMesaReportadoFormset(data, queryset=qs, initial=initial, mesa=mesa)
    fix_opciones(formset)
    is_valid = False
    if qs:
        formset.convert_warnings = True  # monkepatch

    if request.method == 'POST' or qs:
        is_valid = formset.is_valid()

    if is_valid:

        try:
            with transaction.atomic():
                # se guardan los datos. El contenedor `carga`
                # y los votos del formset asociados.
                if carga:
                    carga.fiscal = fiscal
                    carga.save()
                else:
                    carga = Carga.objects.create(
                        mesa_categoria=mesa_categoria,
                        tipo=tipo,
                        fiscal=fiscal,
                    )
                for form in formset:
                    vmr = form.save(commit=False)
                    vmr.carga = carga
                    vmr.save()
                # Libero el token sobre la mc
                mesa_categoria.release()
            carga.actualizar_firma()
            messages.success(request, f'Guardada categoría {categoria} para {mesa}')
        except Exception as e:
            # este catch estaba desde cuando no podia haber multiples cargas para una
            # misma mesa-categoria
            # ahora no podria darte IntegrityError porque esta vista sólo crea objetos
            # y ya no hay constraint.
            # Lo dejo por si queremos canalizar algun otro tipo de excepcion
            capture_exception(e)

        return redirect('siguiente-accion')

    # Llega hasta acá si hubo error.
    return render(
        request, "fiscales/carga.html", {
            'formset': formset,
            'categoria': categoria,
            'object': mesa,
            'is_valid': is_valid or request.method == 'GET',
            'recibir_problema': 'problema',
            'dato_id': mesa_categoria.id,
            'form_problema': IdentificacionDeProblemaForm()
        }
    )

class ReporteDeProblemaCreateView(CreateView):
    http_method_names = ['post']
    form_class = IdentificacionDeProblemaForm
    template_name = "problemas/problema.html"

    @cached_property
    def mesa_categoria(self):
        return get_object_or_404(
            MesaCategoria, id=self.kwargs['mesacategoria_id']
        )

    def form_invalid(self, form):
        messages.info(
            self.request,
            f'No se registró el reporte. Corroborá haber elegido una opción.',
            extra_tags="problema"
        )
        return redirect('siguiente-accion')

    def form_valid(self, form):            
        fiscal = self.request.user.fiscal
        carga = form.save(commit=False)
        carga.fiscal = fiscal
        carga.status = Carga.TIPOS.problema
        # Lo falso grabo para quedarme con la data de sus campos.
        reporte_de_problema = form.save(commit=False)
        tipo_de_problema = reporte_de_problema.tipo_de_problema
        descripcion = reporte_de_problema.descripcion

        # Creo la identificación.
        carga = Carga.objects.create(
            tipo=Carga.TIPOS.problema,
            fiscal=fiscal,
            mesa_categoria=self.mesa_categoria
        )

        # Creo el problema asociado.
        Problema.reportar_problema(fiscal, descripcion, tipo_de_problema, carga=carga)

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
    Muestra la carga actual de la categoria para la mesa
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


class AutocompleteBaseListView(LoginRequiredMixin, ListView):

    def get(self, request, *args, **kwargs):
        data = {'options': [{'value': o.id, 'text': str(o)} for o in self.get_queryset()]}
        return JsonResponse(data, status=200, safe=False)


class SeccionListView(AutocompleteBaseListView):
    model = Seccion

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(distrito__id=self.request.GET['parent_id'])


class CircuitoListView(AutocompleteBaseListView):
    model = Circuito

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(seccion__id=self.request.GET['parent_id'])


class MesaListView(AutocompleteBaseListView):
    model = Mesa

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(lugar_votacion__circuito__id=self.request.GET['parent_id'])

