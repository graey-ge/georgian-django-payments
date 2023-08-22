import random
import string
from typing import Dict, Tuple

from django.conf import settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.timezone import localtime
from geopayment import TBCProvider
from loguru import logger

from georgian_payments.choices import BankTypeChoices, CardTypeChoices
from georgian_payments.sdk.base import AbstractBankSDK


class UfcSdk(AbstractBankSDK, TBCProvider):
    _NAME = 'UFC_CARD'
    unique_by_key = 'RESULT'
    pan_key = 'CARD_NUMBER'
    _PAY_URL = 'https://ecommerce.ufc.ge/ecomm2/ClientHandler?trans_id=%s'

    @property
    def description(self) -> str:
        """default description"""
        return 'Graey Georgian Payments'

    @property
    def client_ip(self) -> str:
        return '1.1.1.1'

    @property
    def service_url(self) -> str:
        return 'https://ecommerce.ufc.ge:18443/ecomm2/MerchantHandler'

    @property
    def cert(self):
        # @TODO UFC Certificate
        return (
            f'{settings.BASE_DIR}/order/banks/ufc_cert_in_pem/ufc_cert.pem',
            f'{settings.BASE_DIR}/order/banks/ufc_cert_in_pem/ufc_cert-key.pem'
        )

    @property
    def status_mapper(self) -> dict:
        return {
            'OK': 1,
            'CREATED': 0,
            'PENDING': 0,
            'REVERSED': 0,  # Or -1 ??
            'AUTOREVERSED': 0,
            'FAILED': -1,
            'DECLINED': -1,
            'TIMEOUT': -2
        }

    def get_failed_text_status(self):
        for r in self.transaction.data_log:
            if self.status_mapper.get(r.get('RESULT', ''), 0) < 0:
                result_code = r.get('RESULT_CODE')
                if not result_code:
                    threeD_secure = r.get('3DSECURE')
                    result_code = '3D' if threeD_secure and threeD_secure != 'AUTHENTICATED' else ''
                return settings.UFC_ERROR_MESSAGES.get(result_code, f'Result Code: {result_code}/ Contact To Bank')
        return 'Unknown'

    def payment_with_new_card(self) -> Dict:
        if self.transaction.save_card:
            biller_client_id = ''.join(random.choice(string.ascii_letters) for _ in range(20))
            biller_client_id += urlsafe_base64_encode(force_bytes(self.transaction.pk))
            result = self.card_register_with_deduction(
                amount=self.transaction.amount, currency='GEL',
                biller_client_id=biller_client_id, perspayee_expiry='1299', expiry='1299', perspayee_gen=1,
                timeout=(5, 10)
            )
        else:
            result = self.get_trans_id(amount=self.transaction.amount, currency='GEL', timeout=(5, 10))
        status = False
        if 'TRANSACTION_ID' in result:
            status = True

        return {
            'status': status,
            'redirect_url': self._PAY_URL % result["TRANSACTION_ID"] if status else None,
            'trx_id': result.get("TRANSACTION_ID", ''),
            'payment_hash': result.get('RRN', '')
        }

    def payment_with_saved_card(self) -> Dict:
        result = self.recurring_payment(
            amount=self.transaction.amount, currency='GEL',
            biller_client_id=self.transaction.bank_card.rec_id, timeout=(5, 10)
        )
        status = True if 'TRANSACTION_ID' in result else False
        trx_id = result.get("TRANSACTION_ID", "0")
        redirect_url = f'{settings.HOST_URL}/ka/success?trans_id={trx_id}' if status else f'{settings.HOST_URL}/ka/fail/'
        return {
            'status': status,
            'redirect_url': redirect_url,
            'trx_id': trx_id,
            'payment_hash': result.get("RRN", '')
        }

    def start_payment(self) -> Dict:
        if self.transaction.bank_card_id:
            return self.payment_with_saved_card()
        return self.payment_with_new_card()

    def save_card(self, data):
        try:
            user = self.transaction.user
            user.cards.create(
                number=data['CARD_NUMBER'],
                rec_id=data['RECC_PMNT_ID'][:-3],
                expiry_date=data['RECC_PMNT_EXPIRY'],
                card_type=CardTypeChoices.get_card_type(data['CARD_NUMBER']),
                bank_type=BankTypeChoices.UFC,
                is_primary=not (user.cards.filter(is_primary=True).exists())
            )
        except Exception as error_message:
            logger.error(f"Card couldn't be created. Transaction ID: {self.transaction.id}, error: {error_message}")

    def check_transaction_status(self) -> Tuple[dict, int]:
        data = self.check_trans_status(trans_id=self.transaction.trx, timeout=(5, 10))
        status = self.status_mapper.get(data.get('RESULT', ''), 0)
        self.transaction.card_hash = data.get('CARD_NUMBER', '****')
        self.transaction.card_bin_hash = data.get('BIN_HASH')
        if status == 1 and self.transaction.check_save_card(data['CARD_NUMBER']):
            self.save_card(data)
        return data, status

    def refund(self, amount) -> Tuple[bool, Dict]:
        result = self.refund_trans(trans_id=self.transaction.trx, amount=amount, timeout=(5, 10))
        answer = result.get('RESULT_CODE') == "000"
        result['DATE_TIME'] = localtime(timezone.now()).isoformat()
        return answer, result

    def cancel(self, amount) -> Tuple[bool, Dict]:
        result = self.reversal_trans(trans_id=self.transaction.trx, amount=amount, timeout=(5, 10))
        answer = (result.get('RESULT_CODE') == '400' and result.get('RESULT') == 'OK') or \
                 result.get('RESULT_CODE') == "000"
        result['DATE_TIME'] = localtime(timezone.now()).isoformat()
        return answer, result
