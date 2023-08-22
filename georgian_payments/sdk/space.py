import json
from typing import Dict, Tuple

import requests
from django.conf import settings
from rest_framework.exceptions import ValidationError

from georgian_payments.choices import ManualActionChoices
from georgian_payments.sdk.base import AbstractBankSDK



class SpaceInstallmentSDK(AbstractBankSDK):
    _NAME = 'SPACE_INSTALLMENT'
    unique_by_key = 'Status'
    SPACE = settings.PAYMENT_CREDENTIALS['space']

    __BASE_URL = SPACE['base_url']
    __API_VERSION = 'v1'
    __CREATE_QR = f'{__BASE_URL}{__API_VERSION}/qr/create'
    __STATUS_LOAN = f'{__BASE_URL}{__API_VERSION}/loans/checkstatus?merchantname=%s&orderId=%s&secret=%s'

    merchant_name = SPACE['merchant_name']
    secret_key = SPACE['secret_key']

    image_path = 'admin/img/bank/space.svg'

    _PAY_URL = 'https://test-%s.com'

    def __init__(self, transaction: 'PaymentTransaction', **kwargs):
        super().__init__(transaction, **kwargs)

    @staticmethod
    def _request(url, method='POST', data=None, is_urlencoded=False):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded' if is_urlencoded else 'application/json'
        }
        response = requests.request(method, url, data=data, headers=headers)
        if response.status_code > 201 or not response.json()['data']:
            raise ValidationError(f'Space Bank Is Not Available | {url} {response.text}')
        if response.content:
            data = response.json()
            return data
        return response.status_code

    def get_failed_text_status(self):
        return 'უარყოფილი (სისტემის მიერ)'

    @property
    def start_payment_data(self):
        return {
            'data': {
                'MerchantName': self.merchant_name,
                'Secret': str(self.secret_key),
                'Type': 1,  # QR Type
                'returnUrl': '',
                'OrderId': self.transaction.id,
                'TotalAmount': self.transaction.amount
            }}

    def start_payment(self) -> Dict:
        data = self._request(
            self.__CREATE_QR,
            data=json.dumps(self.start_payment_data)
        )
        loan_details = data['data']
        return {
            'status': True,
            'redirect_url': loan_details['redirectUrl'],
            'trx_id': loan_details['orderId'],
            'qrCodeId': loan_details['qrCodeId'],
            'qrCodeViewUrl': loan_details['qrCodeViewUrl'],
            'response_status': data['status']
        }

    def check_transaction_status(self) -> Tuple[dict, int]:
        status = -1
        data = self._request(
            self.__STATUS_LOAN % (self.merchant_name, self.transaction.trx, self.secret_key),
            method='GET',
        )['data']

        loan_status = data['status']

        if loan_status == 1:
            status = 0
        if loan_status == 2:
            status = 1

        data['Status'] = loan_status
        del data['status']

        return data, status

    def refund(self, amount) -> Tuple[bool, Dict]:
        return self.cancel()

    def cancel(self, *_, **__) -> Tuple[bool, Dict]:
        self.transaction.set_need_manual_action(ManualActionChoices.REFUND_LOAN)
        return False, {"message": "Created Manual Action"}
