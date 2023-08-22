from typing import TYPE_CHECKING, Dict, Tuple

from django.templatetags.static import static

if TYPE_CHECKING:
    from georgian_payments.models import PaymentTransaction


class AbstractBankSDK:
    _NAME = None
    unique_by_key = None
    pan_key = None
    image_path = None
    _PAY_URL = '%s'

    def __init__(self, transaction: 'PaymentTransaction', **kwargs):
        self.transaction: PaymentTransaction = transaction

    def __str__(self):
        assert self._NAME is not None, "Field: _NAME Must Be Implemented"
        return self._NAME

    @classmethod
    def display(cls):
        return cls._NAME

    @staticmethod
    def get_failed_text_status():
        return 'Contact To Bank'

    def start_payment(self) -> Dict:
        """
        :return: {
        'status': bool,
        'redirect_url': str,
        'trx_id': str,
        'payment_hash': str
        }
        """
        raise NotImplementedError

    def check_transaction_status(self) -> Tuple[dict, int]:
        raise NotImplementedError

    def refund(self, amount) -> Tuple[bool, Dict]:
        raise NotImplementedError

    def cancel(self, amount) -> Tuple[bool, Dict]:
        raise NotImplementedError

    def cash_back(self, amount) -> Tuple[bool, Dict]:
        pass

    @classmethod
    def image_url(cls):
        return static(cls.image_path)

    @classmethod
    def pay_url(cls, trx):
        return cls._PAY_URL % trx
