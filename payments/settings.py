import os

HOST_URL = os.environ.get('HOST', 'http://127.0.0.1')

PAYMENT_CREDENTIALS = {
    'credo': {'merchant_id': '', 'secret_key': ''},
    'space': {
        'base_url': 'https://api.spacebank.ge/api/',
        'merchant_name': '',
        'secret_key': '',
        'redirect_url': '',
    },
    'bog': {
        'client_id': '',
        'secret_key': '',
        'merchant_id': '',
        'terminal_id': '',
        'name': '',
        'intent': 'AUTHORIZE',  # 'CAPTURE',
        'capture_method': 'AUTOMATIC',  # 'AUTOMATIC',
        'show_shop_order_id_on_extract': True,
        'redirect_url': f'{HOST_URL}/%s/success/?trans_id=%s',
        'redirect_fail_url': f'{HOST_URL}/%s/fail/',
        "installment_success_redirect_url": f"{HOST_URL}/%s/success/?show_site=true&trans_id=%s",
        "installment_fail_redirect_url": f"{HOST_URL}/%s/success/?show_site=true&trans_id=%s",
        "installment_reject_redirect_url": f"{HOST_URL}/%s/success/?show_site=true&trans_id=%s",
    },
    'tbc': {
        'merchant_key': '',
        'test_merchant_key': '',
        'test_campaign_id': 1,
        'campaign_id': 1,
        'client_id': '',
        'secret_key': '',
        'bnpl_api_key': '',
        'bnpl_client_id': '',
        'bnpl_client_secret': '',

    },
    'georgian_card': {
        'account_id': "",
        'merchant_id': "",
        'portal_id': "",
        'bank_user_username': "",
        'bank_user_password': "",
        'back_url_s': f'{HOST_URL}/%s/success/?trans_id=%s',
        'back_url_f': f'{HOST_URL}/%s/success/?trans_id=%s',
    }
}
