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
from multiprocessing import Process

import psutil
import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extras import DictCursor

from layoutapply.const import IdParameter, Result
from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.db import DbAccess
from layoutapply.server import app
from layoutapply.setting import LayoutApplyLogConfig
from layoutapply.util import create_randomname
from tests.layoutapply.conftest import mock_run
from tests.layoutapply.test_data import sql

client = TestClient(app)


@pytest.mark.usefixtures("httpserver_listen_address")
class TestCancelAPIServerSuccess:
    """Test cases for successful cancellation of layout apply."""

    def test_cancel_layoutapply_success(self, init_db_instance):
        """Test successful cancellation of a layout apply."""
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
            query_str = """INSERT INTO applystatus
                (applyid, status, processid, executioncommand, processstartedat)
                VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(
                query=query_str, vars=(apply_id, Result.IN_PROGRESS, proc.pid, "".join(execution_cmd), process_start)
            )
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

    def test_cancel_layoutapply_success_when_canceled_data_targeted(self, init_db_instance):
        """Test successful cancellation when the targeted data is already canceled."""
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

    def test_cancel_layoutapply_success_when_suspended_rollback_data(self, init_db_instance):
        """Test successful cancellation when there is suspended rollback data."""
        # Data adjustment before testing.
        apply_id = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            query_str = """INSERT INTO applystatus
                (applyid, status)
                VALUES (%s, %s)"""
            r_query_str = """INSERT INTO rollbackstatus
                (applyid, status)
                VALUES (%s, %s)"""
            cursor.execute(query=query_str, vars=(apply_id, Result.CANCELED))
            cursor.execute(query=r_query_str, vars=(apply_id, Result.SUSPENDED))
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
        self, init_db_instance, rollbackStatus
    ):  # pylint: disable=C0103
        """Test successful cancellation when the rollback status is either completed or failed."""
        # Data adjustment before testing.
        apply_id = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            query_str = """INSERT INTO applystatus
                (applyid, status)
                VALUES (%s, %s)"""
            r_query_str = """INSERT INTO rollbackstatus
                (applyid, status)
                VALUES (%s, %s)"""
            cursor.execute(query=query_str, vars=(apply_id, Result.CANCELED))
            cursor.execute(query=r_query_str, vars=(apply_id, rollbackStatus))
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
class TestCancelAPIServerFailure:
    """Test cases for cancel API server failures."""

    def test_cancel_layoutapply_becomes_failed_when_suspended_data_targeted(self, init_db_instance):
        """Test cancellation failure when the targeted data is suspended."""
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

    def test_cancel_layoutapply_failure_when_completed_data_targeted(self, init_db_instance):
        """Test cancellation failure when the targeted data has already been completed."""
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
        """Test cancellation failure when the database connection fails."""
        mocker.patch.object(DbAccess, "proc_cancel", side_effect=psycopg2.OperationalError)
        response = client.put("/cdim/api/v1/layout-apply/012345678d?action=cancel")
        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40018"
        assert "Could not connect to ApplyStatusDB." in error_response["message"]

    def test_cancel_layoutapply_failure_when_query_failure_occurred(self, mocker):
        """Test cancellation failure when a query failure occurs."""
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

    def test_cancel_layoutapply_failure_when_nonexistent_id(self, init_db_instance):  # pylint: disable=unused-argument
        """Test cancellation failure when the specified applyID does not exist."""

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
        """Test cancellation failure when invalid parameters are provided."""
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.put(request_uri)

        # assert
        assert response.status_code == 400
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    def test_cancel_layoutapply_failure_when_failed_to_load_config_file(self, mocker):
        """Test cancellation failure when the configuration file fails to load."""

        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )
        response = client.put("/cdim/api/v1/layout-apply/012345678a?action=cancel")

        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert "Failed to load layoutapply_config.yaml." in error_response["message"]

    def test_cancel_layoutapply_failure_when_failed_to_load_log_config_file(self, mocker):
        """Test cancellation failure when the log configuration file fails to load."""
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
        self, init_db_instance, execution_command, process_startedat
    ):
        """Test cancellation failure when the subprocess is not found."""

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
            query_str = """INSERT INTO applystatus
                (applyid, status, processid, executioncommand, processstartedat)
                VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(
                query=query_str,
                vars=(apply_id, Result.IN_PROGRESS, proc.pid, register_executioncommand, register_processstartedat),
            )
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

    def test_cancel_layoutapply_failure_when_rollback_data_in_progress(self, init_db_instance):
        """Test cancellation failure when rollback data is in progress."""
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
            query_str = """INSERT INTO applystatus
                (applyid, status)
                VALUES (%s, %s)"""
            r_query_str = """INSERT INTO rollbackstatus
                (applyid, status, processid, executioncommand, processstartedat)
                VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(query=query_str, vars=(apply_id, Result.CANCELED))
            cursor.execute(
                query=r_query_str, vars=(apply_id, Result.IN_PROGRESS, proc.pid, "".join(execution_cmd), process_start)
            )
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
        self, init_db_instance, execution_command, process_startedat
    ):
        """Test cancellation failure when the rollback process and subprocess are not found."""

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
            query_str = """INSERT INTO applystatus
                (applyid, status)
                VALUES (%s, %s)"""
            r_query_str = """INSERT INTO rollbackstatus
                (applyid, status, processid, executioncommand, processstartedat)
                VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(query=query_str, vars=(apply_id, Result.CANCELED))
            cursor.execute(
                query=r_query_str,
                vars=(apply_id, Result.IN_PROGRESS, proc.pid, register_executioncommand, register_processstartedat),
            )
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
            == "Since the process with the specified ID does not exist,"
            + " change the rollbackStatus from IN_PROGRESS to FAILED."
        )
        assert cancel_response["status"] == "CANCELED"
        assert cancel_response["rollbackStatus"] == "FAILED"

        if proc.is_alive():
            proc.terminate()
            proc.join()
