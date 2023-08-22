from loguru import logger
from rest_framework.decorators import action
from rest_framework.fields import CharField
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.viewsets import GenericViewSet

from georgian_payments.models import PaymentTransaction


class TbcSerializer(Serializer):
    PaymentId = CharField(required=True)


class TBCCallBackViewSet(GenericViewSet):
    permission_classes = []

    @action(detail=False, methods=["POST"], serializer_class=TbcSerializer)
    def callback(self, request: Request, *_, **__):
        logger.info(f'TBC Ecommerce Request Data {request.data}')
        payment_id = request.data.get('PaymentId')
        transaction: PaymentTransaction = PaymentTransaction.objects.filter(trx=payment_id).first()
        if transaction:
            transaction.sync_status()
        return Response()
