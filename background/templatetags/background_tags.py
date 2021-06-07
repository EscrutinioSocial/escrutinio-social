from django import template
from background.models import BackgroundImage
from django.conf import settings
from django.templatetags.static import static

register = template.Library()

@register.simple_tag
def background_image_url():
    if BackgroundImage.objects.exists():
    	return BackgroundImage.objects.order_by('?')[0].img.url
    elif getattr(settings, 'DEFAULT_BACKGROUND_IMAGE'):
    	return static(settings.DEFAULT_BACKGROUND_IMAGE)
    return ""