from django.urls import path, include
from rest_framework import routers

from georgian_payments.views import BogCallBackViewSet, GeorgianCardCallBackViewSet, SpaceCallBackViewSet, TBCCallBackViewSet


callback = routers.SimpleRouter()
callback.register(r'bog', BogCallBackViewSet, basename='bog_callback')
callback.register(r'gc', GeorgianCardCallBackViewSet, basename='gc_callback')
callback.register(r'space', SpaceCallBackViewSet, basename='space_callback')
callback.register(r'tbc', TBCCallBackViewSet, basename='tbc_callback')

urlpatterns = [
    path('callback/', include(callback.urls)),

]
