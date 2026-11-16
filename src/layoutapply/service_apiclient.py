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
"""API client package"""

import copy
import json
import time
from http import HTTPMethod, HTTPStatus
from typing import Any

from jsonschema import ValidationError, validate
from requests import Response, exceptions

from layoutapply.common.api import AbstractAPIBase
from layoutapply.common.dateutil import get_str_now
from layoutapply.const import ApiHeaders, ApiUri, Result
from layoutapply.custom_exceptions import (  # noqa: E402
    ConnectTimeoutError,
    ExtendedProcedurePollingExceededException,
    FailedGetServiceInfoException,
    FailedRequestError,
    SuspendProcessException,
    UnexpectedRequestError,
    UrlNotFoundError,
)
from layoutapply.data import Details, Procedure
from layoutapply.schema import extended_procedure_schema


class ServiceAPIBase(AbstractAPIBase):
    """Base class of ServiceAPI"""

    def __init__(  # pylint: disable=C0103
        self,
        workflow_manager_conf: dict,
        logger_args: dict,
        applyID: str = None,
    ) -> None:
        """Constructor

        Args:
            workflow_manager_conf (dict): Configuration for workflow manager
            logger_args (dict): Arguments for Logger
            applyID (str): layoutapply ID
        """
        self.host = workflow_manager_conf.get("host")
        self.port = workflow_manager_conf.get("port")
        self.uri = workflow_manager_conf.get("uri")
        self.timeout = workflow_manager_conf.get("timeout")
        extended_procedure_conf = workflow_manager_conf.get("extended-procedure")
        self.retry_interval = extended_procedure_conf.get("retry").get("default").get("interval")
        self.retry_max_count = extended_procedure_conf.get("retry").get("default").get("max_count")
        self.detail = Details()
        self.logger = None
        self.logger_args = logger_args
        self.tmp_log_handler = None
        self.tmp_logger_name = None
        self.exception_flg = False
        self.is_suspended = False
        self.recent_request_uri = None
        self.applyID = applyID  # pylint: disable=C0103
        super().__init__(self.logger_args)

    def execute(self, procedure: Procedure) -> Details:
        """The execute method sends an API request with retry logic,
        handles errors, and returns execution details along with suspension status.

        Args:
            procedure (Procedure): Procedure object
        Returns:

            Details: Execution result details
        """
        self._set_logger()

        cnt: int = 0
        code: int = None

        self.logger.info(f"Start operationID:[{procedure.operationID}]")
        code, body = self._requests_wrapper(procedure)
        if code != HTTPStatus.ACCEPTED and self.exception_flg is False:
            self.logger.error(f"[E40004]{FailedRequestError(code, body).message}", stack_info=False)
            self.logger.info(f"operationID[{procedure.operationID}] has been retried. retry_count[{cnt}]")
            code, body = self._retry_request(procedure, self.retry_max_count, self.retry_interval, code, body)
            if code != HTTPStatus.ACCEPTED:
                self.is_suspended = True
                self.logger.error(f"[E40025]{SuspendProcessException().message}", stack_info=False)

        self._set_detail(code, body, procedure)
        if self.tmp_log_handler:
            self.logger.removeHandler(self.tmp_log_handler)
        self.logger.info(f"End operationID:[{procedure.operationID}]")
        return self.detail, self.is_suspended

    def _set_detail(self, code: int, body: Any, procedure: Procedure) -> None:
        """set detail object

        Args:
            code (int): HTTP Status code.
            body (Any): Response body
            procedure (Procedure): Procedure object
        """
        self.detail.status = Result.COMPLETED if code == HTTPStatus.ACCEPTED else Result.FAILED
        if code != HTTPStatus.ACCEPTED:
            self.logger.error(f"[E40004]{FailedRequestError(code, body).message}", stack_info=False)
        self.detail.operationID = procedure.operationID
        self.detail.responseBody = body
        self.detail.statusCode = code

    def _requests_wrapper(self, procedure: Procedure):
        """API Request wrapper

        Args:
            procedure (Procedure): Procedure object
        Returns:

            code: Response code from the last request of the retry process
            body: Response body from the last request of the retry process
        """
        response: Response = None
        self.exception_flg = False
        try:
            response = self._requests(procedure)
            code, body = ServiceAPIBase._parse_response(response)
        except exceptions.Timeout:
            exc = ConnectTimeoutError()
            self.logger.error(f"[E40003]{exc.message} operationID:[{procedure.operationID}]", stack_info=True)
            code = exc.status_code
            body = {"code": "E40003", "message": exc.message}
            self.exception_flg = True
        except exceptions.ConnectionError:
            exc = UrlNotFoundError(self.recent_request_uri)
            self.logger.error(f"[E40007]{exc.message} operationID:[{procedure.operationID}]", stack_info=True)
            code = exc.status_code
            body = {"code": "E40007", "message": exc.message}
            self.exception_flg = True
        except exceptions.RequestException as error:
            exc = UnexpectedRequestError(str(error))
            self.logger.error(f"[E40008]{exc.message} operationID:[{procedure.operationID}]", stack_info=True)
            code = exc.status_code
            body = {"code": "E40008", "message": exc.message}
            self.exception_flg = True
        return code, body

    def _requests(self, procedure: Procedure):
        """Describe the request part of each API

        Args:
            procedure (Procedure): Procedure object
        Raises:
            NotImplementedError: Raises an exception when not implemented
        """
        raise NotImplementedError()  # pragma: no cover

    def _retry_request(self, procedure: Procedure, max_count: int, interval: int, code, body):
        """Retry process when receiving a response other than 200

        Args:
            procedure (Procedure): Migration procedure
            max_count: Max count setting for retry
            interval: Interval setting for retry
            code: Response code from initial execution
            body: Response body from initial execution
        Returns:
            code: Response code from the last request of the retry process
            body: Response body from the last request of the retry process
        """
        cnt = 0
        while cnt != max_count:
            time.sleep(interval)
            code, body = self._requests_wrapper(procedure)
            if code == HTTPStatus.ACCEPTED or self.exception_flg is True:
                break
            else:
                self.logger.error(f"[E40004]{FailedRequestError(code, body).message}", stack_info=True)
                self.logger.info(f"operationID[{procedure.operationID}] has been retried. retry_count[{cnt + 1}]")
                cnt += 1
        return code, body

    @classmethod
    def _parse_response(cls, response: Response) -> tuple[int, Any]:
        """Analyze the response and return the HTTP status code and response body.
        If the response result is an error, a JSON object will be returned,
        so it will be returned as a dict.
        Args:
            response (Response): requests.Response object

        Returns:
            tuple[int, Any]: HTTP status code, response body
        """
        code = response.status_code
        body = response.text
        try:
            body = json.loads(body)
        except Exception:  # pylint: disable=W0703
            pass
        return code, body

    # fmt: off
    def _check_service_status(
        self, count: int, interval: int, get_service_obj: Any, procedure: Procedure,
    ) -> tuple[bool, None | dict, str]:
        """Check the expected service state transition

        Args:
            count (int): Max count setting for polling
            interval (int): Interval setting for polling
            get_service_obj (Any): API object for retrieving service information
            procedure (Procedure): Procedure object

        Returns:
            tuple[bool, bool str]: Whether the expected state was achieved, error flag, current service state
        """
        cnt, service_state, is_expected, error_resp = 0, "FAILED", False, None
        while cnt != count:
            response = get_service_obj.execute(procedure)
            # Exit if there is an abnormal termination in obtaining service information.
            if response["code"] != HTTPStatus.OK:
                error_resp = response.get("service_information")
                break
            # Exit if the service state becomes the expected state.
            service_state = response.get("service_information").get("status")
            if service_state != "IN_PROGRESS":
                is_expected = True if service_state == "COMPLETED" else False
                break
            cnt += 1
            time.sleep(interval)
        return is_expected, error_resp, service_state
    # fmt: on


class GetServiceInformationAPI(ServiceAPIBase):
    """Class of GetServiceInformationAPI"""

    def __init__(
        self,
        workflow_manager_conf: dict,
        logger_args: dict,
    ) -> None:  # pylint: disable = W0246
        """Constructor

        Args:
            workflow_manager_conf (dict): Configuration for workflow manager
            logger_args (dict): Arguments for Logger
        """
        super().__init__(workflow_manager_conf, logger_args)
        extended_procedure_conf = workflow_manager_conf.get("extended-procedure")
        polling_conf = extended_procedure_conf.get("polling")
        self.interval = polling_conf.get("interval")
        self.count = polling_conf.get("count")
        self.extended_procedure_id = None

    def _requests(self, procedure: Procedure):
        """Make a request to the get service information API.

        Args:
            procedure (Procedure): Procedure object
        Returns:
            requests.Response: Response
        """
        get_service_information_uri = ApiUri.GET_EXTENDED_PROCEDURE_API.format(
            self.host, self.port, self.uri, self.extended_procedure_id
        )
        self.recent_request_uri = copy.deepcopy(get_service_information_uri)
        get_service_information_method = HTTPMethod.GET
        self.logger.info(
            (
                f"Start request. url:[{get_service_information_uri}], ",
                f"method:[{get_service_information_method}]",
            )
        )
        response = self._get(url=get_service_information_uri, timeout_sec=self.timeout, headers=ApiHeaders)
        self.logger.info(f"Request completed. status:[{response.status_code}], response[{response.text}]")

        return response

    def execute(self, procedure: Procedure) -> dict:
        """Request to get service information API

        Args:
            procedure (Procedure): Procedure object

        Returns:
            service_information: get service information API implementation results
        """

        self._set_logger()

        code, body = self._requests_wrapper(procedure)
        if code == HTTPStatus.OK:
            try:
                validate(body, schema=extended_procedure_schema)
            except ValidationError as err:
                code = HTTPStatus.BAD_REQUEST
                error_message = err.message.split("\n")[-1]
                self.logger.error(f"[E40001]{error_message}", stack_info=False)

        if code != HTTPStatus.OK:
            self.logger.error(f"[E40034]{FailedGetServiceInfoException().message}", stack_info=False)

        return {"code": code, "service_information": body}


class ExtendedProcedureAPIBase(ServiceAPIBase):
    """Base class for Extended Procedure API (Start/Stop)"""

    def __init__(
        self,
        workflow_manager_conf: dict,
        logger_args: dict,
        applyID: str = None,
    ) -> None:
        """Constructor

        Args:
            workflow_manager_conf (dict): Configuration for workflow manager
            logger_args (dict): Arguments for Logger
            applyID (str): layoutapply ID
        """
        super().__init__(workflow_manager_conf, logger_args, applyID)
        self.get_service_api = GetServiceInformationAPI(workflow_manager_conf, logger_args)
        extended_procedure_conf = workflow_manager_conf.get("extended-procedure")
        polling_conf = extended_procedure_conf.get("polling")

        self.interval = polling_conf.get("interval")
        self.count = polling_conf.get("count")

    def _requests(self, procedure: Procedure):
        """Send a request to the service API.

        Args:
            procedure (Procedure): Procedure object
        Returns:
            requests.Response: Response
        """
        self.detail.uri = ApiUri.EXTENDED_PROCEDURE_API.format(self.host, self.port, self.uri)
        self.recent_request_uri = copy.deepcopy(self.detail.uri)
        self.detail.method = HTTPMethod.POST
        self.detail.requestBody = {
            "applyID": self.applyID,
            "targetCPUID": procedure.targetCPUID,
            "targetRequestInstanceID": procedure.targetRequestInstanceID,
            "operation": procedure.operation,
        }
        self.logger.info(
            (
                f"Start request. url:[{self.detail.uri}], ",
                f"method:[{self.detail.method}]",
                f"request body:[{self.detail.requestBody}]",
            )
        )
        response = self._post(
            url=self.detail.uri, data=self.detail.requestBody, timeout_sec=self.timeout, headers=ApiHeaders
        )
        self.logger.info(f"Request completed. status:[{response.status_code}], response[{response.text}]")
        return response

    def execute(self, procedure: Procedure) -> Details:
        """Make a request to the service API.

        Args:
            procedure (Procedure): Procedure object

        Returns:
            Details: Execution result of get service information API
        """
        self._set_logger()
        self.detail.startedAt = get_str_now()
        super().execute(procedure)
        extended_procedure_id = None

        if self.detail.status == Result.COMPLETED:
            if isinstance(self.detail.responseBody, dict) and "extendedProcedureID" in self.detail.responseBody:
                extended_procedure_id = self.detail.responseBody.get("extendedProcedureID")
                self.get_service_api.extended_procedure_id = extended_procedure_id
                self.logger.info(f"extendedProcedureID: [{extended_procedure_id}]")

            is_expected, _, service_state = self._check_service_status(
                self.count, self.interval, self.get_service_api, procedure
            )
            if is_expected is False:
                exc = ExtendedProcedurePollingExceededException(procedure.targetRequestInstanceID, service_state)
                self.logger.error(f"[E40033]{exc.message}", stack_info=False)
                self.detail.status = Result.FAILED
                self.detail.responseBody = {"code": "E40033", "message": exc.message}
        self.detail.endedAt = get_str_now()

        return self.detail, self.is_suspended


class StartAPI(ExtendedProcedureAPIBase):
    """Class of StartAPI"""


class StopAPI(ExtendedProcedureAPIBase):
    """Class of StopAPI"""
