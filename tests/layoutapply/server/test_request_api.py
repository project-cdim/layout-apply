# Copyright (C) 2026 NEC Corporation.
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
import logging  # pylint: disable=W0611 # noqa:F401
import re
from logging.config import dictConfig  # pylint: disable=W0611 # noqa:F401
from multiprocessing import Process  # pylint: disable=W0611 # noqa:F401
from time import sleep

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extras import DictCursor

from layoutapply.const import IdParameter
from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.db import DbAccess
from layoutapply.server import app, main
from layoutapply.setting import LayoutApplyConfig, LayoutApplyLogConfig
from layoutapply.util import create_randomname
from tests.layoutapply.test_data import checkvalid, procedure, sql

client = TestClient(app)


@pytest.mark.usefixtures("httpserver_listen_address")
class TestAPIServerSuccess:
    """Test cases for successful API server responses."""

    @pytest.mark.parametrize(("procedures", "sleep_time", "applyID"), procedure.multi_pattern)
    def test_execute_layoutapply_success(
        self, mocker, sleep_time, procedures, init_db_instance, applyID, docker_services
    ):  # pylint: disable=W0613,C0103
        """Test successful execution of layout apply."""
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
        sleep_time,
        procedures,
        init_db_instance,
    ):
        """Test execution of layout apply when migration steps are empty."""
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
        details = row.get("result")
        assert details == []
        assert len(details) == len(procedures["procedures"])

    @pytest.mark.parametrize(("procedures", "sleep_time"), procedure.proc_empty_pattern)
    @pytest.mark.usefixtures("hardwaremgr_fixture")
    def test_execute_layoutapply_does_not_start_subprocess_when_empty_migration_step(
        self,
        mocker,
        sleep_time,
        procedures,
        init_db_instance,
    ):
        """Test that subprocess functions are not called when migration steps are empty."""
        exec_subprocess_mock = mocker.patch("layoutapply.server._exec_subprocess")
        update_subprocess_mock = mocker.patch.object(DbAccess, "update_subprocess")

        sleep(sleep_time)
        response = client.post("/cdim/api/v1/layout-apply", json=procedures)

        # assert
        assert response.status_code == 202
        exec_subprocess_mock.assert_not_called()
        update_subprocess_mock.assert_not_called()


class TestAPIServerFailure:
    """Test cases for API server responses when failures occur."""

    @pytest.mark.parametrize("procedures", checkvalid.without_required_key)
    def test_execute_layoutapply_failure_when_no_required_key(self, procedures):
        """Test execution of layout apply failure when no required key is provided."""

        response = client.post("/cdim/api/v1/layout-apply", json=procedures)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    @pytest.mark.parametrize("procedures", checkvalid.any_key_combination)
    def test_execute_layoutapply_failure_when_any_key_combination(self, procedures):
        """Test execution of layout apply failure when any key combination is provided."""
        response = client.post("/cdim/api/v1/layout-apply", json=procedures)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    @pytest.mark.parametrize("procedures", checkvalid.invalid_data_type)
    def test_execute_layoutapply_failure_when_invalid_data_type(self, procedures):
        """Test execution of layout apply failure when invalid data type is provided."""

        response = client.post("/cdim/api/v1/layout-apply", json=procedures)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    @pytest.mark.parametrize("procedures", checkvalid.invalid_value)
    def test_execute_layoutapply_failure_when_invalid_value(self, procedures):
        """Test execution of layout apply failure when invalid value is provided."""

        response = client.post("/cdim/api/v1/layout-apply", json=procedures)
        # assert

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    def test_execute_layoutapply_failure_when_failed_to_load_config_file(self, mocker):
        """Test execution of layout apply failure when failed to load config file."""
        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )

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

    def test_execute_layoutapply_failure_when_failed_to_load_log_config_file(self, mocker):
        """Test execution of layout apply failure when failed to load log config file."""
        mocker.patch.object(LayoutApplyLogConfig, "_validate_log_dir", side_effect=[Exception("Dummy message")])

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
        """Test execution of layout apply main failure when failed to load config file."""
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

    def test_execute_layoutapply_failure_when_failure_to_load_secret_file(self, mocker):
        """Test execution of layout apply failure when failure to load secret file."""
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
    def test_execute_layoutapply__failure_when_failed_to_initialize_logger(self, mocker, log_config):
        """Test execution of layout apply failure when failed to initialize logger."""
        mocker.patch.object(LayoutApplyLogConfig, "log_config", log_config)

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
        """Test execution of layout apply failure when query failure occurred."""
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

    def test_execute_layoutapply_failure_when_failed_db_connection(self, mocker):
        """Test execution of layout apply failure when failed to connect to the database."""
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
        init_db_instance,
    ):
        """Test execution of layout apply failure when failed on lock."""
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
        init_db_instance,
    ):
        """Test execution of layout apply failure when in-progress data exists."""
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_delete_target_sql_8, vars=[applyid])
            cursor.execute(query=sql.insert_delete_target_sql_r_8, vars=[applyid])
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
        sleep_time,
        applyID,
        procedures,
        init_db_instance,
    ):  # pylint: disable=W0613, C0103
        """Test execution of layout apply failure when suspended data exists."""
        # arrange
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="""
                    INSERT into applystatus (applyid, status, procedures, result, rollbackprocedures,\
                    startedat, endedat, canceledat, executerollback, resumeprocedures, processid,\
                    executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000008c','SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, \
                    {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,\
                    '{"procedures": [{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001",\
                    "dependencies": []}]}',null,null,null,'2023/10/02 12:23:59',null);
                """)
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
        sleep_time,
        applyid,
        procedures,
        init_db_instance,
    ):
        """Test execution of layout apply failure when rollback suspended data exists."""
        # arrange
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_delete_target_sql_9, vars=[applyid])
            cursor.execute(query=sql.insert_delete_target_sql_r_9, vars=[applyid])
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
    ):  # pylint: disable=W0613, C0103
        """Test execution of layout apply failure when failed to start subprocess."""
        mocker.patch("logging.config.dictConfig")

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
