"""Installed only by `config.settings.e2e`: replaces the payment gateway with a local fake."""

from django.apps import AppConfig


class E2ESupportConfig(AppConfig):
    name = "config.e2e_support"
    label = "e2e_support"

    def ready(self):
        from apps.payments.gateway import use_gateway

        from .gateway import E2EGateway

        use_gateway(E2EGateway())
