# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import functools

import requests

from requests_mock import adapter
from requests_mock import exceptions


class MockerCore(object):
    """A wrapper around common mocking functions.

    Automate the process of mocking the requests library. This will keep the
    same general options available and prevent repeating code.
    """

    _PROXY_FUNCS = set(['last_request',
                        'register_uri',
                        'add_matcher',
                        'request_history'])

    def __init__(self, **kwargs):
        self._adapter = adapter.Adapter()
        self._real_http = kwargs.pop('real_http', False)
        self._real_send = None

        if kwargs:
            raise TypeError('Unexpected Arguments: %s' % ', '.join(kwargs))

    def start(self):
        """Start mocking requests.

        Install the adapter and the wrappers required to intercept requests.
        """
        if self._real_send:
            raise RuntimeError('Mocker has already been started')

        self._real_send = requests.Session.send

        def _fake_get_adapter(session, url):
            return self._adapter

        def _fake_send(session, request, **kwargs):
            real_get_adapter = requests.Session.get_adapter
            requests.Session.get_adapter = _fake_get_adapter

            try:
                return self._real_send(session, request, **kwargs)
            except exceptions.NoMockAddress:
                if not self._real_http:
                    raise
            finally:
                requests.Session.get_adapter = real_get_adapter

            return self._real_send(session, request, **kwargs)

        requests.Session.send = _fake_send

    def stop(self):
        """Stop mocking requests.

        This should have no impact if mocking has not been started.
        """
        if self._real_send:
            requests.Session.send = self._real_send
            self._real_send = None

    def __getattr__(self, name):
        if name in self._PROXY_FUNCS:
            try:
                return getattr(self._adapter, name)
            except AttributeError:
                pass

        raise AttributeError(name)


class Mocker(MockerCore):
    """The standard entry point for mock Adapter loading.
    """
    def __init__(self, **kwargs):
        """Create a new mocker adapter.

        :param str kw: Pass the mock object through to the decorated function
            as this named keyword argument, rather than a positional argument.
        :param bool real_http: True to send the request to the real requested
            uri if there is not a mock installed for it. Defaults to False.
        """
        self._kw = kwargs.pop('kw', None)
        super(Mocker, self).__init__(**kwargs)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.stop()

    def __call__(self, func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            with self as m:
                if self._kw:
                    kwargs[self._kw] = m
                else:
                    args = list(args)
                    args.append(m)

                return func(*args, **kwargs)

        return inner