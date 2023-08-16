from django.urls import path, include
from rest_framework import routers

from payments.views import BogCallBackViewSet, GeorgianCardCallBackViewSet, SpaceCallBackViewSet, TBCCallBackViewSet
from payments.views.checkout import TransactionViewSet

router = routers.SimpleRouter()
router.register(r'transaction', TransactionViewSet, basename='OrderVieSet')

callback = routers.SimpleRouter()
callback.register(r'bog', BogCallBackViewSet, basename='bog_callback')
callback.register(r'gc', GeorgianCardCallBackViewSet, basename='gc_callback')
callback.register(r'space', SpaceCallBackViewSet, basename='space_callback')
callback.register(r'tbc', TBCCallBackViewSet, basename='tbc_callback')

urlpatterns = [
    path('', include(router.urls)),
    path('callback/', include(callback.urls)),

]
