from django.conf import settings
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import Serializer, CharField

SPACE = settings.PAYMENT_CREDENTIALS['space']


class SpaceCallbackSerializer(Serializer):
    OrderId = CharField(required=True)
    Status = CharField(required=True)
    Secret = CharField(required=True)
    Description = CharField(allow_blank=True)
    ClientContributionAmount = CharField(allow_blank=True)

    @staticmethod
    def validate_Secret(secret: str):
        if secret != SPACE['secret_key']:
            raise ValidationError("Secret Key is not Valid.")
        return secret
