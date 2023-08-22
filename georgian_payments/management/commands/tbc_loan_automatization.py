from django.core.management import BaseCommand

from loguru import logger

from georgian_payments.choices import ManualActionChoices
from georgian_payments.models import PaymentTransaction
from georgian_payments.sdk.tbc import TbcInstallmentSDK


class Command(BaseCommand):
    help = "TBC Loan Automation"

    def handle(self, *args, **options):
        tbc = TbcInstallmentSDK()
        data = tbc.status_changes()
        logger.info(data)
        if not data or data.get("status") == 500:
            return
        request_id = data['synchronizationRequestId']
        for change in data['statusChanges']:
            session_id = change['sessionId']
            status_id = change['statusId']
            transaction: PaymentTransaction = PaymentTransaction.objects.filter(trx=session_id).first()
            if transaction is None:
                continue
            is_ok = 0
            # Save Status
            if status_id == 5:
                transaction.set_need_manual_action(ManualActionChoices.CALL_FOR_LOAN_CANCEL)
                pass
            if status_id in [3, 4, 6, 7]:
                is_ok = -1
            elif status_id == 8:
                is_ok = 1
                if change.get('contributionAmount'):
                    transaction.set_need_manual_action(ManualActionChoices.TBC_LOAN_CONTRIBUTION)
                    pass

            try:
                succeed_amount = change.get('amount') - (change.get('contributionAmount', 0) or 0)
                transaction.sync_status(change, is_ok, succeed_amount=succeed_amount)
            except:
                logger.error(
                    'TBC Loan Status Sync Error: '
                    f'Transaction ID: {transaction.id}, NewStatus: {status_id}, SessionId: {session_id}'
                )
        tbc = TbcInstallmentSDK()
        tbc.status_changes_sync(request_id)
