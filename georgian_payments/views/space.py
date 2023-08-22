from loguru import logger
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from georgian_payments.models import PaymentTransaction
from georgian_payments.serialaizers import SpaceCallbackSerializer


class SpaceCallBackViewSet(GenericViewSet):
    permission_classes = []

    @action(detail=False, methods=["POST"], serializer_class=SpaceCallbackSerializer)
    def callback(self, request: Request, *_, **__):
        logger.info(f'SPACE Request Data {request.data}')
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid(raise_exception=False):
            logger.info(f'Serializer NOT VALID {serializer.errors}')
            return Response({'Status': '-1', 'Description': serializer.errors})

        transaction = PaymentTransaction.objects.filter(trx=serializer.data['OrderId']).first()

        if not transaction:
            logger.info(f'Order Not Found {serializer.data["OrderId"]}')
            return Response({'Status': '-1', 'Description': 'Order not found'})

        status = serializer.data.get('Status')
        is_ok = 1 if status == '2' else 0 if status == '1' else -1

        transaction.sync_status(serializer.data, is_ok)

        return Response({'Status': '0', 'Description': 'Success'})
