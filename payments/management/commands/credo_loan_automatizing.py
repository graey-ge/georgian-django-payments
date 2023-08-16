from datetime import timedelta

from django.core.management import BaseCommand
from django.utils import timezone
from django.utils.timezone import localtime

from payments.choices import BankTypeChoices, PaymentTypeChoices, PTTChoices, PTSChoices
from payments.models import PaymentTransaction


class Command(BaseCommand):
    help = "Register Order Automation With Credo"

    def handle(self, *args, **options):
        queryset = PaymentTransaction.objects.filter(
            status=PTSChoices.PENDING,
            payment_method__bank_type=BankTypeChoices.CREDO,
            payment_method__payment_method=PaymentTypeChoices.LOAN,
            trx__isnull=False,
            updated__gte=localtime(timezone.now()) - timedelta(days=3),
            transaction_type=PTTChoices.PAY
        ).exclude(trx='').order_by('-pk').distinct()
        for transaction in queryset:  # type: PaymentTransaction
            transaction.sync_status()
