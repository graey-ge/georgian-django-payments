import hashlib
import json
from datetime import timedelta
from typing import Dict, Tuple

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import localtime
from rest_framework.exceptions import ValidationError

from .base import AbstractBankSDK
from payments.choices import ManualActionChoices
from payments.serialaizers import CredoInstallmentInitialSerializer

CREDO = settings.PAYMENT_CREDENTIALS['credo']


class CredoInstallmentSDK(AbstractBankSDK):
    _NAME = 'CREDO_INSTALLMENT'
    unique_by_key = 'data'

    __BASE_URL = 'https://ganvadeba.credo.ge'
    __INITIAL_LOAN = f'{__BASE_URL}/widget_api/index.php/'
    __STATUS_LOAN = f'{__BASE_URL}/widget/api.php?merchantId=%s&orderCode=%s'

    merchant_id = CREDO['merchant_id']
    secret_key = CREDO['secret_key']

    image_path = 'admin/img/bank/credo.svg'
    _PAY_URL = 'https://ganvadeba.credo.ge/installment/?OrderHash=%s'

    def __init__(self, transaction: 'PaymentTransaction', **kwargs):
        super().__init__(transaction, **kwargs)

    @staticmethod
    def _request(url, method='POST', data=None, is_urlencoded=False):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded' if is_urlencoded else 'application/json'
        }
        response = requests.request(method, url, data=data, headers=headers)
        return response

    def get_failed_text_status(self):
        return 'უარყოფილი'

    def generate_check_string(self, products):
        generated_str = ''
        for product in products:
            for i in product.values():
                generated_str += str(i)
        generated_str += self.secret_key
        generated_check = hashlib.md5(generated_str.encode()).hexdigest()
        return generated_check

    def product_data(self):
        products = []
        for product_info in self.transaction.product_data:
            products.append({
                'price': int(product_info.get('amount', 0) * 100),
                'title': product_info.get('headline', ''),
                'amount': product_info.get('quantity', 1),
                'id': str(product_info.get('product_id', 0)),
                'type': 0
            })
        return {'products': products}

    @property
    def start_payment_data(self):
        product_data = self.product_data()
        data = {
            "merchantId": self.merchant_id,
            "check": self.generate_check_string(product_data['products']),
            'orderCode': self.transaction.id,
            **self.product_data()
        }
        return {
            "credoinstallment": str(data).replace("'", '"')
        }

    def start_payment(self) -> Dict:
        response = self._request(self.__INITIAL_LOAN, data=self.start_payment_data, is_urlencoded=True)
        if response.status_code > 201:
            raise ValidationError(f'CREDO Bank Is Not Available | {self.__INITIAL_LOAN} {response.text}')
        return {
            'status': True,
            'trx_id': self.transaction.id,
            'redirect_url': response.headers['refresh'].split('=', 1)[-1],
            'response_status': 200
        }

    def check_transaction_status(self) -> Tuple[dict, int]:
        status = 0
        response = self._request(
            self.__STATUS_LOAN % (self.merchant_id, self.transaction.trx),
            method='GET',
        )
        if response.status_code == 404:
            if self.transaction.updated > localtime(timezone.now()) - timedelta(hours=1):
                status = -2
            return {}, status
        data = response.json()
        loan_status = int(data['data'])
        if loan_status in [6, 7]:
            status = -1
        elif loan_status in [12, 5]:
            status = 1
        return data, status

    def refund(self, amount) -> Tuple[bool, Dict]:
        return self.cancel()

    def cancel(self, *_, **__) -> Tuple[bool, Dict]:
        self.transaction.set_need_manual_action(ManualActionChoices.REFUND_LOAN)
        return False, {"message": "Created Manual Action"}
