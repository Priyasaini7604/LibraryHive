import os

from django.core.wsgi import get_wsgi_application

# Deployed processes use production settings unless explicitly overridden.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_wsgi_application()
