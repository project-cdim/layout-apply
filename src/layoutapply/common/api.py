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
"""API-related packages"""

import json
from typing import Any

import requests
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_fixed

from layoutapply.cdimlogger import Logger


class Singleton(object):
    """Singleton Class"""

    @classmethod
    def get_instance(cls, input):  # pragma: no cover
        """get_instance"""
        if not hasattr(cls, "_instance"):
            cls._instance = cls(input)
        return cls._instance


class Session(Singleton):
    """Session Class"""

    def __init__(self):
        self.session = requests.Session()


class BaseApiClient:
    """Base class for executing API requests"""

    def __init__(self, logger: Logger, conn_retry_interval: int = 0, conn_retry_max_count: int = 0) -> None:
        """Constructor"""
        self.session = Session().session
        self.conn_retry_interval = conn_retry_interval
        self.conn_retry_max_count = conn_retry_max_count
        self.logger = logger

    def _get(
        self,
        url: str,
        params: dict = None,
        timeout_sec: int = 30,
        headers: dict = None,
    ):
        """Execute the get method of the requests library and return the request result.

        Args:
            url (str): The URL to which the request is sent.
                       If not specified, the URL from the configuration file is used.
            params (dict, optional): Query parameters. Defaults to None.
            timeout_sec (int, optional): Timeout in seconds. Defaults to 30.
            headers (dict, optional): Header information. Defaults to None.

        Returns:
            requests.Response: Response
        """
        for attempt in Retrying(
            retry=retry_if_exception_type(requests.exceptions.ConnectionError),
            stop=stop_after_attempt(self.conn_retry_max_count),
            wait=wait_fixed(self.conn_retry_interval),
            reraise=True,
        ):
            with attempt:
                self._output_log(attempt, url, params, "GET")
                response = self.session.get(url, params=params, timeout=timeout_sec, headers=headers)
        return response

    def _post(
        self,
        url: str,
        params: dict = None,
        data: Any = None,
        timeout_sec: int = 30,
        headers: dict = None,
    ):
        """Execute the post method of the requests library and return the request result.
        If the content-type of data corresponds to application/json, this will be added to the headers.

        Args:
            url (str): The URL to which the request is sent.
                       If not specified, the URL from the configuration file is used.
            params (dict, optional): Set query parameters. Defaults to None.
            data (dict, optional): Set the request body. Defaults to None.
            timeout_sec (int, optional): Timeout in seconds. Defaults to 30.
            headers (dict, optional): Header information. Defaults to None.
        Returns:
            requests.Response: Response.
        """
        headers, data = self._modify_data_and_header(headers, data)
        for attempt in Retrying(
            retry=retry_if_exception_type(requests.exceptions.ConnectionError),
            stop=stop_after_attempt(self.conn_retry_max_count),
            wait=wait_fixed(self.conn_retry_interval),
            reraise=True,
        ):
            with attempt:
                self._output_log(attempt, url, params, "POST")
                response = self.session.post(url, params=params, data=data, timeout=timeout_sec, headers=headers)
        return response

    def _put(
        self,
        url: str,
        params: dict = None,
        data: dict = None,
        timeout_sec: int = 30,
        headers: dict = None,
    ):
        """Execute the put method of the requests library and return the request result.
        If the content-type of data corresponds to application/json, add the above to the header.

        Args:
            url (str): The request destination URL. If not specified, the URL in the configuration file
            params (dict, optional): Set query parameters. Defaults to None. Defaults to None
            data (dict, optional): Set the request body. Defaults to None
            timeout_sec (int, optional): Timeout in seconds. Defaults to 30
            headers (dict, optional): Header information. Defaults to None

        Returns:
            requests.Response: Response
        """
        headers, data = self._modify_data_and_header(headers, data)
        for attempt in Retrying(
            retry=retry_if_exception_type(requests.exceptions.ConnectionError),
            stop=stop_after_attempt(self.conn_retry_max_count),
            wait=wait_fixed(self.conn_retry_interval),
            reraise=True,
        ):
            with attempt:
                self._output_log(attempt, url, params, "PUT")
                response = self.session.put(url, params=params, data=data, timeout=timeout_sec, headers=headers)
        return response

    def _delete(
        self,
        url: str,
        params: dict = None,
        data: dict = None,
        timeout_sec: int = 30,
        headers: dict = None,
    ):
        """Execute the delete method of the requests library and return the request results.
        If the content-type of the data matches application/json, add the aforementioned to the header.

        Args:
            url (str): The URL for the request. If not specified, use the URL described in the configuration file.
            params (dict, optional): Set query parameters. Defaults to None.
            data (dict, optional): Set the request body. Defaults to None.
            timeout_sec (int, optional): Timeout in seconds. Defaults to 30.
            headers (dict, optional): Header information. Defaults to None.

        Returns:
            requests.Response: Response
        """
        headers, data = self._modify_data_and_header(headers, data)
        for attempt in Retrying(
            retry=retry_if_exception_type(requests.exceptions.ConnectionError),
            stop=stop_after_attempt(self.conn_retry_max_count),
            wait=wait_fixed(self.conn_retry_interval),
            reraise=True,
        ):
            with attempt:
                self._output_log(attempt, url, params, "DELETE")
                response = self.session.delete(url, params=params, data=data, timeout=timeout_sec, headers=headers)
        return response

    def _modify_data_and_header(self, headers: Any, data: Any) -> tuple[Any, Any]:
        """Correct the appropriate data and headers for the data to be sent in application/json.

        Args:
            headers (Any): Request headers
            data (Any): Request body

        Returns:
            tuple[Any, Any]: Correctly adjusted data and headers
        """

        # In the case of a dict type, convert it to JSON and add "Content-Type": "application/json".
        add_header = {"Content-Type": "application/json"}
        if isinstance(data, dict):
            # If it cannot be corrected to a JSON string, no additions will be made.
            try:
                data = json.dumps(data)
            except Exception:  # pylint: disable=broad-except
                add_header = None
        elif isinstance(data, str):
            try:
                _ = json.loads(data)
            except Exception:  # pylint: disable=broad-except
                add_header = None
        else:
            add_header = None
        if add_header:
            # If headers is None, initialize it as an empty dictionary and add the add_header item.
            headers = headers if headers else {}
            headers = {**headers, **add_header}

        return headers, data

    def _output_log(self, attempt: Any, url: str, params: dict, method: str):
        """output debug log

        Args:
            attempt (Any): Retry information
            url (str): The URL for the request. If not specified, use the URL described in the configuration file.
            params (dict, optional): Set query parameters. Defaults to None.
            method (str): Run method
        """
        self.logger.debug(f"retry:{attempt.retry_state.attempt_number-1}, URL:{url}, params:{params}, method:{method}")
