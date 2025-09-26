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
"""Custom error package"""

from http import HTTPStatus

import psycopg2
from fastapi.exceptions import RequestValidationError
from jsonschema import ValidationError
from requests import Response

from layoutapply.const import ExitCode


class CustomBaseException(Exception):
    """Base Exception class"""

    @property
    def exit_code(self) -> int:
        """Retrieve ExitCode"""

    @property
    def response_msg(self) -> int:
        """Return a response message"""


class NotAllowedWithError:
    """NotAllowedWith Error Class
    errorcode: E40001 error"""

    def __init__(self):
        """constructor"""
        self.message = (
            "Not allowed with argument"
            " --fields, --status, --started-at-since, --started-at-until, --ended-at-since, --ended-at-until,"
            " --sort-by, --order-by, --limit, --offset."
        )

    @property
    def exit_code(self) -> int:
        """Retrieve ExitCode"""
        return ExitCode.VALIDATION_ERR


class RequestError:
    """Request Error Class
    errorcode: E40001 or E50001 error"""

    def __init__(self, exc: RequestValidationError):
        """constructor

        Args:
            exc (RequestValidationError): Request validation error occurred.
        """
        self.message = exc.errors()

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.BAD_REQUEST.value


class JsonSchemaError(CustomBaseException):
    """Jsonschema error class
    errorcode: E40001 or E50001 error"""

    def __init__(self, exc: ValidationError):
        """constructor

        Args:
            message (str): Location of error occurrence
        """
        self.message = f"Unexpected strings {exc.message}"

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.BAD_REQUEST.value


class OutPathPointError(CustomBaseException):
    """OutPathPoint error class
    errorcode: E40001 error"""

    def __init__(self):
        """constructor"""
        self.message = "Out path points to a directory."

    @property
    def exit_code(self) -> int:
        """Retrieve for CLI ExitCode"""
        return ExitCode.VALIDATION_ERR


class SettingFileLoadException(CustomBaseException):
    """Occurs when a validation check fails during the loading of a configuration file
    errorcode: E40002 or E50002 error"""

    def __init__(self, message, filename):
        super().__init__(message)
        self.message = f"Failed to load {filename}.\n{message}"

    @property
    def exit_code(self) -> int:
        """Retrieve for CLI ExitCode"""
        return ExitCode.CONFIG_ERR

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.INTERNAL_SERVER_ERROR.value


class ConnectTimeoutError(CustomBaseException):
    """ConnectTimeout error class
    errorcode: E40003 or E50003 error"""

    def __init__(self):
        """constructor"""
        super().__init__()
        self.message = "Timeout: Could not connect to server."

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.GATEWAY_TIMEOUT.value


class FailedRequestError(CustomBaseException):
    """errorcode: E40004 or E50004 error"""

    def __init__(self, code, body):
        """constructor

        Args:
            code (str): API status code
            body (str): response body
        """
        super().__init__(code, body)
        self.message = f"Failed to request: status:[{code}], response[{body}]"


class FailedExecuteLayoutApplyError(CustomBaseException):
    """errorcode: E40005 error"""

    def __init__(self):
        """constructor"""
        super().__init__()
        self.message = "Failed to execute LayoutApply."


class FailedOutputError(CustomBaseException):
    """errorcode: E40006 error"""

    def __init__(self):
        """constructor"""
        super().__init__()
        self.message = "Failed to output file."

    @property
    def exit_code(self) -> int:
        """Retrieve for CLI ExitCode"""
        return ExitCode.OUTPUT_FILE_ERR


class UrlNotFoundError(CustomBaseException):
    """errorcode: E40007 or E50006 error"""

    def __init__(self, message):
        """constructor

        Args:
            message (str): Location of error occurrence
        """
        super().__init__(message)
        self.message = f"Connection error occurred. Please check if the URL is correct. {message}"

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.INTERNAL_SERVER_ERROR.value


class UnexpectedRequestError(CustomBaseException):
    """errorcode: E40008 or E50007 error"""

    def __init__(self, err):
        """constructor

        Args:
            message (str): Location of error occurrence
        """
        super().__init__(err)
        self.message = f"Unexpected requests error occurred.{err}"

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.INTERNAL_SERVER_ERROR.value


class InitializeLogSubProcessError(CustomBaseException):
    """errorcode: E40009 error"""

    def __init__(self, err):
        """constructor"""
        super().__init__(err)
        self.message = f"Failed to initialize log in sub process. Output log to standard output.{err}"


class MultipleInstanceError(CustomBaseException):
    """errorcode: E40010 error"""

    def __init__(self):
        """constructor"""
        super().__init__()
        self.message = "Already running. Cannot start multiple instances."

    @property
    def exit_code(self) -> int:
        """Retrieve for CLI ExitCode"""
        return ExitCode.MULTIPLE_RUN_ERR

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.CONFLICT.value


class OperationalError(CustomBaseException):
    """Operational error class
    errorcode: E40018 error"""

    def __init__(self, exc: psycopg2.OperationalError):
        """constructor

        Args:
            message (str): Location of error occurrence
        """
        super().__init__(exc)
        self.message = f"Could not connect to ApplyStatusDB. {exc}"

    @property
    def exit_code(self) -> int:
        """Retrieve for CLI ExitCode"""
        return ExitCode.DB_CONNECT_ERR

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.INTERNAL_SERVER_ERROR.value


class ProgrammingError(CustomBaseException):
    """Programming error class
    errorcode: E40019 error"""

    def __init__(self, exc: psycopg2.ProgrammingError):
        """constructor

        Args:
            message (str): Location of error occurrence
        """
        super().__init__(exc)
        self.message = (
            "Query failed.:"
            + str(exc.pgcode)
            + " Check PostgreSQL's error code table [https://pgsql-jp.github.io/current/html/errcodes-appendix.html]"
        )

    @property
    def exit_code(self) -> int:
        """Retrieve for CLI ExitCode"""
        return ExitCode.QUERY_ERR

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.INTERNAL_SERVER_ERROR.value


class IdNotFoundException(CustomBaseException):
    """Occurs when information for the specified ID does not exist
    errorcode: E40020 or E50010 error"""

    def __init__(self, applyid):
        super().__init__(applyid)
        self.message = f"Specified {applyid} is not found."

    @property
    def exit_code(self) -> int:
        """Retrieve for CLI ExitCode"""
        return ExitCode.ID_NOT_FOUND_ERR

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.NOT_FOUND.value


class OsBootFailureException(CustomBaseException):
    """errorcode: E40021 error"""

    def __init__(self):
        super().__init__()
        self.message = "Confirmed OS boot failure."


class AlreadyExecuteException(CustomBaseException):
    """errorcode: E40022 error"""

    def __init__(self):
        super().__init__()
        self.message = "This layoutapply has already executed."

    @property
    def exit_code(self) -> int:
        """Retrieve for CLI ExitCode"""
        return ExitCode.MULTIPLE_RUN_ERR

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.CONFLICT.value


class FailedGetDeviceInfoException(CustomBaseException):
    """errorcode: E40023 error"""

    def __init__(self):
        super().__init__()
        self.message = "Failed to get device information."


class BeingRunningException(CustomBaseException):
    """errorcode: E40024 error"""

    def __init__(self):
        super().__init__()
        self.message = "Apply ID cannot be deleted because it is currently being running. Try later again."

    @property
    def exit_code(self) -> int:
        """Retrieve for CLI ExitCode"""
        return ExitCode.DELETE_CONFLICT_ERR

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.CONFLICT.value


class SuspendProcessException(CustomBaseException):
    """errorcode: E40025 error"""

    def __init__(self):
        super().__init__()
        self.message = "A serious error has occurred. It suspends processing."


class FailedStartSubprocessException(CustomBaseException):
    """errorcode: E40026 error"""

    def __init__(self, err):
        super().__init__(err)
        self.message = f"Failed to start subprocess. {err}"

    @property
    def exit_code(self) -> int:
        """Retrieve for CLI ExitCode"""
        return ExitCode.SUBPROCESS_RUN_ERR

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.INTERNAL_SERVER_ERROR.value


class SuspendedDataExistException(CustomBaseException):
    """Occurs when an error occurs while loading the secret file
    errorcode: E40027 error"""

    def __init__(self, applyid):
        super().__init__(applyid)
        self.message = f"Suspended data exist. Please resume layoutapply. applyID: {applyid}"

    @property
    def exit_code(self) -> int:
        """Retrieve for CLI ExitCode"""
        return ExitCode.MULTIPLE_RUN_ERR

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.CONFLICT.value


class SubprocessNotFoundException(CustomBaseException):
    """errorcode: E40028 error"""

    def __init__(self, item):
        super().__init__(item)
        self.message = (
            "Since the process with the specified ID does not exist, change the "
            + item
            + " from IN_PROGRESS to FAILED."
        )

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.CONFLICT.value


class PowerStateNotChangeException(CustomBaseException):
    """errorcode: E40029 error"""

    def __init__(self, target_state, target_device_id, power_state):
        super().__init__(target_state, target_device_id, power_state)
        self.message = (
            f"Power state did not change as expected after turning the power {target_state}."
            + f"deviceID: {target_device_id}, current: {power_state}, expect: {target_state}"
        )


class SecretInfoGetException(CustomBaseException):
    """Occurs when an error occurs while loading the secret file
    errorcode: E40030 or E50008 error"""

    def __init__(self, message):
        super().__init__(message)
        self.message = f"Failed to retrieve secret store\n{message}"

    @property
    def exit_code(self) -> int:
        """Retrieve for CLI ExitCode"""
        return ExitCode.SECRET_REQUEST_ERROR

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.INTERNAL_SERVER_ERROR.value


class LoggerLoadException(CustomBaseException):
    """Occurs when reading logger settings fails
    errorcode: E40031 or E50009 error"""

    def __init__(self):
        self.message = "Internal server error. Failed in log initialization."

    @property
    def exit_code(self) -> int:
        """Retrieve for CLI ExitCode"""
        return ExitCode.INTERNAL_ERR

    @property
    def status_code(self) -> int:
        """Retrieve for API StatusCode"""
        return HTTPStatus.INTERNAL_SERVER_ERROR.value


class OSBootMaxRetriesExceededException(CustomBaseException):
    """errorcode: E40032 error"""

    def __init__(self, target_device_id):
        super().__init__(target_device_id)
        self.message = f"The operating system failed to boot after turning the power on. deviceID: {target_device_id}"


class ExtendedProcedurePollingExceededException(CustomBaseException):
    """errorcode: E40033 error"""

    def __init__(self, target_request_instance_id, current_status):
        super().__init__(target_request_instance_id)
        self.message = (
            "The extended process could not be completed. "
            f"requestInstanceID: {target_request_instance_id}, current: {current_status}"
        )


class FailedGetServiceInfoException(CustomBaseException):
    """errorcode: E40034 error"""

    def __init__(self):
        super().__init__()
        self.message = "Failed to get extended process information."


class MessagePublishException(CustomBaseException):
    """Message publish error class"""

    def __init__(self, exc: Exception = None, response: Response = None):
        """constructor

        Args:
            exc (Exception, optional): Exception that occurred. Defaults to None.
            response (Response, optional): Response object from the request. Defaults to None.
        """
        if response is not None:
            status_code = response.status_code
            text = response.content
        elif exc is not None:
            status_code = None
            if hasattr(exc, "response") and exc.response is not None:
                status_code = exc.response.status_code
            text = str(exc)
        else:  # pragma: no cover
            status_code = HTTPStatus.INTERNAL_SERVER_ERROR.value
            text = "Unknown error occurred"
        self.message = f"Failed to publish message: status:[{status_code}], response[{text}]"
