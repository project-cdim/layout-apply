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
import logging
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime
from http import HTTPMethod, HTTPStatus
from typing import Any

from jsonschema import ValidationError, validate
from requests import Response, exceptions

from layoutapply.cdimlogger import Logger
from layoutapply.common.api import BaseApiClient
from layoutapply.common.dateutil import get_str_now
from layoutapply.const import ApiHeaders, ApiUri, RequestBodyAction, Result
from layoutapply.custom_exceptions import (  # noqa: E402
    ConnectTimeoutError,
    FailedGetDeviceInfoException,
    FailedRequestError,
    InitializeLogSubProcessError,
    OsBootFailureException,
    PowerStateNotChangeException,
    SuspendProcessException,
    UnexpectedRequestError,
    UrlNotFoundError,
)
from layoutapply.data import Details, IsOsBoot, Procedure, details_dict_factory
from layoutapply.schema import device_information as device_information_scheme


class HarwareManageAPIBase(BaseApiClient):
    """Base class of HarwareManageAPI"""

    def __init__(
        self,
        hardware_control_conf: dict,
        get_info_conf: dict,
        api_config: dict,
        logger_args: dict,
        server_connection_conf: dict,
    ) -> None:
        """Constructor

        Args:
            hardware_control_conf (dict): Configuration for hardware control functions
            get_info_conf (dict): Configuration for information retrieval functions
            api_config (dict): Retry settings for each API, etc
            logger_args (dict): Arguments for GILogger
        """
        self.host = hardware_control_conf.get("host")
        self.port = hardware_control_conf.get("port")
        self.uri = hardware_control_conf.get("uri")
        self.get_info_conf = get_info_conf
        self.timeout = api_config.get("timeout")
        self.isosboot_conf = api_config.get("isosboot")
        self.retry_targets = api_config.get("retry").get("targets")
        self.retry_default = api_config.get("retry").get("default")
        self.conn_retry_interval = server_connection_conf.get("retry").get("interval")
        self.conn_retry_max_count = server_connection_conf.get("retry").get("max_count")
        self.detail = Details()
        self.logger = None
        self.logger_args = logger_args
        self.tmp_log_handler = None
        self.tmp_logger_name = None
        self.exception_flg = False
        self.is_suspended = False
        self.recent_request_uri = None
        super().__init__(self.logger, self.conn_retry_interval, self.conn_retry_max_count)

    def execute(self, procedure: Procedure) -> Details:
        """Send a request to the API.
        This task is executed asynchronously, and the return value of this function is referred to as the task result
        in the main method. If a timeout occurs on the host side causing an HTTP request error in the hardware control
        function, it will terminate without retrying. It is executed at interval intervals until a normal completion
        (200) is returned or the retry limit is reached based on the retry settings for each API.

        Args:
            procedure (Procedure): Procedure object
        Returns:

            Details: Execution result details
        """
        self._set_logger()

        cnt: int = 0
        code: int = None
        is_retryng = False

        # First execution
        self.logger.info(f"Start operationID:[{procedure.operationID}]")
        code, body = self._requests_wrapper(procedure)
        if code != HTTPStatus.OK and self.exception_flg is False:
            self.logger.error(f"[E40004]{FailedRequestError(code, body).message}", stack_info=False)
            self.logger.info(f"operationID[{procedure.operationID}] has been retried. retry_count[{cnt}]")
            # Retry determination
            is_retryng, interval, max_count = self._is_retry_response(code, body)
            if is_retryng is False:
                interval = self.retry_default["interval"]
                max_count = self.retry_default["max_count"]
            code, body = self._retry_request(procedure, max_count, interval, code, body)
            if code != HTTPStatus.OK:
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
        if code != HTTPStatus.OK:
            self.detail.status = Result.FAILED
            self.logger.error(f"[E40004]{FailedRequestError(code, body).message}", stack_info=False)
        else:
            self.detail.status = Result.COMPLETED
        self.detail.operationID = procedure.operationID
        self.detail.responseBody = body
        self.detail.statusCode = code

    def _set_detail_on_preproc_error(self, procedure: Procedure) -> None:
        """set detail object

        Args:
            procedure (Procedure): Procedure object
        """
        self.detail.status = Result.FAILED
        self.detail.operationID = procedure.operationID

    def _requests_wrapper(self, procedure: Procedure):
        """API Request wrapper

        Args:
            procedure (Procedure): Procedure object
        """
        response: Response = None
        self.exception_flg = False
        try:
            response = self._requests(procedure)
            code, body = HarwareManageAPIBase._parse_response(response)
        except exceptions.Timeout:
            exc = ConnectTimeoutError()
            self.logger.error(f"[E40003]{exc.message} operationID:[{procedure.operationID}]", stack_info=True)
            code = exc.status_code
            body = {
                "code": "E40003",
                "message": exc.message,
            }
            self.exception_flg = True
        except exceptions.ConnectionError:
            exc = UrlNotFoundError(self.recent_request_uri)
            self.logger.error(f"[E40007]{exc.message} operationID:[{procedure.operationID}]", stack_info=True)
            code = exc.status_code
            body = {
                "code": "E40007",
                "message": exc.message,
            }
            self.exception_flg = True
        except exceptions.RequestException as error:
            exc = UnexpectedRequestError(str(error))
            self.logger.error(f"[E40008]{exc.message} operationID:[{procedure.operationID}]", stack_info=True)
            code = exc.status_code
            body = {
                "code": "E40008",
                "message": exc.message,
            }
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

    def _set_logger(self):
        """Set up GILogger.
        If GILogger cannot be initialized for any reason during startup,
        set it to output log content to standard output.
        """
        try:
            self.logger = Logger(**self.logger_args)
        except Exception as error:  # pylint: disable=W0703
            print(
                f"[E40009]{InitializeLogSubProcessError(str(error)).message}",
                file=sys.stderr,
            )
            self.tmp_log_handler = logging.StreamHandler(stream=sys.stdout)
            self.tmp_log_handler.setLevel(logging.DEBUG)
            self.tmp_logger_name = str(os.getpid()) + datetime.now().strftime("%Y%m%d%H%M%S%f")
            self.logger = logging.getLogger(self.tmp_logger_name)
            self.logger.setLevel(logging.DEBUG)
            self.logger.addHandler(self.tmp_log_handler)

    def _is_retry_response(self, status_code: int, body: Any) -> dict:
        """Determine if a retry is necessary.
           If the Response status_code matches the retry settings, it will be a target for retry
        Args:
            status_code (int): Response status code
            body (Any): Response message
        Returns:
            ret(bool): Retry determination
            interval: Interval setting for the applicable retry target
            max_count: Max count setting for the applicable retry target
        """
        ret = False
        interval = None
        max_count = None
        for retry_target in self.retry_targets:
            retry_err_code = retry_target.get("code")
            retry_code = retry_target.get("status_code")
            if status_code == retry_code and (retry_err_code and body.get("code") == retry_err_code):
                ret = True
                interval = retry_target.get("interval")
                max_count = retry_target.get("max_count")
                break
        return ret, interval, max_count

    def _retry_request(self, procedure: Procedure, max_count: int, interval: int, code, body):
        """Retry process when receiving a response other than 200

        Args:
            procedure (Procedure): Migration procedure
            interval: Interval setting for retry
            max_count: Max count setting for retry
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
            if code == HTTPStatus.OK or self.exception_flg is True:
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
    def _check_power_status(
        self, target_state: str, count: int, interval: int, get_info_obj: Any, procedure: Procedure,
    ) -> tuple[bool, None | dict, str]:
        """Check the expected power state transition

        Args:
            target_state (str): Expected power state
            count (int): Max count setting for polling
            interval (int): Interval setting for polling
            get_info_obj (Any): API object for retrieving device information
            procedure (Procedure): Migration procedure

        Returns:
            tuple[bool, bool str]: Whether the expected state was achieved, error flag, current power state
        """
        cnt, power_state, is_expected_power_state, error_resp = 0, "", False, None
        while cnt != count:
            response = get_info_obj.execute(procedure)
            # Exit if there is an abnormal termination in obtaining device information.
            if response["code"] != HTTPStatus.OK:
                error_resp = response.get("device_information")
                break
            # Exit if the power state becomes the expected state.
            power_state = response.get("device_information").get("powerState")
            if power_state == target_state:
                is_expected_power_state = True
                break
            cnt += 1
            time.sleep(interval)
        if cnt == count:
            self.logger.error(f"[E40029]{PowerStateNotChangeException(target_state, procedure.targetDeviceID,
                                                                      power_state).message}", stack_info=False)
        return is_expected_power_state, error_resp, power_state
    # fmt: on

    def _can_power_operate(self, get_info_obj: Any, procedure: Procedure) -> bool | dict:
        """Check if the device power operation is possible

        Args:
            get_info_obj (Any): API object to get device information
            procedure (Procedure): Migration procedure

        Returns:
            bool: Whether the power operation is enabled
            Returns the response body of the information retrieval if the response code is other than 200
        """

        dev_info_res = get_info_obj.execute(procedure)
        dev_info = dev_info_res.get("device_information")
        if dev_info_res["code"] == HTTPStatus.OK:
            return dev_info.get("type") != "CPU" and dev_info.get("powerCapability")
        return dev_info

    def _is_device_cpu(self, get_info_obj: Any, procedure: Procedure) -> bool | None:
        """Check if the device type is CPU

        Args:
            get_info_obj (Any): API object for obtaining device information
            procedure (Procedure): Migration procedure

        Returns:
            bool | None: Returns True if the device type is CPU, otherwise returns False.
            Returns None if the response code for obtaining device information is not 200.
        """
        get_information_responce = get_info_obj.execute(procedure)
        if get_information_responce["code"] == HTTPStatus.OK:
            return get_information_responce.get("device_information")["type"] == "CPU"
        return None

    def _set_procedure_time(self, started_at: str):
        """set procedure time

        Args:
            started_at (str): start time of procedure
        """
        self.detail.startedAt = started_at
        self.detail.endedAt = get_str_now()


class PowerOnAPI(HarwareManageAPIBase):
    """Class of PowerOnAPI"""

    def __init__(
        self,
        hardware_control_conf: dict,
        get_info_conf: dict,
        api_config: dict,
        logger_args: dict,
        server_connection_conf: dict,
    ) -> None:
        """Constructor

        Args:
            hardware_control_conf (dict): Hardware control function settings
            api_config (dict): Retry settings for each API, etc.
            logger_args (dict): GILogger argument
        """
        super().__init__(hardware_control_conf, get_info_conf, api_config, logger_args, server_connection_conf)
        self.is_os_boot_api = IsOSBootAPI(
            hardware_control_conf, get_info_conf, api_config, logger_args, server_connection_conf
        )
        self.get_info_api = GetDeviceInformationAPI(
            hardware_control_conf, get_info_conf, api_config, logger_args, server_connection_conf
        )

    def _requests(self, procedure: Procedure):
        """Send a request to the Power ON API.

        Args:
            procedure (Procedure): Procedure object
        Returns:
            requests.Response: Response
        """
        self.detail.uri = ApiUri.POWERON_API.format(self.host, self.port, self.uri, procedure.targetDeviceID)
        self.recent_request_uri = copy.deepcopy(self.detail.uri)
        self.detail.method = HTTPMethod.PUT
        self.detail.requestBody = {"action": RequestBodyAction.POWERON}
        self.logger.info(
            (
                f"Start request. url:[{self.detail.uri}], ",
                f"method:[{self.detail.method}]",
                f"request body:[{self.detail.requestBody}]",
            )
        )
        response = self._put(
            url=self.detail.uri,
            data=self.detail.requestBody,
            timeout_sec=self.timeout,
            headers=ApiHeaders,
        )
        self.logger.info(f"Request completed. status:[{response.status_code}], response[{response.text}]")
        return response

    def execute(self, procedure: Procedure) -> Details:
        """After executing the power ONAPI, check the OS startup by the OS startup confirmation API.

        Args:
            procedure (Procedure): Migration plan

        Returns:
            Details: Execution results of Power ONAPI and OS Startup Confirmation API
        """
        self.detail.startedAt = get_str_now()
        super().execute(procedure)
        if self.detail.status == Result.COMPLETED:
            is_os_boot_result: IsOsBoot = self.is_os_boot_api.execute(procedure)

            # If the OS boot confirmation ends with the target skip code, proceed to the next migration step.
            if (
                is_os_boot_result.statusCode in self.is_os_boot_api.skip_status_codes
                and is_os_boot_result.code in self.is_os_boot_api.skip_codes
            ):
                self.logger.info("Skip running OS startup confirmation API.", stack_info=True)
            else:
                status = is_os_boot_result.responseBody.get("status")
                if (
                    is_os_boot_result.statusCode != HTTPStatus.OK
                    or status is None
                    or status is False
                    or isinstance(status, bool) is False
                ):
                    self.detail.status = Result.FAILED
                self.detail.isOSBoot = asdict(is_os_boot_result, dict_factory=details_dict_factory)
        self.detail.endedAt = get_str_now()

        return self.detail, self.is_suspended


class IsOSBootAPI(HarwareManageAPIBase):
    """Class of IsOSBootAPI"""

    def __init__(
        self,
        hardware_control_conf: dict,
        get_info_conf: dict,
        api_config: dict,
        logger_args: dict,
        server_connection_conf: dict,
    ) -> None:
        """Constructor

        Args:
            hardware_control_conf (dict): Hardware control function settings
            api_config (dict): Retry settings for each API, etc.
            logger_args (dict): GILogger argument
        """
        super().__init__(hardware_control_conf, get_info_conf, api_config, logger_args, server_connection_conf)
        self.timeout = self.isosboot_conf.get("timeout")
        polling_conf = self.isosboot_conf.get("polling")
        self.polling_interval = polling_conf.get("interval")
        self.polling_count = polling_conf.get("count")
        self.skip_status_codes = [x.get("status_code") for x in polling_conf.get("skip")]
        self.skip_codes = [x.get("code") for x in polling_conf.get("skip")]
        self.is_os_boot_detail = IsOsBoot()
        self.is_os_boot_detail.method = HTTPMethod.GET
        request_conf = self.isosboot_conf.get("request")
        if request_conf is not None and request_conf.get("timeout") is not None:
            self.is_os_boot_detail.queryParameter = {"timeOut": request_conf.get("timeout")}

    def _requests(self, procedure: Procedure):
        """Request the OS startup confirmation API

        Args:
            procedure (Procedure): Procedure object
        Returns:
            requests.Response: Response
        """
        self.is_os_boot_detail.uri = ApiUri.ISOSBOOT_API.format(
            self.host, self.port, self.uri, procedure.targetDeviceID
        )
        self.recent_request_uri = copy.deepcopy(self.is_os_boot_detail.uri)
        self.logger.info(
            (
                f"Start request. url:[{self.is_os_boot_detail.uri}], ",
                f"method:[{self.is_os_boot_detail.method}]",
                f"queryParameter:[{self.is_os_boot_detail.queryParameter}]",
            )
        )
        response = self._get(
            url=self.is_os_boot_detail.uri,
            timeout_sec=self.timeout,
            params=(self.is_os_boot_detail.queryParameter if self.is_os_boot_detail.queryParameter != "" else None),
            headers=ApiHeaders,
        )
        self.logger.info(f"Request completed. status:[{response.status_code}], response[{response.text}]")
        return response

    def execute(self, procedure: Procedure) -> IsOsBoot:
        """Request to OS startup confirmation API

        Args:
            procedure (Procedure): Migration plan

        Returns:
            IsOsBoot: Details of OS startup confirmation API implementation results
        """

        self._set_logger()

        code, body, is_polling = self._decide_polling(procedure)

        # If polling fails up to the limit, output an error log.
        if is_polling:
            self.logger.error(f"[E40021]{OsBootFailureException().message}", stack_info=False)
        self.is_os_boot_detail.statusCode = code
        try:
            body = json.loads(body)
        except Exception:  # pylint: disable=W0703
            pass
        self.is_os_boot_detail.responseBody = body

        return self.is_os_boot_detail

    def _decide_polling(self, procedure: Procedure) -> any:
        """Decide request polling.

        Args:
            procedure (Procedure): Migration plan

        Returns:
            code: is_os_boot response status code
            body: is_os_boot response body
            is_polling: polling flag. execute max polling Yes(True) or No(False).

        """
        cnt: int = 0
        code: int = None
        self.is_os_boot_detail.code = ""
        is_polling = False
        while cnt != self.polling_count:
            code, body = self._requests_wrapper(procedure)
            status = body.get("status", None) if isinstance(body, dict) else None
            if (code == HTTPStatus.OK and status is True) or self.exception_flg is True:
                is_polling = False
                break

            if code == HTTPStatus.OK and status is False:
                is_polling = True
                cnt += 1
                self.logger.info(
                    f"""
                        OS not started. status:[{status}], response[{body}],
                        polling[count:{cnt}, limit:{self.polling_count}]
                    """
                )
                time.sleep(self.polling_interval)
            elif code in self.skip_status_codes and body.get("code") in self.skip_codes:
                self.is_os_boot_detail.code = body.get("code")
                is_polling = False
                self.logger.info(
                    f"""
                        The device is not a CPU. Skip running OS startup confirmation API.
                        device id:{procedure.targetDeviceID},status:[{status}],response[{body}]
                    """
                )
                break
            else:
                self.is_os_boot_detail.code = body.get("code", "")
                self.logger.error(f"[E40021]{OsBootFailureException().message}", stack_info=False)
                break

        return code, body, is_polling


class PowerOffAPI(HarwareManageAPIBase):
    """Class of PowerOffAPI"""

    def __init__(
        self,
        hardware_control_conf: dict,
        get_info_conf: dict,
        api_config: dict,
        logger_args: dict,
        server_connection_conf: dict,
    ) -> None:
        """Constructor

        Args:
            hardware_control_conf (dict): Hardware control function settings
            get_info_conf (dict): Get information function settings
            api_config (dict): Retry settings for each API, etc.
            logger_args (dict): GILogger argument
        """
        super().__init__(hardware_control_conf, get_info_conf, api_config, logger_args, server_connection_conf)
        self.get_info_api = GetDeviceInformationAPI(
            hardware_control_conf, get_info_conf, api_config, logger_args, server_connection_conf
        )
        polling_conf = get_info_conf.get("specs").get("poweroff").get("polling")

        self.interval = polling_conf.get("interval")
        self.count = polling_conf.get("count")

    def _requests(self, procedure: Procedure):
        """Request the Power OFF API.

        Args:
            procedure (Procedure): Procedure object
        Returns:
            requests.Response: Response
        """
        self.detail.uri = ApiUri.POWEROFF_API.format(self.host, self.port, self.uri, procedure.targetDeviceID)
        self.recent_request_uri = copy.deepcopy(self.detail.uri)
        self.detail.method = HTTPMethod.PUT
        self.detail.requestBody = {"action": RequestBodyAction.POWEROFF}
        self.logger.info(
            (
                f"Start request. url:[{self.detail.uri}], ",
                f"method:[{self.detail.method}]",
                f"request body:[{self.detail.requestBody}]",
            )
        )
        response = self._put(
            url=self.detail.uri,
            data=self.detail.requestBody,
            timeout_sec=self.timeout,
            headers=ApiHeaders,
        )
        self.logger.info(f"Request completed. status:[{response.status_code}], response[{response.text}]")
        return response

    def execute(self, procedure: Procedure) -> Details:
        """Request to poweroff

        Args:
            procedure (Procedure): Migration plan

        Returns:
            Details: Details of poweroff API implementation results
        """

        self._set_logger()
        self.detail.startedAt = get_str_now()
        super().execute(procedure)

        if self.detail.status == Result.COMPLETED:
            is_cpu = self._is_device_cpu(self.get_info_api, procedure)

            if is_cpu is True:
                is_expected, _, power_state = self._check_power_status(
                    "Off", self.count, self.interval, self.get_info_api, procedure
                )
                if is_expected is False:
                    self.logger.error(f"[E40023]{FailedGetDeviceInfoException().message}", stack_info=False)
                    self.detail.status = Result.FAILED
                self.detail.getInformation = {"responseBody": {"powerState": power_state}}
            elif is_cpu is None:  # pragma: no cover
                self._set_detail(HTTPStatus.INTERNAL_SERVER_ERROR, None, procedure)
                self.detail.status = Result.FAILED
        self.detail.endedAt = get_str_now()

        return self.detail, self.is_suspended


class GetDeviceInformationAPI(HarwareManageAPIBase):
    """Class of GetDeviceInformationAPI"""

    def __init__(
        self,
        hardware_control_conf: dict,
        get_info_conf: dict,
        api_config: dict,
        logger_args: dict,
        server_connection_conf: dict,
    ) -> None:
        """Constructor

        Args:
            get_info_conf (dict): Hardware control function settings
            api_config (dict): Retry settings for each API, etc.
            logger_args (dict): GILogger argument
        """
        super().__init__(hardware_control_conf, get_info_conf, api_config, logger_args, server_connection_conf)
        self.get_information_host = get_info_conf.get("host")
        self.get_information_port = get_info_conf.get("port")
        self.get_information_uri = get_info_conf.get("uri")
        specs_conf = get_info_conf.get("specs")
        self.get_information_timeout = specs_conf.get("timeout")

    def _requests(self, procedure: Procedure):
        """Make a request to the device information retrieval API.

        Args:
            procedure (Procedure): Procedure object
        Returns:
            requests.Response: Response
        """
        get_device_information_uri = ApiUri.GETDEVICEINFORMATION_API.format(
            self.get_information_host,
            self.get_information_port,
            self.get_information_uri,
            procedure.targetDeviceID,
        )
        self.recent_request_uri = copy.deepcopy(get_device_information_uri)
        get_device_information_method = HTTPMethod.GET
        self.logger.info(
            (
                f"Start request. url:[{get_device_information_uri}], ",
                f"method:[{get_device_information_method}]",
            )
        )
        response = self._get(
            url=get_device_information_uri,
            timeout_sec=self.get_information_timeout,
            headers=ApiHeaders,
        )
        self.logger.info(f"Request completed. status:[{response.status_code}], response[{response.text}]")
        return response

    def execute(self, procedure: Procedure) -> dict:
        """Request to get device information API

        Args:
            procedure (Procedure): Migration plan

        Returns:
            device_information: get device information API implementation results
        """

        self._set_logger()

        code, body = self._requests_wrapper(procedure)
        if isinstance(body, dict) and "type" in body and isinstance(body.get("type"), str):
            body["type"] = body.get("type").upper()
        if code == HTTPStatus.OK:
            try:
                validate(body, schema=device_information_scheme)
            except ValidationError as err:
                code = HTTPStatus.BAD_REQUEST
                error_message = err.message.split("\n")[-1]
                self.logger.error(f"[E40001]{error_message}", stack_info=False)

        if code != HTTPStatus.OK:
            self.logger.error(f"[E40023]{FailedGetDeviceInfoException().message}", stack_info=False)

        return {"code": code, "device_information": body}


class DisconnectAPI(HarwareManageAPIBase):
    """Class of DisconnectAPI"""

    def __init__(
        self,
        hardware_control_conf: dict,
        get_info_conf: dict,
        api_config: dict,
        logger_args: dict,
        server_connection_conf: dict,
    ) -> None:
        args = [hardware_control_conf, get_info_conf, api_config, logger_args, server_connection_conf]
        super().__init__(*args)
        self.poweroff_api = PowerOffAPI(*args)
        self.get_info_api = GetDeviceInformationAPI(*args)
        conf = get_info_conf.get("specs").get("disconnect").get("polling")
        self.count, self.interval = conf.get("count"), conf.get("interval")

    def _requests(self, procedure: Procedure):
        """Make a request to the cutting API.

        Args:
            procedure (Procedure): Procedure object
        Returns:
            requests.Response: Response
        """
        self.detail.uri = ApiUri.DISCONNECT_API.format(self.host, self.port, self.uri, procedure.targetCPUID)
        self.recent_request_uri = copy.deepcopy(self.detail.uri)
        self.detail.method = HTTPMethod.PUT
        self.detail.requestBody = {
            "action": RequestBodyAction.DISCONNECT,
            "deviceID": procedure.targetDeviceID,
        }
        self.logger.info(
            (
                f"Start request. url:[{self.detail.uri}], ",
                f"method:[{self.detail.method}]",
                f"request body:[{self.detail.requestBody}]",
            )
        )
        response = self._put(
            url=self.detail.uri,
            data=self.detail.requestBody,
            timeout_sec=self.timeout,
            headers=ApiHeaders,
        )
        self.logger.info(f"Request completed. status:[{response.status_code}], response[{response.text}]")
        return response

    def execute(self, procedure: Procedure) -> Details:
        """Make a request to the disconnect API.

        Args:
            procedure (Procedure): Procedure object

        Returns:
            Details: Execution result
        """
        self._set_logger()
        started_at = get_str_now()
        super().execute(procedure)

        can_power_operate = self._can_power_operate(self.get_info_api, procedure)

        if can_power_operate is True and self.detail.status == Result.COMPLETED:

            poweroff_detail, self.is_suspended = self.poweroff_api.execute(procedure)
            if poweroff_detail.status == Result.FAILED:
                return poweroff_detail, self.is_suspended

            is_expected, err_resp, power_state = self._check_power_status(
                "Off", self.count, self.interval, self.get_info_api, procedure
            )
            if is_expected is False or err_resp is not None:
                self._set_detail_on_preproc_error(procedure)
                self.detail.getInformation = {"responseBody": err_resp or {"powerState": power_state}}
        elif can_power_operate is False:
            # type is not CPU, no processing
            pass
        else:
            self._set_detail_on_preproc_error(procedure)
            self.detail.getInformation = {"responseBody": can_power_operate}
        self._set_procedure_time(started_at)

        return self.detail, self.is_suspended


class ConnectAPI(HarwareManageAPIBase):
    """Class of ConnectAPI"""

    def __init__(
        self,
        hardware_control_conf: dict,
        get_info_conf: dict,
        api_config: dict,
        logger_args: dict,
        server_connection_conf: dict,
    ) -> None:
        args = [hardware_control_conf, get_info_conf, api_config, logger_args, server_connection_conf]
        super().__init__(*args)
        self.get_info_api = GetDeviceInformationAPI(*args)
        self.poweron_api = PowerOnAPI(*args)
        conf = get_info_conf.get("specs").get("connect").get("polling")
        self.count, self.interval = conf.get("count"), conf.get("interval")

    def _requests(self, procedure: Procedure):
        """Make a request to the connection API

        Args:
            procedure (Procedure): Procedure object
        Returns:
            requests.Response: Response
        """

        self.detail.uri = ApiUri.CONNECT_API.format(
            self.host,
            self.port,
            self.uri,
            procedure.targetCPUID,
        )
        self.recent_request_uri = copy.deepcopy(self.detail.uri)
        self.detail.method = HTTPMethod.PUT
        self.detail.requestBody = {
            "action": RequestBodyAction.CONNECT,
            "deviceID": procedure.targetDeviceID,
        }
        self.logger.info(
            (
                f"Start request. url:[{self.detail.uri}], ",
                f"method:[{self.detail.method}]",
                f"request body:[{self.detail.requestBody}]",
            )
        )
        response = self._put(
            url=self.detail.uri,
            data=self.detail.requestBody,
            timeout_sec=self.timeout,
            headers=ApiHeaders,
        )
        self.logger.info(f"Request completed. status:[{response.status_code}], response[{response.text}]")
        return response

    def execute(self, procedure: Procedure) -> Details:
        """Request to connect API

        Args:
            procedure (Procedure): Migration plan

        Returns:
            Details: Details of boot API implementation results
        """

        self._set_logger()
        started_at = get_str_now()
        can_power_operate = self._can_power_operate(self.get_info_api, procedure)

        if can_power_operate is True:
            poweron_detail, self.is_suspended = self.poweron_api.execute(procedure)

            if poweron_detail.status == Result.FAILED:
                return poweron_detail, self.is_suspended

            is_expected, err_resp, power_state = self._check_power_status(
                "On", self.count, self.interval, self.get_info_api, procedure
            )
            if is_expected is False or err_resp is not None:
                self._set_detail_on_preproc_error(procedure)
                self.detail.getInformation = {"responseBody": err_resp or {"powerState": power_state}}
                self._set_procedure_time(started_at)
                return self.detail, self.is_suspended

            super().execute(procedure)
        elif can_power_operate is False:
            super().execute(procedure)
        else:
            self._set_detail_on_preproc_error(procedure)
            self.detail.getInformation = {"responseBody": can_power_operate}
        self._set_procedure_time(started_at)

        return self.detail, self.is_suspended
