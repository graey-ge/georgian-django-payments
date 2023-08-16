from typing import Union, Dict

from django.http import QueryDict
from requests.auth import AuthBase


class BearerAuth(AuthBase):
    def __init__(self, token):
        self.token = token

    def __eq__(self, other):
        return self.token == other.token

    def __ne__(self, other):
        return not self == other

    def __call__(self, r):
        r.headers['Authorization'] = f"Bearer {self.token}"
        return r


def requests_to_curl(response):
    request = response.request
    command = "curl -X {method} -H {headers} -d '{data}' '{uri}'"
    method = request.method
    uri = request.url
    data = request.body
    headers = ['"{0}: {1}"'.format(k, v) for k, v in request.headers.items()]
    headers = " -H ".join(headers)
    return command.format(method=method, headers=headers, data=data, uri=uri)


def remove_lists_from_dict_values(data: Union[QueryDict]) -> Dict[str, Union[str, int]]:
    _dict = {}
    for k, v in data.items():
        _dict[k] = v
        if isinstance(v, list) or isinstance(v, tuple):
            _dict[k] = v[0]
    return _dict
