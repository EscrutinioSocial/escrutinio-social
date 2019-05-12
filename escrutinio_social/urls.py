from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import url, include
from django.contrib import admin
from material.frontend import urls as frontend_urls
from elecciones import urls as elecciones_urls
from fiscales import urls as fiscales_urls
from fiscales.views import choice_home, QuieroSerFiscal, confirmar_email
from fiscales.forms import AuthenticationFormCustomError
from django.contrib.auth import views as auth_views
from problemas.views import ProblemaCreate
from fancy_cache import cache_page


cached = cache_page(3600 * 24 * 30)

handler404 = 'fiscales.views.fix_404'

urlpatterns = [
    url(r'^$', choice_home, name="home"),
    url(r'^quiero-ser-fiscal/$', QuieroSerFiscal.as_view(), name='quiero-ser-fiscal'),
    url(r'^quiero-ser-fiscal/confirmar-email/(?P<uuid>[0-9a-f-]+)$', confirmar_email, name='confirmar-email'),
    url(r'^login/$', auth_views.LoginView.as_view(authentication_form=AuthenticationFormCustomError), name='login'),

    url(r'', include(frontend_urls)),
    url(r'', include('django.contrib.auth.urls')),
    url(r'^hijack/', include('hijack.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^fiscales/', include(fiscales_urls)),

    url(r'^elecciones/', include(elecciones_urls)),
    url(r'^clasificar-actas/', include('adjuntos.urls')),
    url('^reportar-problema/(?P<mesa_numero>\d+)$', ProblemaCreate.as_view(), name='reportar-problema'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
