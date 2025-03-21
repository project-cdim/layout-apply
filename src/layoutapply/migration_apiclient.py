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
"""API package for generating migration procedures"""

import json
from http import HTTPStatus
from typing import Any

from jsonschema import ValidationError, validate
from requests import Response, exceptions

from layoutapply.cdimlogger import Logger
from layoutapply.common.api import BaseApiClient
from layoutapply.const import ApiHeaders, ApiUri
from layoutapply.custom_exceptions import (
    ConnectTimeoutError,
    FailedRequestError,
    UnexpectedRequestError,
    UrlNotFoundError,
)
from layoutapply.schema import configmanager_api_resp as confmaneger_resp_schema
from layoutapply.schema import get_resources_available_api_resp as get_resources_available_resp_schema


class MigrationBaseAPI(BaseApiClient):
    """Base class for generating migration procedures"""

    def __init__(self, logger: Logger, config: dict, connection_config: dict) -> None:
        self.host, self.port = config.get("host"), config.get("port")
        self.uri: str = config.get("uri")
        self.timeout: int = config.get("timeout")
        self.recent_request_uri = None
        self.retry_interval = connection_config.get("retry").get("interval")
        self.retry_max_count = connection_config.get("retry").get("max_count")

        self.logger: Logger = logger
        super().__init__(self.logger, self.retry_interval, self.retry_max_count)

    def _create_body(self, code: str, msg: str) -> dict:
        """create error body

        Args:
            code (str): error code
            msg (str): error message

        Returns:
            dict: response body
        """
        return {"code": code, "message": msg}

    def execute(self) -> tuple[int, dict]:
        """Make a request to the API"""
        response: Response = None
        try:
            response = self._requests()
            code, body = MigrationBaseAPI._parse_response(response)
            if code != HTTPStatus.OK:
                body = self._create_body("E50004", FailedRequestError(code, body).message)
                self.logger.error(f"[{body['code']}]{body['message']}", stack_info=True)
        except exceptions.Timeout:
            exc = ConnectTimeoutError()
            code = exc.status_code
            body = self._create_body("E50003", exc.message)
            self.logger.error(f"[{body['code']}]{body['message']}", stack_info=True)
        except exceptions.ConnectionError:
            exc = UrlNotFoundError(self.recent_request_uri)
            code = exc.status_code
            body = self._create_body("E50006", exc.message)
            self.logger.error(f"[{body['code']}]{body['message']}", stack_info=True)
        except exceptions.RequestException as err:
            exc = UnexpectedRequestError(str(err))
            code = exc.status_code
            body = self._create_body("E50007", exc.message)
            self.logger.error(f"[{body['code']}]{body['message']}", stack_info=True)
        return code, body

    def _requests(self) -> Response:
        """Describe the request part of each API
        Raises:
            NotImplementedError: Throw an exception when not implemented
        """
        raise NotImplementedError()  # pragma: no cover

    @classmethod
    def _parse_response(cls, response: Response) -> tuple[int, Any]:
        """Parse the response and return the HTTP status code and response body.
        Since the response result is returned as a JSON object in case of an error,
        return it as a dict.
        Args:
            response (Response): requests.Response object

        Returns:
            tuple[int, Any]: HTTP status code, response body
        """
        code, body = response.status_code, response.text
        try:
            body = json.loads(body)
        # pylint: disable=W0703
        except Exception:  # pragma: no cover
            pass
        return code, body


class MigrationAPI(MigrationBaseAPI):
    """API class for generating migration procedure"""

    def __init__(self, logger: Logger, config: dict, connection_config: dict, data: dict) -> None:
        """Constructor

        Args:
            logger (Logger): Logger object
            config (dict): Setting item
            layouts (dict): Request body
        """
        self.data = data
        super().__init__(logger, config, connection_config)

    def _requests(self) -> Response:
        """Request to generate migration procedure.

        Returns:
            Response: API response
        """
        self.recent_request_uri = ApiUri.MIGRATION_PROCEDURES_API.format(self.host, self.port, self.uri)
        self.logger.info(f"Start request. url:[{self.recent_request_uri}], method:[POST]")
        response = self._post(url=self.recent_request_uri, timeout_sec=self.timeout, data=self.data, headers=ApiHeaders)
        self.logger.info(f"Request completed. status:[{response.status_code}], response[{response.text}]")
        return response


class ConfigManagerAPI(MigrationBaseAPI):
    """API class for configuration information management"""

    def _requests(self) -> Response:
        """Request configuration information.

        Returns:
            Response: API response
        """
        self.recent_request_uri = ApiUri.GET_ALLNODES_INFO_API.format(self.host, self.port, self.uri)
        self.logger.info(f"Start request. url:[{self.recent_request_uri}], method:[GET]")
        response = self._get(url=self.recent_request_uri, timeout_sec=self.timeout, headers=ApiHeaders)
        self.logger.info(f"Request completed. status:[{response.status_code}], response[{response.text}]")
        return response

    def execute(self) -> tuple[int, dict]:
        """Request configuration information.

        Returns:
            tuple[int, dict]: code, body
        """
        code, body = super().execute()
        if code == HTTPStatus.OK.value:
            try:
                validate(body, confmaneger_resp_schema)
            except ValidationError as err:
                code = HTTPStatus.BAD_REQUEST.value
                error_message = err.message.split("\n")[-1]
                self.logger.error(f"[E50001]{error_message}", stack_info=False)
                body = {"code": "E50001", "message": error_message}

        return code, body


class GetAvailableResourcesAPI(MigrationBaseAPI):
    """API class for get available resources"""

    def _requests(self) -> Response:
        """Request configuration information.

        Returns:
            Response: API response
        """
        self.recent_request_uri = ApiUri.GET_AVAILABLE_RESOURCES_API.format(self.host, self.port, self.uri)
        self.logger.info(f"Start request. url:[{self.recent_request_uri}], method:[GET]")
        response = self._get(url=self.recent_request_uri, timeout_sec=self.timeout, headers=ApiHeaders)
        self.logger.info(f"Request completed. status:[{response.status_code}], response[{response.text}]")
        return response

    def execute(self) -> tuple[int, dict]:
        """Request configuration information.

        Returns:
            tuple[int, dict]: code, body
        """
        code, body = super().execute()
        if code == HTTPStatus.OK.value:
            try:
                validate(body, get_resources_available_resp_schema)
            except ValidationError as err:
                code = HTTPStatus.BAD_REQUEST.value
                error_message = err.message.split("\n")[-1]
                self.logger.error(f"[E50001]{error_message}", stack_info=False)
                body = {"code": "E50001", "message": error_message}

        return code, body
