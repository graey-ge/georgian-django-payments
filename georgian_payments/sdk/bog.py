import json
from abc import ABC
from datetime import timedelta
from enum import Enum
from typing import Dict, Union, Tuple, TYPE_CHECKING

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import localtime
from loguru import logger
from requests.auth import HTTPBasicAuth

from georgian_payments.choices import PTTChoices, ManualActionChoices
from georgian_payments.sdk.base import AbstractBankSDK
from georgian_payments.utils import requests_to_curl, BearerAuth

if TYPE_CHECKING:
    from georgian_payments.models import PaymentTransaction


class PreAuthChoices(Enum):
    FULL_COMPLETE = 'FULL_COMPLETE'
    CANCEL = 'CANCEL'
    PARTIAL_COMPLETE = 'PARTIAL_COMPLETE'


class AbstractBogSDK(AbstractBankSDK, ABC):
    unique_by_key = 'status'
    __BASE_URL = 'https://ipay.ge/opay/api/v1'
    __TOKEN_URL = f'{__BASE_URL}/oauth2/token'

    BOG = settings.PAYMENT_CREDENTIALS['bog']

    def __init__(self, transaction: 'PaymentTransaction', **kwargs):
        super().__init__(transaction, **kwargs)
        self.app_id = None
        self.token_expires_in = None
        self.merchant_id = self.BOG['merchant_id']
        self.client_id = self.BOG['client_id']
        self.secret_key = self.BOG['secret_key']
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(self.client_id, self.secret_key)
        self.is_generated_token = False

    def _generate_jwt_auth(self):
        self.is_generated_token = True
        response = self._request(self.__TOKEN_URL, data={
            'grant_type': 'client_credentials'
        }, is_urlencoded=True)
        self.session.auth = BearerAuth(response['access_token'])
        self.app_id = response['app_id']
        self.token_expires_in = response['expires_in']

    def _request(self, url, method='POST', data=None, is_urlencoded=False) -> Union[int, dict]:
        if not self.is_generated_token:
            self._generate_jwt_auth()
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded' if is_urlencoded else 'application/json'
        }
        response = self.session.request(method, url, data=data, headers=headers)
        if url != self.__TOKEN_URL:
            logger.info(requests_to_curl(response))
        if response.status_code != 200:
            logger.error(f'Bog Bank Is Not Available | {url} | {response.text} | {response.status_code}')
        if response.content and response.status_code == 200:
            return response.json()
        return response.status_code


class BogPaySDK(AbstractBogSDK):
    pan_key = 'pan'
    _NAME = 'BOG_CARD'
    __BASE_URL = 'https://ipay.ge/opay/api/v1'
    __REQUEST_ORDER_URL = f'{__BASE_URL}/checkout/orders'
    __REQUEST_ORDER_SUBSCRIPTION = f'{__BASE_URL}/checkout/payment/subscription'
    __FINISH_PRE_AUTH = f'{__BASE_URL}/checkout/payment/%s/pre-auth/completion'
    __CHECK_ORDER_STATUS_URL = f'{__BASE_URL}/checkout/payment/%s'
    __REFUND_URL = f'{__BASE_URL}/checkout/refund'
    _PAY_URL = "https://ipay.ge/?order_id=%s&locale=ka"
    BOG = settings.PAYMENT_CREDENTIALS['bog']

    def pay_with_new_card(self) -> Dict:
        request_data = {
            'shop_order_id': self.transaction.id,
            'intent': self.BOG['intent'],
            'locale': "ka",
            'redirect_url': self.BOG['redirect_url'] % self.transaction.id,
            'show_shop_order_id_on_extract': self.BOG['show_shop_order_id_on_extract'],
            'capture_method': self.BOG['capture_method'],
            'purchase_units': [
                {
                    "amount": {
                        "currency_code": "GEL",
                        "value": str(round(self.transaction.amount, 2))
                    }
                }
            ],
            **self.product_data()
        }
        data = self._request(self.__REQUEST_ORDER_URL, data=json.dumps(request_data))
        status = False
        if isinstance(data, dict) and data.get('status') == 'CREATED':
            status = True
        return {
            'status': status,
            'redirect_url': data['links'][1]['href'] if status else None,
            'trx_id': data.get('order_id', ''),
            'payment_hash': data.get('payment_hash', '')
        }

    def product_data(self):
        products_information = self.transaction.product_data
        items = [{
            'amount': str(round(product_info.get('amount', 0))),
            'description': product_info.get('headline', ''),
            'quantity': str(product_info.get('quantity', 1)),
            'product_id': str(product_info.get('product_id', 0)),
        } for product_info in products_information]
        return {'items': items}

    def pay_with_saved_card(self) -> Dict:
        # cd9010e87ff894abf4e7c97336e480c6e24d0ad4 - გადახდილი - დაბრუნებული
        request_data = {
            "order_id": self.transaction.id,
            "amount": {
                "currency_code": "GEL",
                "value": str(round(self.transaction.amount, 2))
            },
            "shop_order_id": self.transaction.id,
            "purchase_description": f"Transaction | {self.transaction.id}"
        }
        status = False
        data = self._request(self.__REQUEST_ORDER_SUBSCRIPTION, data=json.dumps(request_data))
        if not isinstance(data, dict):
            return {'status': status, 'trx_id': '', 'redirect_url': ''}
        if data.get('status') in ['in_progress', 'success']:
            status = True
        trx_id = data.get('order_id', '')
        redirect_url = self.BOG['redirect_url'] % trx_id if status else self.BOG['redirect_fail_url']
        return {
            'status': status,
            'redirect_url': redirect_url,
            'trx_id': trx_id,
            'payment_hash': data.get('payment_hash', '')
        }

    def check_transaction_status(self) -> Tuple[dict, int]:
        status_mapper = {
            'error': -1,
            'success': 1,
            'in_progress': 0
        }
        data = self._request(self.__CHECK_ORDER_STATUS_URL % self.transaction.trx, method='GET')
        self.transaction.card_hash = data.get('pan', '****') or "****"
        is_ok = status_mapper.get(data.get('status', ''), -1)
        if is_ok == -1 and self.transaction.created + timedelta(minutes=15) < timezone.now():
            is_ok = -2
        return data, is_ok

    def finish_pre_auth(self, status: PreAuthChoices = PreAuthChoices.FULL_COMPLETE, amount=None):
        request_data = {
            "auth_type": status.value
        }
        if amount is not None:
            assert status == PreAuthChoices.PARTIAL_COMPLETE, f"Status Must Be {PreAuthChoices.PARTIAL_COMPLETE.value}"
            request_data["amount"] = amount

        data = self._request(self.__FINISH_PRE_AUTH % self.transaction.trx, method='POST',
                             data=json.dumps(request_data))
        return data

    def refund(self, amount) -> Tuple[bool, Dict]:
        return self.cancel(amount)

    def cancel(self, amount) -> Tuple[bool, Dict]:
        status_code = self._request(  # here, status_code always will be int
            self.__REFUND_URL,
            method='POST',
            data=dict(order_id=self.transaction.trx, amount=round(amount, 2)),
            is_urlencoded=True
        )
        data = {
            'HTTP_STATUS_CODE': status_code
        }
        if status_code == 200:
            data = {
                'status': 'refunded',
                'HTTP_STATUS_CODE': 200,
                'DATE_TIME': localtime(timezone.now()).isoformat()
            }
        return status_code == 200, data

    def start_payment(self) -> Dict:
        if self.transaction.bank_card:
            return self.pay_with_saved_card()
        return self.pay_with_new_card()


class BogInstallmentSDK(AbstractBogSDK):
    _NAME = 'BOG_LOAN'
    __INSTALLMENT_BASE_URL = 'https://installment.bog.ge/v1'
    __REQUEST_INSTALLMENT_URL = f'{__INSTALLMENT_BASE_URL}/installment/checkout'
    __CALCULATE_INSTALLMENT_URL = f'{__INSTALLMENT_BASE_URL}/services/installment/calculate'
    __CHECK_INSTALLMENT_STATUS_URL = f'{__INSTALLMENT_BASE_URL}/installment/checkout/%s'
    image_path = 'admin/img/bank/bog.jpeg'
    _PAY_URL = "https://installment.bog.ge/?order_id=%s&locale=ka"
    BOG = settings.PAYMENT_CREDENTIALS['bog']

    def __init__(self, transaction: 'PaymentTransaction'):
        super().__init__(transaction)
        self.installment_options = transaction.additional_data.get('installment_options', {})
        if transaction.transaction_type == PTTChoices.PAY:
            assert self.installment_options, 'Bog Installment Need Installment Options'

    def calculate_installment(self):
        return self._request(self.__CALCULATE_INSTALLMENT_URL, method='POST', data=json.dumps({
            'amount': self.transaction.amount,
            'client_id': self.client_id
        }))

    def product_data(self):
        products_information = self.transaction.product_data

        cart_items = [{
            'amount': str(round(product_info.get('amount', 0))),
            'item_description': product_info.get('headline', ''),
            'quantity': str(product_info.get('quantity', 1)),
            'item_vendor_code': str(product_info.get('product_id', 0)),
        } for product_info in products_information]
        return {
            'cart_items': cart_items
        }

    def start_payment(self) -> Dict:
        request_data = {
            'shop_order_id': self.transaction.id,
            "intent": "LOAN",
            "installment_month": self.installment_options['month'],
            "installment_type": self.installment_options["discount_code"],
            "success_redirect_url": self.BOG["installment_success_redirect_url"] % self.transaction.id,
            "fail_redirect_url": self.BOG["installment_fail_redirect_url"] % self.transaction.id,
            "reject_redirect_url": self.BOG["installment_reject_redirect_url"] % self.transaction.id,
            "validate_items": False,
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": "GEL",
                        "value": round(self.transaction.amount, 2)
                    }
                }
            ],
            **self.product_data()
        }
        data = self._request(self.__REQUEST_INSTALLMENT_URL, method='POST', data=json.dumps(request_data))
        status = False
        if isinstance(data, dict) and data.get('status') == 'CREATED':
            status = True
        return {
            'status': status,
            'redirect_url': data['links'][1]['href'] if status else None,
            'trx_id': data['order_id']
        }

    def check_transaction_status(self):
        data = self._request(self.__CHECK_INSTALLMENT_STATUS_URL % self.transaction.trx, method='GET')
        status_mapper = {
            'error': -1,
            'success': 1,
            'in_progress': 0
        }
        is_ok = status_mapper.get(data.get('status', ''), -1)
        if is_ok == -1 and self.transaction.created + timedelta(minutes=50) < timezone.now():
            is_ok = -2
        return data, is_ok

    def refund(self, amount) -> Tuple[bool, Dict]:
        return self.cancel(amount)

    def cancel(self, *_, **__) -> Tuple[bool, Dict]:
        self.transaction.set_need_manual_action(ManualActionChoices.REFUND_LOAN)
        return False, {"message": "Created Manual Action"}
