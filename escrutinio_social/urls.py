from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import url, include
from django.contrib import admin
from django.contrib.auth import views as auth_views

from fancy_cache import cache_page

from material.frontend import urls as frontend_urls

from elecciones import urls as elecciones_urls

from problemas import urls as problemas_urls

from fiscales import urls as fiscales_urls
from fiscales.views import (
    choice_home,
    confirmar_email,
    EnviarEmail,
    permission_denied,
    quiero_validar_gracias,
    QuieroSerFiscal,
)
from fiscales.forms import AuthenticationFormCustomError

from api import urls as api_urls
from antitrolling import urls as antitrolling_urls

cached = cache_page(3600 * 24 * 30)

urlpatterns = [
    url(r'^$', choice_home, name="home"),
    url(r'^permission-denied$', permission_denied, name='permission-denied'),
    url(r'^quiero-validar/(?P<codigo_ref>\w+)?$', QuieroSerFiscal.as_view(), name='quiero-validar'),
    url(r'^quiero-validar/gracias/$', quiero_validar_gracias, name='quiero-validar-gracias'),
    url(r'^quiero-validar/confirmar-email/(?P<uuid>[0-9a-f-]+)$', confirmar_email, name='confirmar-email'),
    url(r'^login/$', auth_views.LoginView.as_view(
        authentication_form=AuthenticationFormCustomError
    ), name='login'),
    url(r'', include(frontend_urls)),
    url(r'', include('django.contrib.auth.urls')),
    url(r'^hijack/', include('hijack.urls')),
    url('^admin/enviar_email$', EnviarEmail.as_view(), name='enviar-email'),
    url(r'^admin/', admin.site.urls),
    url(r'^fiscales/', include(fiscales_urls)),

    url(r'^elecciones/', include(elecciones_urls)),
    url(r'^clasificar-actas/', include('adjuntos.urls')),

    url(r'^api/', include(api_urls)),
    url(r'^problemas/', include(problemas_urls)),
    url(r'^antitrolling/', include(antitrolling_urls)),
    url(r'^summernote/', include('django_summernote.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    import debug_toolbar
    from django.urls import include, path
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),

        # For django versions before 2.0:
        # url(r'^__debug__/', include(debug_toolbar.urls)),

    ] + urlpatterns
    SHOW_TOOLBAR_CALLBACK = True
