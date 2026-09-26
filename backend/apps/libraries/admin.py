from django.contrib import admin
from .models import Library, Seat, PricingPlan

admin.site.register(Library)
admin.site.register(Seat)
admin.site.register(PricingPlan)