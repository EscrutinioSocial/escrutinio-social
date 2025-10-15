import io
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic.edit import FormView
from django.core.files.uploadedfile import SimpleUploadedFile

from pdf2image import convert_from_bytes
import structlog

from adjuntos.forms import AgregarAttachmentsForm
from adjuntos.models import Attachment

logger = structlog.get_logger(__name__)


def image_to_uploadedfile(pil_image, name):
    """Recibe una instancia de PIL.Image, la guarda como jpg y la wrappea como un UploadFile"""
    buf = io.BytesIO()
    pil_image.save(buf, format="jpeg")
    return SimpleUploadedFile(
        name=name, content=buf.getvalue(), content_type="image/jpeg"
    )


class AgregarAdjuntos(FormView):
    """
    Permite subir una o más imágenes, generando instancias de ``Attachment``
    Si una imagen ya existe en el sistema, se exluye con un mensaje de error
    vía `messages` framework o en el lateral de la pantalla de carga.
    """

    form_class = AgregarAttachmentsForm

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.resultados_carga = []

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(AgregarAdjuntos, self).get_context_data(**kwargs)
        context["url_to_post"] = reverse(self.url_to_post)
        context["resultados_carga"] = self.resultados_carga
        return context

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist("file_field")
        pre_identificacion = kwargs.get("pre_identificacion", None)
        if form.is_valid():
            contador_archivos = 0
            for file in files:
                instances = self.procesar_adjunto(
                    file, request.user.fiscal, pre_identificacion
                )
                contador_archivos += len(instances)

            if contador_archivos > 0:
                self.mostrar_mensaje_archivos_cargados(contador_archivos)
            if len(self.resultados_carga) > 0:
                # Hay que volver a mostrar la misma pantalla para que se muestren
                # los resultados de carga.
                return self.render_to_response(self.get_context_data())
            else:
                return redirect(reverse(self.url_to_post))

        return self.form_invalid(form)

    def agregar_resultado_carga(self, nivel, mensaje):
        self.resultados_carga.append((nivel, mensaje))

    def procesar_adjunto(self, file_from_form, subido_por, pre_identificacion=None):
        if file_from_form.content_type == "application/pdf":
            images = [
                image_to_uploadedfile(image, f"{file_from_form.name}-page-{idx}.jpg")
                for idx, image in enumerate(convert_from_bytes(file_from_form.read()))
            ]
        else:
            # ya es una imagen,
            images = [file_from_form]

        parent = None
        instances = []
        for image in images:
            attach_instance = self.cargar_informacion_adjunto(
                image, subido_por, pre_identificacion, parent=parent
            )
            parent = parent or attach_instance
            instances.append(attach_instance)
        return instances

    def cargar_informacion_adjunto(
        self, adjunto, subido_por, pre_identificacion=None, parent=None
    ):
        try:
            instance = Attachment(mimetype=adjunto.content_type, parent=parent)
            instance.foto.save(adjunto.name, adjunto, save=False)
            instance.subido_por = subido_por
            if pre_identificacion is not None:
                instance.pre_identificacion = pre_identificacion
            instance.save()
            return instance
        except IntegrityError:
            self.agregar_resultado_carga(
                messages.WARNING,
                f"El archivo {adjunto.name} ya fue subido con anterioridad. <br>"
                "Verificá si era el que querías subir y, si lo era, "
                "no tenés que hacer nada.<br> ¡Gracias!",
            )
        return None

    def mostrar_mensaje_archivos_cargados(self, contador):
        self.agregar_resultado_carga(
            messages.INFO if contador == 0 else messages.SUCCESS,
            f"Subiste {contador} imágenes de actas. Gracias!",
        )

    def mostrar_mensaje_tipo_archivo_invalido(self, nombre_archivo):
        self.agregar_resultado_carga(
            messages.WARNING, f"{nombre_archivo} ignorado. No es una imagen"
        )
