"""Local development settings."""

from decouple import config

from .base import *
from .base import REST_FRAMEWORK

DEBUG = config("DEBUG", default=True, cast=bool)

# Browsable API is convenient locally; production serves JSON only.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
}

SCHEMA_PUBLIC = True
