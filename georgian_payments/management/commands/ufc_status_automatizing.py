from datetime import timedelta

from django.core.management import BaseCommand
from django.db.models import Q
from django.utils import timezone

from georgian_payments.choices import BankTypeChoices, PaymentTypeChoices, PTSChoices, PTTChoices
from georgian_payments.models import PaymentTransaction


class Command(BaseCommand):
    help = "Register Transaction Automation With UFC"

    def handle(self, *args, **options):
        payment_transactions = PaymentTransaction.objects.filter(
            Q(status=PTSChoices.PENDING),
            payment_method__bank_type=BankTypeChoices.UFC,
            payment_method__payment_method=PaymentTypeChoices.CARD,
            trx__isnull=False,
            created__gte=timezone.now() - timedelta(minutes=40),
            transaction_type__in=[PTTChoices.PAY, PTTChoices.CONTRIBUTION]
        ).exclude(trx='').order_by('pk').distinct()
        for transaction in payment_transactions:
            transaction.sync_status()
