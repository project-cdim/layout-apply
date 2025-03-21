# Copyright (C) 2025 NEC Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
#  under the License.
"""API Related Packages"""

import json
import time

import pytest
import requests
from pytest_httpserver import HeaderValueMatcher, HTTPServer
from werkzeug import Request, Response

from layoutapply.cdimlogger import Logger
from layoutapply.common.api import BaseApiClient
from layoutapply.setting import LayoutApplyConfig

# NOTICE: Add the dummy server's IP/HOST to the NO_PROXY environment variable.
# os.environ["NO_PROXY"] = "localhost"


def case_insensitive_compare(actual: str, expected: str) -> bool:
    """Function for Checking Request Headers"""
    return actual.lower() == expected.lower()


HeaderValueMatcher.DEFAULT_MATCHERS["Content-Type"] = case_insensitive_compare


@pytest.mark.usefixtures("httpserver_listen_address")
class DummayApiClient(BaseApiClient):
    """Dummy Client for Testing BaseApiClient"""

    def __init__(self, url) -> None:
        config = LayoutApplyConfig()
        self.retry_interval = config.server_connection.get("retry").get("interval")
        self.retry_max_count = config.server_connection.get("retry").get("max_count")
        print(config)
        self.logger = Logger(**config.logger_args)
        super().__init__(self.logger, self.retry_interval, self.retry_max_count)
        self.url = url

    def get(self, params=None, timeout_sec=5):
        return self._get(self.url, params, timeout_sec)

    def post(self, params=None, data=None, timeout_sec=5):
        return self._post(self.url, params=params, data=data, timeout_sec=timeout_sec)

    def put(self, params=None, data=None, timeout_sec=5):
        return self._put(self.url, params=params, data=data, timeout_sec=timeout_sec)

    def delete(self, params=None, data=None, timeout_sec=5):
        return self._delete(self.url, params=params, data=data, timeout_sec=timeout_sec)

    def _output_log(self, attempt=None, url=None, params=None, method=None):
        pass


class TestBaseApiClient:
    """Base Class for Making API Requests"""

    @pytest.mark.parametrize(
        "params, payload",
        [
            (
                {"q_key": "q_val"},
                {"resp_key": "resp_val"},
            ),
            (
                None,
                {},
            ),
        ],
    )
    def test_get_can_request(self, params, payload, httpserver: HTTPServer, init_db_instance):
        # arrange
        # Set to respond_with_json when returning the response body.
        httpserver.expect_request("/test", method="GET").respond_with_json(payload)

        # act
        client = DummayApiClient(httpserver.url_for("/test"))
        response = client.get(params=params)

        # assert
        assert response.status_code == 200
        assert json.loads(response.text) == payload

    def test_get_timeout_setting_enabled_when_wait_2_seconds_with_timeout_1_second(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        # When performing server-side processing (such as waiting for a timeout), bind the method to respond_with_handler.
        def sleeping(request):
            time.sleep(2)

        httpserver.expect_request("/test", method="GET").respond_with_handler(sleeping)

        # act/assert
        client = DummayApiClient(httpserver.url_for("/test"))
        with pytest.raises(requests.exceptions.ReadTimeout):
            response = client.get(timeout_sec=1)

    @pytest.mark.parametrize(
        "wait",
        [4, 6],
    )
    def test_get_default_timeout_of_5_seconds_when_wait_4_and_6_senconds(
        self, wait, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        httpserver.clear()

        def sleeping(request: Request):
            time.sleep(wait)

        httpserver.expect_request("/test", method="GET").respond_with_handler(sleeping)
        httpserver.check_assertions()

        # act/assert
        client = DummayApiClient(httpserver.url_for("/test"))

        if int(wait) >= 5:
            with pytest.raises(Exception):
                response = client.get()
        else:
            response = client.get()
            # assert
            assert response.status_code == 200

    @pytest.mark.parametrize(
        "params, data",
        [
            (
                {"q_key": "q_val"},
                {"body_key": "body_val"},
            ),
            (
                None,
                None,
            ),
        ],
    )
    def test_post_can_request(self, params, data, httpserver: HTTPServer, init_db_instance):
        # arrange
        httpserver.clear()

        # If simply returning a status code, set the status_code in a requests.Response object to respond_with_response.
        def response(request: Request):
            resp = Response().status_code = 201
            return resp

        # If there is data in JSON format, check if there is a "Content-Type": "application/json" in the header.
        if data:
            httpserver.expect_request(
                "/test", method="POST", headers={"Content-Type": "application/json"}
            ).respond_with_response(Response("", status=201))
        else:
            httpserver.expect_request("/test", method="POST").respond_with_response(Response("", status=201))
        httpserver.check_assertions()
        # act
        client = DummayApiClient(httpserver.url_for("/test"))
        response = client.post(params=params, data=data)

        # assert
        assert response.status_code == 201

    def test_post_timeout_setting_enabled_when_wait_2_seconds_with_timeout_1_second(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        httpserver.clear()

        def sleeping(request):
            time.sleep(2)

        httpserver.expect_request("/test", method="POST").respond_with_handler(sleeping)
        httpserver.check_assertions()
        # act/assert
        client = DummayApiClient(httpserver.url_for("/test"))
        with pytest.raises(requests.exceptions.ReadTimeout):
            client.post(timeout_sec=1)

    @pytest.mark.parametrize(
        "wait",
        [4, 6],
    )
    def test_post_default_timeout_of_5_seconds_when_wait_4_and_6_senconds(
        self, wait, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        httpserver.clear()

        def sleeping(request: Request):
            time.sleep(wait)

        httpserver.expect_request("/test", method="POST").respond_with_handler(sleeping)
        httpserver.check_assertions()

        # act/assert
        client = DummayApiClient(httpserver.url_for("/test"))

        if int(wait) >= 5:
            with pytest.raises(Exception):
                response = client.post()
        else:
            response = client.post()
            # assert
            assert response.status_code == 200

    @pytest.mark.parametrize(
        "params, data",
        [
            (
                {"q_key": "q_val"},
                {"body_key": "body_val"},
            ),
            (
                None,
                None,
            ),
        ],
    )
    def test_put_can_request(self, params, data, httpserver: HTTPServer, init_db_instance):
        # arrange
        httpserver.clear()
        # If you simply want to return a status code, set the status_code of the requests.Response object with respond_with_response.
        # If there is data in JSON format, check if the header includes "Content-Type": "application/json".
        if data:
            httpserver.expect_request(
                "/test", method="PUT", headers={"Content-Type": "application/json"}
            ).respond_with_response(Response("", status=204))
        else:
            httpserver.expect_request("/test", method="PUT").respond_with_response(Response("", status=204))
        httpserver.check_assertions()
        # act
        client = DummayApiClient(httpserver.url_for("/test"))
        response = client.put(params=params, data=data)

        # assert
        assert response.status_code == 204

    def test_put_timeout_setting_enabled_when_wait_2_seconds_with_timeout_1_second(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        httpserver.clear()

        def sleeping(request: Request):
            time.sleep(2)

        httpserver.expect_request("/test", method="PUT").respond_with_handler(sleeping)
        httpserver.check_assertions()

        # act/assert
        client = DummayApiClient(httpserver.url_for("/test"))

        with pytest.raises(Exception):
            client.put(timeout_sec=1)

    @pytest.mark.parametrize(
        "wait",
        [4, 6],
    )
    def test_put_default_timeout_of_5_seconds_when_wait_4_and_6_senconds(
        self, wait, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        httpserver.clear()

        def sleeping(request: Request):
            time.sleep(wait)

        httpserver.expect_request("/test", method="PUT").respond_with_handler(sleeping)
        httpserver.check_assertions()

        # act/assert
        client = DummayApiClient(httpserver.url_for("/test"))

        if int(wait) >= 5:
            with pytest.raises(Exception):
                response = client.put()
        else:
            response = client.put()
            # assert
            assert response.status_code == 200

    @pytest.mark.parametrize(
        "params, data",
        [
            (
                {"q_key": "q_val"},
                {"body_key": "body_val"},
            ),
            (
                None,
                None,
            ),
        ],
    )
    def test_delete_can_request(self, params, data, httpserver: HTTPServer, init_db_instance):
        # arrange
        httpserver.clear()
        # If you simply return a status code, set the status_code in the requests.Response object with respond_with_response.
        # If JSON data exists, check if the header contains "Content-Type": "application/json".
        if data:
            httpserver.expect_request(
                "/test", method="DELETE", headers={"Content-Type": "application/json"}
            ).respond_with_response(Response("", status=204))
        else:
            httpserver.expect_request("/test", method="DELETE").respond_with_response(Response("", status=204))
        httpserver.check_assertions()
        # act
        client = DummayApiClient(httpserver.url_for("/test"))
        response = client.delete(params=params, data=data)

        # assert
        assert response.status_code == 204

    def test_delete_timeout_setting_enabled_when_wait_2_seconds_with_timeout_1_second(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        httpserver.clear()

        def sleeping(request: Request):
            time.sleep(2)

        httpserver.expect_request("/test", method="DELETE").respond_with_handler(sleeping)
        httpserver.check_assertions()

        # act/assert
        client = DummayApiClient(httpserver.url_for("/test"))

        with pytest.raises(Exception):
            client.delete(timeout_sec=1)

    @pytest.mark.parametrize(
        "wait",
        [4, 6],
    )
    def test_delete_default_timeout_of_5_seconds_when_wait_4_and_6_senconds(
        self, wait, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        httpserver.clear()

        def sleeping(request: Request):
            time.sleep(wait)

        httpserver.expect_request("/test", method="DELETE").respond_with_handler(sleeping)
        httpserver.check_assertions()

        # act/assert
        client = DummayApiClient(httpserver.url_for("/test"))

        if int(wait) >= 5:
            with pytest.raises(Exception):
                response = client.delete()
        else:
            response = client.delete()
            # assert
            assert response.status_code == 200

    @pytest.mark.parametrize(
        "data",
        [
            # In the case of a dict type
            {"q_key": "q_val"},
            # In the case of JSON strings
            json.dumps(
                {"q_key": "q_val"},
            ),
        ],
    )
    @pytest.mark.parametrize(
        "headers",
        [
            # If not set
            None,
            # In the case of an empty dictionary
            {},
            # If any other headers are already set
            {"x-api-key": "xxxxxxxx"},
        ],
    )
    def test_modify_headers_and_data_are_properly_modified_when_modify_data_and_the_header_contenttype_is_applicationJson(
        self, headers, data, init_db_instance
    ):
        client = DummayApiClient("")
        res_header, res_data = client._modify_data_and_header(headers=headers, data=data)
        assert "Content-Type" in res_header
        assert res_header["Content-Type"] == "application/json"
        # If any other headers are already set, the key will not disappear.
        if isinstance(headers, dict) and len(headers.keys()) != 1:
            for key in headers.keys():
                assert res_header[key] == headers[key]
        # Being a JSON-formatted string.
        json.loads(res_data)

    import logging

    @pytest.mark.parametrize(
        "data",
        [
            # Undefined
            None,
            # The value is different
            1,
            # A dictionary type that contains data which cannot be serialized with json.dumps
            {"logger": logging.getLogger()},
            # If it's not a JSON string
            "Not Json Strings.",
        ],
    )
    @pytest.mark.parametrize(
        "headers",
        [
            # Undefined
            None,
            # In the case of an empty dictionary
            {},
            # If any other headers are already set
            {"x-api-key": "xxxxxxxx"},
        ],
    )
    def test_modify_headers_and_data_are_not_modified_when_modify_data_but_the_header_contenttype_is_not_applicationJson(
        self, headers, data, init_db_instance
    ):
        client = DummayApiClient("")
        res_header, res_data = client._modify_data_and_header(headers=headers, data=data)
        assert res_header == headers
        assert res_data == data
