import uuid
from typing import Union

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from sdk import UfcSdk, SpaceInstallmentSDK, BogPaySDK, GCBank, TbcInstallmentSDK, BogInstallmentSDK, \
    CredoInstallmentSDK
from choices import PTSChoices, PTTChoices, PaymentTypeChoices, BankTypeChoices, CardTypeChoices, \
    ManualActionChoices


class Card(models.Model):
    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True)
    number = models.CharField(max_length=16)
    rec_id = models.CharField(max_length=41, default="")
    expiry_date = models.CharField(max_length=5, default="0000")
    record_date = models.DateTimeField(auto_now_add=True)
    is_primary = models.BooleanField(default=False)
    card_type = models.CharField(max_length=255, choices=CardTypeChoices.choices, default=CardTypeChoices.VISA)
    bank_type = models.PositiveSmallIntegerField(verbose_name="Bank",
                                                 choices=BankTypeChoices.choices,
                                                 default=BankTypeChoices.UFC)
    card_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cards'
    )

    def __str__(self):
        return self.number


class PaymentMethod(models.Model):
    payment_type = models.PositiveSmallIntegerField(choices=PaymentTypeChoices.choices, default=PaymentTypeChoices.CARD)
    bank_type = models.PositiveSmallIntegerField(verbose_name="Bank", choices=BankTypeChoices.choices,
                                                 default=BankTypeChoices.TBC)

    min_amount = models.FloatField(_('Min Amount'), default=0)
    max_amount = models.FloatField(_('Max Amount'), default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _('Payment Method')
        verbose_name_plural = _('Payment Methods')
        unique_together = ('payment_type', 'bank_type')

    def __str__(self):
        return f'{self.get_bank_type_display()} - {self.get_payment_type_display()}'

    @property
    def engine_class(self):
        payment_mapper = {
            (PaymentTypeChoices.CARD.value, BankTypeChoices.UFC.value): UfcSdk,
            (PaymentTypeChoices.LOAN.value, BankTypeChoices.SPACE.value): SpaceInstallmentSDK,
            (PaymentTypeChoices.CARD.value, BankTypeChoices.BOG.value): BogPaySDK,
            (PaymentTypeChoices.CARD.value, BankTypeChoices.UFC.value): UfcSdk,
            (PaymentTypeChoices.APPLE_PAY.value, BankTypeChoices.GC.value): GCBank,
            (PaymentTypeChoices.LOAN.value, BankTypeChoices.TBC.value): TbcInstallmentSDK,
            (PaymentTypeChoices.LOAN.value, BankTypeChoices.BOG.value): BogInstallmentSDK,
            (PaymentTypeChoices.LOAN.value, BankTypeChoices.SPACE.value): SpaceInstallmentSDK,
            (PaymentTypeChoices.LOAN.value, BankTypeChoices.CREDO.value): CredoInstallmentSDK,
            # (PaymentTypeChoices.CARD.value, BankTypeChoices.TBC.value): TbcECommerceSDK,
        }
        return payment_mapper[(self.payment_type, self.bank_type)]

    @property
    def is_installment(self):
        return self.payment_type in (PaymentTypeChoices.LOAN,)


class PaymentTransaction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='User', related_name='payment_transactions',
                             on_delete=models.PROTECT)
    trx = models.CharField(max_length=100, default='')
    pay_id = models.CharField(max_length=255, default='')
    amount = models.FloatField()
    refunded = models.FloatField(default=0)
    card_hash = models.CharField(max_length=30, default="****")
    card_bin_hash = models.CharField(max_length=255, null=True, blank=True)
    status = models.SmallIntegerField(choices=PTSChoices.choices, default=PTSChoices.PENDING)
    transaction_type = models.SmallIntegerField(choices=PTTChoices.choices, default=PTTChoices.PAY)
    data_log = models.JSONField(default=list)
    additional_data = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    save_card = models.BooleanField(default=True)
    bank_card = models.ForeignKey(
        'Card', verbose_name='Card', related_name='transactions', on_delete=models.SET_NULL, null=True,
        blank=True
    )
    payment_method = models.ForeignKey(
        PaymentMethod, verbose_name='Payment Method', related_name='payment_transactions',
        on_delete=models.PROTECT
    )
    manual_action = models.PositiveSmallIntegerField(
        verbose_name=_("მანუალური მოქმედება"), choices=ManualActionChoices.choices,
        null=True, blank=True
    )

    class Meta:
        verbose_name = _('Payment Transaction')
        verbose_name_plural = _('Payment Transactions')

    @property
    def engine(self) -> Union[UfcSdk]:
        return self.payment_method.engine_class(self)

    @property
    def product_data(self) -> list:
        """
        :return:
        Example: [{'headline','product1, 'amount' : 1.23, 'quantity': 1, 'product_id': 1}]
        """
        raise NotImplementedError

    def set_need_manual_action(self, action, commit=True):
        self.manual_action = action
        if commit:
            self.save(update_fields=['manual_action'])

    def sync_status(self, data=None, is_ok=None, succeed_amount=None, save_data=True):
        if not (data and is_ok):
            data, is_ok = self.engine.check_transaction_status()
        if is_ok == 1:
            self.status = PTSChoices.SUCCESS
            if succeed_amount:
                self.amount = succeed_amount
        if is_ok == -1:
            self.status = PTSChoices.FAILED
        if is_ok == -2:
            self.status = PTSChoices.TIMEOUT
        unique_by_key = self.engine.unique_by_key
        save = not (any(filter(lambda x: x.get(unique_by_key, '') == data.get(unique_by_key, ''), self.data_log)))
        if save_data and (save or data.get(unique_by_key) is None) and data:
            self.data_log.append(data)
        self.save(update_fields=['status', 'data_log', 'amount', 'card_hash', 'updated', 'card_bin_hash'])

    def check_save_card(self, pan):
        return self.save_card and (not self.bank_card_id) and not (self.user.cards.filter(number=pan).exists())

    def _initial_payment(self) -> dict:
        data = self.engine.start_payment()
        trx, pay_id = data.pop('trx_id', ''), data.pop('payment_hash', '')
        self.trx = trx if trx else ''
        self.pay_id = pay_id if pay_id else ''
        self.status = PTSChoices.PENDING if data.get('status') else PTSChoices.ERROR
        self.save(update_fields=['trx', 'pay_id', 'status'])
        return data

    def register_as_paid(self, commit=True):
        self.status = PTSChoices.SUCCESS

        if commit:
            self.save(update_fields=['status'])

    def run(self) -> Union[PTSChoices, dict]:
        if self.transaction_type in [PTTChoices.PAY, PTTChoices.CONTRIBUTION]:
            return self._initial_payment()

    @property
    def text_status(self):
        if self.status == PTSChoices.SUCCESS:
            return "Ok"
        if self.status == PTSChoices.TIMEOUT:
            return "Time Out"
        if self.status == PTSChoices.FAILED:
            return self.engine.get_failed_text_status()
        if self.status == PTSChoices.PENDING:
            return "Pending"
        if self.status == PTSChoices.ERROR:
            return "Error With Initial (Maybe Bank Was In Down)"
        return "Unknown"
