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


import io
import json
import logging
import logging.config
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

from layoutapply.common.logger import Logger
from layoutapply.const import ApiExecuteResultIdx
from layoutapply.data import Details, Procedure
from layoutapply.service_apiclient import ExtendedProcedureAPIBase, GetServiceInformationAPI, StartAPI, StopAPI
from layoutapply.setting import LayoutApplyConfig, LayoutApplyLogConfig
from tests.layoutapply.conftest import (
    EXTENDED_PROCEDURE_ID,
    WORKFLOW_MANAGER_HOST,
    WORKFLOW_MANAGER_PORT,
    WORKFLOW_MANAGER_URI,
)


class TestServiceAPIBase:
    @pytest.fixture(autouse=True)
    def setup_config(self, httpserver):
        config = LayoutApplyConfig()
        config.workflow_manager["host"] = httpserver.host
        config.workflow_manager["port"] = httpserver.port
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 1
        config.workflow_manager["extended-procedure"]["polling"]["interval"] = 1
        config.workflow_manager["extended-procedure"]["retry"]["default"]["max_count"] = 1
        config.workflow_manager["extended-procedure"]["retry"]["default"]["interval"] = 1

        self.config = config

    def test_service_can_request_to_start_api(self, httpserver, capsys, init_db_instance):
        # arrange
        config = self.config

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "start",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "COMPLETED",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {"extendedProcedureID": f"{EXTENDED_PROCEDURE_ID}"}
        assert result.status == "COMPLETED"
        assert result.statusCode == 202

    def test_service_request_to_start_api_when_failed_to_load_the_logs(
        self, mocker, httpserver, capfd, init_db_instance
    ):
        # arrange
        config = self.config

        mocker.patch.object(
            Logger, "__init__", side_effect=Exception("Internal server error. Failed in log initialization")
        )
        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        _, err = capfd.readouterr()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 500
        assert (
            "[E40009]Failed to initialize log in sub process. Output log to standard output.Internal server error. Failed in log initialization"
            in err
        )

    def test_service_request_to_start_api_when_retry_success(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["retry"]["default"]["max_count"] = 3

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        call_count = 0

        def custom_handler(request):
            nonlocal call_count
            call_count += 1

            if call_count == 3:
                response_data = {
                    "code": "150001",
                    "message": "Error occured when calling another REST API internally",
                    "detail": {
                        "message": "400 Client Error: Bad Request for url: http://localhost:8800/layout-design/",
                        "method": "POST",
                        "url": "http://localhost:8800/layout-design/",
                        "responseBody": {
                            "code": "E20001",
                            "message": "Invalid value is specified for query parameters. query name: fields",
                        },
                    },
                }
                return Response(
                    response=json.dumps(response_data), status=500, headers={"Content-Type": "application/json"}
                )
            else:
                response_data = {"extendedProcedureID": EXTENDED_PROCEDURE_ID}
                return Response(
                    response=json.dumps(response_data), status=202, headers={"Content-Type": "application/json"}
                )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_handler(custom_handler)

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "start",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "COMPLETED",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "COMPLETED"
        assert result.statusCode == 202
        assert result.queryParameter == ""
        assert result.responseBody == {"extendedProcedureID": f"{EXTENDED_PROCEDURE_ID}"}

    def test_service_request_to_start_api_when_recieve_500_error(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {
                "code": "150001",
                "message": "Error occured when calling another REST API internally",
                "detail": {
                    "message": "400 Client Error: Bad Request for url: http://localhost:8800/layout-design/",
                    "method": "POST",
                    "url": "http://localhost:8800/layout-design/",
                    "responseBody": {
                        "code": "E20001",
                        "message": "Invalid value is specified for query parameters. query name: fields",
                    },
                },
            },
            status=500,
        )
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {
                "code": "150001",
                "message": "Error occured when calling another REST API internally",
                "detail": {
                    "message": "400 Client Error: Bad Request for url: http://localhost:8800/layout-design/",
                    "method": "POST",
                    "url": "http://localhost:8800/layout-design/",
                    "responseBody": {
                        "code": "E20001",
                        "message": "Invalid value is specified for query parameters. query name: fields",
                    },
                },
            },
            status=500,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 500
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "150001",
            "message": "Error occured when calling another REST API internally",
            "detail": {
                "message": "400 Client Error: Bad Request for url: http://localhost:8800/layout-design/",
                "method": "POST",
                "url": "http://localhost:8800/layout-design/",
                "responseBody": {
                    "code": "E20001",
                    "message": "Invalid value is specified for query parameters. query name: fields",
                },
            },
        }
        assert "[E40025]A serious error has occurred. It suspends processing." in caplog.text

    def test_service_request_to_start_api_when_recieve_503_error(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {},
            status=503,
        )
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {},
            status=503,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 503
        assert result.queryParameter == ""
        assert result.responseBody == {}
        assert "[E40025]A serious error has occurred. It suspends processing." in caplog.text

    def test_service_request_to_start_api_when_recieve_404_error(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"code": "340402", "message": f"targetCPUID {hostCpuId} not found"}, status=404)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"code": "340402", "message": f"targetCPUID {hostCpuId} not found"}, status=404)

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 404
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "340402",
            "message": f"targetCPUID {hostCpuId} not found",
        }
        assert "[E40025]A serious error has occurred. It suspends processing." in caplog.text

    def test_service_request_to_start_api_when_recieve_409_error(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {
                "code": "340901",
                "message": f"Another extended procedure for the same instance already running: targetRequestInstanceID={targetRequestInstanceID}",
            },
            status=409,
        )
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {
                "code": "340901",
                "message": f"Another extended procedure for the same instance already running: targetRequestInstanceID={targetRequestInstanceID}",
            },
            status=409,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 409
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "340901",
            "message": f"Another extended procedure for the same instance already running: targetRequestInstanceID={targetRequestInstanceID}",
        }
        assert "[E40025]A serious error has occurred. It suspends processing." in caplog.text

    def test_service_request_to_start_api_when_recieve_422_error(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["retry"]["default"]["max_count"] = 2

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"detail": [{"loc": ["string", 0], "msg": "string", "type": "string"}]}, status=422)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"detail": [{"loc": ["string", 0], "msg": "string", "type": "string"}]}, status=422)

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 422
        assert result.queryParameter == ""
        assert result.responseBody == {"detail": [{"loc": ["string", 0], "msg": "string", "type": "string"}]}
        assert "[E40025]A serious error has occurred. It suspends processing." in caplog.text

    def test_service_request_to_start_api_when_time_out(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        timeout_sec = 1
        workflow_manager_conf = config.workflow_manager.copy()
        workflow_manager_conf["timeout"] = timeout_sec

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": workflow_manager_conf,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        def sleeping(request: Request):
            sleep(timeout_sec + 5)  # Timeout value + 5-second delay
            return Response("", status=200)

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_handler(sleeping)

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 504
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40003",
            "message": "Timeout: Could not connect to server.",
        }
        assert "[E40003]Timeout: Could not connect to server." in caplog.text

    def test_service_request_to_start_api_when_connection_error(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        mocker.patch.object(api_obj, "recent_request_uri", "http://10.000.111.111:8000/test")

        def _requests(self, payload):
            raise exceptions.ConnectionError()

        api_obj._requests = types.MethodType(_requests, api_obj)

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        # httpserver.clear()

        # assert
        assert result.responseBody == {
            "code": "E40007",
            "message": "Connection error occurred. Please check if the URL is correct. http://10.000.111.111:8000/test",
        }
        assert result.statusCode == 500
        assert result.status == "FAILED"
        assert "Connection error occurred. Please check if the URL is correct." in caplog.text

    def test_service_request_to_start_api_when_request_exception(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        mocker.patch.object(api_obj, "_requests", side_effect=exceptions.RequestException("Unexpected error"))

        def _requests(self, payload):
            raise exceptions.RequestException()

        api_obj._requests = types.MethodType(_requests, api_obj)

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]

        # assert
        assert result.responseBody == {
            "code": "E40008",
            "message": "Unexpected requests error occurred.",
        }
        assert result.queryParameter == ""
        assert result.statusCode == 500
        assert result.status == "FAILED"
        assert "[E40008]Unexpected requests error occurred." in caplog.text

    def test_service_request_to_start_api_when_polling_success(self, httpserver, mocker, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)

        call_count = 0

        def custom_get_handler(request):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                response_data = {
                    "applyID": applyID,
                    "targetCPUID": hostCpuId,
                    "targetRequestInstanceID": targetRequestInstanceID,
                    "operation": "start",
                    "id": EXTENDED_PROCEDURE_ID,
                    "status": "IN_PROGRESS",
                    "serviceInstanceID": str(uuid4()),
                }
            else:
                response_data = {
                    "applyID": applyID,
                    "targetCPUID": hostCpuId,
                    "targetRequestInstanceID": targetRequestInstanceID,
                    "operation": "start",
                    "id": EXTENDED_PROCEDURE_ID,
                    "status": "COMPLETED",
                    "serviceInstanceID": str(uuid4()),
                }

            return Response(
                response=json.dumps(response_data), status=200, headers={"Content-Type": "application/json"}
            )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_handler(custom_get_handler)

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {"extendedProcedureID": f"{EXTENDED_PROCEDURE_ID}"}
        assert result.status == "COMPLETED"
        assert result.statusCode == 202

    def test_service_request_to_start_api_when_polling_exceeded(self, httpserver, mocker, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "start",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "IN_PROGRESS",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "start",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "IN_PROGRESS",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: IN_PROGRESS",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert (
            f"[E40033]The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: IN_PROGRESS"
            in caplog.text
        )

    def test_service_request_to_start_api_when_GetServiceInfo_receive_FAILED(
        self, httpserver, mocker, caplog, init_db_instance
    ):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "start",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "FAILED",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert (
            f"[E40033]The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED"
            in caplog.text
        )

    def test_service_request_to_start_api_when_polling_receive_FAILED(
        self, httpserver, mocker, caplog, init_db_instance
    ):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "start",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "FAILED",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "start",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "FAILED",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert (
            f"[E40033]The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED"
            in caplog.text
        )

    def test_service_request_to_start_api_when_polling_receive_404_error(
        self, httpserver, mocker, caplog, init_db_instance
    ):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {"code": "340401", "message": f"Extended procedure {EXTENDED_PROCEDURE_ID} not found"},
            status=404,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert "[E40034]Failed to get extended process information." in caplog.text

    def test_service_request_to_start_api_when_polling_receive_422_error(
        self, httpserver, mocker, caplog, init_db_instance
    ):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {"detail": [{"loc": ["string", 0], "msg": "string", "type": "string"}]},
            status=422,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert "[E40034]Failed to get extended process information." in caplog.text

    def test_service_request_to_start_api_when_polling_receive_500_error(
        self, httpserver, mocker, caplog, init_db_instance
    ):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {},
            status=500,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert "[E40034]Failed to get extended process information." in caplog.text

    def test_service_request_to_start_api_when_validate_error(self, httpserver, mocker, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "start",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "dummy",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED",
        }

        assert "[E40001]'dummy' is not one of ['IN_PROGRESS', 'COMPLETED', 'FAILED']" in caplog.text

    def test_start_api_without_extended_procedure_id(self, httpserver, mocker, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StartAPI = StartAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )

        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        procedure = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {
                "message": "Request accepted",
                # The response does not contain the extendedProcedureID.
            },
            status=202,
        )

        # act
        result, is_suspended = api_obj.execute(procedure)

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert "extendedProcedureID:" not in caplog.text
        assert api_obj.get_service_api.extended_procedure_id is None

    def test_service_can_request_to_stop_api(self, httpserver, init_db_instance):
        # arrange
        config = self.config

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "stop",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "COMPLETED",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {"extendedProcedureID": f"{EXTENDED_PROCEDURE_ID}"}
        assert result.status == "COMPLETED"
        assert result.statusCode == 202

    def test_service_can_request_to_stop_api_when_failed_to_load_the_logs(
        self, mocker, httpserver, capfd, init_db_instance
    ):
        # arrange
        config = self.config

        mocker.patch.object(
            Logger, "__init__", side_effect=Exception("Internal server error. Failed in log initialization")
        )
        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        _, err = capfd.readouterr()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 500
        assert (
            "[E40009]Failed to initialize log in sub process. Output log to standard output.Internal server error. Failed in log initialization"
            in err
        )

    def test_service_request_to_stop_api_when_retry_success(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["retry"]["default"]["max_count"] = 2
        config.workflow_manager["extended-procedure"]["retry"]["default"]["interval"] = 1

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        call_count = 0

        def custom_handler(request):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                response_data = {
                    "code": "150001",
                    "message": "Error occured when calling another REST API internally",
                    "detail": {
                        "message": "400 Client Error: Bad Request for url: http://localhost:8800/layout-design/",
                        "method": "POST",
                        "url": "http://localhost:8800/layout-design/",
                        "responseBody": {
                            "code": "E20001",
                            "message": "Invalid value is specified for query parameters. query name: fields",
                        },
                    },
                }
                return Response(
                    response=json.dumps(response_data), status=500, headers={"Content-Type": "application/json"}
                )
            else:
                response_data = {"extendedProcedureID": EXTENDED_PROCEDURE_ID}
                return Response(
                    response=json.dumps(response_data), status=202, headers={"Content-Type": "application/json"}
                )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_handler(custom_handler)

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "stop",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "COMPLETED",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "COMPLETED"
        assert result.statusCode == 202
        assert result.queryParameter == ""
        assert result.responseBody == {"extendedProcedureID": f"{EXTENDED_PROCEDURE_ID}"}

    def test_service_request_to_stop_api_when_recieve_500_error(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {
                "code": "150001",
                "message": "Error occured when calling another REST API internally",
                "detail": {
                    "message": "400 Client Error: Bad Request for url: http://localhost:8800/layout-design/",
                    "method": "POST",
                    "url": "http://localhost:8800/layout-design/",
                    "responseBody": {
                        "code": "E20001",
                        "message": "Invalid value is specified for query parameters. query name: fields",
                    },
                },
            },
            status=500,
        )
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {
                "code": "150001",
                "message": "Error occured when calling another REST API internally",
                "detail": {
                    "message": "400 Client Error: Bad Request for url: http://localhost:8800/layout-design/",
                    "method": "POST",
                    "url": "http://localhost:8800/layout-design/",
                    "responseBody": {
                        "code": "E20001",
                        "message": "Invalid value is specified for query parameters. query name: fields",
                    },
                },
            },
            status=500,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 500
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "150001",
            "message": "Error occured when calling another REST API internally",
            "detail": {
                "message": "400 Client Error: Bad Request for url: http://localhost:8800/layout-design/",
                "method": "POST",
                "url": "http://localhost:8800/layout-design/",
                "responseBody": {
                    "code": "E20001",
                    "message": "Invalid value is specified for query parameters. query name: fields",
                },
            },
        }
        assert "[E40025]A serious error has occurred. It suspends processing." in caplog.text

    def test_service_request_to_stop_api_when_recieve_503_error(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {},
            status=503,
        )
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {},
            status=503,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 503
        assert result.queryParameter == ""
        assert result.responseBody == {}
        assert "[E40025]A serious error has occurred. It suspends processing." in caplog.text

    def test_service_request_to_stop_api_when_recieve_404_error(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        config.workflow_manager["extended-procedure"]["retry"]["default"]["max_count"] = 2
        config.workflow_manager["extended-procedure"]["retry"]["default"]["interval"] = 1

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"code": "340402", "message": f"targetCPUID {hostCpuId} not found"}, status=404)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"code": "340402", "message": f"targetCPUID {hostCpuId} not found"}, status=404)

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 404
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "340402",
            "message": f"targetCPUID {hostCpuId} not found",
        }
        assert "[E40025]A serious error has occurred. It suspends processing." in caplog.text

    def test_service_request_to_stop_api_when_recieve_409_error(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        config.workflow_manager["extended-procedure"]["retry"]["default"]["max_count"] = 2
        config.workflow_manager["extended-procedure"]["retry"]["default"]["interval"] = 1

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {
                "code": "340901",
                "message": f"Another extended procedure for the same instance already running: targetRequestInstanceID={targetRequestInstanceID}",
            },
            status=409,
        )
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {
                "code": "340901",
                "message": f"Another extended procedure for the same instance already running: targetRequestInstanceID={targetRequestInstanceID}",
            },
            status=409,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 409
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "340901",
            "message": f"Another extended procedure for the same instance already running: targetRequestInstanceID={targetRequestInstanceID}",
        }
        assert "[E40025]A serious error has occurred. It suspends processing." in caplog.text

    def test_service_request_to_stop_api_when_recieve_422_error(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        config.workflow_manager["extended-procedure"]["retry"]["default"]["max_count"] = 2
        config.workflow_manager["extended-procedure"]["retry"]["default"]["interval"] = 1

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"detail": [{"loc": ["string", 0], "msg": "string", "type": "string"}]}, status=422)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"detail": [{"loc": ["string", 0], "msg": "string", "type": "string"}]}, status=422)

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 422
        assert result.queryParameter == ""
        assert result.responseBody == {"detail": [{"loc": ["string", 0], "msg": "string", "type": "string"}]}
        assert "[E40025]A serious error has occurred. It suspends processing." in caplog.text

    def test_service_request_to_stop_api_when_time_out(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        timeout_sec = 1
        workflow_manager_conf = config.workflow_manager.copy()
        workflow_manager_conf["timeout"] = timeout_sec

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": workflow_manager_conf,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        def sleeping(request: Request):
            sleep(timeout_sec + 5)  # Timeout value + 5-second delay
            return Response("", status=202)

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_handler(sleeping)

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 504
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40003",
            "message": "Timeout: Could not connect to server.",
        }
        assert "[E40003]Timeout: Could not connect to server." in caplog.text

    def test_service_request_to_stop_api_when_connection_error(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        config.workflow_manager["extended-procedure"]["retry"]["default"]["max_count"] = 2
        config.workflow_manager["extended-procedure"]["retry"]["default"]["interval"] = 1

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        mocker.patch.object(api_obj, "recent_request_uri", "http://10.000.111.111:8000/test")

        def _requests(self, payload):
            raise exceptions.ConnectionError()

        api_obj._requests = types.MethodType(_requests, api_obj)

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        # httpserver.clear()

        # assert
        assert result.responseBody == {
            "code": "E40007",
            "message": "Connection error occurred. Please check if the URL is correct. http://10.000.111.111:8000/test",
        }
        assert result.queryParameter == ""
        assert result.statusCode == 500
        assert result.status == "FAILED"
        assert "Connection error occurred. Please check if the URL is correct." in caplog.text

    def test_service_request_to_stop_api_when_request_exception(self, mocker, httpserver, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        config.workflow_manager["extended-procedure"]["retry"]["default"]["max_count"] = 2
        config.workflow_manager["extended-procedure"]["retry"]["default"]["interval"] = 1

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        mocker.patch.object(api_obj, "_requests", side_effect=exceptions.RequestException("Unexpected error"))

        def _requests(self, payload):
            raise exceptions.RequestException()

        api_obj._requests = types.MethodType(_requests, api_obj)

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]

        # assert
        assert result.responseBody == {
            "code": "E40008",
            "message": "Unexpected requests error occurred.",
        }
        assert result.queryParameter == ""
        assert result.statusCode == 500
        assert result.status == "FAILED"
        assert "[E40008]Unexpected requests error occurred." in caplog.text

    def test_service_request_to_stop_api_when_polling_success(self, httpserver, mocker, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)

        call_count = 0

        def custom_get_handler(request):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                response_data = {
                    "applyID": applyID,
                    "targetCPUID": hostCpuId,
                    "targetRequestInstanceID": targetRequestInstanceID,
                    "operation": "stop",
                    "id": EXTENDED_PROCEDURE_ID,
                    "status": "IN_PROGRESS",
                    "serviceInstanceID": str(uuid4()),
                }
            else:
                response_data = {
                    "applyID": applyID,
                    "targetCPUID": hostCpuId,
                    "targetRequestInstanceID": targetRequestInstanceID,
                    "operation": "stop",
                    "id": EXTENDED_PROCEDURE_ID,
                    "status": "COMPLETED",
                    "serviceInstanceID": str(uuid4()),
                }

            return Response(
                response=json.dumps(response_data), status=200, headers={"Content-Type": "application/json"}
            )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_handler(custom_get_handler)

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {"extendedProcedureID": f"{EXTENDED_PROCEDURE_ID}"}
        assert result.status == "COMPLETED"
        assert result.statusCode == 202

    def test_service_request_to_stop_api_when_polling_exceeded(self, httpserver, mocker, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "stop",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "IN_PROGRESS",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "stop",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "IN_PROGRESS",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: IN_PROGRESS",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert (
            f"[E40033]The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: IN_PROGRESS"
            in caplog.text
        )

    def test_service_request_to_stop_api_when_GetServiceInfo_receive_FAILED(
        self, httpserver, mocker, caplog, init_db_instance
    ):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "start",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "FAILED",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert (
            f"[E40033]The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED"
            in caplog.text
        )

    def test_service_request_to_stop_api_when_polling_receive_FAILED(
        self, httpserver, mocker, caplog, init_db_instance
    ):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "start",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "FAILED",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "start",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "FAILED",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert (
            f"[E40033]The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED"
            in caplog.text
        )

    def test_service_request_to_stop_api_when_polling_receive_404_error(
        self, httpserver, mocker, caplog, init_db_instance
    ):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {"code": "340401", "message": f"Extended procedure {EXTENDED_PROCEDURE_ID} not found"},
            status=404,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert "[E40034]Failed to get extended process information." in caplog.text

    def test_service_request_to_stop_api_when_polling_receive_422_error(
        self, httpserver, mocker, caplog, init_db_instance
    ):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {"detail": [{"loc": ["string", 0], "msg": "string", "type": "string"}]},
            status=422,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert "[E40034]Failed to get extended process information." in caplog.text

    def test_service_request_to_stop_api_when_polling_receive_500_error(
        self, httpserver, mocker, caplog, init_db_instance
    ):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {},
            status=500,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED",
        }
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert "[E40034]Failed to get extended process information." in caplog.text

    def test_service_request_to_stop_api_when_validate_error(self, httpserver, mocker, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetRequestInstanceID → targetServiceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": applyID,
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "stop",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "dummy",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )

        # act
        execute_result = api_obj.execute(paylod)
        result: Details = execute_result[ApiExecuteResultIdx.DETAIL]
        httpserver.clear()

        # assert
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert result.queryParameter == ""
        assert result.responseBody == {
            "code": "E40033",
            "message": f"The extended process could not be completed. requestInstanceID: {targetRequestInstanceID}, current: FAILED",
        }

        assert "[E40001]'dummy' is not one of ['IN_PROGRESS', 'COMPLETED', 'FAILED']" in caplog.text

    def test_stop_api_without_extended_procedure_id(self, httpserver, mocker, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config
        config.workflow_manager["extended-procedure"]["polling"]["count"] = 2

        applyID = str(uuid4())
        api_obj: StopAPI = StopAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
                "applyID": applyID,
            }
        )

        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        procedure = Procedure(
            **{
                "operationID": 1,
                "operation": "stop",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure"), method="POST"
        ).respond_with_json(
            {
                "message": "Request accepted",
                # The response does not contain the extendedProcedureID.
            },
            status=202,
        )

        # act
        result, is_suspended = api_obj.execute(procedure)

        # assert
        assert result.operationID == 1
        assert result.method == "POST"
        assert result.status == "FAILED"
        assert result.statusCode == 202
        assert "extendedProcedureID:" not in caplog.text
        assert api_obj.get_service_api.extended_procedure_id is None

    def test_service_can_request_to_get_service_infromation_api(self, httpserver, mocker, caplog, init_db_instance):
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        config = self.config

        api_obj: GetServiceInformationAPI = GetServiceInformationAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
            }
        )

        api_obj.extended_procedure_id = EXTENDED_PROCEDURE_ID

        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        procedure = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,  # targetServiceID → targetRequestInstanceID
                "dependencies": [],
            }
        )

        httpserver.expect_request(
            re.compile(f"\/{WORKFLOW_MANAGER_URI}\/extended-procedure\/{EXTENDED_PROCEDURE_ID}"), method="GET"
        ).respond_with_json(
            {
                "applyID": str(uuid4()),
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "operation": "start",
                "id": EXTENDED_PROCEDURE_ID,
                "status": "COMPLETED",
                "serviceInstanceID": str(uuid4()),
            },
            status=200,
        )

        # act
        result = api_obj.execute(procedure)
        httpserver.clear()

        # assert
        assert result["code"] == 200
        assert result["service_information"]["status"] == "COMPLETED"
        assert result["service_information"]["id"] == EXTENDED_PROCEDURE_ID
        assert "Request completed. status:[200]" in caplog.text

    def test_service_can_request_to_get_service_information_api_when_failed_to_load_the_logs(
        self, mocker, init_db_instance
    ):
        # arrange
        config = LayoutApplyConfig()
        mocker.patch.object(
            Logger, "__init__", side_effect=Exception("Internal server error. Failed in log initialization")
        )
        api_obj: GetServiceInformationAPI = GetServiceInformationAPI(
            **{
                "workflow_manager_conf": config.workflow_manager,
                "logger_args": LayoutApplyLogConfig().log_config,
            }
        )
        hostCpuId = str(uuid4())
        targetRequestInstanceID = str(uuid4())
        paylod = Procedure(
            **{
                "operationID": 1,
                "operation": "start",
                "targetCPUID": hostCpuId,
                "targetRequestInstanceID": targetRequestInstanceID,
                "dependencies": [],
            }
        )
        # act
        result = api_obj.execute(paylod)
        # assert
        assert result["code"] == 503
