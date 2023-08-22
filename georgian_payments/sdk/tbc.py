import json
from typing import Dict, Tuple, TYPE_CHECKING

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from loguru import logger
from requests.auth import HTTPBasicAuth

from georgian_payments.choices import ManualActionChoices
from georgian_payments.sdk.base import AbstractBankSDK
from georgian_payments.utils import BearerAuth

if TYPE_CHECKING:
    from georgian_payments.models import PaymentTransaction



class TbcInstallmentSDK(AbstractBankSDK):
    _NAME = 'TBC_LOAN'
    unique_by_key = 'statusId'
    __BASE_URL = 'https://api.tbcbank.ge/'
    __TOKEN_URL = f'{__BASE_URL}oauth/token'
    __API_VERSION = 'v1'
    __INITIAL_LOAN = f'{__BASE_URL}{__API_VERSION}/online-installments/applications'
    __CONFIRM_LOAN = f'{__BASE_URL}{__API_VERSION}/online-installments/applications/%s/confirm'
    __CANCEL_LOAN = f'{__BASE_URL}{__API_VERSION}/online-installments/applications/%s/cancel'
    __STATUS_LOAN = f'{__BASE_URL}{__API_VERSION}/online-installments/applications/%s/status'
    __STATUS_CHANGES = f'{__BASE_URL}{__API_VERSION}/online-installments/merchant/applications/status-changes'
    __STATUS_CHANGES_SYNC = f'{__BASE_URL}{__API_VERSION}/online-installments/merchant/applications/status-changes-sync'

    TBC = settings.PAYMENT_CREDENTIALS['tbc']

    client_id = TBC['client_id']
    secret_key = TBC['secret_key']
    merchant_key = TBC['merchant_key']
    campaign_id = TBC['campaign_id']

    image_path = 'admin/img/bank/tbc.png'
    _PAY_URL = "https://tbcinstallment.tbcbank.ge/Installment/InitializeNewLoan?sessionId=%s"

    def __init__(self, transaction: 'PaymentTransaction' = None, **kwargs):
        super().__init__(transaction, **kwargs)
        self.token_expires_in = None
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(self.client_id, self.secret_key)
        self.is_generated_token = False

    def _generate_jwt_auth(self):
        self.is_generated_token = True
        response = self._request(self.__TOKEN_URL, data={
            'grant_type': 'client_credentials',
            'scope': 'online_installments'
        }, is_urlencoded=True)
        self.session.auth = BearerAuth(response['access_token'])
        self.token_expires_in = response['expires_in']
        # print(int(round(datetime.now().timestamp() * 1000)))
        # print(self.token_expires_in)

    def _request(self, url, method='POST', data=None, is_urlencoded=False):
        if not self.is_generated_token:
            self._generate_jwt_auth()
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded' if is_urlencoded else 'application/json'
        }
        response = self.session.request(method, url, data=data, headers=headers)
        if response.status_code > 201:
            logger.error(f'Tbc Bank Is Not Available | {url} {response.text}')
        if response.content:
            data = response.json()
            if 'location' in response.headers:
                data['redirect_url'] = response.headers['location']
            return data
        return response.status_code

    def product_data(self):
        products = []
        for product_info in self.transaction.product_data:
            products.append({
                'price': product_info.get('amount', 0),
                'name': product_info.get('headline', ''),
                'quantity': product_info.get('quantity', 1),
            })
        return {'products': products}

    @property
    def start_payment_data(self):
        return {
            'invoiceId': self.transaction.id,
            'priceTotal': self.transaction.amount,
            'merchantKey': self.merchant_key,
            'campaignId': str(self.transaction.additional_data.get('campaign_id', self.campaign_id))
            if not settings.STAGE else self.campaign_id,
            **self.product_data()
        }

    def start_payment(self) -> Dict:
        data: dict = self._request(
            self.__INITIAL_LOAN,
            data=json.dumps(self.start_payment_data)
        )
        return {
            'status': 'redirect_url' in data,
            'redirect_url': data.get('redirect_url'),
            'trx_id': data.get('sessionId')
        }

    def confirm_loan(self):
        data = self._request(
            self.__CONFIRM_LOAN % self.transaction.trx,
            data=json.dumps({
                'merchantKey': self.merchant_key,
            })
        )
        return data

    def cancel_loan(self):
        data = self._request(
            self.__CANCEL_LOAN % self.transaction.trx,
            data=json.dumps({
                'merchantKey': self.merchant_key,
            })
        )
        return data

    def check_transaction_status(self) -> Tuple[dict, int]:
        data = self._request(
            self.__STATUS_LOAN % self.transaction.trx,
            method='GET',
            data=json.dumps({
                'merchantKey': self.merchant_key,
            })
        )
        status_id = data.get('statusId')
        is_ok = 0
        if status_id in [3, 4, 6, 7]:
            is_ok = -1
        elif status_id == 8:
            is_ok = 1
        return data, is_ok

    def status_changes(self):
        data = self._request(
            self.__STATUS_CHANGES,
            method='GET',
            data=json.dumps({
                'merchantKey': self.merchant_key,
                'take': 30
            })
        )
        return data

    def status_changes_sync(self, request_id):
        data = self._request(
            self.__STATUS_CHANGES_SYNC,
            data=json.dumps({
                'merchantKey': self.merchant_key,
                'synchronizationRequestId': request_id
            })
        )
        return data

    def refund(self, amount) -> Tuple[bool, Dict]:
        return self.cancel()

    def cancel(self, *_, **__) -> Tuple[bool, Dict]:
        self.transaction.set_need_manual_action(ManualActionChoices.REFUND_LOAN)
        return False, {"message": "Created Manual Action"}


class TbcBNPLInstallmentSDK(AbstractBankSDK):
    _NAME = 'TBC_BNPL_LOAN'
    unique_by_key = 'status'

    __BASE_URL = 'https://api.tbcbank.ge/'
    __TOKEN_URL = f'{__BASE_URL}oauth/token'
    __API_VERSION = 'v1'
    __INITIAL_PAYMENT = f'{__BASE_URL}{__API_VERSION}/tpay/payments'
    __GENERATE_TOKEN = f'{__BASE_URL}{__API_VERSION}/tpay/access-token'
    __STATUS_LOAN = f'{__BASE_URL}{__API_VERSION}/tpay/payments/%s'
    TBC = settings.PAYMENT_CREDENTIALS['tbc']

    client_id = TBC['bnpl_client_id']
    client_secret = TBC['bnpl_client_secret']

    image_path = 'admin/img/bank/tbc.png'
    _PAY_URL = 'https://ecom.tbcpayments.ge/Pay/choose/=%s?lang=en'

    def __init__(self, transaction: 'PaymentTransaction' = None, **kwargs):
        super().__init__(transaction, **kwargs)

    def _generate_jwt_token(self):
        data = {'client_id': self.client_id, 'client_secret': self.client_secret}
        response = self._request(url=self.__GENERATE_TOKEN, data=data, is_urlencoded=True)
        return response['access_token']

    def _request(self, url, method='POST', data=None, is_urlencoded=False):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded' if is_urlencoded else 'application/json',
            "apikey": self.TBC['bnpl_api_key'],
            "accept": "text/plain",
        }
        if url != self.__GENERATE_TOKEN:
            headers['Authorization'] = f'Bearer {self._generate_jwt_token()}'
        response = requests.request(method, url, data=data, headers=headers)
        if response.status_code > 201:
            raise ValidationError(f'TBC Bank Is Not Available | {url} {response.text}')
        return response.json()

    def product_data(self):
        products = []
        for product_info in self.transaction.product_data:
            products.append({
                'Price': round(product_info.get('amount', 0), 2),
                'Name': product_info.get('headline', ''),
                'Quantity': product_info.get('quantity', 1),
            })
        return {'installmentProducts': products}

    @property
    def start_payment_data(self):
        domain = 'https://stg.veli.store' if settings.STAGE else 'https://veli.store'
        return {
            'merchantPaymentId': self.transaction.id,
            'amount': {
                'currency': 'GEL',
                'total': round(self.transaction.amount, 2),
                'subTotal': 0,
                'tax': 0,
                'shipping': 0,
            },
            'expirationMinutes': '10',
            'methods': ['4', '7'],
            'returnurl': 'https://veli.store/',
            'callbackUrl': f'{domain}/api/order/payment/tbc_payment/callback/',
            'preAuth': False,
            'language': 'ka',
            **self.product_data()
        }

    @staticmethod
    def get_redirect_url(data):
        links = data['links']
        for link in links:
            if link['method'] == 'REDIRECT':
                return link['uri']
        return None

    def start_payment(self) -> Dict:
        data: dict = self._request(self.__INITIAL_PAYMENT, data=json.dumps(self.start_payment_data))
        return {
            'status': True if data['status'] == 'Created' else False,
            'redirect_url': self.get_redirect_url(data),
            'trx_id': data['payId']
        }

    def set_card_payment_methods(self, data):
        self.transaction.card_hash = data['paymentCardNumber']
        self.transaction.payment_method_id = 1  # TBC CARD
        self.transaction.save(update_fields=['card_hash', 'payment_method_id'])

    def check_transaction_status(self) -> Tuple[dict, int]:
        status = 0
        data = self._request(
            self.__STATUS_LOAN % self.transaction.trx,
            method='GET',
        )

        loan_status = data['status']
        if loan_status == 'Failed':
            status = -1
        elif loan_status == 'Succeeded':
            operation_type = data['operationType']
            if operation_type == 0:  # WEB QR Payments
                self.set_card_payment_methods(data)
            status = 1
        elif loan_status == 'Expired':
            status = -2

        return data, status

    def get_failed_text_status(self):
        return 'უარყოფილი'

    def refund(self, amount) -> Tuple[bool, Dict]:
        return self.cancel()

    def cancel(self, *_, **__) -> Tuple[bool, Dict]:
        self.transaction.set_need_manual_action(ManualActionChoices.REFUND_LOAN)
        return False, {"message": "Created Manual Action"}
