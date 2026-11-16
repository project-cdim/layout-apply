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
"""Test for api"""

import json
import logging
import re
import secrets
import string
import urllib
from logging import DEBUG, ERROR
from logging.config import dictConfig
from multiprocessing import Process
from time import sleep

import psutil
import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extras import DictCursor
from pytest_httpserver import HTTPServer
from werkzeug import Response

from layoutapply.const import IdParameter, Result
from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.db import DbAccess
from layoutapply.server import _exec_subprocess, _initialize, app, main
from layoutapply.setting import LayoutApplyConfig, LayoutApplyLogConfig
from layoutapply.util import create_randomname
from tests.layoutapply.conftest import CONF_NODES_URL
from tests.layoutapply.test_data import checkvalid, migration, procedure, sql

client = TestClient(app)

LOG_PATH = "/var/log/cdim/app_layout_apply.log"


BASE_CONFIG = {
    "layout_apply": {"host": "0.0.0.0", "port": 8003, "request": {}},
    "db": {
        "dbname": "layoutapply",
        "user": "user01",
        "password": "P@ssw0rd",
        "host": "localhost",
        "port": 5435,
    },
    "get_information": {
        "host": "localhost",
        "port": 48889,
        "uri": "api/v1",
        "specs": {
            "poweroff": {
                "polling": {
                    "count": 5,
                    "interval": 1,
                },
            },
            "connect": {
                "polling": {
                    "count": 5,
                    "interval": 1,
                },
            },
            "disconnect": {
                "polling": {
                    "count": 5,
                    "interval": 1,
                },
            },
            "timeout": 10,
        },
    },
    "hardware_control": {
        "host": "localhost",
        "port": 48889,
        "uri": "cdim/api/v1",
        "disconnect": {
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
                    "interval": 5,
                    "max_count": 5,
                },
            },
            "timeout": 10,
        },
        "isosboot": {
            "polling": {
                "count": 5,
                "interval": 1,
                "targets": [
                    {
                        "status_code": 204,
                    },
                ],
                "skip": [
                    {"status_code": 400, "code": "EF003BAS010"},
                ],
            },
            "request": {"timeout": 2},
            "timeout": 10,
        },
    },
    "log": {
        "logging_level": "INFO",
        "log_dir": "./",
        "file": "app_layout_apply.log",
        "rotation_size": 1000000,
        "backup_files": 3,
        "stdout": False,
    },
    "migration_procedure_generator": {
        "host": "localhost",
        "port": 48889,
        "uri": "cdim/api/v1",
        "timeout": 30,
    },
    "configuration_manager": {
        "host": "localhost",
        "port": 48889,
        "uri": "cdim/api/v1",
        "timeout": 30,
    },
    "message_broker": {
        "host": "localhost",
        "port": 3500,
        "pubsub": "layout_apply_apply",
        "topic": "layout_apply_apply.completed",
    },
}

get_list_assert_target = {
    "totalCount": 9,
    "count": 9,
    "applyResults": [
        {
            "applyID": "000000001a",
            "status": "IN_PROGRESS",
            "startedAt": "2023-10-02T00:00:00Z",
        },
        {
            "status": "CANCELING",
            "applyID": "000000002b",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": True,
        },
        {
            "status": "COMPLETED",
            "applyID": "000000003c",
            "startedAt": "2023-10-02T00:00:00Z",
            "endedAt": "2023-10-02T12:23:59Z",
        },
        {
            "status": "FAILED",
            "applyID": "000000004d",
            "startedAt": "2023-10-02T00:00:01Z",
            "endedAt": "2023-10-02T12:24:00Z",
        },
        {
            "status": "CANCELED",
            "applyID": "000000005e",
            "startedAt": "2023-10-02T00:00:02Z",
            "endedAt": "2023-10-02T12:24:01Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": False,
        },
        {
            "status": "CANCELED",
            "applyID": "000000006f",
            "startedAt": "2023-10-03T00:00:00Z",
            "endedAt": "2023-10-04T12:23:59Z",
            "canceledAt": "2023-10-03T12:00:00Z",
            "executeRollback": True,
            "rollbackStatus": "COMPLETED",
            "rollbackStartedAt": "2023-10-03T12:20:00Z",
            "rollbackEndedAt": "2023-10-04T12:23:59Z",
        },
        {
            "status": "CANCELING",
            "applyID": "000000007a",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": True,
            "rollbackStartedAt": "2023-10-02T12:20:00Z",
        },
        {
            "status": "CANCELING",
            "applyID": "000000008b",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": False,
        },
        {
            "status": "SUSPENDED",
            "applyID": "000000009c",
            "startedAt": "2023-10-02T00:00:01Z",
            "suspendedAt": "2024-01-02T12:23:00Z",
        },
    ],
}


@pytest.mark.usefixtures("httpserver_listen_address")
class TestAPIServer:

    @pytest.mark.parametrize(("procedures", "sleep_time", "applyID"), procedure.multi_pattern)
    def test_execute_layoutapply_success(
        self, mocker, sleep_time, procedures, init_db_instance, applyID, docker_services
    ):
        mocker.patch("layoutapply.server._exec_subprocess", return_value=(None, "return_data", 1))
        mocker.patch.object(DbAccess, "update_subprocess", return_value=None)
        response = client.post("/cdim/api/v1/layout-apply", json=procedures)
        id_ = json.loads(response.content).get("applyID")
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{id_}'")
            init_db_instance.commit()
            row = cursor.fetchone()

        # assert
        # generated ID must be 10 digits long.
        assert len(row.get("applyid")) == 10

        assert response.status_code == 202
        assert response.charset_encoding == "utf-8"
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    @pytest.mark.parametrize(("procedures", "sleep_time"), procedure.proc_empty_pattern)
    @pytest.mark.usefixtures("hardwaremgr_fixture")
    def test_execute_layoutapply_status_completed_when_empty_migration_step(
        self,
        mocker,
        sleep_time,
        procedures,
        init_db_instance,
    ):
        # arrange

        sleep(sleep_time)
        response = client.post("/cdim/api/v1/layout-apply", json=procedures)
        id_ = json.loads(response.content).get("applyID")
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{id_}'")
            row = cursor.fetchone()

        # assert
        # generated ID must be 10 digits long.
        assert len(row.get("applyid")) == 10

        assert response.status_code == 202
        assert row.get("status") == "COMPLETED"
        assert row.get("rollbackprocedures") is None
        assert row.get("procedures") == []
        details = row.get("applyresult")
        assert details == []
        assert len(details) == len(procedures["procedures"])

    @pytest.mark.parametrize("procedures", checkvalid.without_required_key)
    def test_execute_layoutapply_failure_when_no_required_key(self, procedures):
        # arrange

        response = client.post("/cdim/api/v1/layout-apply", json=procedures)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    @pytest.mark.parametrize("procedures", checkvalid.any_key_combination)
    def test_execute_layoutapply_failure_when_any_key_combination(self, procedures):
        # arrange

        response = client.post("/cdim/api/v1/layout-apply", json=procedures)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    @pytest.mark.parametrize("procedures", checkvalid.invalid_data_type)
    def test_execute_layoutapply_failure_when_invalid_data_type(self, procedures):
        # arrange

        response = client.post("/cdim/api/v1/layout-apply", json=procedures)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    @pytest.mark.parametrize("procedures", checkvalid.invalid_value)
    def test_execute_layoutapply_failure_when_invalid_value(self, procedures):
        # arrange

        response = client.post("/cdim/api/v1/layout-apply", json=procedures)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    def test_execute_layoutapply_failure_when_failed_to_load_config_file(self, mocker):
        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )

        # arrange

        procedure_data = {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetDeviceID": "466cdeb7-d67b-4f0b-805e-85d54c7b5f41",
                    "dependencies": [],
                }
            ],
        }
        response = client.post("/cdim/api/v1/layout-apply", json=procedure_data)
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_config.yaml.\n('Dummy message',)"

    def test_execute_layoutapply_failure_when_failed_to_load_log_config_file(self, mocker, docker_services):
        mocker.patch.object(LayoutApplyLogConfig, "_validate_log_dir", side_effect=[Exception("Dummy message")])

        # arrange

        procedure_data = {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetDeviceID": "466cdeb7-d67b-4f0b-805e-85d54c7b5f41",
                    "dependencies": [],
                }
            ],
        }
        response = client.post("/cdim/api/v1/layout-apply", json=procedure_data)
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_log_config.yaml.\n('Dummy message',)"

    def test_execute_layoutapply_main_failure_when_failed_to_load_config_file(self, capfd, mocker):
        # arrange
        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )

        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert

        assert excinfo.value.code == 2
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""

        regex = re.compile(r"^Failed to load layoutapply_config.yaml")
        assert regex.search(err)

    def test_execute_layoutapply_failure_when_failure_to_load_secret_file(self, mocker, init_db_instance):
        # arrange
        mocker.patch.object(LayoutApplyConfig, "_get_secret", side_effect=[Exception("Dummy message")])

        # arrange

        procedure_data = {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetDeviceID": "466cdeb7-d67b-4f0b-805e-85d54c7b5f41",
                    "dependencies": [],
                }
            ],
        }
        response = client.post("/cdim/api/v1/layout-apply", json=procedure_data)
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40030"

    @pytest.mark.parametrize(
        "log_config",
        [
            {
                "version": 1,
                "formatters": {
                    "standard": {
                        "format": "%(asctime)s %(levelname)s %(message)s",
                        "datefmt": "%Y/%m/%d %H:%M:%S.%f",
                    }
                },
                "handlers": {
                    "file": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "level": "INFO",
                        "formatter": "standard",
                        "filename": "test/test",
                        "maxBytes": 100000000,
                        "backupCount": 72,
                        "encoding": "utf-8",
                    },
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO",
                        "formatter": "standard",
                        "stream": "ext://sys.stdout",
                    },
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["file", "console"],
                },
            }
        ],
    )
    def test_execute_layoutapply__failure_when_failed_to_initialize_logger(self, mocker, log_config, init_db_instance):
        mocker.patch.object(LayoutApplyLogConfig, "log_config", log_config)

        # arrange

        procedure_data = {
            "procedures": [
                {
                    "operationID": 1,
                    "operation": "shutdown",
                    "targetDeviceID": "466cdeb7-d67b-4f0b-805e-85d54c7b5f41",
                    "dependencies": [],
                }
            ],
        }
        response = client.post("/cdim/api/v1/layout-apply", json=procedure_data)
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40031"

    def test_execute_layoutapply_failure_when_query_failure_occurred(self, mocker, caplog):
        mocker.patch("logging.config.dictConfig")

        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        # act
        response = client.post("/cdim/api/v1/layout-apply", json=procedure.single_pattern[0][0])

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40019"
        assert "Query failed." in error_response["message"]
        assert "[E40019]Query failed." in caplog.text

    def test_execute_layoutapply_failure_when_failed_db_connection(self, mocker, init_db_instance):
        # arrange
        mocker.patch.object(DbAccess, "_get_running_data", side_effect=psycopg2.OperationalError)

        # act
        response = client.post("/cdim/api/v1/layout-apply", json=procedure.single_pattern[0][0])
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40018"
        assert "Could not connect to ApplyStatusDB." in error_response["message"]

    def test_execute_layoutapply_failure_when_failed_on_lock(
        self,
        mocker,
        init_db_instance,
    ):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
        init_db_instance.commit()
        # arrange

        # act
        response = client.post("/cdim/api/v1/layout-apply", json=procedure.single_pattern[0][0])

        # assert

        assert response.status_code == 409

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40010"
        assert error_response["message"] == "Already running. Cannot start multiple instances."

    def test_execute_layoutapply_failure_when_in_progress_data_exists(
        self,
        mocker,
        init_db_instance,
    ):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_delete_target_sql_8, vars=[applyid])
        init_db_instance.commit()

        # act
        response = client.post("/cdim/api/v1/layout-apply", json=procedure.single_pattern[0][0])

        # assert

        assert response.status_code == 409

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40010"
        assert error_response["message"] == "Already running. Cannot start multiple instances."

    @pytest.mark.parametrize(("procedures", "sleep_time", "applyID"), procedure.single_pattern)
    def test_execute_layoutapply_failure_when_suspended_data_exists(
        self,
        mocker,
        sleep_time,
        applyID,
        procedures,
        init_db_instance,
    ):
        # arrange
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""
                    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES 
                    ('300000008c','SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,null,null,null,null,'{"procedures": [{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]}',null,null,null,null,'2023/10/02 12:23:59',null);
                """
            )
        init_db_instance.commit()

        sleep(sleep_time)
        response = client.post("/cdim/api/v1/layout-apply", json=procedures)

        # assert

        assert response.status_code == 409

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40027"
        assert "Suspended data exist. Please resume layoutapply. applyID:" in error_response["message"]

    @pytest.mark.parametrize(("procedures", "sleep_time", "applyid"), procedure.single_pattern)
    def test_execute_layoutapply_failure_when_rollback_suspended_data_exists(
        self,
        mocker,
        sleep_time,
        applyid,
        procedures,
        init_db_instance,
    ):
        # arrange
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_delete_target_sql_9, vars=[applyid])
        init_db_instance.commit()

        sleep(sleep_time)
        response = client.post("/cdim/api/v1/layout-apply", json=procedures)

        # assert

        assert response.status_code == 409

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40027"
        assert "Suspended data exist. Please resume layoutapply. applyID:" in error_response["message"]

    @pytest.mark.parametrize(("procedures", "sleep_time", "applyID"), procedure.single_pattern)
    def test_execute_layoutapply_failure_when_failed_to_start_subprocess(
        self, mocker, sleep_time, applyID, procedures, init_db_instance, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # arrange

        # psycopg2.connect is mocked
        mocker.patch(
            "multiprocessing.Process.start",
            side_effect=Exception(),
        )

        sleep(sleep_time)
        response = client.post("/cdim/api/v1/layout-apply", json=procedures)
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40026"
        assert "Failed to start subprocess. " in error_response["message"]
        assert "[E40026]Failed to start subprocess." in caplog.text


def mock_run():
    cnt = 0
    while cnt < 3:
        sleep(1)
        cnt += 1
    return None


@pytest.mark.usefixtures("httpserver_listen_address")
class TestCancelAPIServer:

    def test_cancel_layoutapply_success(self, mocker, init_db_instance):
        # arrange
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        # Register the execution process in the database.
        proc_obj = psutil.Process(proc.pid)
        execution_cmd = proc_obj.cmdline()
        process_start = str(proc_obj.create_time())
        apply_id = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            query_str = f"INSERT INTO applystatus (applyid, status, processid, executioncommand, processstartedat) VALUES ('{apply_id}', '{Result.IN_PROGRESS}', {proc.pid}, '{"".join(execution_cmd)}', '{process_start}')"
            cursor.execute(query=query_str)
        init_db_instance.commit()
        # arrange

        url = f"/cdim/api/v1/layout-apply/{apply_id}?action=cancel"
        response = client.put(url)
        # Delete the mock process.
        proc.terminate()
        proc.join()
        # assert

        assert response.status_code == 202
        cancel_response = json.loads(response.content.decode())
        assert cancel_response["status"] == "CANCELING"

        if proc.is_alive():
            proc.terminate()
            proc.join()

    def test_cancel_layoutapply_becomes_failed_when_suspended_data_targeted(self, mocker, init_db_instance):
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="INSERT INTO applyStatus (applyID,status,startedAt) VALUES('e876543210','SUSPENDED',null)"
            )
        init_db_instance.commit()
        # arrange

        response = client.put("/cdim/api/v1/layout-apply/e876543210?action=cancel")

        # assert

        assert response.status_code == 202
        cancel_response = json.loads(response.content.decode())
        assert cancel_response["status"] == "FAILED"

    def test_cancel_layoutapply_success_when_canceled_data_targeted(self, mocker, init_db_instance):
        # arrange

        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_status_canceled_sql, vars=[applyid])
        init_db_instance.commit()

        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=cancel")

        # assert
        assert response.status_code == 200
        cancel_response = json.loads(response.content.decode())
        assert cancel_response["status"] == "CANCELED"

    def test_cancel_layoutapply_failure_when_completed_data_targeted(self, mocker, init_db_instance):
        # arrangge
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_status_completed_sql, vars=[applyid])
        init_db_instance.commit()

        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=cancel")

        # assert
        assert response.status_code == 409
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40022"
        assert error_response["message"] == "This layoutapply has already executed."

    def test_cancel_layoutapply_failure_when_failed_db_connection(self, mocker):
        mocker.patch.object(DbAccess, "proc_cancel", side_effect=psycopg2.OperationalError)
        response = client.put("/cdim/api/v1/layout-apply/012345678d?action=cancel")
        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40018"
        assert "Could not connect to ApplyStatusDB." in error_response["message"]

    def test_cancel_layoutapply_failure_when_query_failure_occurred(self, mocker):
        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        # act
        response = client.put("/cdim/api/v1/layout-apply/123456789a?action=cancel")

        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40019"
        assert "Query failed." in error_response["message"]

    def test_cancel_layoutapply_failure_when_nonexistent_id(self, mocker, init_db_instance):

        response = client.put("/cdim/api/v1/layout-apply/abcdeabcde?action=cancel")
        # assert
        assert response.status_code == 404
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40020"
        assert error_response["message"] == "Specified abcdeabcde is not found."

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "012345678g?action=cancel",
            "012345678a?action=canceling",
            "012345678a?action=cancel&rollbackOnCancel=talse",
        ],
    )
    def test_cancel_layoutapply_failure_when_invalid_parameter(self, parameter_uri):
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.put(request_uri)

        # assert
        assert response.status_code == 400
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    def test_cancel_layoutapply_failure_when_failed_to_load_config_file(self, mocker, init_db_instance):

        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )
        response = client.put("/cdim/api/v1/layout-apply/012345678a?action=cancel")

        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert "Failed to load layoutapply_config.yaml." in error_response["message"]

    def test_cancel_layoutapply_failure_when_failed_to_load_log_config_file(self, mocker):
        mocker.patch.object(LayoutApplyLogConfig, "_validate_log_dir", side_effect=[Exception("Dummy message")])

        # arrange
        response = client.put("/cdim/api/v1/layout-apply/012345678a?action=cancel")
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_log_config.yaml.\n('Dummy message',)"

    @pytest.mark.parametrize(
        ("execution_command", "process_startedat"),
        [
            ("dummy", "normal"),
            ("normal", "dummy"),
            ("dummy", "dummy"),
        ],
    )
    def test_cancel_layoutapply_becomes_failed_when_subprocess_not_found(
        self, mocker, init_db_instance, execution_command, process_startedat
    ):

        # arrange
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        proc_obj = psutil.Process(proc.pid)
        if execution_command == "dummy":
            register_executioncommand = execution_command
        else:
            register_executioncommand = "".join(proc_obj.cmdline())
        if process_startedat == "dummy":
            register_processstartedat = process_startedat
        else:
            register_processstartedat = str(proc_obj.create_time())
        # Register data that does not match the execution process in the database.
        apply_id = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            query_str = f"INSERT INTO applystatus (applyid, status, processid, executioncommand, processstartedat) VALUES ('{apply_id}', '{Result.IN_PROGRESS}', {proc.pid}, '{register_executioncommand}', '{register_processstartedat}')"
            cursor.execute(query=query_str)
        init_db_instance.commit()
        # arrange

        url = f"/cdim/api/v1/layout-apply/{apply_id}?action=cancel"
        response = client.put(url)
        # Delete the mock process.
        proc.terminate()
        proc.join()
        # assert
        assert response.status_code == 409
        cancel_response = json.loads(response.content.decode())
        assert cancel_response["code"] == "E40028"
        assert (
            cancel_response["message"]
            == "Since the process with the specified ID does not exist, change the status from IN_PROGRESS to FAILED."
        )
        assert cancel_response["status"] == "FAILED"

        if proc.is_alive():
            proc.terminate()
            proc.join()

    def test_cancel_layoutapply_failure_when_rollback_data_in_progress(self, mocker, init_db_instance):
        # arrange
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        # Register the execution process in the database.
        proc_obj = psutil.Process(proc.pid)
        execution_cmd = proc_obj.cmdline()
        process_start = str(proc_obj.create_time())
        apply_id = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            query_str = f"INSERT INTO applystatus (applyid, status, rollbackstatus, processid, executioncommand, processstartedat) VALUES ('{apply_id}', '{Result.CANCELED}', '{Result.IN_PROGRESS}', {proc.pid}, '{"".join(execution_cmd)}', '{process_start}')"
            cursor.execute(query=query_str)
        init_db_instance.commit()
        # arrange

        url = f"/cdim/api/v1/layout-apply/{apply_id}?action=cancel"
        response = client.put(url)
        # Delete the mock process.
        proc.terminate()
        proc.join()
        # assert

        assert response.status_code == 409

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40022"
        assert error_response["message"] == "This layoutapply has already executed."

        if proc.is_alive():
            proc.terminate()
            proc.join()

    @pytest.mark.parametrize(
        ("execution_command", "process_startedat"),
        [
            ("dummy", "normal"),
            ("normal", "dummy"),
            ("dummy", "dummy"),
        ],
    )
    def test_cancel_layoutapply_becomes_failed_when_rollback_and_subprocess_not_found(
        self, mocker, init_db_instance, execution_command, process_startedat
    ):

        # arrange
        # Execute a mock process.
        proc = Process(target=mock_run, daemon=True)
        proc.start()
        proc_obj = psutil.Process(proc.pid)
        if execution_command == "dummy":
            register_executioncommand = execution_command
        else:
            register_executioncommand = "".join(proc_obj.cmdline())
        if process_startedat == "dummy":
            register_processstartedat = process_startedat
        else:
            register_processstartedat = str(proc_obj.create_time())
        # Register data that does not match the execution process in the database.
        apply_id = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            query_str = f"INSERT INTO applystatus (applyid, status, rollbackstatus, processid, executioncommand, processstartedat) VALUES ('{apply_id}', '{Result.CANCELED}', '{Result.IN_PROGRESS}', {proc.pid}, '{register_executioncommand}', '{register_processstartedat}')"
            cursor.execute(query=query_str)
        init_db_instance.commit()
        # arrange

        url = f"/cdim/api/v1/layout-apply/{apply_id}?action=cancel"
        response = client.put(url)
        # Delete the mock process.
        proc.terminate()
        proc.join()
        # assert

        assert response.status_code == 409

        cancel_response = json.loads(response.content.decode())
        assert cancel_response["code"] == "E40028"
        assert (
            cancel_response["message"]
            == "Since the process with the specified ID does not exist, change the rollbackStatus from IN_PROGRESS to FAILED."
        )
        assert cancel_response["status"] == "CANCELED"
        assert cancel_response["rollbackStatus"] == "FAILED"

        if proc.is_alive():
            proc.terminate()
            proc.join()

    def test_cancel_layoutapply_success_when_suspended_rollback_data(self, mocker, init_db_instance):
        # Data adjustment before testing.
        apply_id = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query=f"INSERT INTO applyStatus (applyID,status,rollbackstatus,startedAt) VALUES('{apply_id}','{Result.CANCELED}','{Result.SUSPENDED}',null)"
            )
        init_db_instance.commit()
        # arrange

        url = f"/cdim/api/v1/layout-apply/{apply_id}?action=cancel"
        response = client.put(url)

        # assert

        assert response.status_code == 202

        cancel_response = json.loads(response.content.decode())
        assert cancel_response["status"] == "CANCELED"
        assert cancel_response["rollbackStatus"] == "FAILED"

    @pytest.mark.parametrize(
        ("rollbackStatus"),
        [
            (Result.COMPLETED),
            (Result.FAILED),
        ],
    )
    def test_cancel_layoutapply_success_when_roll_completed_or_failed_data(
        self, mocker, init_db_instance, rollbackStatus
    ):
        # Data adjustment before testing.
        apply_id = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query=f"INSERT INTO applyStatus (applyID,status,rollbackstatus,startedAt) VALUES('{apply_id}','{Result.CANCELED}','{rollbackStatus}',null)"
            )
        init_db_instance.commit()
        # arrange

        url = f"/cdim/api/v1/layout-apply/{apply_id}?action=cancel"
        response = client.put(url)

        # assert

        assert response.status_code == 200

        cancel_response = json.loads(response.content.decode())
        assert cancel_response["status"] == "CANCELED"
        assert cancel_response["rollbackStatus"] == rollbackStatus


@pytest.mark.usefixtures("httpserver_listen_address")
class TestGetAPIServer:

    def test_get_applystatus_failure_when_failed_to_load_config_file(self, mocker):
        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )

        response = client.get("/cdim/api/v1/layout-apply/123456789a")
        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_config.yaml.\n('Dummy message',)"

    def test_get_applystatus_failure_when_failed_to_load_log_config_file(self, mocker):
        mocker.patch.object(LayoutApplyLogConfig, "_validate_log_dir", side_effect=[Exception("Dummy message")])

        # arrange
        response = client.get("/cdim/api/v1/layout-apply/123456789a")
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_log_config.yaml.\n('Dummy message',)"

    def test_get_applystatus_failure_when_query_failure_occurred(self, mocker, caplog):
        mocker.patch("logging.config.dictConfig")

        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        # act
        response = client.get("/cdim/api/v1/layout-apply/123456789a")

        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40019"
        assert "Query failed." in error_response["message"]
        assert "[E40019]Query failed." in caplog.text

    def test_get_applystatus_failure_when_failed_db_connection(self, mocker):
        # arrange
        mocker.patch.object(DbAccess, "get_apply_status", side_effect=psycopg2.OperationalError)

        # act
        response = client.get("/cdim/api/v1/layout-apply/123456789a")
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40018"
        assert "Could not connect to ApplyStatusDB." in error_response["message"]

    def test_get_applystatus_failure_when_nonexistent_id(self, mocker, init_db_instance, caplog):
        mocker.patch("logging.config.dictConfig")

        # act
        response = client.get("/cdim/api/v1/layout-apply/9999999999")

        # assert

        assert response.status_code == 404

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40020"
        assert error_response["message"] == "Specified 9999999999 is not found."
        assert "[E40020]Specified 9999999999 is not found." in caplog.text

    @pytest.mark.parametrize(
        ("insert_sql", "assert_target"),
        [
            (
                sql.get_list_insert_sql_1,
                {
                    "status": "IN_PROGRESS",
                    "applyID": "000000001a",
                    "startedAt": "2023-10-02T00:00:00Z",
                    "procedures": {"procedures": "pre_test"},
                },
            ),
            (
                sql.get_list_insert_sql_2,
                {
                    "status": "CANCELING",
                    "applyID": "000000002b",
                    "startedAt": "2023-10-01T23:59:59Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": True,
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"test": "test"},
                },
            ),
            (
                sql.get_list_insert_sql_3,
                {
                    "status": "COMPLETED",
                    "applyID": "000000003c",
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "startedAt": "2023-10-02T00:00:00Z",
                    "endedAt": "2023-10-02T12:23:59Z",
                },
            ),
            (
                sql.get_list_insert_sql_4,
                {
                    "status": "FAILED",
                    "applyID": "000000004d",
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "startedAt": "2023-10-02T00:00:01Z",
                    "endedAt": "2023-10-02T12:24:00Z",
                },
            ),
            (
                sql.get_list_insert_sql_5,
                {
                    "status": "CANCELED",
                    "applyID": "000000005e",
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"test": "test"},
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ),
            (
                sql.get_list_insert_sql_6,
                {
                    "status": "CANCELED",
                    "applyID": "000000006f",
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"test": "test"},
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                    "rollbackStatus": "COMPLETED",
                    "rollbackResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackStartedAt": "2023-10-03T12:20:00Z",
                    "rollbackEndedAt": "2023-10-04T12:23:59Z",
                },
            ),
            (
                sql.get_list_insert_sql_7,
                {
                    "status": "CANCELING",
                    "applyID": "000000007a",
                    "startedAt": "2023-10-01T23:59:59Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": True,
                    "rollbackStartedAt": "2023-10-02T12:20:00Z",
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"test": "test"},
                },
            ),
            (
                sql.get_list_insert_sql_8,
                {
                    "status": "CANCELING",
                    "applyID": "000000008b",
                    "startedAt": "2023-10-01T23:59:59Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                },
            ),
        ],
    )
    def test_get_applystatus_success(self, mocker, init_db_instance, insert_sql, assert_target, caplog):
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.INFO)

        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
        init_db_instance.commit()
        assert_target["applyID"] = applyid

        # act
        response = client.get(f"/cdim/api/v1/layout-apply/{applyid}")

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == assert_target
        assert "Completed successfully." in caplog.text
        # data adjustment after testing
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.delete_for_applyid_sql, vars=[applyid])
        init_db_instance.commit()

    @pytest.mark.parametrize(
        ("insert_sql", "assert_target"),
        [
            (
                sql.insert_resumed_get_target_sql_1,
                {
                    "status": "IN_PROGRESS",
                    "applyID": "300000006a",
                    "startedAt": "2023-10-02T00:00:00Z",
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "resumedAt": "2023-10-03T12:23:59Z",
                    "procedures": {"procedures": "pre_test"},
                    "resumeProcedures": {"test": "pre_test"},
                },
            ),
            (
                sql.insert_resumed_get_target_sql_2,
                {
                    "status": "CANCELING",
                    "applyID": "300000007b",
                    "startedAt": "2023-10-02T00:00:00Z",
                    "canceledAt": "2023-10-02T00:00:01Z",
                    "executeRollback": True,
                    "rollbackResult": [{"test": "test"}, {"test": "test"}],
                    "rollbackStartedAt": "2023-10-02T00:00:02Z",
                    "resumeResult": [{"test": "test"}],
                    "resumedAt": "2023-10-03T12:23:59Z",
                    "procedures": {"procedures": "pre_test"},
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "resumeProcedures": {"test": "pre_test"},
                },
            ),
            (
                sql.insert_resumed_get_target_sql_5,
                {
                    "status": "IN_PROGRESS",
                    "applyID": "300000004d",
                    "startedAt": "2023-10-02T00:00:00Z",
                    "applyResult": [{"test": "test"}, {"test": "test"}],
                    "resumeResult": [{"test": "test"}],
                    "resumedAt": "2023-10-03T12:23:59Z",
                    "procedures": {"procedures": "pre_test"},
                    "resumeProcedures": {"test": "pre_test"},
                },
            ),
        ],
    )
    def test_get_applystatus_success_when_state_in_progress_or_canceling_data(
        self, mocker, init_db_instance, assert_target, insert_sql, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
        init_db_instance.commit()
        assert_target["applyID"] = applyid

        # act
        response = client.get(f"/cdim/api/v1/layout-apply/{applyid}")

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == assert_target
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        ("insert_sql", "assert_target"),
        [
            (
                sql.get_valid_insert_sql,
                {
                    "status": "COMPLETED",
                    "applyID": "999999999a",
                    "procedures": [],
                    "applyResult": [],
                    "startedAt": "2023-10-02T00:00:00Z",
                    "endedAt": "2023-10-02T12:23:59Z",
                },
            )
        ],
    )
    def test_get_applystatus_success_when_valid_data(self, mocker, init_db_instance, assert_target, insert_sql, caplog):
        mocker.patch("logging.config.dictConfig")

        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
        init_db_instance.commit()
        assert_target["applyID"] = applyid

        # act
        response = client.get(f"/cdim/api/v1/layout-apply/{applyid}")

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == assert_target
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "args",
        [
            ("g21bc21587"),  # character type violation
            ("ABCDEF0123"),  # character type violation
            ("あBCDEF0123"),  # character type violation
            ("a21bc2158"),  # character length violation
            ("a21bc215871"),  # character length violation
            ("a"),  # character length violation
        ],
    )
    def test_get_applystatus_failure_when_invalid_id(self, args):
        # arrange

        response = client.get(f"/cdim/api/v1/layout-apply/{args}")
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    @pytest.mark.parametrize(
        ("insert_sql", "assert_target"),
        [
            (
                sql.get_valid_insert_sql,
                {
                    "status": "COMPLETED",
                    "applyID": "999999999a",
                    "procedures": [],
                    "applyResult": [],
                    "startedAt": "2023-10-02T00:00:00Z",
                    "endedAt": "2023-10-02T12:23:59Z",
                },
            )
        ],
    )
    def test_get_applystatus_success_when_invalid_option_specified(
        self, mocker, init_db_instance, assert_target, insert_sql, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
        init_db_instance.commit()
        assert_target["applyID"] = applyid

        # act
        response = client.get(f"/cdim/api/v1/layout-apply/{applyid}", params={"fields": ["procedures"]})

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == assert_target
        assert "Completed successfully." in caplog.text


@pytest.mark.usefixtures("httpserver_listen_address")
class TestGetListAPIServer:

    def insert_list_data(self, init_db_instance):
        """Data registration for apply status list"""
        id_list = []
        get_applystatus_list = [
            sql.get_list_insert_sql_1,
            sql.get_list_insert_sql_2,
            sql.get_list_insert_sql_3,
            sql.get_list_insert_sql_4,
            sql.get_list_insert_sql_5,
            sql.get_list_insert_sql_6,
            sql.get_list_insert_sql_7,
            sql.get_list_insert_sql_8,
            sql.get_list_insert_sql_9,
        ]
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            for insert_sql in get_applystatus_list:
                applyid = create_randomname(IdParameter.LENGTH)
                id_list.append(applyid)
                cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()
            return id_list

    def test_get_applystatus_list_failure_when_failed_to_load_config_file(self, mocker):

        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )

        response = client.get("/cdim/api/v1/layout-apply")
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_config.yaml.\n('Dummy message',)"

    def test_get_applystatus_list_failure_when_failed_to_load_log_config_file(self, mocker, docker_services):
        mocker.patch.object(LayoutApplyLogConfig, "_validate_log_dir", side_effect=[Exception("Dummy message")])

        # arrange
        response = client.get("/cdim/api/v1/layout-apply")
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_log_config.yaml.\n('Dummy message',)"

    def test_get_applystatus_list_failure_when_query_failure_occurred(self, mocker, caplog, docker_services):
        mocker.patch("logging.config.dictConfig")

        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        # act
        response = client.get("/cdim/api/v1/layout-apply")

        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40019"
        assert "Query failed." in error_response["message"]
        assert "[E40019]Query failed." in caplog.text

    def test_get_applystatus_list_failure_when_failed_db_connection(self, mocker, docker_services):
        # arrange
        mocker.patch.object(DbAccess, "get_apply_status_list", side_effect=psycopg2.OperationalError)

        # act
        response = client.get("/cdim/api/v1/layout-apply")
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40018"
        assert "Could not connect to ApplyStatusDB." in error_response["message"]

    @pytest.mark.parametrize(
        "query_parameter",
        [
            {"status": "IN_PROGRES"},
            {"status": ""},
            {"startedAtSince": "T11:11:11Z"},
            {"startedAtSince": "20231102T111111Z"},
            {"startedAtSince": "2023-11-02 11:11:11"},
            {"startedAtSince": "2023/11/02T11:11:11Z"},
            {"startedAtSince": "20231102T11:11:11Z"},
            {"startedAtSince": "2023-11-0211:11:11Z"},
            {"startedAtSince": ""},
            {"startedAtUntil": "2023-11-02"},
            {"startedAtUntil": "T11:11:11Z"},
            {"startedAtUntil": "20231102T111111Z"},
            {"startedAtUntil": "2023-11-02 11:11:11"},
            {"startedAtUntil": "2023/11/02T11:11:11Z"},
            {"startedAtUntil": "20231102T11:11:11Z"},
            {"startedAtUntil": "2023-11-0211:11:11Z"},
            {"startedAtUntil": ""},
            {"endedAtSince": "2023-11-02"},
            {"endedAtSince": "T11:11:11Z"},
            {"endedAtSince": "20231102T111111Z"},
            {"endedAtSince": "2023-11-02 11:11:11"},
            {"endedAtSince": "2023/11/02T11:11:11Z"},
            {"endedAtSince": "20231102T11:11:11Z"},
            {"endedAtSince": "2023-11-0211:11:11Z"},
            {"endedAtSince": ""},
            {"endedAtUntil": "2023-11-02"},
            {"endedAtUntil": "T11:11:11Z"},
            {"endedAtUntil": "20231102T111111Z"},
            {"endedAtUntil": "2023-11-02 11:11:11"},
            {"endedAtUntil": "2023/11/02T11:11:11Z"},
            {"endedAtUntil": "20231102T11:11:11Z"},
            {"endedAtUntil": "2023-11-0211:11:11Z"},
            {"endedAtUntil": ""},
            {"endedAtUntil": "2023-11-02T11:11:11+"},
            {"endedAtUntil": "2023-11-02T11:11:11-09"},
            {"endedAtUntil": "2023-11-02T11:11:11-24:00"},
            {"endedAtUntil": "2023-11-02T11:11:11Z+09:00"},
            {"sortBy": ""},
            {"sortBy": "status"},
            {"orderBy": ""},
            {"orderBy": "new"},
            {"limit": ""},
            {"limit": "-1"},
            {"offset": ""},
            {"offset": "-1"},
        ],
    )
    def test_get_applystatus_list_failure_when_invalid_parameter(self, query_parameter):
        request_uri = "/cdim/api/v1/layout-apply/"
        encoded_params = urllib.parse.urlencode(query_parameter)
        full_url = f"{request_uri}?{encoded_params}"

        response = client.get(full_url)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    @pytest.mark.parametrize(
        "query_parameter",
        [
            {"startedAtSince": "0000-11-02T11:11:11+09:00"},
        ],
    )
    def test_get_applystatus_list_failure_when_invalid_time_specification(self, mocker, query_parameter):
        request_uri = "/cdim/api/v1/layout-apply/"
        encoded_params = urllib.parse.urlencode(query_parameter)
        full_url = f"{request_uri}?{encoded_params}"

        response = client.get(full_url)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    @pytest.mark.parametrize(
        "query_parameter",
        [
            {"startedAtSince": "2023-10-02T23:59:00Z"},
            {"startedAtSince": "2023-10-03T00:00:00Z"},
            {"startedAtSince": "2023-10-02T23:59:00-00:01"},
            {"startedAtSince": "2023-10-03T00:00:01+00:01"},
        ],
    )
    def test_get_applystatus_list_success_when_start_time_specified(
        self, mocker, query_parameter, init_db_instance, caplog, docker_services
    ):
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.INFO)
        # Data adjustment before testing.
        id_list = self.insert_list_data(init_db_instance)

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        encoded_params = urllib.parse.urlencode(query_parameter)
        full_url = f"{request_uri}?{encoded_params}"

        response = client.get(full_url)
        # response = client.get(request_uri, params=query_parameter)

        get_list_assert_target_1 = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": id_list[5],
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                    "rollbackStatus": "COMPLETED",
                    "rollbackStartedAt": "2023-10-03T12:20:00Z",
                    "rollbackEndedAt": "2023-10-04T12:23:59Z",
                },
            ],
        }

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_1
        assert "Completed successfully." in caplog.text

    def test_get_applystatus_list_success(self, mocker, init_db_instance, caplog):
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()
        # act
        response = client.get("/cdim/api/v1/layout-apply")

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())

        assert get_response["count"] == get_list_assert_target["count"]
        assert get_response["totalCount"] == get_list_assert_target["totalCount"]
        for a in get_response["applyResults"]:
            assert a in get_list_assert_target["applyResults"]
        assert "Completed successfully." in caplog.text

    def test_get_applystatus_list_success_when_no_results_fetched(self, mocker, init_db_instance, caplog):
        mocker.patch("logging.config.dictConfig")

        assert_target = {
            "totalCount": 0,
            "count": 0,
            "applyResults": [],
        }

        # act
        response = client.get("/cdim/api/v1/layout-apply")

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == assert_target
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "params",
        [
            ({"fields": [""]}),  # empty string
            ({"fields": ["procedure"]}),  # invalid name
            ({"fields": ["applyresult"]}),  # invalid name
            ({"fields": ["rollbackProcedure"]}),  # invalid name
            ({"fields": ["rollbackresult"]}),  # invalid name
        ],
    )
    def test_get_applystatus_list_failure_when_invalid_field(self, params):

        # arrange

        response = client.get("/cdim/api/v1/layout-apply", params=params)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    @pytest.mark.parametrize(
        "params, fields",
        [
            (
                {"fields": ["procedures"]},
                ["procedures"],
            ),  # fields:procedures
            (
                {"fields": ["applyResult"]},
                ["applyResult"],
            ),  # fields:applyResult
            (
                {"fields": ["rollbackProcedures"]},
                ["rollbackProcedures"],
            ),  # fields:rollbackProcedures
            (
                {"fields": ["rollbackResult"]},
                ["rollbackResult"],
            ),  # fields:rollbackResult
            (
                {"fields": ["procedures", "applyResult"]},
                ["procedures", "applyResult"],
            ),  # fields:procedures/applyResult
            (
                {"fields": ["procedures", "rollbackProcedures"]},
                ["procedures", "rollbackProcedures"],
            ),  # fields:procedures/rollbackProcedures
            (
                {"fields": ["procedures", "rollbackResult"]},
                ["procedures", "rollbackResult"],
            ),  # fields:procedures/rollbackResult
            (
                {"fields": ["applyResult", "rollbackProcedures"]},
                ["applyResult", "rollbackProcedures"],
            ),  # fields:applyResult/rollbackProcedures
            (
                {"fields": ["applyResult", "rollbackResult"]},
                ["applyResult", "rollbackResult"],
            ),  # fields:applyResult/rollbackResult
            (
                {"fields": ["rollbackProcedures", "rollbackResult"]},
                ["rollbackProcedures", "rollbackResult"],
            ),  # fields:rollbackProcedures/rollbackResult
            (
                {"fields": ["procedures", "applyResult", "rollbackProcedures"]},
                ["procedures", "applyResult", "rollbackProcedures"],
            ),  # fields:procedures/applyResult/rollbackProcedures
            (
                {"fields": ["procedures", "applyResult", "rollbackResult"]},
                ["procedures", "applyResult", "rollbackResult"],
            ),  # fields:procedures/applyResult/rollbackResult
            (
                {"fields": ["procedures", "rollbackProcedures", "rollbackResult"]},
                ["procedures", "rollbackProcedures", "rollbackResult"],
            ),  # fields:procedures/rollbackProcedures/rollbackResult
            (
                {"fields": ["applyResult", "rollbackProcedures", "rollbackResult"]},
                ["applyResult", "rollbackProcedures", "rollbackResult"],
            ),  # fields:applyResult/rollbackProcedures/rollbackResult
            (
                {
                    "fields": [
                        "procedures",
                        "applyResult",
                        "rollbackProcedures",
                        "rollbackResult",
                    ]
                },
                ["procedures", "applyResult", "rollbackProcedures", "rollbackResult"],
            ),  # fields:procedures/applyResult/rollbackProcedures/rollbackResult
        ],
    )
    def test_get_applystatus_list_success_when_field_specified(
        self, mocker, docker_services, init_db_instance, params, fields, caplog
    ):
        mocker.patch("logging.config.dictConfig", lambda config: None)

        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.INFO)

        def _fields_check(check_targets: list, fields: list, result: dict):
            for target in check_targets:
                if target in fields:
                    assert target in result
                else:
                    assert target not in result

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()
        response = client.get("/cdim/api/v1/layout-apply", params=params)

        # assert
        assert response.status_code == 200
        get_response = json.loads(response.content.decode())
        # Only items specified in the fields are output, and unspecified items are not output.
        applyResults = get_response.get("applyResults")
        # standard output displays only the items specified by fields, and items not specified are not displayed.
        for result in applyResults:
            match result.get("status"):
                case "COMPLETED" | "FAILED":
                    # no rollback related items with fields specified.
                    assert "rollbackProcedures" not in result
                    assert "rollbackResult" not in result
                    _fields_check(["procedures", "applyResult"], fields, result)
                case "IN_PROGRESS":
                    # no items that can be specified in fields
                    assert "applyResult" not in result
                    assert "rollbackProcedures" not in result
                    assert "rollbackResult" not in result
                case "CANCELING":
                    # no items that can be specified in fields
                    assert "rollbackResult" not in result
                case "CANCELED":
                    if result.get("executeRollback") is False:
                        assert "rollbackResult" not in result
                        _fields_check(
                            ["procedures", "applyResult", "rollbackProcedures"],
                            fields,
                            result,
                        )
                    else:
                        _fields_check(
                            [
                                "procedures",
                                "applyResult",
                                "rollbackProcedures",
                                "rollbackResult",
                            ],
                            fields,
                            result,
                        )
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?status=CANCELED&startedAtSince=2023-10-02T00:00:03Z&startedAtUntil=2023-10-03T00:00:01Z&endedAtSince=2023-10-02T12:24:01Z&endedAtUntil=2023-10-04T12:24:00Z",
        ],
    )
    def test_get_applystatus_list_success_when_only_start_date_start_out_of_range(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        # "applyID": "000000006f"（target）"applyID": "000000005e"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": "000000006f",
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                    "rollbackStatus": "COMPLETED",
                    "rollbackStartedAt": "2023-10-03T12:20:00Z",
                    "rollbackEndedAt": "2023-10-04T12:23:59Z",
                },
            ],
        }

        # assert

        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_all
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?status=CANCELED&startedAtSince=2023-10-02T00:00:02Z&startedAtUntil=2023-10-02T23:59:59Z&endedAtSince=2023-10-02T12:24:01Z&endedAtUntil=2023-10-04T12:24:00Z",
        ],
    )
    def test_get_applystatus_list_success_when_only_end_date_end_out_of_range(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        # "applyID": "000000005e"（target）"applyID": "000000006f"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": "000000005e",
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_all
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?status=CANCELED&startedAtSince=2023-10-02T00:00:02Z&startedAtUntil=2023-10-03T00:00:00Z&endedAtSince=2023-10-02T12:24:02Z&endedAtUntil=2023-10-04T12:24:00Z",
        ],
    )
    def test_get_applystatus_list_success_when_only_end_date_start_out_of_range(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        # "applyID": "000000006f"（target）"applyID": "000000005e"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": "000000006f",
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                    "rollbackStatus": "COMPLETED",
                    "rollbackStartedAt": "2023-10-03T12:20:00Z",
                    "rollbackEndedAt": "2023-10-04T12:23:59Z",
                },
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_all
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?status=CANCELED&startedAtSince=2023-10-02T00:00:02Z&startedAtUntil=2023-10-03T00:00:00Z&endedAtSince=2023-10-02T12:24:01Z&endedAtUntil=2023-10-04T12:23:58Z",
        ],
    )
    def test_get_applystatus_list_success_when_end_date_end_out_of_range(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        # "applyID": "000000005e"（target）"applyID": "000000006f"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": "000000005e",
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_all
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?status=CANCELED&startedAtSince=2023-10-05T00:00:00Z&startedAtUntil=2023-10-06T00:00:00Z&endedAtSince=2023-10-05T00:00:00Z&endedAtUntil=2023-10-06T23:59:59Z",
        ],
    )
    def test_get_applystatus_list_success_when_boundary_value_of_end_date_end(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        # "applyID": "000000005e"、"applyID": "000000006f"（no target）
        get_list_assert_target_all = {
            "totalCount": 0,
            "count": 0,
            "applyResults": [],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_all
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?status=IN_PROGRESS",
        ],
    )
    def test_get_applystatus_list_success_when_status_specified(self, mocker, parameter_uri, init_db_instance, caplog):
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        get_list_assert_target_status = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "applyID": "000000001a",
                    "status": "IN_PROGRESS",
                    "startedAt": "2023-10-02T00:00:00Z",
                },
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_status
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?startedAtSince=2023-10-02T00:00:01Z&startedAtUntil=2023-10-02T00:00:02Z&endedAtSince=2023-10-02T12:24:00Z&endedAtUntil=2023-10-02T12:24:01Z",
        ],
    )
    def test_get_applystatus_list_success_when_time_equals_for_time_specification(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        get_list_assert_target_equal = {
            "totalCount": 2,
            "count": 2,
            "applyResults": [
                {
                    "status": "FAILED",
                    "applyID": "000000004d",
                    "startedAt": "2023-10-02T00:00:01Z",
                    "endedAt": "2023-10-02T12:24:00Z",
                },
                {
                    "status": "CANCELED",
                    "applyID": "000000005e",
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response["count"] == get_list_assert_target_equal["count"]
        assert get_response["totalCount"] == get_list_assert_target_equal["totalCount"]
        for a in get_response["applyResults"]:
            a in get_list_assert_target_equal["applyResults"]
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?startedAtSince=2023-10-02T00:00:02Z&startedAtUntil=2023-10-02T00:00:03Z&endedAtSince=2023-10-02T12:24:01Z&endedAtUntil=2023-10-02T12:24:02Z",
        ],
    )
    def test_get_applystatus_list_success_when_add_second_to_upper_time_limit(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        get_list_assert_target_plus1 = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": "000000005e",
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target_plus1
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?startedAtSince=2023-10-02T00:00:00Z&startedAtUntil=2023-10-02T00:00:01Z&endedAtSince=2023-10-02T12:23:59Z&endedAtUntil=2023-10-02T12:24:00Z",
        ],
    )
    def test_get_applystatus_list_success_when_subtract_second_from_lower_time_limit(
        self, mocker, parameter_uri, init_db_instance, caplog
    ):
        mocker.patch("logging.config.dictConfig")
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)

        get_list_assert_target_minus1 = {
            "totalCount": 2,
            "count": 2,
            "applyResults": [
                {
                    "status": "COMPLETED",
                    "applyID": "000000003c",
                    "startedAt": "2023-10-02T00:00:00Z",
                    "endedAt": "2023-10-02T12:23:59Z",
                },
                {
                    "status": "FAILED",
                    "applyID": "000000004d",
                    "startedAt": "2023-10-02T00:00:01Z",
                    "endedAt": "2023-10-02T12:24:00Z",
                },
            ],
        }

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response["count"] == get_list_assert_target_minus1["count"]
        assert get_response["totalCount"] == get_list_assert_target_minus1["totalCount"]
        for a in get_response["applyResults"]:
            a in get_list_assert_target_minus1["applyResults"]
        assert "Completed successfully." in caplog.text

    def test_get_applystatus_list_success_when_no_specified_sortby_and_orderby_and_count_offset(
        self, mocker, init_db_instance, caplog, docker_services
    ):
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger()
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/?status=IN_PROGRESS"
        response = client.get(request_uri)

        get_list_assert_target = {"totalCount": 1, "count": 1}
        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response["count"] == get_list_assert_target["count"]
        assert get_response["totalCount"] == get_list_assert_target["totalCount"]

        assert "Completed successfully." in caplog.text
        log_msg = json.loads(caplog.messages[11]).get("message")
        assert "ORDER BY startedAt desc " in log_msg
        assert "LIMIT 20 " in log_msg
        assert "OFFSET 0" in log_msg

    def test_get_applystatus_list_success_when_specified_offset_exceed_data_count_registered_database(
        self, mocker, init_db_instance, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/?offset=10"
        response = client.get(request_uri)

        get_list_assert_target = {"totalCount": 9, "count": 0, "applyResults": []}

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response == get_list_assert_target
        assert "Completed successfully." in caplog.text

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "?sortBy=endedAt",
            "?sortBy=startedAt",
            "?orderBy=asc",
            "?orderBy=desc",
            "?limit=10",
            "?limit=2",
            "?offset=0",
            "?offset=1",
        ],
    )
    def test_get_applystatus_listsuccess_when_specified_sortby_and_orderby_and_count_offset(
        self, mocker, parameter_uri: str, init_db_instance, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql)
        init_db_instance.commit()

        # act
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.get(request_uri)
        count = 9
        if parameter_uri[1:].startswith("offset"):
            count = count - int(parameter_uri[-1])
        if parameter_uri[1:].startswith("limit") and int(re.findall(r"\d+", parameter_uri)[0]) < 9:
            count = int(parameter_uri[-1])

        get_list_assert_target = {"totalCount": 9, "count": count}

        # assert
        assert response.status_code == 200

        get_response = json.loads(response.content.decode())
        assert get_response["count"] == get_list_assert_target["count"]
        assert get_response["totalCount"] == get_list_assert_target["totalCount"]

        assert "Completed successfully." in caplog.text


@pytest.mark.usefixtures("httpserver_listen_address")
class TestDeleteAPIServer:

    @pytest.mark.parametrize(
        ("insert_sql"),
        [
            (sql.get_list_insert_sql_3),
            (sql.get_list_insert_sql_4),
            (sql.get_list_insert_sql_5),
            (sql.get_list_insert_sql_6),
        ],
    )
    def test_delete_layoutapply_success(self, mocker, init_db_instance, insert_sql):
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
        init_db_instance.commit()

        # arrange

        request_uri = f"/cdim/api/v1/layout-apply/{applyid}"
        response = client.delete(request_uri)

        # assert

        assert response.status_code == 204

    @pytest.mark.parametrize(
        ("insert_sql"),
        [
            (sql.get_list_insert_sql_1),
            (sql.get_list_insert_sql_2),
            (sql.get_list_insert_sql_9),
        ],
    )
    def test_delete_layoutapply_failure_when_status_in_progress(self, insert_sql, mocker, init_db_instance):
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
        init_db_instance.commit()

        request_uri = f"/cdim/api/v1/layout-apply/{applyid}"
        response = client.delete(request_uri)

        # assert
        assert response.status_code == 409
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40024"
        assert (
            error_response["message"]
            == "Apply ID cannot be deleted because it is currently being running. Try later again."
        )

    @pytest.mark.parametrize(
        ("insert_sql"),
        [
            (sql.insert_delete_target_sql_8),
            (sql.insert_delete_target_sql_9),
        ],
    )
    def test_delete_layoutapply_failure_when_rollbackstatus_in_progress(self, insert_sql, init_db_instance):
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
        init_db_instance.commit()

        response = client.delete(f"/cdim/api/v1/layout-apply/{applyid}")
        # assert

        assert response.status_code == 409

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40024"
        assert (
            error_response["message"]
            == "Apply ID cannot be deleted because it is currently being running. Try later again."
        )

    def test_delete_layoutapply_failure_when_failed_db_connection(self, mocker):
        mocker.patch.object(DbAccess, "get_apply_status", side_effect=psycopg2.OperationalError)

        response = client.delete("/cdim/api/v1/layout-apply/012345678d")
        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40018"
        assert "Could not connect to ApplyStatusDB." in error_response["message"]

    def test_delete_layoutapply_failure_when_query_failure_occurred(self, mocker):
        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        # act
        response = client.delete("/cdim/api/v1/layout-apply/123456789a")

        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40019"
        assert "Query failed." in error_response["message"]

    def test_delete_layoutapply_failure_when_nonexistent_id(self, mocker, init_db_instance):

        response = client.delete("/cdim/api/v1/layout-apply/abcdeabcde")
        # assert
        assert response.status_code == 404
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40020"
        assert error_response["message"] == "Specified abcdeabcde is not found."

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "012345678g",
        ],
    )
    def test_delete_layoutapply_failure_when_invalid_parameter(self, parameter_uri):
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.delete(request_uri)
        # assert
        assert response.status_code == 400
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"


@pytest.mark.usefixtures("httpserver_listen_address")
class TestResumeAPIServer:

    @pytest.mark.usefixtures("hardwaremgr_fixture")
    def test_resume_layoutapply_success(self, mocker, init_db_instance):
        mocker.patch("layoutapply.server._exec_subprocess", return_value=(None, "return_data", 1))
        mocker.patch.object(DbAccess, "update_subprocess", return_value=None)
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_resumed_target_sql_1, vars=[applyid])
            init_db_instance.commit()
        # arrange
        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")

        # assert
        assert response.status_code == 202
        resume_response = json.loads(response.content.decode())
        assert resume_response["status"] == "IN_PROGRESS"

    def test_resume_layoutapply_success_when_rollbackstatus_suspended(self, mocker, init_db_instance):
        # arrange
        mocker.patch("layoutapply.server._exec_subprocess", return_value=(None, "return_data", 1))
        mocker.patch.object(DbAccess, "update_subprocess", return_value=None)
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_resumed_get_target_sql_4, vars=[applyid])
        init_db_instance.commit()
        # arrange

        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")
        # assert
        assert response.status_code == 202
        resume_response = json.loads(response.content.decode())
        assert resume_response["status"] == "CANCELED"
        assert resume_response["rollbackStatus"] == "IN_PROGRESS"

    def test_resume_layoutapply_success_when_rollbackstatus_completed(self, mocker, init_db_instance):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid])
        init_db_instance.commit()

        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")
        # assert
        assert response.status_code == 200
        resume_response = json.loads(response.content.decode())
        assert resume_response["status"] == "CANCELED"
        assert resume_response["rollbackStatus"] == "COMPLETED"
        sleep(5)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()
            pid = row.get("processid")
            if pid is not None:
                process = psutil.Process(pid)
                if process.is_running():
                    process.terminate()

    def test_resume_layoutapply_success_when_status_canceled(self, mocker, init_db_instance):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid])
        init_db_instance.commit()

        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")
        # assert
        assert response.status_code == 200
        resume_response = json.loads(response.content.decode())
        assert resume_response["status"] == "CANCELED"

    def test_resume_layoutapply_success_when_status_completed(self, mocker, init_db_instance):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_3, vars=[applyid])
        init_db_instance.commit()

        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")
        # assert
        assert response.status_code == 200
        resume_response = json.loads(response.content.decode())
        assert resume_response["status"] == "COMPLETED"

        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()
            pid = row.get("processid")
            if pid is not None:
                process = psutil.Process(pid)
                if process.is_running():
                    process.terminate()

    def test_resume_layoutapply_success_when_status_failed(self, mocker, init_db_instance):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_4, vars=[applyid])
            init_db_instance.commit()

        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")
        # assert
        assert response.status_code == 200
        resume_response = json.loads(response.content.decode())
        assert resume_response["status"] == "FAILED"

    def test_resume_layoutapply_failure_when_rollbackstatus_in_progress(self, mocker, init_db_instance):
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""
                    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES 
                    ('300000011b','CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','{"test": "pre_test"}','2023/10/02 00:00:00','2023/10/02 01:00:00','2023/10/02 00:30:00',TRUE,'IN_PROGRESS',null,'2023/10/02 00:40:00',null,'[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',null,null,null,null,'2023/10/02 00:50:00',null);
                """
            )
        init_db_instance.commit()

        response = client.put("/cdim/api/v1/layout-apply/300000011b?action=resume")
        # assert
        assert response.status_code == 409
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40022"
        assert error_response["message"] == "This layoutapply has already executed."

    def test_resume_layoutapply_failure_when_status_in_progress(self, mocker, init_db_instance):
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
        init_db_instance.commit()

        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")
        # assert
        assert response.status_code == 409
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40022"
        assert error_response["message"] == "This layoutapply has already executed."

    def test_resume_layoutapply_failure_when_failed_db_connection(self, mocker):
        mocker.patch.object(DbAccess, "proc_resume", side_effect=psycopg2.OperationalError)

        response = client.put("/cdim/api/v1/layout-apply/000000001a?action=resume")
        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40018"
        assert "Could not connect to ApplyStatusDB." in error_response["message"]

    def test_resume_layoutapply_failure_when_query_failure_occurred(self, mocker):
        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)

        # psycopg2.extras.DictCursor is mocked
        mock_dictcursor = mocker.MagicMock()
        mock_dictcursor.__enter__.return_value = mock_cursor
        mocker.patch.object(psycopg2.extras, "DictCursor", return_value=mock_dictcursor)

        # act
        response = client.put("/cdim/api/v1/layout-apply/000000001a?action=resume")

        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40019"
        assert "Query failed." in error_response["message"]

    def test_resume_layoutapply_failure_when_nonexistent_id(self, mocker, init_db_instance, docker_services):

        response = client.put("/cdim/api/v1/layout-apply/abcdeabcde?action=resume")
        # assert
        assert response.status_code == 404
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40020"
        assert error_response["message"] == "Specified abcdeabcde is not found."

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "012345678g?action=resume",
            "012345678a?action=resuma",
        ],
    )
    def test_resume_layoutapply_failure_when_invalid_parameter(self, parameter_uri):
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri

        response = client.put(request_uri)
        # assert
        assert response.status_code == 400
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    def test_resume_layoutapply_failure_when_failed_to_load_config_file(self, mocker, init_db_instance):

        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )

        response = client.put("/cdim/api/v1/layout-apply/012345678a?action=resume")
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert "Failed to load layoutapply_config.yaml." in error_response["message"]

    def test_resume_layoutapply_failure_when_failed_to_load_log_config_file(self, mocker):
        mocker.patch.object(LayoutApplyLogConfig, "_validate_log_dir", side_effect=[Exception("Dummy message")])

        # arrange
        response = client.put("/cdim/api/v1/layout-apply/012345678a?action=resume")
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_log_config.yaml.\n('Dummy message',)"

    def test_resume_layoutapply_failure_when_failed_to_start_subprocess(self, mocker, init_db_instance, caplog):
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""
                    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES 
                    ('300000006d','SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,null,null,null,null,'{"procedures": [{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]}',null,null,null,null,'2023/10/02 12:23:59',null);
                """
            )
        init_db_instance.commit()
        # psycopg2.connect is mocked
        mocker.patch(
            "multiprocessing.Process.start",
            side_effect=Exception(),
        )

        response = client.put("/cdim/api/v1/layout-apply/300000006d?action=resume")

        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40026"
        assert "Failed to start subprocess. " in error_response["message"]
        assert "[E40026]Failed to start subprocess." in caplog.text

    def test_resume_layoutapply_failure_when_failed_to_start_subprocess_in_suspended(
        self, mocker, init_db_instance, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""
                    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES 
                    ('300000021a','CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','{"test": "pre_test"}','2023/10/02 00:00:00','2023/10/02 01:00:00','2023/10/02 00:30:00',TRUE,'SUSPENDED',null,'2023/10/02 00:40:00',null,'[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',null,null,null,null,'2023/10/02 00:50:00',null);
                """
            )
        init_db_instance.commit()
        # psycopg2.connect is mocked
        mocker.patch(
            "multiprocessing.Process.start",
            side_effect=Exception(),
        )

        response = client.put("/cdim/api/v1/layout-apply/300000021a?action=resume")
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="DELETE FROM applystatus WHERE applyid = '300000021a'")
        init_db_instance.commit()

        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40026"
        assert "Failed to start subprocess. " in error_response["message"]
        assert "[E40026]Failed to start subprocess." in caplog.text

    def test_main_traceback_not_output_when_server_shutdown(self, mocker):
        # arrange
        mockup = mocker.patch("layoutapply.server.uvicorn.run", side_effect=KeyboardInterrupt)

        main()

        # assert
        # confirm that no unexpected exceptions have occurred during server shutdown.
        assert mockup.call_count == 1


@pytest.fixture()
def get_applyID():
    return "".join([secrets.choice(string.hexdigits) for i in range(10)]).lower()


@pytest.mark.usefixtures("httpserver_listen_address")
class TestMigrateAPIServer:

    @pytest.mark.usefixtures("migration_server_fixture")
    def test_execute_migration_success(self, init_db_instance):
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("migration_server_fixture_multi")
    def test_execute_migration_success_when_multiple_current_nodes(self, init_db_instance):
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("migration_server_fixture")
    def test_execute_migration_success_when_node_empty(self, init_db_instance):
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA_EMPTY)
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("migration_server_fixture_nodeid_specified")
    def test_execute_migration_success_when_nodeid_specified(self, init_db_instance):
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA_WITH_TARGETNODEID)
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("migration_server_fixture_nodeid_specified")
    def test_execute_migration_success_when_nodeid_specified_multi(self, init_db_instance):
        # arrange
        response = client.post(
            "/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA_WITH_TARGETNODEID_MULTIPLE
        )
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("migration_server_fixture_nodeid_specified")
    def test_execute_migration_success_when_nodeid_empty(self, init_db_instance):
        # arrange
        response = client.post(
            "/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA_WITH_TARGETNODEID_EMPTY
        )
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("get_available_resources_nothing_bound_devices")
    def test_execute_migration_success_when_bound_device_nothing(self, init_db_instance):
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("migration_server_fixture_nodeid_specified")
    def test_execute_migration_failure_when_nodeid_invalid(self, init_db_instance):
        # arrange
        response = client.post(
            "/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA_WITH_TARGETNODEID_INVALID
        )

        # assert
        assert response.status_code == 404
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50010"

    def test_execute_migration_failure_when_failed_to_load_config_file(self, mocker):

        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50002"
        assert "Failed to load layoutapply_config.yaml." in error_response["message"]

    def test_execute_migration_failure_when_failed_to_load_log_config_file(self, mocker):
        mocker.patch.object(LayoutApplyLogConfig, "_validate_log_dir", side_effect=[Exception("Dummy message")])

        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        # assert

        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50002"
        assert "Failed to load layoutapply_log_config.yaml." in error_response["message"]

    @pytest.mark.parametrize("layout", checkvalid.newLayout_without_required_key)
    def test_execute_migration_failure_when_no_required_key(self, layout):
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=layout)
        # assert
        assert response.status_code == 400
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50001"

    @pytest.mark.parametrize("layout", checkvalid.newLayout_invalid_data_type)
    def test_execute_migration_failure_when_invalid_data_type(self, layout):
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=layout)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50001"

    @pytest.mark.parametrize("layout", checkvalid.newLayout_invalid_value)
    def test_execute_migration_failure_when_invalid_value(self, layout):
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=layout)

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50001"

    @pytest.mark.usefixtures("migration_server_fixture")
    @pytest.mark.parametrize("layout", checkvalid.newLayout_unkown_device)
    def test_execute_migration_success_when_unknown_device(self, layout, init_db_instance):
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=layout)
        resp_data = json.loads(response.content)
        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None

    @pytest.mark.usefixtures("conf_manager_server_err_fixture")
    def test_execute_migration_failure_when_config_info_management_api_failure(self, mocker, caplog):
        mocker.patch("logging.config.dictConfig")

        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        body = json.loads(response.content.decode())
        api_err_msg = {
            "code": "xxxx",
            "message": "Failed to access to DB",
        }

        # assert
        assert body.get("code") == "E50004"
        assert body.get("message") == f"Failed to request: status:[500], response[{api_err_msg}]"
        assert "[E50004]Failed to request:" in caplog.text

    @pytest.mark.usefixtures("migration_server_err_fixture")
    def test_execute_migration_failure_when_migration_step_generation_api_failure(
        self, httpserver, docker_services, mocker, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        httpserver.expect_request(re.compile(rf"\/cdim/api\/v1\/{CONF_NODES_URL}"), method="GET").respond_with_response(
            Response(
                bytes(json.dumps(migration.CONF_NODES_API_RESP_DATA), encoding="utf-8"),
                status=200,
            )
        )
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        body = json.loads(response.content.decode())
        api_err_msg = {
            "code": "xxxx",
            "message": "desiredLayout is a required property.",
        }
        httpserver.clear()

        # assert
        assert body.get("code") == "E50004"
        assert body.get("message") == f"Failed to request: status:[500], response[{api_err_msg}]"
        assert "[E50004]Failed to request:" in caplog.text

    def test_execute_migration_failure_when_failed_to_load_secret_file(self, mocker, init_db_instance):
        # arrange
        mocker.patch.object(LayoutApplyConfig, "_get_secret", side_effect=[Exception("Dummy message")])

        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50008"

    @pytest.mark.parametrize(
        "log_config",
        [
            {
                "version": 1,
                "formatters": {
                    "standard": {
                        "format": "%(asctime)s %(levelname)s %(message)s",
                        "datefmt": "%Y/%m/%d %H:%M:%S.%f",
                    }
                },
                "handlers": {
                    "file": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "level": "INFO",
                        "formatter": "standard",
                        "filename": "test/test",
                        "maxBytes": 100000000,
                        "backupCount": 72,
                        "encoding": "utf-8",
                    },
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO",
                        "formatter": "standard",
                        "stream": "ext://sys.stdout",
                    },
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["file", "console"],
                },
            }
        ],
    )
    def test_execute_migration_failure_when_failed_to_initialize_logger(
        self, mocker, log_config, init_db_instance, docker_services
    ):

        mocker.patch.object(LayoutApplyLogConfig, "log_config", log_config)

        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50009"

    @pytest.mark.usefixtures("get_available_resources_err_fixture")
    def test_execute_migration_failure_when_get_available_resources_api_failure(
        self, init_db_instance, docker_services, mocker, caplog
    ):
        mocker.patch("logging.config.dictConfig")

        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        body = json.loads(response.content.decode())
        api_err_msg = {
            "code": "xxxx",
            "message": "Failed to access to DB",
        }

        # assert
        assert body.get("code") == "E50004"
        assert body.get("message") == f"Failed to request: status:[500], response[{api_err_msg}]"
        "[E50004]Failed to request:" in caplog.text
