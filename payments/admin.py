from django.contrib import admin

from payments.models import PaymentMethod, PaymentTransaction


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    pass


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    pass
