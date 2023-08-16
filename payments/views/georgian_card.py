from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from loguru import logger
from rest_framework.authentication import BasicAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from payments.choices import CardTypeChoices, BankTypeChoices, PTSChoices
from payments.models import PaymentTransaction
from payments.sdk.georgian_card import GCBank

GEORGIAN_CARD_SETTINGS = settings.PAYMENT_CREDENTIALS['georgian_card']


class GeorgianCardCallBackViewSet(ViewSet):

    @staticmethod
    def fail_check(message):
        data = GCBank.get_check_fail_xml(message)
        r = StringIO()
        r.write(data)
        return HttpResponse(r.getvalue(), content_type="application/xml")

    @staticmethod
    def accept_check(transaction: PaymentTransaction):
        data = GCBank(transaction).get_check_accept_xml
        r = StringIO()
        r.write(data)
        return HttpResponse(r.getvalue(), content_type="application/xml")

    @staticmethod
    def save_user_card(transaction, data):
        fully_authenticated_status = data.get('p.isFullyAuthenticated', 'N')
        card_register_status = data.get('card.registered', 'N')
        card_recurrent = data.get('card.recurrent', 'N')
        if fully_authenticated_status == 'Y' and card_register_status == 'Y' and card_recurrent == 'Y':
            transaction.user.cards.create(
                number=data.get('p.maskedPan'),
                rec_id=data.get('card.id'),
                card_type=CardTypeChoices.get_card_type(data.get('p.maskedPan')),
                bank_type=BankTypeChoices.GC,
                is_primary=not (transaction.user.cards.filter(is_primary=True).exists())
            )

    @action(
        detail=False, methods=["GET"],
        authentication_classes=[BasicAuthentication],
        permission_classes=[IsAuthenticated]
    )
    def check(self, request: Request, *_, **__):
        logger.info(request.query_params)
        transaction: PaymentTransaction = PaymentTransaction.objects.filter(
            pk=request.query_params.get('o.transaction_id', 0)
        ).first()
        if transaction is None:
            return self.fail_check('Transaction Not Found')
        transaction.data_log.append({
            'Check Data': request.query_params.dict()
        })
        transaction.trx = request.query_params.get('trx_id', '')
        transaction.save(update_fields=['data_log', 'trx', 'updated'])
        if not transaction.user.is_active:
            return self.fail_check('User Is Not Active')
        if transaction.status != PTSChoices.PENDING:
            return self.fail_check('Bad Transaction Status In Veli')
        if GEORGIAN_CARD_SETTINGS['merchant_id'] != request.query_params.get('merch_id'):
            return self.fail_check('Merchant Not Found')
        return self.accept_check(transaction)

    @action(
        detail=False, methods=["GET"],
        authentication_classes=[BasicAuthentication],
        permission_classes=[IsAuthenticated]
    )
    def register(self, request: Request, *_, **__):
        logger.info(request.query_params)
        pk = request.query_params.get('o.transaction_id', 0)
        if not str(pk).isdigit():
            raise NotFound()
        transaction: PaymentTransaction = PaymentTransaction.objects.filter(
            pk=request.query_params.get('o.transaction_id', 0),
            trx=request.query_params.get('trx_id')
        ).first()
        if transaction is None:
            raise NotFound()

        data = request.query_params.dict()
        is_ok = int(data.get('result_code', 2))
        transaction.data_log.append({
            'Register Data': data
        })
        if is_ok != 1:
            is_ok = -1
            if transaction.created + timedelta(minutes=20) < timezone.now():
                is_ok = -2
        transaction.card_hash = data.get('p.maskedPan', '****') or "****"
        transaction.sync_status(data, is_ok, save_data=False)
        if transaction.save_card:
            self.save_user_card(transaction, data)
        return self.register_success_response()

    @staticmethod
    def register_success_response():
        content = render_to_string('payment/register_response.xml')
        r = StringIO()
        r.write(content)
        return HttpResponse(r.getvalue(), content_type="application/xml")

    @action(
        detail=False, methods=["POST"],
        authentication_classes=[],
        permission_classes=[]
    )
    def apple_pay_accept(self, request: Request, *_, **__):
        data = request.data.get('apple_data')
        pk = request.data.get('trans_id', 0)
        t: PaymentTransaction = PaymentTransaction.objects.filter(pk=pk).first()
        if t is None:
            raise NotFound
        t.additional_data['apple_data'] = data
        t.save(update_fields=['additional_data'])
        g = GCBank(t)
        status_code, result = g.apple_pay_accept()
        t.data_log.append({
            "accept_result": result
        })
        t.save(update_fields=['data_log'])
        return Response(result, status=status_code)
