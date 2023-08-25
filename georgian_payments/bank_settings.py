# -*- coding: utf-8 -*-
import os

from django.conf import settings

BASE_DIR = os.path.dirname(os.path.realpath(__file__))

DEFAULT_CREDO_SETTINGS = {
    'merchant_id': '',
    'secret_key': ''
}

DEFAULT_SPACE_SETTINGS = {
    'base_url': '',
    'merchant_name': '',
    'secret_key': '',
    'redirect_url': '',
}

DEFAULT_BOG_SETTINGS = {
    'client_id': '',
    'secret_key': '',
    'merchant_id': '',
    'terminal_id': '',
    'name': '',
    'intent': 'AUTHORIZE',  # 'CAPTURE',
    'capture_method': 'AUTOMATIC',  # 'AUTOMATIC',
    'show_shop_order_id_on_extract': True,
    'redirect_url': '',
    'redirect_fail_url': '',
    "installment_success_redirect_url": "",
    "installment_fail_redirect_url": "",
    "installment_reject_redirect_url": "",
}

DEFAULT_TBC_SETTINGS = {
    'merchant_key': '',
    'test_merchant_key': '',
    'test_campaign_id': None,
    'campaign_id': None,
    'client_id': '',
    'secret_key': '',
    'bnpl_api_key': '',
    'bnpl_client_id': '',
    'bnpl_client_secret': '',

}

DEFAULT_GEORGIAN_CARD_SETTINGS = {
    'account_id': "",
    'merchant_id': "",
    'portal_id': "",
    'bank_user_username': "",
    'bank_user_password': "",
    'back_url_s': '',
    'back_url_f': '',
}

TBC_SETTINGS = getattr(settings, 'TBC_SETTINGS', DEFAULT_TBC_SETTINGS)
BOG_SETTINGS = getattr(settings, 'BOG_SETTINGS', DEFAULT_BOG_SETTINGS)
GEORGIAN_CARD_SETTINGS = getattr(settings, 'GEORGIAN_CARD_SETTINGS', DEFAULT_GEORGIAN_CARD_SETTINGS)
CREDO_SETTINGS = getattr(settings, 'CREDO_SETTINGS', DEFAULT_CREDO_SETTINGS)
SPACE_SETTINGS = getattr(settings, 'SPACE_SETTINGS', DEFAULT_SPACE_SETTINGS)
