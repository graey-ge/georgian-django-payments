import json
from typing import Union, Dict, Tuple

import requests
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.timezone import localtime
from loguru import logger

from choices import PaymentTypeChoices
from sdk import AbstractBankSDK

GEORGIAN_CARD_SETTINGS = settings.PAYMENT_CREDENTIALS['georgian_card']


class GCBank(AbstractBankSDK):
    unique_by_key = 'state'
    # PORTAL = '66EF9A2E6D429D8F0C767574F9353E8B'
    APP_PORTAL = 'B017853764E36EB69E831F9B46880E61'
    pan_key = 'p.maskedPan'
    _NAME = 'GEORGIAN_CARD'
    __BASE_URL = 'https://mpi.gc.ge'
    __REQUEST_TRANSACTION_URL = f'{__BASE_URL}/page1/'
    __REQUEST_TRANSACTION_SUBSCRIPTION = f'{__BASE_URL}/open/api/v4/{APP_PORTAL}/payment/%s/start'
    __TOKEN_URL = f'{__BASE_URL}/open/api/v4/{APP_PORTAL}/token/'
    __START_SESSION_URL = f'{__BASE_URL}/open/api/v4/{APP_PORTAL}/session/start/' \
                          f'?identifier=FIDS9ECTGA6Q7API&password=V9ZGM0CTE8J63HR4ONI7'
    __CHECK_STATUS_URL = f'{__BASE_URL}/open/api/v4/{APP_PORTAL}/merchant/history/trx/%s'
    __REFUND_URL = f'{__BASE_URL}/open/api/v4/{APP_PORTAL}/merchant/history/trx/%s/refund/?currency=GEL&amount=%s'
    _PAY_URL = f"{__REQUEST_TRANSACTION_URL}?merch_id={GEORGIAN_CARD_SETTINGS['merchant_id']}" \
               f"&back_url_s={GEORGIAN_CARD_SETTINGS['back_url_s']}&back_url_f={GEORGIAN_CARD_SETTINGS['back_url_f']}" \
               f"&o.transaction_id=%s&lang_code=%s"
    __APPLE_ACCEPT_URL = f'{__BASE_URL}/open/api/v4/{APP_PORTAL}/payment/%s/applepay/accept'
    __APPLE_CHECK_TRANS_URL = f'{__BASE_URL}/open/api/v4/{APP_PORTAL}/payment/%s'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lang = 'ka'

    @classmethod
    def pay_url(cls, pk):
        lang = 'ka'
        return cls._PAY_URL % (lang, pk, lang, pk, pk, lang)

    def start_session(self) -> Union[str, None]:
        r = requests.post(self.__START_SESSION_URL)
        if r.status_code == 200:
            return r.json()['sessionId']
        return None

    def get_token(self) -> Union[None, str]:
        r = requests.post(self.__TOKEN_URL)
        if r.status_code != 200:
            logger.error('GC Token Is Not Available')
            return None
        return r.json()['token']

    @property
    def redirect_url(self):
        url = self._PAY_URL
        pk = self.transaction.id
        return url % (self.lang, pk, self.lang, pk, pk, self.lang)

    def start_payment(self) -> Dict:
        if self.transaction.bank_card or \
                self.transaction.payment_method.payment_type == PaymentTypeChoices.APPLE_PAY:
            return self.pay_with_saved_card()
        return self.pay_with_new_card()

    def pay_with_new_card(self):
        return {
            'status': True,
            'redirect_url': self.redirect_url,
            'trx_id': "",
            'payment_hash': ""
        }

    def pay_with_saved_card(self):
        token = self.get_token()
        r = requests.post(
            self.__REQUEST_TRANSACTION_SUBSCRIPTION % token,
            data={
                'merchantId': GEORGIAN_CARD_SETTINGS['merchant_id'],
                'returnUrl': GEORGIAN_CARD_SETTINGS['back_url_s'] % (self.lang, self.transaction.id),
                'lang': 'ka',
                'params.transaction_id': self.transaction.id
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        data = r.json()
        logger.info(f'GC : {data}')
        return {
            'status': True,
            'redirect_url': GEORGIAN_CARD_SETTINGS['back_url_s'] % (self.lang, self.transaction.id),
            'trx_id': token,
            'payment_hash': token
        }

    @property
    def get_check_accept_xml(self) -> str:
        return render_to_string('payment/check_response.xml', context={
            "result": {
                "code": 1,
                "desc": "Successful"
            },
            "merchant_trx": self.transaction.trx,
            "short_desc": f'ID: {self.transaction.id}',
            "long_desc": f'Greay/{self.transaction.id}',
            "account_id": GEORGIAN_CARD_SETTINGS['account_id'],
            "amount": int(self.transaction.amount * 100),
            "save_card": False,  # self.transaction.save_card,
            "card_id": None,  # self.transaction.bank_card.rec_id if self.transaction.bank_card_id else None,
            "is_withdrawal": False  # For Future
        })

    @staticmethod
    def get_check_fail_xml(message) -> str:
        return render_to_string('payment/check_response.xml', context={
            "accept": False,
            "result": {
                "code": 2,
                "desc": message
            }
        })

    def _check_transaction_status(self) -> Tuple[dict, int]:
        session_id = self.start_session()
        r = requests.get(
            self.__CHECK_STATUS_URL % self.transaction.trx,
            headers={
                'X-IV-Authorization': f'Session {session_id}'
            }
        )
        if r.status_code != 200:
            return {self.unique_by_key: 'Unknown'}, 0
        logger.info(r.json())
        return r.json(), 0

    def check_transaction_status(self) -> Tuple[dict, int]:
        return self.check_apple_pay_transaction()

    def refund(self, amount) -> Tuple[bool, Dict]:
        session_id = self.start_session()
        r = requests.post(self.__REFUND_URL % (self.transaction.trx, int(amount * 100)), headers={
            'X-IV-Authorization': f'Session {session_id}'
        })
        try:
            data = r.json()
        except:
            data = {self.unique_by_key: 'Unknown'}
        data['time'] = localtime(timezone.now()).isoformat()
        logger.info(data)
        if r.status_code != 200:
            return False, data
        return True, data

    def cancel(self, amount) -> Tuple[bool, Dict]:
        return self.refund(amount)

    def apple_pay_accept(self):
        r = requests.post(
            self.__APPLE_ACCEPT_URL % self.transaction.pay_id,
            data=json.dumps(
                {"token": self.transaction.additional_data['apple_data']}
            ).replace('": {', '":{').replace('"}, "', '"},"').replace('": "', '":"'),
            headers={
                'Content-Type': 'application/json; charset=UTF-8'
            }
        )
        return r.status_code, r.json()

    def check_apple_pay_transaction(self) -> Tuple[dict, int]:
        r = requests.post(
            self.__APPLE_CHECK_TRANS_URL % self.transaction.pay_id
        )
        data = r.json()
        data.pop('merchant', None)
        status = 0
        if data.get('state') == 'result':
            status = 0 if data['result']['status'] == 'FAILED' else 1
        return r.json(), status
