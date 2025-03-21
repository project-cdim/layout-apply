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
"""Enum package for fixed values"""

from enum import IntEnum, StrEnum, _simple_enum

# API Call Header
ApiHeaders = {"accept": "application/json"}


@_simple_enum(StrEnum)
class TimeFormat:
    """Constant definition of date format"""

    UTC_DATETIME_STR_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
    TZ_DATETIME_STR_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


@_simple_enum(IntEnum)
class ExitCode:
    """Definition of return value constant"""

    def __new__(cls, value):
        obj = int.__new__(cls, value)
        obj._value_ = value
        return obj

    # Normal termination
    NORMAL = 0
    # Validation error
    VALIDATION_ERR = 1
    # Configuration file loading error
    CONFIG_ERR = 2
    # LayoutApply error
    LAYOUTAPPLY_ERR = 3
    # Exclusive control fails
    MULTIPLE_RUN_ERR = 4
    # Failed to start subprocess
    SUBPROCESS_RUN_ERR = 5
    # Failed to start the socket communication server for handling cancellations
    #    SOCKET_SERVER_ERR = 6
    # Failed to send the cancellation request
    SOCKET_CLIENT_ERR = 7
    # apply request is not being triggered upon cancellation
    NOT_RUNNING_ERR = 8
    # A timeout occurred when sending the cancellation request
    SOCKET_TIMEOUT_ERR = 9
    # Failed to connect to the database
    DB_CONNECT_ERR = 10
    # Failed to execute query
    QUERY_ERR = 11
    # specified ID does not exist
    ID_NOT_FOUND_ERR = 12
    # File output failed
    OUTPUT_FILE_ERR = 13
    # Deletion failed due to being in progress (status "IN_PROGRESS" or "CANCELING").
    DELETE_CONFLICT_ERR = 14
    # Failed to retrieve secret information
    SECRET_REQUEST_ERROR = 15
    # Internal Server Error
    INTERNAL_ERR = 16


@_simple_enum(IntEnum)
class IdParameter:
    """Definition of return value constants"""

    def __new__(cls, value):
        obj = int.__new__(cls, value)
        obj._value_ = value
        return obj

    LENGTH = 10


@_simple_enum(StrEnum)
class Operation:
    """Constants for request types"""

    def __new__(cls, value):
        obj = str.__new__(cls, value)
        obj._value_ = value
        return obj

    POWEROFF = "shutdown"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    POWERON = "boot"


@_simple_enum(StrEnum)
class RequestBodyAction:
    """Constants for request bodies"""

    def __new__(cls, value):
        obj = str.__new__(cls, value)
        obj._value_ = value
        return obj

    POWEROFF = "off"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    POWERON = "on"
    RESET = "reset"


@_simple_enum(StrEnum)
class ApiUri:
    """Constants for URI of API calls by request type"""

    def __new__(cls, value):
        obj = str.__new__(cls, value)
        obj._value_ = value
        return obj

    # URI for LayoutApplyAPI call
    POWEROFF_API = "http://{}:{}/{}/devices/{}/power"
    CONNECT_API = "http://{}:{}/{}/cpu/{}/aggregations"
    DISCONNECT_API = "http://{}:{}/{}/cpu/{}/aggregations"
    POWERON_API = "http://{}:{}/{}/devices/{}/power"
    ISOSBOOT_API = "http://{}:{}/{}/cpu/{}/is-os-ready"
    # URI for GetDeviceInformationAPI call
    GETDEVICEINFORMATION_API = "http://{}:{}/{}/devices/{}/specs"
    # URI for MigrationProceduresAPI call
    MIGRATION_PROCEDURES_API = "http://{}:{}/{}/migration-procedures"
    # URI for ConfigurationManagerAPI call
    GET_ALLNODES_INFO_API = "http://{}:{}/{}/nodes"
    # URI for GetAvailableResourcesAPI call
    GET_AVAILABLE_RESOURCES_API = "http://{}:{}/{}/resources/available"


@_simple_enum(StrEnum)
class Result:
    """Character constants representing API execution results"""

    def __new__(cls, value):
        obj = str.__new__(cls, value)
        obj._value_ = value
        return obj

    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIP = "SKIPPED"
    CANCELING = "CANCELING"
    CANCELED = "CANCELED"
    SUSPENDED = "SUSPENDED"


@_simple_enum(IntEnum)
class ApiExecuteResultIdx:
    """Index definition of the return values of the API request method"""

    def __new__(cls, value):
        obj = int.__new__(cls, value)
        obj._value_ = value
        return obj

    # Return index
    DETAIL = 0
    SUSPEND_FLG = 1


@_simple_enum(StrEnum)
class Action:
    """String constant representing the type of action"""

    def __new__(cls, value):
        obj = str.__new__(cls, value)
        obj._value_ = value
        return obj

    REQUEST = "request"
    CANCEL = "cancel"
    GET = "get"
    DELETE = "delete"
    RESUME = "resume"
    ROLLBACK_RESUME = "rollback_resume"


@_simple_enum(StrEnum)
class RequestParameter:
    """Secret Info Request parameter value"""

    URL = "http://127.0.0.1:3500/v1.0/secrets/cdim-layout-apply/cdim-layout-apply"
    STORE_NAME = "cdim-layout-apply"


@_simple_enum(StrEnum)
class DbConfigName:
    """The value is used as the key when its retrieved from the secret store"""

    DBNAME = "dbname"
    PASS = "password"
    USER = "user"
    HOST = "host"
    PORT = "port"


@_simple_enum(StrEnum)
class RequestType:
    """The value is the request type"""

    CLI = "cli"
    API = "api"
