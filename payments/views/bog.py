from datetime import timedelta

from django.http import QueryDict
from django.utils import timezone
from loguru import logger
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from payments.choices import CardTypeChoices, BankTypeChoices, PTTChoices
from payments.models import PaymentTransaction
from payments.utils import remove_lists_from_dict_values


class BogCallBackViewSet(ViewSet):
    permission_classes = []
    authentication_classes = []

    @action(detail=False, methods=["POST"])
    def change_transaction_status(self, request: Request, *_, **__):
        logger.info(f"Request Data: {request.data}")
        data: dict = remove_lists_from_dict_values(request.data)
        trx = data.get('order_id', '')
        transaction: PaymentTransaction = PaymentTransaction.objects.filter(trx=trx).first()
        if transaction is None:
            logger.error(f'BOG Transaction | Transaction Not Found id: |{data.get("shop_order_id")}| - trx: |{trx}|')
            return Response(status=status.HTTP_400_BAD_REQUEST)
        is_success = data.get('status')
        is_ok = 1 if is_success == 'success' else -1 if is_success == 'error' else 0
        if is_ok == -1:
            time_out_minutes = 50 if data.get('payment_method') == 'BOG_LOAN' else 15
            if transaction.created + timedelta(minutes=time_out_minutes) < timezone.now():
                is_ok = -2
        if data.get('payment_method') == 'BOG_CARD':
            card_type = data.get('card_type')
            data['pan'] = '5***' if card_type == 'Mastercard' else '4***' if card_type == 'Visa' else '3***'
        transaction.card_hash = data.get('pan', '****') or "****"
        transaction.sync_status(data, is_ok)
        if is_ok == 1:
            if data.get('payment_method') == 'GC_CARD' and transaction.check_save_card(data.get('pan')):
                try:
                    transaction.user.cards.create(
                        number=data.get('pan'),
                        rec_id=data.get('order_id'),
                        card_type=CardTypeChoices.get_card_type(data['pan']),
                        bank_type=BankTypeChoices.BOG,
                        is_primary=not (transaction.user.cards.filter(is_primary=True).exists())
                    )
                except:
                    logger.error(f"BOG CARD CREATE | Card couldn't be created Transaction Id: {transaction.id}")
        return Response()

    @action(detail=False, methods=["POST"])
    def refund_status(self, request: Request, *_, **__):
        logger.info(f"BOG REFUND | {request.data}")
        data: QueryDict = request.data
        transaction: PaymentTransaction = PaymentTransaction.objects.filter(
            trx=data.get('order_id', ''),
            pay_id=data.get('payment_hash', ''),
            order_id=data.get('shop_order_id', ''),
            transaction_type__in=[PTTChoices.REFUND, PTTChoices.CASHBACK]
        ).first()
        if transaction is None:
            logger.error(f'BOG | REFUNDED | Transaction Not Found {data}')
            return Response()
        transaction.data_log.append(data)
        transaction.save(update_fields=['data_log'])
        if transaction.payment_method.is_installment:
            # @TODO REFUND STATUS
            # transaction.order.refunds.update(payment_status=RefundPaymentStatusChoices.RETURNED)
            pass
        return Response()
