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
"""Test for delete command"""

import re
import sys

import psycopg2
import pytest
from psycopg2.extras import DictCursor

from layoutapply.cli import main
from layoutapply.const import ExitCode, IdParameter
from layoutapply.db import DbAccess
from layoutapply.util import create_randomname
from tests.layoutapply.test_data import sql


class TestHelp:
    """Test cases for the help command."""

    @pytest.mark.parametrize(
        "args",
        [
            (
                [
                    "delete",
                    "--help",
                ]
            ),
            (
                [
                    "delete",
                    "-h",
                ]
            ),
        ],
    )
    def test_cmd_delete_success_when_help(
        self,
        args,
        capfd,
    ):
        """Test delete command help message."""
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0
        out, _ = capfd.readouterr()

        # help message is displayed in the standard output
        assert "usage" in out
        assert "options:" in out
        assert "-h" in out
        assert "--help" in out
        assert "--apply-id" in out
        assert "APPLY_ID" in out
        assert "specified applyID for delete. applyID as a string." in out


@pytest.mark.usefixtures("httpserver_listen_address")
class TestDeleteSuccess:
    """Test cases for the delete command when it succeeds."""

    @pytest.mark.parametrize(
        ("insert_sql"),
        [
            (sql.get_list_insert_sql_3),
            (sql.get_list_insert_sql_4),
            (sql.get_list_insert_sql_5),
            (sql.get_list_insert_sql_6),
        ],
    )
    def test_cmd_delete_success_when_id_not_in_execution(self, init_db_instance, insert_sql, capfd):
        """Test delete command success when the apply ID is not in execution."""
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()
        assert_print = "Success.\n"

        args = ["delete", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # message indicating the change in reflection status due to cancellation is output to the standard output.
        assert out == assert_print
        # There is no standard error output.
        assert err == ""


class TestDeleteFailure:
    """Test cases for the delete command when it fails."""

    @pytest.mark.parametrize(
        ("insert_sql"),
        [
            (sql.get_list_insert_sql_1),
            (sql.get_list_insert_sql_2),
            (sql.get_list_insert_sql_7),
        ],
    )
    def test_cmd_delete_failure_when_id_in_execution(self, init_db_instance, insert_sql, capfd):
        """Test delete command failure when the apply ID is currently in execution."""
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()
        assert_print = "[E40024]Apply ID cannot be deleted because it is currently being running. Try later again.\n"

        args = ["delete", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.DELETE_CONFLICT_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # standard error outputs the E40024 error.
        assert err == assert_print

    @pytest.mark.parametrize(
        ("insert_sql", "r_insert_sql"),
        [
            (sql.insert_delete_target_sql_8, sql.insert_delete_target_sql_r_8),
            (sql.insert_delete_target_sql_9, sql.insert_delete_target_sql_r_9),
        ],
    )
    def test_cmd_delete_failure_when_rollback_id_in_progress(self, init_db_instance, insert_sql, r_insert_sql, capfd):
        """Test delete command failure when the rollback ID is currently in progress."""

        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            cursor.execute(query=r_insert_sql, vars=[applyid])
            init_db_instance.commit()

        assert_print = "[E40024]Apply ID cannot be deleted because it is currently being running. Try later again.\n"

        args = ["delete", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.DELETE_CONFLICT_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # standard error outputs the E40024 error.
        assert err == assert_print

    @pytest.mark.parametrize("args", [["delete", "--apply-id", "012345678g"]])
    def test_cmd_delete_failure_when_invalid_option(self, args, capfd):
        """Test delete command failure when an invalid option is provided."""
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.VALIDATION_ERR
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert err.startswith("[E40001]")

    @pytest.mark.parametrize("args", [["delete", "--apply-id", "012345678a"]])
    def test_cmd_delete_failure_when_invalid_config_file(self, mocker, args, capfd):
        """Test delete command failure when the configuration file is invalid."""
        config = {
            "log": {
                "logging_level": "INFO",
                "log_dir": "./",
                "rotation_size": 1000000,
                "backup_files": 3,
            },
            "layout_apply": {
                "host": "0.0.0.0",
                "port": 8003,
            },
            "db": {
                "dbname": "ApplyStatusDB",
                "user": "user01",
                "password": "P@ssw0rd",
                "host": "localhost",
                "port": 5432,
            },
            "hardware_control": {
                # No required item
                # "host": "localhost",
                "port": 8888,
                "uri": "api/v1",
                "disconnect": {
                    "retry": {
                        "interval": 5,
                        "max_count": 5,
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                            },
                        ],
                        "skip": [
                            {"status_code": 400, "code": "EF003BAS010"},
                        ],
                    }
                },
            },
            "message_broker": {
                "host": "localhost",
                "port": 3500,
                "pubsub": "layout_apply_apply",
                "topic": "layout_apply_apply.completed",
            },
        }

        mocker.patch("yaml.safe_load").return_value = config
        sys.argv = ["cli.py", *args]

        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert

        assert excinfo.value.code == 2
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # There is an error message in the standard error output that starts with the specified error code
        regex = re.compile(r"^\[E40002\]Failed to load layoutapply_config.yaml.")
        assert regex.search(err)

    @pytest.mark.parametrize("args", [["delete", "--apply-id", "012345678a"]])
    def test_cmd_delete_failure_when_failed_db_connection(self, mocker, args, capfd):
        """Test delete command failure when the database connection cannot be established."""
        assert_print = "[E40018]Could not connect to ApplyStatusDB."
        mocker.patch.object(DbAccess, "get_apply_status", side_effect=psycopg2.OperationalError)
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.DB_CONNECT_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""

        assert assert_print in err

    @pytest.mark.parametrize("args", [["delete", "--apply-id", "012345678d"]])
    def test_cmd_delete_failure_when_query_failure_occurred(self, mocker, args, capfd):
        """Test delete command failure when a query failure occurs."""
        assert_print = "[E40019]Query failed."
        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.QUERY_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # error E40019 is output to the standard error.
        assert assert_print in err

    @pytest.mark.parametrize("args", [["delete", "--apply-id", "abcdeabcde"]])
    def test_cmd_delete_failure_when_nonexistent_id(
        self, init_db_instance, args, capfd, docker_services
    ):  # pylint: disable=unused-argument
        """Test delete command failure when the specified apply ID does not exist."""
        assert_print = "[E40020]Specified abcdeabcde is not found.\n"

        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.ID_NOT_FOUND_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # standard error outputs the E40020 error.
        assert err == assert_print
