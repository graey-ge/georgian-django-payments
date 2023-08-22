from django.db.models import IntegerChoices


class CardTypeChoices(IntegerChoices):
    VISA = 1, "Visa"
    MASTERCARD = 2, "Mastercard"
    AMERICAN_EXPRESS = 3, "American Express"
    UNKNOWN = 4, 'Unknown'

    @classmethod
    def get_card_type(cls, pan: str):
        if pan[0] == "4":
            return cls.VISA
        if pan[0] == "5":
            return cls.MASTERCARD
        if pan[0:2] in ("34", "37"):
            return cls.AMERICAN_EXPRESS
        return cls.UNKNOWN


class PTSChoices(IntegerChoices):
    ERROR = -3
    TIMEOUT = -2
    FAILED = -1
    PENDING = 0
    SUCCESS = 1


class PTTChoices(IntegerChoices):
    REFUND = -2
    CASHBACK = -1
    PAY = 1
    CONTRIBUTION = 2


class PaymentTypeChoices(IntegerChoices):
    NONE = 0, 'None'
    CARD = 1, 'Card'
    LOAN = 2, 'Installment'
    APPLE_PAY = 3, 'Apple Pay'
    GOOGLE_PAY = 4, 'Google Pay'


class BankTypeChoices(IntegerChoices):
    UFC = 1, 'UFC'
    BOG = 2, 'Bank Of Georgia'
    TBC = 3, 'TBC'
    CREDO = 4, 'Credo'
    SPACE = 5, 'Space'
    GC = 6, 'Georgian Card'


class ManualActionChoices(IntegerChoices):
    CHECK_TBC_LOAN = 1, "დამტკიცდა განვადება თბს -ში"
    REFUND_LOAN = 2, "გასაუქმებელია განვადება"
    CALL_FOR_LOAN_CANCEL = 3, "დასარეკია მომხმარებელთან განვადების გაუქმებაზე"
    TBC_LOAN_CONTRIBUTION = 4, "მომხმარებელს გადასახდელი აქვს თანამონაწილეობის თანხა"
