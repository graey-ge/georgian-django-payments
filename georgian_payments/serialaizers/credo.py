from rest_framework.fields import IntegerField, SerializerMethodField
from rest_framework.serializers import Serializer



class PreSoldForCredoSerializer(Serializer):
    id = IntegerField()
    title = SerializerMethodField()
    amount = IntegerField()
    price = SerializerMethodField()
    type = SerializerMethodField()

    @staticmethod
    def get_title(obj):
        return ''.replace('"', '')

    @staticmethod
    def get_price(obj):
        return 0

    @staticmethod
    def get_type(obj):
        return 0

    class Meta:
        fields = ('id', 'title', 'amount', 'price', 'type')


class CredoInstallmentInitialSerializer(Serializer):
    # products = PreSoldForCredoSerializer(source='', many=True)

    class Meta:
        fields = ('products',)
