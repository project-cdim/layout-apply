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
"""Test of the API Client Package"""

import json
import re
import types
from logging import ERROR
from time import sleep
from uuid import uuid4

import pytest
import requests
from pytest_httpserver import HTTPServer
from requests import exceptions
from werkzeug import Request, Response

from layoutapply.apiclient import (
    ConnectAPI,
    DisconnectAPI,
    GetDeviceInformationAPI,
    HarwareManageAPIBase,
    IsOSBootAPI,
    PowerOffAPI,
    PowerOnAPI,
)
from layoutapply.const import ApiExecuteResultIdx, ApiUri
from layoutapply.data import Details, IsOsBoot, Procedure
from layoutapply.setting import LayoutApplyConfig
from tests.layoutapply.conftest import DEVICE_INFO_URL, OPERATION_URL, OS_BOOT_URL, POWER_OPERATION_URL


class TestHarwareManageAPIBase:
    """Since the retry and timeout sections have already been implemented and
    standardized in the parent class (TestHardwareManageAPIBase),
    the test will only be conducted for the power-on API regarding this process.
    """

    def test_common_can_request(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        index = result.uri.rfind("devices")
        start_deviceid = result.uri[index + 8 : index + 12]

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert start_deviceid != "None"
        assert re.fullmatch(
            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
            result.uri,
        )
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "COMPLETED"
        assert result.statusCode == 200

    @pytest.mark.parametrize(
        "retry_status_code, retry_err_code, retry_targets",
        [
            # retry setting single
            (
                503,
                "ER005BAS001",
                [
                    {
                        "status_code": 503,
                        "code": "ER005BAS001",
                        "interval": 2,
                        "max_count": 4,
                    },
                ],
            ),
            # retry setting multi
            (
                429,
                "ER005BAS001",
                [
                    {
                        "status_code": 503,
                        "code": "ER005BAS001",
                        "interval": 2,
                        "max_count": 3,
                    },
                    {
                        "status_code": 429,
                        "code": "ER005BAS001",
                        "interval": 2,
                        "max_count": 4,
                    },
                ],
            ),
        ],
    )
    def test_common_retry_when_response_is_retry_set(
        self,
        httpserver: HTTPServer,
        retry_status_code,
        retry_err_code,
        retry_targets,
        init_db_instance,
    ):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": retry_targets,
                        "default": {
                            "interval": 2,
                            "max_count": 3,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")
        # initial run, plus 4 retries, envisions the fifth execution.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": retry_err_code, "message": "retry0"}, status=retry_status_code)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": retry_err_code, "message": "retry1"}, status=retry_status_code)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": retry_err_code, "message": "retry2"}, status=retry_status_code)
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )
        # Insert the retry target to confirm that retries are not counted again, even if the retry target is received again midway.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": retry_err_code, "message": "retry3"}, status=retry_status_code)
        # This message is expected to be returned as the final response.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": retry_err_code, "message": "retry4"}, status=500)

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": retry_err_code,
            "message": "retry4",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 500

    def test_common_stop_retry_when_received_normal_response_during_retry(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 5,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 5,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        # pattern where the first attempt fails and the second attempt succeeds.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "Duplicate requests CPU"}, status=503)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_response(Response("", status=200))

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "COMPLETED"
        assert result.statusCode == 200

        # pattern where the first attempt fails and the thrid attempt succeeds.
        # arrange
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "Duplicate requests CPU"}, status=503)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "Duplicate requests CPU"}, status=503)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_response(Response("", status=200))

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "COMPLETED"
        assert result.statusCode == 200

        # pattern where the first attempt fails and the last attempt succeeds.
        # arrange
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "Duplicate requests CPU"}, status=503)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "Duplicate requests CPU"}, status=503)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "Duplicate requests CPU"}, status=503)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_response(Response("", status=200))

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()
        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "COMPLETED"
        assert result.statusCode == 200

    def test_common_no_retry_when_max_retry_is_0(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 0,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")
        # initial run with 0 retries, executed only once.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "retry1"}, status=503)
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )
        # This message is not called.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "retry2", "message": "Something Error."}, status=500)

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "ER005BAS001",
            "message": "retry1",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 503

    def test_common_no_retry_when_failure_code_not_for_retry(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )
        # Initial execution with 0 retries, executed only once.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json(
            # code is not an error code subject to retry.
            {"code": 504, "message": "Duplicate Requests CPU"},
            status=503,
        )
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json(
            {"code": 504, "message": "Duplicate Requests CPU"},
            status=503,
        )
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "retry2", "message": "Something Error."}, status=500)

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()
        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": 504,
            "message": "Duplicate Requests CPU",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 503

    def test_common_retry_on_failure_when_status_code_not_for_retry(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )
        # Initial execution with 0 retries, executed only once.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json(
            # Execution with retry on error occurrence.
            {"code": 504, "message": "Duplicate requests CPU"},
            status=502,
        )
        # Execution with retry on error occurrence.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json(
            # Execution with retry on error occurrence.
            {"code": 504, "message": "Duplicate requests CPU"},
            status=502,
        )
        # message is not called.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "retry2", "message": "Something Error."}, status=500)

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()
        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": 504,
            "message": "Duplicate requests CPU",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 502

    def test_common_no_retry_when_timed_out(self, httpserver: HTTPServer, caplog, init_db_instance):
        timeout_sec = 1
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": timeout_sec,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        # Timeout, then cause a timeout after a 5-second sleep.
        def sleeping(request: Request):
            sleep(timeout_sec + 5)

        err_msg = {"message": "Exxxxx", "code": "ER005BAS001"}
        uri = config.hardware_control.get("uri")

        # Initial execution with 0 retries, executed only once.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_handler(sleeping)
        # message is not called.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json(err_msg, status=503)

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()
        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 504
        assert (
            json.loads(caplog.record_tuples[0][2]).get("message")
            == "[E40003]Timeout: Could not connect to server. operationID:[1]"
        )

    def test_common_retry_each_when_retry_on_status_and_failure(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 5,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 4,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")

        # A retry is initiated upon receiving an error response. During the process,
        # a retry-eligible response is received, but the retry continues according to the error retry settings.
        # arrange
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "dummy"}, status=500)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "retry0"}, status=500)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "retry1"}, status=503)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "retry2"}, status=503)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "retry3"}, status=500)
        # retry is not performed because the max_count in the error retry settings is set to 4,
        # whereas the target requires 5.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "retry3"}, status=500)

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()
        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == {"code": "ER005BAS001", "message": "retry3"}
        assert result.status == "FAILED"
        assert result.statusCode == 500

    def test_poweroff_can_request_to_poweroff_api(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOffAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        get_information_uri = config.get_information.get("uri")
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(Response(response='{"type": "memory", "powerState": "Off"}', status=200))

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "shutdown",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()
        index = result.uri.rfind("devices")
        start_deviceid = result.uri[index + 8 : index + 12]

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert start_deviceid != "None"
        assert re.fullmatch(
            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
            result.uri,
        )
        assert result.requestBody == {"action": "off"}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "COMPLETED"
        assert result.statusCode == 200

    def test_connect_can_request_to_connect_api(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = ConnectAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "memory", "powerState": "Off", "powerCapability": False},
            status=200,
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        hostCpuId = str(uuid4())
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "connect",
                "targetCPUID": hostCpuId,
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        cpu_index = result.uri.rfind("cpu")
        start_cpuid = result.uri[cpu_index + 4 : cpu_index + 8]

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert start_cpuid != "None"
        assert re.fullmatch(
            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
            result.uri,
        )
        assert result.requestBody == {"action": "connect", "deviceID": targetDeviceID}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "COMPLETED"
        assert result.statusCode == 200

    def test_connect_becomes_failed_when_failed_to_get_device_info(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = ConnectAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"code": "EF007BAS000", "message": "invalid request"},
            status=500,
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        hostCpuId = str(uuid4())
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "connect",
                "targetCPUID": hostCpuId,
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == paylod.operationID
        assert result.method == ""
        assert result.requestBody == ""
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.statusCode == ""
        assert result.status == "FAILED"
        assert result.getInformation == {"responseBody": {"code": "EF007BAS000", "message": "invalid request"}}

    def test_connect_can_request_when_powercapability_is_true(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = ConnectAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "memory", "powerState": "On", "powerCapability": True},
            status=200,
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {
                "code": "EF003BAS010",
                "message": "A request that is not supported was made for the specified device ID.",
            },
            status=400,
        )

        hostCpuId = str(uuid4())
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "connect",
                "targetCPUID": hostCpuId,
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        cpu_index = result.uri.rfind("cpu")
        start_cpuid = result.uri[cpu_index + 4 : cpu_index + 8]

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert start_cpuid != "None"
        assert re.fullmatch(
            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
            result.uri,
        )
        assert result.requestBody == {"action": "connect", "deviceID": targetDeviceID}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "COMPLETED"
        assert result.statusCode == 200

    def test_connect_result_is_failed_when_failed_power_on_request_with_powercapability_true(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = ConnectAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "memory", "powerState": "On", "powerCapability": True},
            status=200,
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response(
                '{"code":"CF001BAS000", "message":"Unexpected Error"}',
                status=500,
            )
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {
                "code": "EF003BAS010",
                "message": "A request that is not supported was made for the specified device ID.",
            },
            status=400,
        )

        hostCpuId = str(uuid4())
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "connect",
                "targetCPUID": hostCpuId,
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "CF001BAS000",
            "message": "Unexpected Error",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 500

    def test_disconnect_can_request_to_disconnect_api(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = DisconnectAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                    "poweroff": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 2,
                                    "max_count": 1,
                                },
                            ],
                            "default": {
                                "interval": 2,
                                "max_count": 1,
                            },
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "memory", "powerState": "Off", "powerCapability": False},
            status=200,
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        hostCpuId = str(uuid4())
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "disconnect",
                "targetCPUID": hostCpuId,
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        cpu_index = result.uri.rfind("cpu")
        start_cpuid = result.uri[cpu_index + 4 : cpu_index + 8]

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert start_cpuid != "None"
        assert re.fullmatch(
            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
            result.uri,
        )
        assert result.requestBody == {
            "action": "disconnect",
            "deviceID": targetDeviceID,
        }
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "COMPLETED"
        assert result.statusCode == 200

    def test_disconnect_can_request_when_powercapability_is_true(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = DisconnectAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                    "poweroff": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 2,
                                    "max_count": 1,
                                },
                            ],
                            "default": {
                                "interval": 2,
                                "max_count": 1,
                            },
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "memory", "powerState": "Off", "powerCapability": True},
            status=200,
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        hostCpuId = str(uuid4())
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "disconnect",
                "targetCPUID": hostCpuId,
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        cpu_index = result.uri.rfind("cpu")
        start_cpuid = result.uri[cpu_index + 4 : cpu_index + 8]

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert start_cpuid != "None"
        assert re.fullmatch(
            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
            result.uri,
        )
        assert result.requestBody == {
            "action": "disconnect",
            "deviceID": targetDeviceID,
        }
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "COMPLETED"
        assert result.statusCode == 200

    def test_disconnect_becomes_failed_when_failed_power_off_request_with_powercapability_true(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = DisconnectAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                    "poweroff": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 2,
                                    "max_count": 1,
                                },
                            ],
                            "default": {
                                "interval": 2,
                                "max_count": 1,
                            },
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "memory", "powerState": "Off", "powerCapability": True},
            status=200,
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response(
                '{"code":"CF001BAS000", "message":"Unexpected Error"}',
                status=500,
            )
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        hostCpuId = str(uuid4())
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "disconnect",
                "targetCPUID": hostCpuId,
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "off"}
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "CF001BAS000",
            "message": "Unexpected Error",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 500

    def test_disconnect_becomes_failed_when_failed_to_get_device_info(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = DisconnectAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                    "poweroff": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 2,
                                    "max_count": 1,
                                },
                            ],
                            "default": {
                                "interval": 2,
                                "max_count": 1,
                            },
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"code": "EF007BAS000", "message": "invalid request"},
            status=500,
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        hostCpuId = str(uuid4())
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "disconnect",
                "targetCPUID": hostCpuId,
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        cpu_index = result.uri.rfind("cpu")
        start_cpuid = result.uri[cpu_index + 4 : cpu_index + 8]

        # assert
        assert result.operationID == paylod.operationID
        assert result.method == "PUT"
        assert start_cpuid != "None"
        assert re.fullmatch(
            f"http:\/\/{host}:{port}\/{uri}\/{OPERATION_URL}",
            result.uri,
        )
        assert result.requestBody == {
            "action": "disconnect",
            "deviceID": targetDeviceID,
        }
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "FAILED"
        assert result.getInformation == {"responseBody": {"code": "EF007BAS000", "message": "invalid request"}}
        assert result.statusCode == 200

    def test_common_result_is_500_when_connect_failure_occurred(self, init_db_instance, mocker):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        mocker.patch.object(api_obj, "recent_request_uri", "http://10.000.111.111:8000/test")

        def _requests(self, payload):
            raise exceptions.ConnectionError()

        api_obj._requests = types.MethodType(_requests, api_obj)

        #        mocker.patch("requests.put")
        #        requests.put.side_effect = exceptions.ConnectionError()
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]

        # assert
        assert result.operationID == 1

        assert result.responseBody == {
            "code": "E40007",
            "message": "Connection error occurred. Please check if the URL is correct. http://10.000.111.111:8000/test",
            # "message": f"Connection error occurred. Please check if the URL is correct. http://localhost:48889/dagsw/api/v1/devices/{targetDeviceID}/power",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 500

    @pytest.mark.parametrize(
        "test_response",
        [
            ('{"type": "STORAGE", "powerState": "PoweringOn", "powerCapability":true}'),
            ('{"type": "MEMORY", "powerState": "PoweringOn", "powerCapability":true}'),
        ],
    )
    def test_connect_failure_when_power_check_polling_exceeded(
        self, httpserver: HTTPServer, capfd, caplog, test_response, init_db_instance
    ):
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = ConnectAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "dagsw/api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "isosboot": {
                        "polling": {
                            "count": 4,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        def polling_handler(request: Request):
            print("[Assertion]Called GET API.")
            return Response(response=test_response, status=200)

        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_handler(polling_handler)
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {
                "code": "EF003BAS010",
                "message": "A request that is not supported was made for the specified device ID.",
            },
            status=400,
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        hostCpuId = str(uuid4())
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "connect",
                "targetCPUID": hostCpuId,
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        _ = api_obj.execute(paylod)
        # API is executed the number of times specified in the polling settings plus one additional time, including execution for determining the device type when the power is initially turned off.
        out, _ = capfd.readouterr()
        assert out.count("[Assertion]Called GET API.") == 4
        # Error logs are being output.
        assert "[E40029]Power state did not change as expected after turning the power On." in caplog.text

    def test_connect_result_is_success_when_last_polling_attempt_succeeded(
        self, httpserver: HTTPServer, capfd, caplog, init_db_instance
    ):
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = ConnectAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "dagsw/api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "isosboot": {
                        "polling": {
                            "count": 3,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        def polling_handler(request: Request):
            print("[Assertion]Called GET API.")
            response = '{"type": "MEMORY", "powerState": "PoweringOn", "powerCapability":true}'
            return Response(
                response=response,
                status=200,
            )

        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")

        # Retrieve device information before polling.
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_handler(
            lambda res: Response(
                response='{"type": "MEMORY", "powerState": "Off", "powerCapability": true}',
                status=200,
            )
        )
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_response(Response("", status=200))
        httpserver.expect_ordered_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {
                "code": "EF003BAS010",
                "message": "A request that is not supported was made for the specified device ID.",
            },
            status=400,
        )
        # Polling started.
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_handler(polling_handler)
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_handler(polling_handler)
        # Succeeded on the third attempt.
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_json({"type": "MEMORY", "powerState": "On", "powerCapability": True}, status=200)
        httpserver.expect_ordered_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        hostCpuId = str(uuid4())
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "connect",
                "targetCPUID": hostCpuId,
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        result: Details = api_obj.execute(paylod)[ApiExecuteResultIdx.DETAIL]
        # mockup returning a 204 status is called twice, as the polling succeeds on the third attempt.
        out, _ = capfd.readouterr()
        assert out.count("[Assertion]Called GET API.") == 2
        # No error logs are being output.
        assert len(caplog.record_tuples) == 0
        assert result.status == "COMPLETED"

    def test_disconnect_becomes_failed_when_failed_to_disconnect(
        self, httpserver: HTTPServer, capfd, caplog, init_db_instance
    ):
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = DisconnectAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "dagsw/api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "poweroff": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 2,
                                    "max_count": 1,
                                },
                            ],
                            "default": {
                                "interval": 2,
                                "max_count": 1,
                            },
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(Response('{"type":"MEMORY","powerCapability": true}', status=200))
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response(
                '{"code": "EF004BAS002","message": "The FM failed to disconnect."}',
                status=500,
            )
        )

        hostCpuId = str(uuid4())
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "disconnect",
                "targetCPUID": hostCpuId,
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        result: Details = api_obj.execute(paylod)[ApiExecuteResultIdx.DETAIL]

        assert result.method == "PUT"
        assert result.operationID == paylod.operationID
        assert result.status == "FAILED"
        assert result.statusCode == 500
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "EF004BAS002",
            "message": "The FM failed to disconnect.",
        }
        assert result.requestBody == {
            "action": "disconnect",
            "deviceID": targetDeviceID,
        }

    @pytest.mark.parametrize(
        "test_response",
        [
            ('{"type": "STORAGE", "powerState": "PoweringOff", "powerCapability":true}'),
            ('{"type": "MEMORY", "powerState": "PoweringOff", "powerCapability":true}'),
        ],
    )
    def test_disconnect_failure_when_power_check_polling_exceeded(
        self, httpserver: HTTPServer, capfd, caplog, test_response, init_db_instance
    ):
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = DisconnectAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "dagsw/api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "poweroff": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 2,
                                    "max_count": 1,
                                },
                            ],
                            "default": {
                                "interval": 2,
                                "max_count": 1,
                            },
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        def polling_handler(request: Request):
            print("[Assertion]Called GET API.")
            return Response(response=test_response, status=200)

        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_handler(polling_handler)
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        hostCpuId = str(uuid4())
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "disconnect",
                "targetCPUID": hostCpuId,
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        _ = api_obj.execute(paylod)
        # API is executed the number of times specified in the polling settings plus one additional time, including execution for determining the device type when the power is initially turned off.
        out, _ = capfd.readouterr()
        assert out.count("[Assertion]Called GET API.") == 5
        # Error logs are being output.
        assert "[E40029]Power state did not change as expected after turning the power Off." in caplog.text

    def test_disconnect_result_is_success_when_last_polling_attempt_succeeded(
        self, httpserver: HTTPServer, capfd, caplog, init_db_instance
    ):
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = DisconnectAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "dagsw/api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "poweroff": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 2,
                                    "max_count": 1,
                                },
                            ],
                            "default": {
                                "interval": 2,
                                "max_count": 1,
                            },
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        def polling_handler(request: Request):
            print("[Assertion]Called GET API.")
            response = '{"type": "MEMORY", "powerState": "PoweringOff", "powerCapability":true}'
            return Response(
                response=response,
                status=200,
            )

        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")

        httpserver.expect_ordered_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        # Retrieve device information before polling.
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_handler(
            lambda res: Response(
                response='{"type": "MEMORY", "powerState": "On", "powerCapability": true}',
                status=200,
            )
        )
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_response(Response("", status=200))
        # get device type
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_json({"type": "MEMORY"}, status=200)
        # Polling started.
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_handler(polling_handler)
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_handler(polling_handler)
        # Succeeded on the third attempt.
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_json({"type": "MEMORY", "powerState": "Off", "powerCapability": True}, status=200)

        hostCpuId = str(uuid4())
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "disconnect",
                "targetCPUID": hostCpuId,
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        result: Details = api_obj.execute(paylod)[ApiExecuteResultIdx.DETAIL]
        # mockup returning a 204 status is called twice, as the polling succeeds on the third attempt.
        out, _ = capfd.readouterr()
        assert out.count("[Assertion]Called GET API.") == 2
        # No error logs are being output.
        assert len(caplog.record_tuples) == 0
        assert result.status == "COMPLETED"

    def test_common_no_failure_when_raw_code_returned_on_abnormal_exit(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_data(
            "NG",
            status=502,
        )
        # Retry on error occurrence.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_data(
            "NG",
            status=502,
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.responseBody == "NG"
        assert result.statusCode == 502

    def test_common_result_is_500_when_unexpected_failure_occurred(self, mocker, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        def _requests(self, payload):
            raise exceptions.TooManyRedirects()

        api_obj._requests = types.MethodType(_requests, api_obj)

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]

        # assert
        assert result.operationID == 1
        assert result.status == "FAILED"
        assert result.statusCode == 500

    def test_common_log_to_stdout_when_failed_to_initialize_log(
        self, mocker, capfd, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        # Logger some error occurred during initialization.
        mocker.patch("layoutapply.apiclient.Logger").side_effect = Exception("Log Error")

        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "COMPLETED"
        assert result.statusCode == 200

        out, err = capfd.readouterr()
        # Info-level log messages are being output to standard output.
        assert "Start request." in out
        assert "Request completed." in out

    @pytest.mark.parametrize(
        "retry_targets",
        [
            # no message
            [{"status_code": 503, "max_count": 2, "interval": 1}],
            # no status
            [{"code": "ER005BAS001", "max_count": 2, "interval": 1}],
            # no status, no message
            [{"max_count": 2, "interval": 1}],
        ],
    )
    def test_common_no_retry_when_invalid_retry_setting(self, httpserver: HTTPServer, retry_targets, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": retry_targets,
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        # First execution.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json(
            {"code": "ER005BAS001", "message": "Duplicate Requests CPU"},
            status=503,
        )
        # Execution with retry on error.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json(
            {"code": "ER005BAS001", "message": "Duplicate Requests CPU"},
            status=503,
        )
        # message is not called.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "retry2", "message": "Something Error."}, status=500)
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "ER005BAS001",
            "message": "Duplicate Requests CPU",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 503

    def test_poweron_becomes_failed_when_failed_os_check_after_execution(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        is_os_boot_status_code = 500
        is_os_boot_response = {"code": "Exxxxx", "message": "something error"}
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            is_os_boot_response, status=is_os_boot_status_code
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert_boot_uri = ApiUri.POWERON_API.format(
            config.hardware_control.get("host"),
            config.hardware_control.get("port"),
            config.hardware_control.get("uri"),
            targetDeviceID,
        )
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "FAILED"
        assert result.uri == assert_boot_uri
        assert result.statusCode == 200
        assert_is_os_boot_uri = ApiUri.ISOSBOOT_API.format(
            config.hardware_control.get("host"),
            config.hardware_control.get("port"),
            config.hardware_control.get("uri"),
            targetDeviceID,
        )
        assert result.isOSBoot == {
            "uri": assert_is_os_boot_uri,
            "queryParameter": {"timeOut": 2},
            "method": "GET",
            "statusCode": is_os_boot_status_code,
            "responseBody": is_os_boot_response,
        }

    def test_poweron_becomes_completed_when_success_os_check_after_execution(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        is_os_boot_status_code = 200
        is_os_boot_response = {
            "status": True,
            "IpAddress": "xxx.xxx.xxx.xxx",
        }
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )

        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            is_os_boot_response, status=is_os_boot_status_code
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert_boot_uri = ApiUri.POWERON_API.format(
            config.hardware_control.get("host"),
            config.hardware_control.get("port"),
            config.hardware_control.get("uri"),
            targetDeviceID,
        )
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "COMPLETED"
        assert result.uri == assert_boot_uri
        assert result.statusCode == 200
        assert_is_os_boot_uri = ApiUri.ISOSBOOT_API.format(
            config.hardware_control.get("host"),
            config.hardware_control.get("port"),
            config.hardware_control.get("uri"),
            targetDeviceID,
        )
        assert result.isOSBoot == {
            "uri": assert_is_os_boot_uri,
            "queryParameter": {"timeOut": 2},
            "method": "GET",
            "statusCode": is_os_boot_status_code,
            "responseBody": is_os_boot_response,
        }

    def test_poweron_os_boot_check_api_not_executed_when_failed(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        is_os_boot_status_code = 200
        is_os_boot_response = {"status": True, "IpAddress": "xxx.xxx.xxx.xxx"}
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 5,
                                "max_count": 5,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 2,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=500)
        )
        # Not being called.
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            is_os_boot_response, status=is_os_boot_status_code
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert_boot_uri = ApiUri.POWERON_API.format(
            config.hardware_control.get("host"),
            config.hardware_control.get("port"),
            config.hardware_control.get("uri"),
            targetDeviceID,
        )
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "FAILED"
        assert result.uri == assert_boot_uri
        assert result.statusCode == 500
        assert result.isOSBoot == ""

    def test_poweron_becomes_completed_when_skipped_status_code_on_os_check(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        is_os_boot_status_code = 400
        is_os_boot_response = {
            "code": "EF003BAS010",
            "message": "A non-existent CPU device was specified.",
        }
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            is_os_boot_response, status=is_os_boot_status_code
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert_boot_uri = ApiUri.POWERON_API.format(
            config.hardware_control.get("host"),
            config.hardware_control.get("port"),
            config.hardware_control.get("uri"),
            targetDeviceID,
        )
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "COMPLETED"
        assert result.uri == assert_boot_uri
        assert result.statusCode == 200
        assert result.isOSBoot == ""

    def test_isosboot_os_boot_check_api_settings_applied(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        # act
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = IsOSBootAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 100,
                            "interval": 60,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 200,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        # assert
        assert api_obj.host == config.hardware_control.get("host")
        assert api_obj.port == config.hardware_control.get("port")
        assert api_obj.uri == config.hardware_control.get("uri")
        assert api_obj.polling_interval == 60
        assert api_obj.polling_count == 100
        assert api_obj.skip_status_codes == [400]
        assert api_obj.is_os_boot_detail.queryParameter == {"timeOut": 2}

        # arrange
        # act
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = IsOSBootAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 100,
                            "interval": 60,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                                {"status_code": 404, "code": "test"},
                            ],
                        },
                        # No request parameters.
                        # "request": {"timeout": 2},
                        "timeout": 200,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        # assert
        assert 404 in api_obj.skip_status_codes
        assert 400 in api_obj.skip_status_codes
        assert len(api_obj.skip_status_codes) == 2
        assert api_obj.is_os_boot_detail.queryParameter == ""

        # arrange
        # act
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = IsOSBootAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 100,
                            "interval": 60,
                            "skip": [],
                        },
                        # No request parameters.
                        # "request": {"timeout": 2},
                        "timeout": 200,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        # assert
        assert api_obj.skip_status_codes == []

    def test_isosboot_not_added_to_query_params_when_no_request_timeout_setting(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = IsOSBootAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 100,
                            "interval": 60,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        # "request": {"timeout": 2},
                        "timeout": 200,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        def assert_query(request: Request):
            assert request.query_string == b""
            return Response('{"status": true, "IPAddress": "192.168.122.11"}', status=200)

        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_handler(
            assert_query
        )
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        _ = api_obj.execute(paylod)

    def test_isosboot_added_to_query_params_when_with_request_timeout_setting(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = IsOSBootAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 100,
                            "interval": 60,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 200,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        def assert_query(request: Request):
            assert request.query_string == b"timeOut=2"
            return Response('{"status":true,"IPAddress": "192.168.122.11"}', status=200)

        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_handler(
            assert_query
        )
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        _ = api_obj.execute(paylod)

    def test_isosboot_failure_when_polling_exceeded_limit(
        self, httpserver: HTTPServer, capfd, caplog, init_db_instance
    ):
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = IsOSBootAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 3,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 200,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        def polling_handler(request: Request):
            print("[Assertion]Called IS OS API.")
            return Response('{"status": false, "IPAddress": "192.168.122.11"}', status=200)

        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_handler(
            polling_handler
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        _ = api_obj.execute(paylod)
        # API is being executed the number of times specified in the polling settings.
        out, _ = capfd.readouterr()
        assert out.count("[Assertion]Called IS OS API.") == 3
        # Error logs are being output.
        assert "[E40021]Confirmed OS boot failure." in caplog.text

    def test_isosboot_result_is_success_when_last_polling_attempt_succeeded(
        self, httpserver: HTTPServer, capfd, caplog, init_db_instance
    ):
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = IsOSBootAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 3,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        def polling_handler(request: Request):
            print("[Assertion]Called IS OS API.")
            return Response('{"status":false,"IPAddress": "192.168.122.11"}', status=200)

        uri = config.hardware_control.get("uri")
        httpserver.expect_ordered_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_handler(
            polling_handler
        )
        httpserver.expect_ordered_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_handler(
            polling_handler
        )
        # Succeeded on the third attempt.
        httpserver.expect_ordered_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_response(
            Response('{"status":true,"IPAddress": "192.168.122.11"}', status=200)
        )
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        result: IsOsBoot = api_obj.execute(paylod)
        # mockup returning a 204 status is called twice, as the polling succeeds on the third attempt.
        out, _ = capfd.readouterr()
        assert out.count("[Assertion]Called IS OS API.") == 2
        # No error logs are being output.
        assert len(caplog.record_tuples) == 0
        assert result.statusCode == 200

    def test_isosboot_no_polling_when_skipped_status_code_returned(
        self, httpserver: HTTPServer, capfd, caplog, init_db_instance
    ):
        is_os_boot_status_code = 400
        is_os_boot_response = {
            "code": "EF003BAS010",
            "message": "A non-existent CPU device was specified.",
        }
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = IsOSBootAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 3,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 200,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        uri = config.hardware_control.get("uri")
        httpserver.expect_ordered_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            is_os_boot_response, status=is_os_boot_status_code
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

    def test_isosboot_failure_when_no_status_in_response_body(
        self, httpserver: HTTPServer, capfd, caplog, init_db_instance
    ):
        is_os_boot_status_code = 200
        is_os_boot_response = {
            "IPAddress": "xxxx.xxxx.xxxx.xxx",
        }
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = IsOSBootAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 3,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 200,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        uri = config.hardware_control.get("uri")
        httpserver.expect_ordered_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            is_os_boot_response, status=is_os_boot_status_code
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        result: IsOsBoot = api_obj.execute(paylod)

        assert len(caplog.record_tuples) == 1
        assert "status" not in result.responseBody
        assert "[E40021]Confirmed OS boot failure." in caplog.text
        assert result.statusCode == 200

    def test_isosboot_failure_when_response_code_is_500(self, httpserver: HTTPServer, capfd, caplog, init_db_instance):
        is_os_boot_status_code = 200
        is_os_boot_response = {
            "IPAddress": "xxxx.xxxx.xxxx.xxx",
        }
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = IsOSBootAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 3,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 200,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        uri = config.hardware_control.get("uri")
        httpserver.expect_ordered_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            is_os_boot_response, status=is_os_boot_status_code
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        result: IsOsBoot = api_obj.execute(paylod)

        assert len(caplog.record_tuples) == 1
        assert "status" not in result.responseBody
        assert "[E40021]Confirmed OS boot failure." in caplog.text
        assert result.statusCode == 200

    def test_isosboot_failure_when_status_not_bool_in_response(
        self, httpserver: HTTPServer, capfd, caplog, init_db_instance
    ):
        is_os_boot_status_code = 200
        is_os_boot_response = {
            "status": "true",
            "IPAddress": "xxxx.xxxx.xxxx.xxx",
        }
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = IsOSBootAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 3,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 200,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        uri = config.hardware_control.get("uri")
        httpserver.expect_ordered_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            is_os_boot_response, status=is_os_boot_status_code
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        result: IsOsBoot = api_obj.execute(paylod)

        assert len(caplog.record_tuples) == 1
        assert "status" in result.responseBody
        assert isinstance(result.responseBody.get("status"), bool) is False
        assert "[E40021]Confirmed OS boot failure." in caplog.text
        assert result.statusCode == 200

    def test_poweron_becomes_failed_when_non_skipped_failure_code_on_os_check(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        is_os_boot_status_code = 400
        is_os_boot_response = {
            "code": "EF003BAS010",
            "message": "A non-existent CPU device was specified.",
        }
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "test"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            is_os_boot_response, status=is_os_boot_status_code
        )

        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert_boot_uri = ApiUri.POWERON_API.format(
            config.hardware_control.get("host"),
            config.hardware_control.get("port"),
            config.hardware_control.get("uri"),
            targetDeviceID,
        )
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "FAILED"
        assert result.uri == assert_boot_uri

    def test_poweron_becomes_failed_when_no_status_in_response_on_os_check(
        self, httpserver: HTTPServer, init_db_instance
    ):
        # arrange
        is_os_boot_status_code = 200
        is_os_boot_response = {
            "IPAddress": "xxxx.xxxx.xxxx.xxx",
        }
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOnAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                    "timeout": 10,
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "test"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )
        uri = config.hardware_control.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            is_os_boot_response, status=is_os_boot_status_code
        )

        httpserver.expect_request(re.compile(f"\/{uri}\/{DEVICE_INFO_URL}"), method="GET").respond_with_json(
            {"type": "CPU"}, status=200
        )

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "boot",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert_boot_uri = ApiUri.POWERON_API.format(
            config.hardware_control.get("host"),
            config.hardware_control.get("port"),
            config.hardware_control.get("uri"),
            targetDeviceID,
        )
        assert result.operationID == 1
        assert result.method == "PUT"
        assert result.requestBody == {"action": "on"}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "FAILED"
        assert result.uri == assert_boot_uri

    def test_poweroff_can_receive_failure_result_when_abnormal_exit(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOffAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=500)
        )
        get_information_uri = config.get_information.get("uri")
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(Response(response='{"type": "CPU", "powerState": "Off"}', status=200))

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "shutdown",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        index = result.uri.rfind("devices")
        start_deviceid = result.uri[index + 8 : index + 12]

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert start_deviceid != "None"
        assert re.fullmatch(
            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
            result.uri,
        )
        assert result.requestBody == {"action": "off"}
        assert result.queryParameter == ""
        assert result.responseBody == ""
        assert result.status == "FAILED"
        assert result.statusCode == 500

    @pytest.mark.parametrize(
        "test_response",
        [
            ('{"type": "CPU", "powerState": "PoweringOff"}'),
            ('{"type": "CPU"}'),
        ],
    )
    def test_poweroff_failure_when_power_status_polling_exceeded(
        self, httpserver: HTTPServer, capfd, caplog, test_response, init_db_instance
    ):
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOffAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "dagsw/api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 15,
                                "interval": 6,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 15,
                                "interval": 6,
                            },
                        },
                        "timeout": 10,
                    },
                },
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        def polling_handler(request: Request):
            print("[Assertion]Called IS GET API.")
            return Response(response=test_response, status=200)

        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        get_information_uri = config.get_information.get("uri")
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_handler(polling_handler)

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "shutdown",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        _ = api_obj.execute(paylod)
        # API is executed the number of times specified in the polling settings plus one additional time, including execution for determining the device type when the power is initially turned off.
        out, _ = capfd.readouterr()
        assert out.count("[Assertion]Called IS GET API.") == 4
        # Error logs are being output.
        assert "[E40023]Failed to get device information." in caplog.text

    def test_poweroff_result_is_success_when_last_power_status_polling_succeeded(
        self, httpserver: HTTPServer, capfd, caplog, init_db_instance
    ):
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOffAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "dagsw/api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 15,
                                "interval": 6,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 15,
                                "interval": 6,
                            },
                        },
                        "timeout": 10,
                    },
                },
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        def polling_handler(request: Request):
            print("[Assertion]Called IS GET API.")
            return Response(response='{"type": "CPU", "powerState": "PoweringOff"}', status=200)

        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")
        # During the execution of the poweroff API.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"message": "success case"}, status=200)
        # Checking the power status.
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_handler(polling_handler)
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_handler(polling_handler)
        # Succeeded on the third attempt.
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(Response(response='{"type": "CPU", "powerState": "Off"}', status=200))

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "shutdown",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()
        # mock returning "PoweringOff" is called twice (since it succeeds on the third polling attempt).
        out, _ = capfd.readouterr()
        assert out.count("[Assertion]Called IS GET API.") == 2
        # No error logs are being output.
        assert len(caplog.record_tuples) == 0
        assert result.statusCode == 200

    def test_deviceinfo_failure_log_output_when_non_200_response_for_device_info(
        self, httpserver: HTTPServer, capfd, caplog, init_db_instance
    ):
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOffAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        get_information_uri = config.get_information.get("uri")
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(Response(response='{"type": "CPU", "powerState": "Off"}', status=500))

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "shutdown",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert re.fullmatch(
            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
            result.uri,
        )
        assert result.requestBody == {"action": "off"}
        assert result.queryParameter == ""
        assert result.responseBody is None
        assert result.status == "FAILED"
        assert result.statusCode == 500

    def test_deviceinfo_failure_when_failure_during_device_info_polling(
        self, httpserver: HTTPServer, capfd, caplog, init_db_instance
    ):
        # arrange
        caplog.set_level(ERROR)
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOffAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "dagsw/api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 3,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 15,
                                "interval": 6,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 15,
                                "interval": 6,
                            },
                        },
                        "timeout": 10,
                    },
                },
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        def polling_handler(request: Request):
            print("[Assertion]Called IS GET API.")
            return Response(response='{"type": "CPU", "powerState": "PoweringOff"}', status=200)

        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")
        # During the execution of the poweroff API.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_response(Response("", status=200))
        # Checking the power status.
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_handler(polling_handler)
        # Power state validation error.
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(Response(response='{"type": "CPU", "powerState": "dummy"}', status=200))
        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "shutdown",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()
        # mock returning "PoweringOff" is called twice
        # (since it encounters an error on the second polling attempt, it is effectively called once successfully).
        out, _ = capfd.readouterr()
        assert out.count("[Assertion]Called IS GET API.") == 1
        # poweroff API succeeded and returned a 200 status code,
        # but the process failed due to an error in concluding device information retrieval, resulting in a FAILED state.
        assert result.statusCode == 200
        assert result.status == "FAILED"

    def test_poweroff_poweroff_can_retry_by_settings(self, httpserver: HTTPServer, init_db_instance):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = PowerOffAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 4,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")
        # While executing the device information retrieval API in the power-off device type branching.
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "1st take"}, status=503)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"code": "ER005BAS001", "message": "retry 1st"}, status=503)
        httpserver.expect_ordered_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_json({"message": "success case"}, status=200)
        # Checking the power status.
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(Response(response='{"type": "CPU", "powerState": "Off"}', status=200))
        httpserver.expect_ordered_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(Response(response='{"type": "CPU", "powerState": "Off"}', status=200))

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "shutdown",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        index = result.uri.rfind("devices")
        start_deviceid = result.uri[index + 8 : index + 12]

        # assert
        assert result.operationID == 1
        assert result.method == "PUT"
        assert start_deviceid != "None"
        assert re.fullmatch(
            f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",
            result.uri,
        )
        assert result.requestBody == {"action": "off"}
        assert result.queryParameter == ""
        assert result.responseBody == {"message": "success case"}
        assert result.status == "COMPLETED"
        assert result.statusCode == 200
        assert result.getInformation.get("responseBody") == {"powerState": "Off"}

    @pytest.mark.parametrize(
        "test_response",
        [
            ('{"type": "cpu", "powerState": "Off"}'),
            ('{"type": "Cpu", "powerState": "Off"}'),
            ('{"type": "CPU", "powerState": "Off"}'),
        ],
    )
    def test_deviceinfo_success_when_device_info_case_mixed(
        self, httpserver: HTTPServer, test_response, init_db_instance
    ):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = GetDeviceInformationAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        get_information_uri = config.get_information.get("uri")
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(Response(response=test_response, status=200))

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "shutdown",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        result = api_obj.execute(paylod)

        # assert
        assert result["code"] == 200

    @pytest.mark.parametrize(
        "test_response",
        [
            ('{"type": "Accelerator", "powerState": "Off"}'),
            ('{"type": "DSP", "powerState": "Off"}'),
            ('{"type": "FPGA", "powerState": "Off"}'),
            ('{"type": "GPU", "powerState": "Off"}'),
            ('{"type": "UnknownProcessor", "powerState": "Off"}'),
            ('{"type": "memory", "powerState": "Off"}'),
            ('{"type": "storage", "powerState": "Off"}'),
            ('{"type": "networkInterface", "powerState": "Off"}'),
            ('{"type": "graphicController", "powerState": "Off"}'),
            ('{"type": "virtualMedia", "powerState": "Off"}'),
            ('{"type": "switch", "powerState": "Off"}'),
        ],
    )
    def test_deviceinfo_success_when_previous_device_info_value(
        self, httpserver: HTTPServer, test_response, init_db_instance
    ):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = GetDeviceInformationAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        get_information_uri = config.get_information.get("uri")
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(Response(response=test_response, status=200))

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "shutdown",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )
        # act
        result = api_obj.execute(paylod)

        # assert
        assert result["code"] == 200

    @pytest.mark.parametrize(
        "test_response",
        [
            ("test"),
            ('{"powerState": "Off"}'),
            ('{"type": "", "powerState": "Off"}'),
            ('{"type": "error", "powerState": "Off"}'),
        ],
    )
    def test_deviceinfo_failure_when_invalid_device_info_value(
        self, httpserver: HTTPServer, test_response, init_db_instance
    ):
        # arrange
        config = LayoutApplyConfig()
        api_obj: HarwareManageAPIBase = GetDeviceInformationAPI(
            **{
                "hardware_control_conf": config.hardware_control,
                "get_info_conf": config.get_information,
                "api_config": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 2,
                                "max_count": 1,
                            },
                        ],
                        "default": {
                            "interval": 2,
                            "max_count": 1,
                        },
                    },
                },
                "logger_args": config.logger_args,
                "server_connection_conf": config.server_connection,
            }
        )

        get_information_uri = config.get_information.get("uri")
        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(Response(response=test_response, status=200))

        targetDeviceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "shutdown",
                "targetDeviceID": targetDeviceID,
                "dependencies": [],
            }
        )

        # act
        result = api_obj.execute(paylod)

        # assert
        assert result["code"] == 400
