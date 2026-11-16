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
"""Test for delete api"""

import json

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extras import DictCursor

from layoutapply.const import IdParameter
from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.db import DbAccess
from layoutapply.server import app
from layoutapply.setting import LayoutApplyLogConfig
from layoutapply.util import create_randomname
from tests.layoutapply.test_data import sql

client = TestClient(app)


@pytest.mark.usefixtures("httpserver_listen_address")
class TestDeleteAPIServerSuccess:
    """Test class for successful deletion of layout apply."""

    @pytest.mark.parametrize(
        ("insert_sql, rollback_sql"),
        [
            (sql.get_list_insert_sql_3, ""),
            (sql.get_list_insert_sql_4, ""),
            (sql.get_list_insert_sql_5, ""),
            (sql.get_list_insert_sql_6, sql.get_list_insert_sql_r_6),
            (sql.get_list_insert_sql_6, sql.get_list_insert_sql_r_6_failed),
        ],
    )
    def test_delete_layoutapply_success(self, init_db_instance, insert_sql, rollback_sql):
        """Test successful deletion of layout apply."""
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            if rollback_sql:
                cursor.execute(query=rollback_sql, vars=[applyid])
        init_db_instance.commit()

        # arrange

        request_uri = f"/cdim/api/v1/layout-apply/{applyid}"
        response = client.delete(request_uri)

        # assert

        assert response.status_code == 204
        get_response = client.get(request_uri)
        assert get_response.status_code == 404


@pytest.mark.usefixtures("httpserver_listen_address")
class TestDeleteAPIServerFailure:
    """Test class for failure scenarios of deletion of layout apply."""

    @pytest.mark.parametrize(
        ("insert_sql"),
        [
            (sql.get_list_insert_sql_1),
            (sql.get_list_insert_sql_2),
            (sql.get_list_insert_sql_9),
        ],
    )
    def test_delete_layoutapply_failure_when_status_in_progress(self, insert_sql, init_db_instance):
        """Test deletion failure when the status is in progress."""
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
        ("insert_sql, rollback_sql"),
        [
            (sql.insert_delete_target_sql_8, sql.insert_delete_target_sql_r_8),
            (sql.insert_delete_target_sql_9, sql.insert_delete_target_sql_r_9),
        ],
    )
    def test_delete_layoutapply_failure_when_rollbackstatus_in_progress(
        self, insert_sql, rollback_sql, init_db_instance
    ):
        """Test deletion failure when the rollback status is in progress."""
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            cursor.execute(query=rollback_sql, vars=[applyid])
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
        """Test deletion failure when the database connection fails."""
        mocker.patch.object(DbAccess, "get_apply_status", side_effect=psycopg2.OperationalError)

        response = client.delete("/cdim/api/v1/layout-apply/012345678d")
        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40018"
        assert "Could not connect to ApplyStatusDB." in error_response["message"]

    def test_delete_layoutapply_failure_when_query_failure_occurred(self, mocker):
        """Test deletion failure when a query failure occurs."""
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

    def test_delete_layoutapply_failure_when_nonexistent_id(self, init_db_instance):  # pylint: disable=unused-argument
        """Test deletion failure when the specified ID does not exist."""

        response = client.delete("/cdim/api/v1/layout-apply/abcdeabcde")
        # assert
        assert response.status_code == 404
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40020"
        assert error_response["message"] == "Specified abcdeabcde is not found."

    @pytest.mark.parametrize(
        "parameter_uri",
        [
            "012345678g",  # non-hex character
            "123456789",  # 9 chars (too short)
            "0123456789a",  # 11 chars (too long)
            "ABCDEF1234",  # uppercase not allowed by pattern
            "01234-6789",  # symbol included
        ],
    )
    def test_delete_layoutapply_failure_when_invalid_parameter(self, parameter_uri):
        """Test deletion failure when the parameter is invalid."""
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri
        response = client.delete(request_uri)
        # assert
        assert response.status_code == 400
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    def test_delete_layoutapply_failure_when_failed_to_load_config_file(self, mocker):
        """Test deletion failure when server config cannot be loaded."""
        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )

        response = client.delete("/cdim/api/v1/layout-apply/012345678a")

        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_config.yaml.\n('Dummy message',)"

    def test_delete_layoutapply_failure_when_failed_to_load_log_config_file(
        self, mocker, docker_services
    ):  # pylint: disable=W0613
        """Test deletion failure when log config cannot be loaded."""
        mocker.patch.object(LayoutApplyLogConfig, "_validate_log_dir", side_effect=[Exception("Dummy message")])

        response = client.delete("/cdim/api/v1/layout-apply/012345678a")

        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_log_config.yaml.\n('Dummy message',)"
