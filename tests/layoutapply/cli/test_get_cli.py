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
"""Test for command"""

import copy
import json
import logging
import logging.config  # pylint:disable=unused-import
import os
import re
import sys
import tempfile

import psycopg2
import pytest
from psycopg2.extras import DictCursor

from layoutapply.cli import main
from layoutapply.const import ExitCode, IdParameter, Result
from layoutapply.db import DbAccess
from layoutapply.util import create_randomname
from tests.layoutapply.test_data import sql

get_list_assert_target = {
    "count": 9,
    "applyResults": [
        {
            "applyID": "000000001a",
            "status": "IN_PROGRESS",
            "startedAt": "2023-10-02T00:00:00Z",
            "procedures": {"procedures": "pre_test"},
        },
        {
            "status": "CANCELING",
            "applyID": "000000002b",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": True,
            "procedures": {"procedures": "pre_test"},
            "result": [{"test": "test"}, {"test": "test"}],
            "rollbackProcedures": {"procedures": "test"},
        },
        {
            "status": "COMPLETED",
            "applyID": "000000003c",
            "procedures": {"procedures": "pre_test"},
            "result": [{"test": "test"}, {"test": "test"}],
            "startedAt": "2023-10-02T00:00:00Z",
            "endedAt": "2023-10-02T12:23:59Z",
        },
        {
            "status": "FAILED",
            "applyID": "000000004d",
            "procedures": {"procedures": "pre_test"},
            "result": [{"test": "test"}, {"test": "test"}],
            "startedAt": "2023-10-02T00:00:01Z",
            "endedAt": "2023-10-02T12:24:00Z",
        },
        {
            "status": "CANCELED",
            "applyID": "000000005e",
            "procedures": {"procedures": "pre_test"},
            "result": [{"test": "test"}, {"test": "test"}],
            "rollbackProcedures": {"procedures": "test"},
            "startedAt": "2023-10-02T00:00:02Z",
            "endedAt": "2023-10-02T12:24:01Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": False,
        },
        {
            "status": "CANCELED",
            "applyID": "000000006f",
            "procedures": {"procedures": "pre_test"},
            "result": [{"test": "test"}, {"test": "test"}],
            "rollbackProcedures": {"procedures": "test"},
            "startedAt": "2023-10-03T00:00:00Z",
            "endedAt": "2023-10-04T12:23:59Z",
            "canceledAt": "2023-10-03T12:00:00Z",
            "executeRollback": True,
        },
        {
            "status": "CANCELING",
            "applyID": "000000007a",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": True,
            "procedures": {"procedures": "pre_test"},
            "result": [{"test": "test"}, {"test": "test"}],
            "rollbackProcedures": {"procedures": "test"},
        },
        {
            "status": "CANCELING",
            "applyID": "000000008b",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": False,
            "procedures": {"procedures": "pre_test"},
            "result": [{"test": "test"}, {"test": "test"}],
        },
        {
            "status": "SUSPENDED",
            "applyID": "000000009c",
            "procedures": {"procedures": "pre_test"},
            "result": [{"test": "test"}, {"test": "test"}],
            "startedAt": "2023-10-02T00:00:01Z",
            "resumeProcedures": {"procedures": "pre_test"},
            "suspendedAt": "2024-01-02T12:23:00Z",
        },
    ],
}


get_list_assert_target_default = {
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
        },
        {
            "status": "CANCELING",
            "applyID": "000000007a",
            "startedAt": "2023-10-01T23:59:59Z",
            "canceledAt": "2023-10-02T12:00:00Z",
            "executeRollback": True,
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


@pytest.fixture()
def get_list_assert_target_no_fields():
    """Fixture that returns a version of get_list_assert_target with no procedures for IN_PROGRESS entries."""
    # Create a deep copy to avoid modifying the original data.
    no_fields_target = copy.deepcopy(get_list_assert_target)

    # Delete the procedures of the IN_PROGRESS entry.
    for result_dict in no_fields_target["applyResults"]:
        if result_dict.get("status") == "IN_PROGRESS" and "procedures" in result_dict:
            del result_dict["procedures"]

    return no_fields_target


class TestHelp:
    """Test class for help command."""

    @pytest.mark.parametrize(
        "args",
        [
            (
                [
                    "--help",
                ]
            ),
            (
                [
                    "-h",
                ]
            ),
        ],
    )
    def test_common_usage_displayed_when_help_specified(
        self,
        args,
        capfd,
    ):
        """Test that the common usage is displayed when help is specified."""
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0
        out, _ = capfd.readouterr()

        # help message is displayed in the standard output
        assert "usage" in out
        assert "positional arguments" in out
        assert "request" in out
        assert "cancel" in out
        assert "get" in out
        assert "delete" in out
        assert "resume" in out
        assert "options:" in out
        assert "-h" in out
        assert "--help" in out

    def test_common_usage_displayed_when_no_subcommand_specified(
        self,
        capfd,
    ):
        """Test that the common usage is displayed when no subcommand is specified."""
        sys.argv = ["cli.py"]
        main()
        out, _ = capfd.readouterr()

        # help message is displayed in the standard output
        assert "usage" in out
        assert "positional arguments" in out
        assert "request" in out
        assert "cancel" in out
        assert "get" in out
        assert "delete" in out
        assert "resume" in out
        assert "options:" in out
        assert "-h" in out
        assert "--help" in out

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "--apply-id", "a21bc21587", "b51b1215ce"]),  # multi ids
            (["get", "--apply-id"]),  # no id
            (["get", "a21bc21587"]),  # no id option
            (["get", "--apply-ids", "a21bc21587"]),  # invalid option
            (["--apply-id", "a21bc21587"]),  # no subcommand
            (["gets", "--apply-id", "a21bc21587"]),  # invalid subcommand
            (["a21bc21587"]),  # no id option and subcommand
            (["get", "--apply-id"]),  # no id
            (["get", "--apply-id", "a21bc21587", "--outputs"]),  # invalid output
            (["get", "--apply-id", "a21bc21587", "--utput"]),  # invalid output
            (["get", "--apply-id", "a21bc21587", "-p"]),  # invalid output
            (["get", "--apply-id", "a21bc21587", "-n"]),  # invalid output
            (["get", "--apply-id", "a21bc21587", "-oo", "test"]),  # invalid output
        ],
    )
    def test_cmd_get_usage_displayed(self, args, capfd):
        """Test that the usage message is displayed for invalid get command usage."""
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit):
            main()
        _, err = capfd.readouterr()
        # An error message is displayed.
        assert "usage:" in err

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "--help"]),
            (["get", "-h"]),
        ],
    )
    def test_cmd_get_help_displayed(self, args, capfd):
        """Test that the help message is displayed for the get command."""
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit):
            main()
        out, err = capfd.readouterr()

        assert_out = out.replace("\n", "")
        assert_out = re.sub("\s+", " ", assert_out)
        assert err == ""
        assert "usage:" in assert_out
        assert "get" in assert_out
        assert "[-h]" in assert_out
        assert "--apply-id" in assert_out
        assert "APPLY_ID" in assert_out
        assert "[-o OUTPUT_FILE]" in assert_out
        assert "[-f ITEM,ITEM....ITEM]" in assert_out
        assert "-h, --help" in assert_out
        assert "show this help message and exit" in assert_out
        assert "--apply-id" in assert_out
        assert "APPLY_ID" in assert_out
        assert "get ID as a string. If not specified, get all apply status." in assert_out
        apply_id_help = (
            "specify the items to be included in the return information. If not specified, that items are not included."
        )
        assert apply_id_help in assert_out
        assert (
            "not allowed with argument --fields, --status, --started-at-since, --started-at-until, "
            + "--ended-at- since, --ended-at-until, --sort-by, --order-by, --limit, --offset."
            in assert_out
        )
        assert (
            "specify the status for return information. set "
            + "[IN_PROGRESS | COMPLETED | FAILED | CANCELING | CANCELED | SUSPENDED]"
            in assert_out
        )
        assert "-s," in assert_out
        assert "--status STATUS" in assert_out
        assert "specify the startpoint of started time for return information." in assert_out
        assert "-ss," in assert_out
        assert "--started-at-since STARTED_AT_SINCE" in assert_out
        assert "specify the endpoint of started time for return information." in assert_out
        assert "-su," in assert_out
        assert "--started-at-until STARTED_AT_UNTIL" in assert_out
        assert "specify the startpoint of ended time for return information." in assert_out
        assert "-es," in assert_out
        assert "--ended-at-since ENDED_AT_SINCE" in assert_out
        assert "specify the endpoint of ended time for return information." in assert_out
        assert "-eu," in assert_out
        assert "--ended-at-until ENDED_AT_UNTIL" in assert_out
        assert "--order-by ORDER_BY" in assert_out
        assert "--sort-by SORT_BY" in assert_out
        assert "--limit NUMBER" in assert_out
        assert "--offset NUMBER" in assert_out
        assert "-o," in assert_out
        assert "--output OUTPUT_FILE" in assert_out

    @pytest.mark.parametrize(
        "args",
        [
            (["gets", "a21bc21587"]),  # invalid subcommand
            (["get", "--outputs"]),  # invalid output
            (["get", "--utput"]),  # invalid output
            (["get", "-p"]),  # invalid output
            (["get", "-n"]),  # invalid output
            (["get", "-oo", "test"]),  # invalid output
            (["get", "--status"]),  # status option has no value
            (["get", "--stasus"]),  # status is invalid
            (["get", "--tatus"]),  # status is invalid
            (["get", "-r"]),  # status is invalid
            (["get", "-t"]),  # status is invalid
            (["get", "--started-at-since"]),  # started-at-since option has no value
            (["get", "--started-at-sinci"]),  # started-at-since is invalid
            (["get", "--tarted-at-since"]),  # started-at-since is invalid
            (["get", "-sss", "test"]),  # ss is invalid
            (["get", "--started-at-until"]),  # started-at-until option has no value
            (["get", "--started-at-untii"]),  # started-at-until is invalid
            (["get", "--tarted-at-until"]),  # started-at-until is invalid
            (["get", "-sus", "test"]),  # su is invalid
            (["get", "--ended-at-since"]),  # ended-at-since option has no value
            (["get", "--ended-at-sinci"]),  # ended-at-since is invalid
            (["get", "--nded-at-since"]),  # ended-at-since is invalid
            (["get", "-ess", "test"]),  # es is invalid
            (["get", "--ended-at-until"]),  # ended-at-until option has no value
            (["get", "--ended-at-untii"]),  # ended-at-until is invalid
            (["get", "--nded-at-until"]),  # ended-at-until is invalid
            (["get", "-eus", "test"]),  # eu is invalid
            (["get", "-ob", "endedat"]),  # order-by is invalid
            (["get", "--orderBy", "endedat"]),  # order-by is invalid
            (["get", "-sb", "asc"]),  # sort-by is invalid
            (["get", "--sortBy", "asc"]),  # sort-by is invalid
            (["get", "-l", "5"]),  # limit is invalid
            (["get", "--limits", "5"]),  # limit is invalid
            (["get", "-of", "2"]),  # offset is invalid
            (["get", "-ofset", "2"]),  # offset is invalid
        ],
    )
    def test_cmd_get_all_usage_displayed_when_invalid_option(self, args, capfd):
        """Test that the usage message is displayed when an invalid option is provided."""
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit):
            main()
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out in "usage:"
        assert "usage:" in err


class TestGetSuccess:
    """Test class for successful get command executions."""

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
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "rollback": {
                        "procedures": {"procedures": "pre_test"},
                        "startedAt": "2023-10-02T00:00:00Z",
                        "result": [{"test": "test"}],
                    },
                },
            ),
            (
                sql.get_list_insert_sql_3,
                {
                    "status": "COMPLETED",
                    "applyID": "000000003c",
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
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
                    "result": [{"test": "test"}, {"test": "test"}],
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
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ),
            (
                sql.get_list_insert_sql_9,
                {
                    "status": "SUSPENDED",
                    "applyID": "000000009c",
                    "startedAt": "2023-10-02T00:00:01Z",
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "resumeProcedures": {"procedures": "pre_test"},
                    "suspendedAt": "2024-01-02T12:23:00Z",
                },
            ),
            (
                sql.get_list_insert_sql_6,
                {
                    "status": "CANCELED",
                    "applyID": "000000006f",
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                    "rollback": {
                        "status": "COMPLETED",
                        "procedures": {"procedures": "pre_test"},
                        "result": [{"test": "test"}, {"test": "test"}],
                        "startedAt": "2023-10-03T12:20:00Z",
                        "endedAt": "2023-10-04T12:23:59Z",
                    },
                },
            ),
            (
                sql.get_list_insert_sql_6,
                {
                    "status": "CANCELED",
                    "applyID": "000000007g",
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                    "rollback": {
                        "status": "FAILED",
                        "procedures": {"procedures": "pre_test"},
                        "result": [{"test": "test"}, {"test": "test"}],
                        "startedAt": "2023-10-03T12:20:00Z",
                        "endedAt": "2023-10-04T12:23:59Z",
                    },
                },
            ),
            (
                sql.get_list_insert_sql_6,
                {
                    "status": "CANCELED",
                    "applyID": "000000008h",
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                    "rollback": {
                        "status": "SUSPENDED",
                        "procedures": {"procedures": "pre_test"},
                        "result": [{"test": "test"}, {"test": "test"}],
                        "startedAt": "2023-10-03T12:20:00Z",
                        "suspendedAt": "2023-10-04T12:23:59Z",
                        "resumeProcedures": {"procedures": "pre_test"},
                    },
                },
            ),
        ],
    )
    def test_cmd_get_can_output_file(self, init_db_instance, insert_sql, assert_target, capfd):
        """Test that the 'get' command can output to a file."""
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        # started_at = get_str_now()
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            if assert_target["applyID"] == "000000002b":
                cursor.execute(
                    query="INSERT INTO rollbackstatus (status, procedures, result, startedAt, applyid) \
                        VALUES(%s,%s,%s,%s,%s)",
                    vars=[
                        Result.IN_PROGRESS,
                        '{"procedures": "pre_test"}',
                        '[{"test": "test"}]',
                        "2023-10-02T00:00:00Z",
                        applyid,
                    ],
                )
            if assert_target["applyID"] == "000000006f":
                # check_flg = True
                cursor.execute(query=sql.get_list_insert_sql_r_6, vars=[applyid])
            if assert_target["applyID"] == "000000007g":
                # check_flg = True
                cursor.execute(query=sql.get_list_insert_sql_r_6_failed, vars=[applyid])
            if assert_target["applyID"] == "000000008h":
                # check_flg = True
                cursor.execute(query=sql.get_list_insert_sql_r_6_suspended, vars=[applyid])
            init_db_instance.commit()

        assert_target["applyID"] = applyid
        args = ["get", "--apply-id", applyid, "--output", "applystatus.json"]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()

        # assert
        # standard output is being displayed.
        assert out == "Success.\n"
        # There is no standard error output.
        assert err == ""
        out_path = args[4]
        assert os.path.exists(out_path)
        with open(out_path, "r", encoding="utf-8") as file:
            assert assert_target == json.load(file)
            try:
                os.remove(out_path)
            except Exception:
                pass

    def test_cmd_get_success_when_status_is_in_progress(self, init_db_instance, capfd):
        """Test that the 'get' command succeeds when the status is IN_PROGRESS."""
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
            init_db_instance.commit()
        assert_target = {
            "status": "IN_PROGRESS",
            "applyID": "000000001a",
            "startedAt": "2023-10-02T00:00:00Z",
            "procedures": {"procedures": "pre_test"},
        }
        assert_target["applyID"] = applyid

        args = ["get", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays the information about
        # the reflection status of the configuration proposal specified by the applyID.
        assert json.loads(out) == assert_target
        # There is no standard error output.
        assert err == ""

    def test_cmd_get_success_when_procedure_valid(self, init_db_instance, capfd):
        """Test that the 'get' command succeeds when the procedure is valid."""
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_valid_insert_sql, vars=[applyid])
            init_db_instance.commit()
        assert_target = {
            "status": "COMPLETED",
            "applyID": "999999999a",
            "procedures": [],
            "result": [],
            "startedAt": "2023-10-02T00:00:00Z",
            "endedAt": "2023-10-02T12:23:59Z",
        }
        assert_target["applyID"] = applyid

        args = ["get", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays the information about
        # the reflection status of the configuration proposal specified by the applyID.
        assert json.loads(out) == assert_target
        # There is no standard error output.
        assert err == ""

    def test_cmd_get_success_when_rollback_completed_after_cancel(self, init_db_instance, capfd):
        """Test that the 'get' command succeeds when the rollback is completed after cancel."""
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""INSERT INTO applystatus
                    (applyid, status, procedures, result, rollbackprocedures,
                    startedat, endedat, canceledat, executerollback)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid,
                    Result.CANCELED,
                    '{"procedures": "pre_test"}',
                    '[{"test": "test"}, {"test": "test"}]',
                    '{"procedures": "rollback_test"}',
                    "2023-10-03 00:00:00",
                    "2023-10-04 12:23:59",
                    "2023-10-03 12:00:00",
                    True,
                ),
            )
            cursor.execute(
                query="""INSERT INTO rollbackstatus
                    (applyid, status, procedures, result, startedat, endedat)
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid,
                    Result.COMPLETED,
                    '{"procedures": "rollback_test"}',
                    '[{"test": "rollback_result"}]',
                    "2023-10-03 12:20:00",
                    "2023-10-04 12:23:59",
                ),
            )
        init_db_instance.commit()

        assert_target = {
            "status": "CANCELED",
            "applyID": applyid,
            "procedures": {"procedures": "pre_test"},
            "result": [{"test": "test"}, {"test": "test"}],
            "rollbackProcedures": {"procedures": "rollback_test"},
            "startedAt": "2023-10-03T00:00:00Z",
            "endedAt": "2023-10-04T12:23:59Z",
            "canceledAt": "2023-10-03T12:00:00Z",
            "executeRollback": True,
            "rollback": {
                "applyID": applyid,
                "status": "COMPLETED",
                "procedures": {"procedures": "rollback_test"},
                "result": [{"test": "rollback_result"}],
                "rollbackProcedures": None,
                "startedAt": "2023-10-03T12:20:00Z",
                "endedAt": "2023-10-04T12:23:59Z",
                "canceledAt": None,
                "resumeProcedures": None,
                "suspendedAt": None,
                "resumedAt": None,
            },
        }

        # act
        args = ["get", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        output_json = json.loads(out)

        assert output_json["status"] == assert_target["status"]
        assert output_json["applyID"] == assert_target["applyID"]
        assert output_json["procedures"] == assert_target["procedures"]
        assert output_json["result"] == assert_target["result"]
        assert output_json["rollbackProcedures"] == assert_target["rollbackProcedures"]
        assert output_json["startedAt"] == assert_target["startedAt"]
        assert output_json["endedAt"] == assert_target["endedAt"]
        assert output_json["canceledAt"] == assert_target["canceledAt"]
        assert output_json["executeRollback"] == assert_target["executeRollback"]

        assert "rollback" in output_json
        assert output_json["rollback"]["status"] == "COMPLETED"
        assert output_json["rollback"]["result"] == [{"test": "rollback_result"}]
        assert output_json["rollback"]["startedAt"] == "2023-10-03T12:20:00Z"
        assert output_json["rollback"]["endedAt"] == "2023-10-04T12:23:59Z"

        assert err == ""

    def test_cmd_get_success_when_multiple_resume_with_rollback(self, init_db_instance, capfd):
        """Test that the 'get' command succeeds when there are multiple resume points with rollback."""
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""INSERT INTO applystatus
                    (applyid, status, procedures, result, rollbackprocedures,
                    startedat, endedat, canceledat, executerollback, resumeprocedures, resumedat, suspendedat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid,
                    Result.CANCELED,
                    '{"procedures": "apply_test"}',
                    '[{"operationID": 1, "status": "FAILED", "startedAt": "2023-10-11T00:00:00Z", \
                    "endedAt": "2023-10-11T09:00:00Z"}, {"operationID": 1, "status": "COMPLETED", \
                    "startedAt": "2023-10-11T10:00:00Z", "endedAt": "2023-10-11T14:50:00Z"}, \
                    {"operationID": 2, "status": "FAILED", "startedAt": "2023-10-11T14:50:00Z", \
                    "endedAt": "2023-10-11T15:00:00Z"}]',
                    '{"procedures": "rollback_test"}',
                    "2023-10-11 00:00:00",
                    "2023-10-11 16:00:00",
                    "2023-10-11 15:00:00",
                    True,
                    '[{"resume": 1, "procedure": "retry_after_suspend"}]',
                    "2023-10-11 10:00:00",
                    "2023-10-11 09:00:00",
                ),
            )
            cursor.execute(
                query="""INSERT INTO rollbackstatus
                    (applyid, status, procedures, result, startedat, endedat, resumeprocedures, resumedat, suspendedat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid,
                    Result.COMPLETED,
                    '{"procedures": "rollback_test"}',
                    '[{"operationID": 2, "status": "FAILED", "startedAt": "2023-10-11T15:10:00Z", \
                    "endedAt": "2023-10-11T15:30:00Z"}, {"operationID": 2, "status": "COMPLETED", \
                    "startedAt": "2023-10-11T15:40:00Z", "endedAt": "2023-10-11T15:50:00Z"}, \
                    {"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-11T15:50:00Z", \
                    "endedAt": "2023-10-11T16:00:00Z"}]',
                    "2023-10-11 15:10:00",
                    "2023-10-11 16:00:00",
                    '[{"resume": 1, "procedure": "retry_rollback"}]',
                    "2023-10-11 15:40:00",
                    "2023-10-11 15:30:00",
                ),
            )
        init_db_instance.commit()

        # act
        args = ["get", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        output_json = json.loads(out)

        assert output_json["status"] == "CANCELED"
        assert output_json["applyID"] == applyid
        assert output_json["procedures"] == {"procedures": "apply_test"}
        assert len(output_json["result"]) == 3

        assert output_json["result"][0]["operationID"] == 1
        assert output_json["result"][0]["status"] == "FAILED"
        assert output_json["result"][1]["operationID"] == 1
        assert output_json["result"][1]["status"] == "COMPLETED"
        assert output_json["result"][2]["operationID"] == 2
        assert output_json["result"][2]["status"] == "FAILED"

        assert output_json["executeRollback"] is True
        assert output_json["resumeProcedures"] == [{"resume": 1, "procedure": "retry_after_suspend"}]
        assert output_json["resumedAt"] == "2023-10-11T10:00:00Z"
        assert output_json["suspendedAt"] == "2023-10-11T09:00:00Z"

        assert "rollback" in output_json
        assert output_json["rollback"]["status"] == "COMPLETED"
        assert len(output_json["rollback"]["result"]) == 3

        assert output_json["rollback"]["result"][0]["operationID"] == 2
        assert output_json["rollback"]["result"][0]["status"] == "FAILED"
        assert output_json["rollback"]["result"][1]["operationID"] == 2
        assert output_json["rollback"]["result"][1]["status"] == "COMPLETED"
        assert output_json["rollback"]["result"][2]["operationID"] == 1
        assert output_json["rollback"]["result"][2]["status"] == "COMPLETED"

        assert output_json["rollback"]["resumeProcedures"] == [{"resume": 1, "procedure": "retry_rollback"}]
        assert output_json["rollback"]["resumedAt"] == "2023-10-11T15:40:00Z"
        assert output_json["rollback"]["suspendedAt"] == "2023-10-11T15:30:00Z"

        assert err == ""

    def test_cmd_get_success_when_rollback_suspended_and_resumed(self, init_db_instance, capfd):
        """Test the CLI command for getting the status when rollback is suspended and then resumed."""
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""INSERT INTO applystatus
                    (applyid, status, procedures, result, rollbackprocedures,
                    startedat, endedat, canceledat, executerollback)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid,
                    Result.CANCELED,
                    '{"procedures": "apply_test"}',
                    '[{"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-15T10:00:00Z", \
                    "endedAt": "2023-10-15T11:00:00Z"}, {"operationID": 2, "status": "COMPLETED", \
                    "startedAt": "2023-10-15T11:00:00Z", "endedAt": "2023-10-15T12:00:00Z"}]',
                    '{"procedures": "rollback_test"}',
                    "2023-10-15 10:00:00",
                    "2023-10-15 16:00:00",
                    "2023-10-15 12:30:00",
                    True,
                ),
            )
            cursor.execute(
                query="""INSERT INTO rollbackstatus
                    (applyid, status, procedures, result, startedat, endedat, resumeprocedures, resumedat, suspendedat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid,
                    Result.COMPLETED,
                    '{"procedures": "rollback_test"}',
                    '[{"operationID": 2, "status": "FAILED", "startedAt": "2023-10-15T13:00:00Z", \
                    "endedAt": "2023-10-15T14:00:00Z"}, {"operationID": 2, "status": "COMPLETED", \
                    "startedAt": "2023-10-15T15:00:00Z", "endedAt": "2023-10-15T15:30:00Z"}, \
                    {"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-15T15:30:00Z", \
                    "endedAt": "2023-10-15T16:00:00Z"}]',
                    "2023-10-15 13:00:00",
                    "2023-10-15 16:00:00",
                    '{"procedures": "retry_rollback_after_suspend"}',
                    "2023-10-15 15:00:00",
                    "2023-10-15 14:00:00",
                ),
            )
        init_db_instance.commit()

        # act
        args = ["get", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()

        output_json = json.loads(out)

        assert output_json["status"] == "CANCELED"
        assert output_json["applyID"] == applyid
        assert output_json["procedures"] == {"procedures": "apply_test"}
        assert len(output_json["result"]) == 2
        assert output_json["result"][0]["operationID"] == 1
        assert output_json["result"][0]["status"] == "COMPLETED"
        assert output_json["result"][1]["operationID"] == 2
        assert output_json["result"][1]["status"] == "COMPLETED"
        assert output_json["executeRollback"] is True
        assert output_json["canceledAt"] == "2023-10-15T12:30:00Z"

        assert "rollback" in output_json
        assert output_json["rollback"]["status"] == "COMPLETED"
        assert len(output_json["rollback"]["result"]) == 3

        assert output_json["rollback"]["result"][0]["operationID"] == 2
        assert output_json["rollback"]["result"][0]["status"] == "FAILED"
        assert output_json["rollback"]["result"][0]["startedAt"] == "2023-10-15T13:00:00Z"
        assert output_json["rollback"]["result"][0]["endedAt"] == "2023-10-15T14:00:00Z"

        assert output_json["rollback"]["result"][1]["operationID"] == 2
        assert output_json["rollback"]["result"][1]["status"] == "COMPLETED"
        assert output_json["rollback"]["result"][1]["startedAt"] == "2023-10-15T15:00:00Z"
        assert output_json["rollback"]["result"][1]["endedAt"] == "2023-10-15T15:30:00Z"

        assert output_json["rollback"]["result"][2]["operationID"] == 1
        assert output_json["rollback"]["result"][2]["status"] == "COMPLETED"
        assert output_json["rollback"]["result"][2]["startedAt"] == "2023-10-15T15:30:00Z"
        assert output_json["rollback"]["result"][2]["endedAt"] == "2023-10-15T16:00:00Z"

        assert output_json["rollback"]["suspendedAt"] == "2023-10-15T14:00:00Z"
        assert output_json["rollback"]["resumedAt"] == "2023-10-15T15:00:00Z"
        assert output_json["rollback"]["resumeProcedures"] == {"procedures": "retry_rollback_after_suspend"}
        assert output_json["rollback"]["startedAt"] == "2023-10-15T13:00:00Z"
        assert output_json["rollback"]["endedAt"] == "2023-10-15T16:00:00Z"

        assert err == ""

    def test_cmd_get_success_when_resumed_then_canceled_with_rollback(self, init_db_instance, capfd):
        """Test the 'get' command when an apply is resumed and then canceled with a rollback."""
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                query="""INSERT INTO applystatus
                    (applyid, status, procedures, result, rollbackprocedures,
                    startedat, endedat, canceledat, executerollback, resumeprocedures, resumedat, suspendedat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid,
                    Result.CANCELED,
                    '{"procedures": "apply_test"}',
                    '[{"operationID": 1, "status": "FAILED", "startedAt": "2023-10-20T10:00:00Z", \
                    "endedAt": "2023-10-20T11:00:00Z"}, {"operationID": 1, "status": "COMPLETED", \
                    "startedAt": "2023-10-20T14:00:00Z", "endedAt": "2023-10-20T15:00:00Z"}, \
                    {"operationID": 2, "status": "CANCELED", "startedAt": "2023-10-20T15:00:00Z", \
                    "endedAt": "2023-10-20T15:30:00Z"}]',
                    '{"procedures": "rollback_test"}',
                    "2023-10-20 10:00:00",
                    "2023-10-20 17:00:00",
                    "2023-10-20 15:30:00",
                    True,
                    '{"procedures": "resume_after_suspend"}',
                    "2023-10-20 14:00:00",
                    "2023-10-20 11:00:00",
                ),
            )
            cursor.execute(
                query="""INSERT INTO rollbackstatus
                    (applyid, status, procedures, result, startedat, endedat)
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid,
                    Result.COMPLETED,
                    '{"procedures": "rollback_test"}',
                    '[{"operationID": 2, "status": "COMPLETED", "startedAt": "2023-10-20T15:40:00Z", \
                    "endedAt": "2023-10-20T16:00:00Z"}, {"operationID": 1, "status": "COMPLETED", \
                    "startedAt": "2023-10-20T16:00:00Z", "endedAt": "2023-10-20T17:00:00Z"}]',
                    "2023-10-20 15:40:00",
                    "2023-10-20 17:00:00",
                ),
            )
        init_db_instance.commit()

        # act
        args = ["get", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()

        output_json = json.loads(out)

        assert output_json["status"] == "CANCELED"
        assert output_json["applyID"] == applyid
        assert output_json["procedures"] == {"procedures": "apply_test"}
        assert len(output_json["result"]) == 3

        assert output_json["result"][0]["operationID"] == 1
        assert output_json["result"][0]["status"] == "FAILED"
        assert output_json["result"][0]["startedAt"] == "2023-10-20T10:00:00Z"
        assert output_json["result"][0]["endedAt"] == "2023-10-20T11:00:00Z"

        assert output_json["result"][1]["operationID"] == 1
        assert output_json["result"][1]["status"] == "COMPLETED"
        assert output_json["result"][1]["startedAt"] == "2023-10-20T14:00:00Z"
        assert output_json["result"][1]["endedAt"] == "2023-10-20T15:00:00Z"

        assert output_json["result"][2]["operationID"] == 2
        assert output_json["result"][2]["status"] == "CANCELED"
        assert output_json["result"][2]["startedAt"] == "2023-10-20T15:00:00Z"
        assert output_json["result"][2]["endedAt"] == "2023-10-20T15:30:00Z"

        assert output_json["executeRollback"] is True
        assert output_json["suspendedAt"] == "2023-10-20T11:00:00Z"
        assert output_json["resumedAt"] == "2023-10-20T14:00:00Z"
        assert output_json["resumeProcedures"] == {"procedures": "resume_after_suspend"}
        assert output_json["canceledAt"] == "2023-10-20T15:30:00Z"

        assert "rollback" in output_json
        assert output_json["rollback"]["status"] == "COMPLETED"
        assert len(output_json["rollback"]["result"]) == 2

        assert output_json["rollback"]["result"][0]["operationID"] == 2
        assert output_json["rollback"]["result"][0]["status"] == "COMPLETED"
        assert output_json["rollback"]["result"][0]["startedAt"] == "2023-10-20T15:40:00Z"
        assert output_json["rollback"]["result"][0]["endedAt"] == "2023-10-20T16:00:00Z"

        assert output_json["rollback"]["result"][1]["operationID"] == 1
        assert output_json["rollback"]["result"][1]["status"] == "COMPLETED"
        assert output_json["rollback"]["result"][1]["startedAt"] == "2023-10-20T16:00:00Z"
        assert output_json["rollback"]["result"][1]["endedAt"] == "2023-10-20T17:00:00Z"

        assert output_json["rollback"]["startedAt"] == "2023-10-20T15:40:00Z"
        assert output_json["rollback"]["endedAt"] == "2023-10-20T17:00:00Z"

        assert err == ""

    @pytest.mark.parametrize("args", [["get"]])
    def test_cmd_get_all_failure_when_query_failure_occurred(self, args, mocker, capfd, caplog):
        """Test that the command fails when a query failure occurs."""
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.ERROR)

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
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 11
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""

        assert "[E40019]Query failed." in err
        assert "[E40019]Query failed." in caplog.text

    def test_cmd_get_all_success_when_no_fields_and_out_file(self, init_db_instance, capfd):
        """Test that the command succeeds when no fields are specified and an output file is provided."""
        # Data adjustment before testing.
        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target_default["applyResults"]):
            result_dict["applyID"] = id_list[i]

        args = ["get", "--output", "applystatus_list.json"]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()

        # assert
        # standard output is being displayed.
        assert out == "Success.\n"
        # There is no standard error output.
        assert err == ""
        out_path = args[2]
        assert os.path.exists(out_path)
        with open(out_path, "r", encoding="utf-8") as file:
            output = json.load(file)
            assert get_list_assert_target_default["count"] == output["count"]
            for apply in output["applyResults"]:
                assert apply in get_list_assert_target_default["applyResults"]

            try:
                os.remove(out_path)
            except Exception:
                pass

    def test_cmd_get_all_success_when_no_fields_and_no_out_file(self, init_db_instance, capfd):
        """Test that the command succeeds when no fields are specified and no output file is provided."""
        # arrange
        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target_default["applyResults"]):
            result_dict["applyID"] = id_list[i]

        args = ["get"]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        a = json.loads(out)
        for apply in a["applyResults"]:
            assert apply in get_list_assert_target_default["applyResults"]
        # There is no standard error output.
        assert err == ""

    def test_cmd_get_all_success_when_file_output_made(self, init_db_instance, capfd):
        """Test that the command succeeds when an output file is specified."""
        # Data adjustment before testing.
        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target["applyResults"]):
            result_dict["applyID"] = id_list[i]
        args = [
            "get",
            "--fields",
            "procedures,result,rollbackProcedures,resumeProcedures",
            "--output",
            "applystatus_list.json",
        ]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()

        # assert
        # standard output is being displayed.
        assert out == "Success.\n"
        # There is no standard error output.
        assert err == ""

        out_path = args[4]
        assert os.path.exists(out_path)
        with open(out_path, "r", encoding="utf-8") as file:
            output = json.load(file)
            assert get_list_assert_target["count"] == output["count"]
            for apply in output["applyResults"]:
                assert apply in get_list_assert_target["applyResults"]

            try:
                os.remove(out_path)
            except Exception:
                pass

    def test_cmd_get_all_success_when_no_file_output(self, init_db_instance, capfd):
        """Test that the command succeeds when no output file is specified."""
        # arrange
        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target["applyResults"]):
            result_dict["applyID"] = id_list[i]
        args = [
            "get",
            "--fields",
            "procedures,result,rollbackProcedures,resumeProcedures",
        ]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        a = json.loads(out)
        for apply in a["applyResults"]:
            assert apply in get_list_assert_target["applyResults"]
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize("args", [["get"]])
    def test_cmd_get_all_success_when_no_results_fetched(
        self, init_db_instance, args, capfd
    ):  # pylint: disable=unused-argument
        """Test that the command succeeds when no results are fetched."""
        assert_target = {
            "totalCount": 0,
            "count": 0,
            "applyResults": [],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == assert_target
        # There is no standard error output.
        assert err == ""

    def test_cmd_get_all_success_with_cancel_and_rollback_patterns(self, init_db_instance, capfd):
        """Test that the command succeeds with cancelled and rollback patterns."""
        applyid_list = []

        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            # pattern 1: Cancelled and rollback
            applyid1 = create_randomname(IdParameter.LENGTH)
            applyid_list.append(applyid1)
            cursor.execute(
                query="""INSERT INTO applystatus
                    (applyid, status, procedures, result, rollbackprocedures,
                    startedat, endedat, canceledat, executerollback)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid1,
                    Result.CANCELED,
                    '{"procedures": "pre_test"}',
                    '[{"test": "test"}, {"test": "test"}]',
                    '{"procedures": "rollback_test"}',
                    "2023-10-03 00:00:00",
                    "2023-10-04 12:23:59",
                    "2023-10-03 12:00:00",
                    True,
                ),
            )
            cursor.execute(
                query="""INSERT INTO rollbackstatus
                    (applyid, status, procedures, result, startedat, endedat)
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid1,
                    Result.COMPLETED,
                    '{"procedures": "rollback_test"}',
                    '[{"test": "rollback_result"}]',
                    "2023-10-03 12:20:00",
                    "2023-10-04 12:23:59",
                ),
            )

            # pattern 2: Cancelled and multiple rollbacks
            applyid2 = create_randomname(IdParameter.LENGTH)
            applyid_list.append(applyid2)
            cursor.execute(
                query="""INSERT INTO applystatus
                    (applyid, status, procedures, result, rollbackprocedures,
                    startedat, endedat, canceledat, executerollback, resumeprocedures, resumedat, suspendedat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid2,
                    Result.CANCELED,
                    '{"procedures": "apply_test"}',
                    '[{"operationID": 1, "status": "FAILED", "startedAt": "2023-10-11T00:00:00Z", \
                    "endedAt": "2023-10-11T09:00:00Z"}, {"operationID": 1, "status": "COMPLETED", \
                    "startedAt": "2023-10-11T10:00:00Z", "endedAt": "2023-10-11T14:50:00Z"}, \
                    {"operationID": 2, "status": "FAILED", "startedAt": "2023-10-11T14:50:00Z", \
                    "endedAt": "2023-10-11T15:00:00Z"}]',
                    '{"procedures": "rollback_test"}',
                    "2023-10-11 00:00:00",
                    "2023-10-11 16:00:00",
                    "2023-10-11 15:00:00",
                    True,
                    '[{"resume": 1, "procedure": "retry_after_suspend"}]',
                    "2023-10-11 10:00:00",
                    "2023-10-11 09:00:00",
                ),
            )
            cursor.execute(
                query="""INSERT INTO rollbackstatus
                    (applyid, status, procedures, result, startedat, endedat, resumeprocedures, resumedat, suspendedat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid2,
                    Result.COMPLETED,
                    '{"procedures": "rollback_test"}',
                    '[{"operationID": 2, "status": "FAILED", "startedAt": "2023-10-11T15:10:00Z", \
                    "endedAt": "2023-10-11T15:30:00Z"}, {"operationID": 2, "status": "COMPLETED", \
                    "startedAt": "2023-10-11T15:40:00Z", "endedAt": "2023-10-11T15:50:00Z"}, \
                    {"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-11T15:50:00Z", \
                    "endedAt": "2023-10-11T16:00:00Z"}]',
                    "2023-10-11 15:10:00",
                    "2023-10-11 16:00:00",
                    '[{"resume": 1, "procedure": "retry_rollback"}]',
                    "2023-10-11 15:40:00",
                    "2023-10-11 15:30:00",
                ),
            )

            # pattern 3: interrupt and resume during rollback
            applyid3 = create_randomname(IdParameter.LENGTH)
            applyid_list.append(applyid3)
            cursor.execute(
                query="""INSERT INTO applystatus
                    (applyid, status, procedures, result, rollbackprocedures,
                    startedat, endedat, canceledat, executerollback)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid3,
                    Result.CANCELED,
                    '{"procedures": "apply_test"}',
                    '[{"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-15T10:00:00Z", \
                    "endedAt": "2023-10-15T11:00:00Z"}, {"operationID": 2, "status": "COMPLETED", \
                    "startedAt": "2023-10-15T11:00:00Z", "endedAt": "2023-10-15T12:00:00Z"}]',
                    '{"procedures": "rollback_test"}',
                    "2023-10-15 10:00:00",
                    "2023-10-15 16:00:00",
                    "2023-10-15 12:30:00",
                    True,
                ),
            )
            cursor.execute(
                query="""INSERT INTO rollbackstatus
                    (applyid, status, procedures, result, startedat, endedat, resumeprocedures, resumedat, suspendedat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid3,
                    Result.COMPLETED,
                    '{"procedures": "rollback_test"}',
                    '[{"operationID": 2, "status": "FAILED", "startedAt": "2023-10-15T13:00:00Z", \
                    "endedAt": "2023-10-15T14:00:00Z"}, {"operationID": 2, "status": "COMPLETED", \
                    "startedAt": "2023-10-15T15:00:00Z", "endedAt": "2023-10-15T15:30:00Z"}, \
                    {"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-15T15:30:00Z", \
                    "endedAt": "2023-10-15T16:00:00Z"}]',
                    "2023-10-15 13:00:00",
                    "2023-10-15 16:00:00",
                    '{"procedures": "retry_rollback_after_suspend"}',
                    "2023-10-15 15:00:00",
                    "2023-10-15 14:00:00",
                ),
            )

            # pattern 4: Cancel after resume and rollback completed
            applyid4 = create_randomname(IdParameter.LENGTH)
            applyid_list.append(applyid4)
            cursor.execute(
                query="""INSERT INTO applystatus
                    (applyid, status, procedures, result, rollbackprocedures,
                    startedat, endedat, canceledat, executerollback, resumeprocedures, resumedat, suspendedat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid4,
                    Result.CANCELED,
                    '{"procedures": "apply_test"}',
                    '[{"operationID": 1, "status": "FAILED", "startedAt": "2023-10-20T10:00:00Z", \
                    "endedAt": "2023-10-20T11:00:00Z"}, {"operationID": 1, "status": "COMPLETED", \
                    "startedAt": "2023-10-20T14:00:00Z", "endedAt": "2023-10-20T15:00:00Z"}, \
                    {"operationID": 2, "status": "CANCELED", "startedAt": "2023-10-20T15:00:00Z", \
                    "endedAt": "2023-10-20T15:30:00Z"}]',
                    '{"procedures": "rollback_test"}',
                    "2023-10-20 10:00:00",
                    "2023-10-20 17:00:00",
                    "2023-10-20 15:30:00",
                    True,
                    '{"procedures": "resume_after_suspend"}',
                    "2023-10-20 14:00:00",
                    "2023-10-20 11:00:00",
                ),
            )
            cursor.execute(
                query="""INSERT INTO rollbackstatus
                    (applyid, status, procedures, result, startedat, endedat)
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                vars=(
                    applyid4,
                    Result.COMPLETED,
                    '{"procedures": "rollback_test"}',
                    '[{"operationID": 2, "status": "COMPLETED", "startedAt": "2023-10-20T15:40:00Z", \
                    "endedAt": "2023-10-20T16:00:00Z"}, {"operationID": 1, "status": "COMPLETED", \
                    "startedAt": "2023-10-20T16:00:00Z", "endedAt": "2023-10-20T17:00:00Z"}]',
                    "2023-10-20 15:40:00",
                    "2023-10-20 17:00:00",
                ),
            )
        init_db_instance.commit()

        # act
        args = ["get"]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()

        output_json = json.loads(out)

        assert output_json["totalCount"] == 4
        assert output_json["count"] == 4
        assert len(output_json["applyResults"]) == 4

        apply_results = output_json["applyResults"]
        results_by_id = {result["applyID"]: result for result in apply_results}

        # pattern 1: Cancelled and rollback
        result1 = results_by_id[applyid1]
        assert result1["status"] == "CANCELED"
        assert result1["executeRollback"] is True
        assert result1["startedAt"] == "2023-10-03T00:00:00Z"
        assert result1["endedAt"] == "2023-10-04T12:23:59Z"
        assert result1["canceledAt"] == "2023-10-03T12:00:00Z"
        assert "rollback" in result1
        assert result1["rollback"]["status"] == "COMPLETED"
        assert result1["rollback"]["startedAt"] == "2023-10-03T12:20:00Z"
        assert result1["rollback"]["endedAt"] == "2023-10-04T12:23:59Z"

        # pattern 2: Cancelled and multiple rollbacks
        result2 = results_by_id[applyid2]
        assert result2["status"] == "CANCELED"
        assert result2["executeRollback"] is True
        assert result2["startedAt"] == "2023-10-11T00:00:00Z"
        assert result2["endedAt"] == "2023-10-11T16:00:00Z"
        assert result2["canceledAt"] == "2023-10-11T15:00:00Z"
        assert result2["suspendedAt"] == "2023-10-11T09:00:00Z"
        assert result2["resumedAt"] == "2023-10-11T10:00:00Z"
        assert "rollback" in result2
        assert result2["rollback"]["status"] == "COMPLETED"
        assert result2["rollback"]["startedAt"] == "2023-10-11T15:10:00Z"
        assert result2["rollback"]["endedAt"] == "2023-10-11T16:00:00Z"

        # pattern 3: interrupt and resume during rollback
        result3 = results_by_id[applyid3]
        assert result3["status"] == "CANCELED"
        assert result3["executeRollback"] is True
        assert result3["startedAt"] == "2023-10-15T10:00:00Z"
        assert result3["endedAt"] == "2023-10-15T16:00:00Z"
        assert result3["canceledAt"] == "2023-10-15T12:30:00Z"
        assert "rollback" in result3
        assert result3["rollback"]["status"] == "COMPLETED"
        assert result3["rollback"]["startedAt"] == "2023-10-15T13:00:00Z"
        assert result3["rollback"]["endedAt"] == "2023-10-15T16:00:00Z"

        # pattern 4: Cancel after resume and rollback completed
        result4 = results_by_id[applyid4]
        assert result4["status"] == "CANCELED"
        assert result4["executeRollback"] is True
        assert result4["startedAt"] == "2023-10-20T10:00:00Z"
        assert result4["endedAt"] == "2023-10-20T17:00:00Z"
        assert result4["canceledAt"] == "2023-10-20T15:30:00Z"
        assert result4["suspendedAt"] == "2023-10-20T11:00:00Z"
        assert result4["resumedAt"] == "2023-10-20T14:00:00Z"
        assert "rollback" in result4
        assert result4["rollback"]["status"] == "COMPLETED"
        assert result4["rollback"]["startedAt"] == "2023-10-20T15:40:00Z"
        assert result4["rollback"]["endedAt"] == "2023-10-20T17:00:00Z"

        assert err == ""

    @pytest.mark.parametrize(
        ("assert_target", "insert_sql"),
        [
            (
                {
                    "status": "IN_PROGRESS",
                    "applyID": "300000004d",
                    "procedures": {"procedures": "pre_test"},
                    "startedAt": "2023-10-02T00:00:00Z",
                    "result": [{"test": "test"}, {"test": "test"}],
                    "resumedAt": "2023-10-03T12:23:59Z",
                    "resumeProcedures": {"procedures": "pre_test"},
                },
                sql.insert_resumed_get_target_sql_1,
            ),
            (
                {
                    "status": "CANCELING",
                    "applyID": "300000005e",
                    "procedures": {"procedures": "pre_test"},
                    "startedAt": "2023-10-02T00:00:00Z",
                    "result": [{"test": "test"}, {"test": "test"}],
                    "canceledAt": "2023-10-02T00:00:01Z",
                    "executeRollback": True,
                    "resumedAt": "2023-10-03T12:23:59Z",
                    "resumeProcedures": {"procedures": "pre_test"},
                },
                sql.insert_resumed_get_target_sql_2,
            ),
            (
                {
                    "status": "IN_PROGRESS",
                    "applyID": "300000004d",
                    "procedures": {"procedures": "pre_test"},
                    "startedAt": "2023-10-02T00:00:00Z",
                    "result": [{"test": "test"}, {"test": "test"}],
                    "resumedAt": "2023-10-03T12:23:59Z",
                    "resumeProcedures": {"procedures": "pre_test"},
                },
                sql.insert_resumed_get_target_sql_5,
            ),
        ],
    )
    def test_cmd_get_success_when_state_in_progress_or_canceling(
        self, init_db_instance, assert_target, insert_sql, capfd
    ):
        """Test that the CLI successfully retrieves
        the target when the state is IN_PROGRESS or CANCELING."""
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()

        assert_target["applyID"] = applyid
        args = ["get", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays the information regarding
        # reflection status of the configuration proposal specified by the applyID.
        assert json.loads(out) == assert_target
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,result,rollbackProcedures,resumeProcedures",
                "-s",
                "CANCELED",
                "-ss",
                "2023-10-02T00:00:03Z",
                "-su",
                "2023-10-03T00:00:01Z",
                "-es",
                "2023-10-02T12:24:01Z",
                "-eu",
                "2023-10-04T12:24:00Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_start_date_only_not_in_range(self, init_db_instance, args, capfd):
        """Test that the CLI successfully retrieves all entries when
        the start date is only specified and not in the range."""
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_1])
            init_db_instance.commit()
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_2])
            init_db_instance.commit()

        # "applyID": "000000006f"（target）"applyID": "000000005e"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": applyid_2,
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == get_list_assert_target_all

        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,result,rollbackProcedures,resumeProcedures",
                "-s",
                "CANCELED",
                "-ss",
                "2023-10-02T00:00:02Z",
                "-su",
                "2023-10-02T23:59:59Z",
                "-es",
                "2023-10-02T12:24:01Z",
                "-eu",
                "2023-10-04T12:24:00Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_end_date_only_not_in_range(self, init_db_instance, args, capfd):
        """Test that the CLI successfully retrieves all entries when"""
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_1])
            init_db_instance.commit()
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_2])
            init_db_instance.commit()

        # "applyID": "000000005e"（target）"applyID": "000000006f"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": applyid_1,
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == get_list_assert_target_all
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,result,rollbackProcedures,resumeProcedures",
                "-s",
                "CANCELED",
                "-ss",
                "2023-10-02T00:00:02Z",
                "-su",
                "2023-10-03T00:00:00Z",
                "-es",
                "2023-10-02T12:24:02Z",
                "-eu",
                "2023-10-04T12:24:00Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_end_date_start_only_not_in_range(self, init_db_instance, args, capfd):
        """Test that the CLI successfully retrieves all entries when
        the end date and start date are specified but not in the range."""
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_1])
            init_db_instance.commit()
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_2])
            init_db_instance.commit()

        # "applyID": "000000006f"（target）"applyID": "000000005e"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": applyid_2,
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-03T00:00:00Z",
                    "endedAt": "2023-10-04T12:23:59Z",
                    "canceledAt": "2023-10-03T12:00:00Z",
                    "executeRollback": True,
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        output = json.loads(out)
        assert output == get_list_assert_target_all
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args, fields",
        [
            (
                ["get"],
                [],
            ),  # fields:None
            (
                ["get", "--fields", "procedures"],
                ["procedures"],
            ),  # fields:procedures
            (
                ["get", "--fields", "result"],
                ["result"],
            ),  # fields:result
            (
                ["get", "--fields", "rollbackProcedures"],
                ["rollbackProcedures"],
            ),  # fields:rollbackProcedures
            (
                ["get", "--fields", "resumeProcedures"],
                ["resumeProcedures"],
            ),  # fields:resumeProcedures
            (
                ["get", "--fields", "procedures,result"],
                ["procedures", "result"],
            ),  # fields:procedures/result
            (
                ["get", "--fields", "procedures,rollbackProcedures"],
                ["procedures", "rollbackProcedures"],
            ),  # fields:procedures/rollbackProcedures
            (
                ["get", "--fields", "procedures,resumeProcedures"],
                ["procedures", "resumeProcedures"],
            ),  # fields:procedures/resumeProcedures
            (
                ["get", "--fields", "result,rollbackProcedures"],
                ["result", "rollbackProcedures"],
            ),  # fields:result/rollbackProcedures
            (
                ["get", "--fields", "result,resumeProcedures"],
                ["result", "resumeProcedures"],
            ),  # fields:result/resumeProcedures
            (
                ["get", "--fields", "rollbackProcedures,resumeProcedures"],
                ["rollbackProcedures", "resumeProcedures"],
            ),  # fields:rollbackProcedures/resumeProcedures
            (
                [
                    "get",
                    "--fields",
                    "procedures,result,rollbackProcedures",
                ],
                ["procedures", "result", "rollbackProcedures"],
            ),  # fields:procedures/result/rollbackProcedures
            (
                [
                    "get",
                    "--fields",
                    "procedures,result,resumeProcedures",
                ],
                ["procedures", "result", "resumeProcedures"],
            ),  # fields:procedures/result/resumeProcedures
            (
                [
                    "get",
                    "--fields",
                    "procedures,rollbackProcedures,resumeProcedures",
                ],
                ["procedures", "rollbackProcedures", "resumeProcedures"],
            ),  # fields:procedures/rollbackProcedures/resumeProcedures
            (
                [
                    "get",
                    "--fields",
                    "result,rollbackProcedures,resumeProcedures",
                ],
                ["result", "rollbackProcedures", "resumeProcedures"],
            ),  # fields:result/rollbackProcedures/resumeProcedures
            (
                [
                    "get",
                    "--fields",
                    "procedures,result,rollbackProcedures,resumeProcedures",
                ],
                ["procedures", "result", "rollbackProcedures", "resumeProcedures"],
            ),  # fields:procedures/result/rollbackProcedures/resumeProcedures
        ],
    )
    def test_cmd_get_all_success_when_fields_specified(self, init_db_instance, args, fields, capfd):
        """Test that the CLI successfully retrieves all entries with the specified fields."""

        def _fields_check(check_targets: list, fields: list, result: dict):
            for target in check_targets:
                if target in fields:
                    assert target in result
                else:
                    assert target not in result
                if "rollback" in result:
                    if target != "rollbackProcedures":
                        if target in fields:
                            assert target in result["rollback"]
                        else:
                            assert target not in result["rollback"]

        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        applyid_3 = create_randomname(IdParameter.LENGTH)
        applyid_4 = create_randomname(IdParameter.LENGTH)
        applyid_5 = create_randomname(IdParameter.LENGTH)
        applyid_6 = create_randomname(IdParameter.LENGTH)
        applyid_7 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_fields_insert_sql_1, vars=[applyid_1])
            cursor.execute(query=sql.get_fields_insert_sql_2, vars=[applyid_2])
            cursor.execute(query=sql.get_fields_insert_sql_3, vars=[applyid_3])
            cursor.execute(query=sql.get_fields_insert_sql_4, vars=[applyid_4])
            cursor.execute(query=sql.get_fields_insert_sql_5, vars=[applyid_5])
            cursor.execute(query=sql.get_fields_insert_sql_6, vars=[applyid_6])
            cursor.execute(query=sql.get_fields_insert_sql_r_6, vars=[applyid_6])
            cursor.execute(query=sql.get_fields_insert_sql_7, vars=[applyid_7])
            init_db_instance.commit()

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        applyResults = json.loads(out).get("applyResults")
        # standard output displays only the items specified by fields, and items not specified are not displayed.
        for result in applyResults:
            match result.get("status"):
                case "COMPLETED" | "FAILED":
                    # no rollback data
                    assert "rollbackProcedures" not in result
                    _fields_check(["procedures", "result"], fields, result)
                case "IN_PROGRESS":
                    # no items that can be specified in fields
                    assert "result" not in result
                    assert "rollbackProcedures" not in result
                case "CANCELING":
                    # no items that can be specified in fields
                    assert "rollbackProcedures" not in result
                case "CANCELED":
                    _fields_check(
                        ["procedures", "result", "rollbackProcedures"],
                        fields,
                        result,
                    )
                case "SUSPENDED":
                    # no rollback data
                    assert "rollbackProcedures" not in result
                    _fields_check(["procedures", "result", "resumeProcedures"], fields, result)

        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,result,rollbackProcedures,resumeProcedures",
                "-s",
                "CANCELED",
                "-ss",
                "2023-10-02T00:00:02Z",
                "-su",
                "2023-10-03T00:00:00Z",
                "-es",
                "2023-10-02T12:24:01Z",
                "-eu",
                "2023-10-04T12:23:58Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_end_date_end_only_not_in_range(self, init_db_instance, args, capfd):
        """Test that the CLI successfully retrieves all entries when
        the end date is specified but not in the range."""
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_1])
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_2])
            init_db_instance.commit()

        # "applyID": "000000005e"（target）"applyID": "000000006f"（no target）
        get_list_assert_target_all = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": applyid_1,
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == get_list_assert_target_all
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,result,rollbackProcedures,resumeProcedures",
                "-s",
                "CANCELED",
                "-ss",
                "2023-10-05T00:00:00Z",
                "-su",
                "2023-10-06T00:00:00Z",
                "-es",
                "2023-10-05T00:00:00Z",
                "-eu",
                "2023-10-06T23:59:59Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_both_start_and_end_date_outside_range(self, init_db_instance, args, capfd):
        """Test that the CLI successfully retrieves all entries when both
        the start and end dates are specified but not in the range."""
        # arrange
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_1])
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_2])
            init_db_instance.commit()

        # "applyID": "000000005e"、"applyID": "000000006f"（no target）
        get_list_assert_target_all = {
            "totalCount": 0,
            "count": 0,
            "applyResults": [],
        }

        sys.argv = ["cli.py", *args]

        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == get_list_assert_target_all
        # There is no standard error output.
        assert err == ""

    def test_cmd_get_all_success_when_state_specified(self, init_db_instance, capfd):
        """Test that the CLI successfully retrieves all entries when the state is specified."""
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid_1])
            cursor.execute(query=sql.get_list_insert_sql_3, vars=[applyid_2])
            init_db_instance.commit()

        get_list_assert_target_status = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "applyID": applyid_1,
                    "status": "IN_PROGRESS",
                    "startedAt": "2023-10-02T00:00:00Z",
                },
            ],
        }

        args = ["get", "--status", "IN_PROGRESS"]
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == get_list_assert_target_status
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,result,rollbackProcedures,resumeProcedures",
                "--started-at-since",
                "2023-10-02T00:00:02Z",
                "--started-at-until",
                "2023-10-02T00:00:03Z",
                "--ended-at-since",
                "2023-10-02T12:24:01Z",
                "--ended-at-until",
                "2023-10-02T12:24:02Z",
            ]
        ],
    )
    def test_cmd_get_all_failure_when_add_second_to_upper_time_limit(self, init_db_instance, args, capfd):
        """Test that the CLI fails to retrieve entries when the upper time limit is incremented by one second."""
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        applyid_3 = create_randomname(IdParameter.LENGTH)
        applyid_4 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_3, vars=[applyid_1])
            cursor.execute(query=sql.get_list_insert_sql_4, vars=[applyid_2])
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_3])
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_4])
            init_db_instance.commit()

        get_list_assert_target_plus1 = {
            "totalCount": 1,
            "count": 1,
            "applyResults": [
                {
                    "status": "CANCELED",
                    "applyID": applyid_3,
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == get_list_assert_target_plus1
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,result,rollbackProcedures,resumeProcedures",
                "--started-at-since",
                "2023-10-02T00:00:00Z",
                "--started-at-until",
                "2023-10-02T00:00:01Z",
                "--ended-at-since",
                "2023-10-02T12:23:59Z",
                "--ended-at-until",
                "2023-10-02T12:24:00Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_subtract_second_from_lower_time_limit(self, init_db_instance, args, capfd):
        """Test that the CLI successfully retrieves all entries when
        the lower time limit is decremented by one second."""
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        applyid_3 = create_randomname(IdParameter.LENGTH)
        applyid_4 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid_1])
            cursor.execute(query=sql.get_list_insert_sql_3, vars=[applyid_2])
            cursor.execute(query=sql.get_list_insert_sql_4, vars=[applyid_3])
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_4])
            init_db_instance.commit()

        get_list_assert_target_minus1 = {
            "totalCount": 2,
            "count": 2,
            "applyResults": [
                {
                    "status": "COMPLETED",
                    "applyID": applyid_2,
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "startedAt": "2023-10-02T00:00:00Z",
                    "endedAt": "2023-10-02T12:23:59Z",
                },
                {
                    "status": "FAILED",
                    "applyID": applyid_3,
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "startedAt": "2023-10-02T00:00:01Z",
                    "endedAt": "2023-10-02T12:24:00Z",
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        res = json.loads(out)
        assert res["count"] == get_list_assert_target_minus1["count"]
        assert res["totalCount"] == get_list_assert_target_minus1["totalCount"]
        for a in res["applyResults"]:
            a in get_list_assert_target_minus1["applyResults"]
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        ["args", "count"],
        [
            (
                [
                    "get",
                    "--fields",
                    "procedures,result,rollbackProcedures,resumeProcedures",
                    "--sort-by",
                    "startedAt",
                ],
                9,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,result,rollbackProcedures,resumeProcedures",
                    "--sort-by",
                    "endedAt",
                ],
                9,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,result,rollbackProcedures,resumeProcedures",
                    "--order-by",
                    "asc",
                ],
                9,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,result,rollbackProcedures,resumeProcedures",
                    "--order-by",
                    "desc",
                ],
                9,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,result,rollbackProcedures,resumeProcedures",
                    "--limit",
                    "5",
                ],
                5,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,result,rollbackProcedures,resumeProcedures",
                    "--limit",
                    "100",
                ],
                9,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,result,rollbackProcedures,resumeProcedures",
                    "--offset",
                    "0",
                ],
                9,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,result,rollbackProcedures,resumeProcedures",
                    "--offset",
                    "8",
                ],
                1,
            ),
            (
                [
                    "get",
                    "--fields",
                    "procedures,result,rollbackProcedures,resumeProcedures",
                    "--order-by",
                    "desc",
                    "--sort-by",
                    "endedAt",
                    "--limit",
                    "10",
                    "--offset",
                    "0",
                ],
                9,
            ),
        ],
    )
    def test_cmd_get_all_success_when_specified_sortby_and_orderby_and_count_offset(
        self, init_db_instance, count, args, capfd
    ):
        """Test that the CLI successfully retrieves all entries when"""
        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target["applyResults"]):
            result_dict["applyID"] = id_list[i]

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        a = json.loads(out)
        assert a["totalCount"] == len(id_list)
        assert a["count"] == count
        for apply in a["applyResults"]:
            assert apply in get_list_assert_target["applyResults"]
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "-s", "IN_PROGRESS"]),
        ],
    )
    def test_cmd_get_all_success_when_no_specified_sortby_and_orderby_and_count_offset(
        self, init_db_instance, args, capfd, get_list_assert_target_no_fields, mocker, caplog, docker_services
    ):  # pylint: disable=unused-argument
        """Test that the CLI successfully
        retrieves all entries when no sort by, order by, count, or offset is specified."""
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger()
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target_no_fields["applyResults"]):
            result_dict["applyID"] = id_list[i]

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        a = json.loads(out)
        assert a["totalCount"] == 1
        for apply in a["applyResults"]:
            assert apply in get_list_assert_target_no_fields["applyResults"]
        # There is no standard error output.
        assert err == ""

        assert "ORDER BY startedAt desc " in caplog.text
        assert "LIMIT 20 " in caplog.text
        assert "OFFSET 0" in caplog.text

    @pytest.mark.parametrize(
        "args",
        [
            (
                [
                    "get",
                    "--fields",
                    "procedures,result,rollbackProcedures,resumeProcedures",
                    "--offset",
                    "10",
                ]
            ),
        ],
    )
    def test_cmd_get_all_success_when_specified_offset_exceed_data_count_registered_database(
        self, init_db_instance, args, capfd
    ):
        """Test that the CLI successfully
        retrieves all entries when the specified offset exceeds the data count."""
        id_list = self.insert_list_data(init_db_instance)
        for i, result_dict in enumerate(get_list_assert_target["applyResults"]):
            result_dict["applyID"] = id_list[i]

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        a = json.loads(out)
        assert a["totalCount"] == 9
        assert a["count"] == 0
        assert a["applyResults"] == []
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "args",
        [
            [
                "get",
                "--fields",
                "procedures,result,rollbackProcedures,resumeProcedures",
                "--started-at-since",
                "2023-10-02T00:00:01Z",
                "--started-at-until",
                "2023-10-02T00:00:02Z",
                "--ended-at-since",
                "2023-10-02T12:24:00Z",
                "--ended-at-until",
                "2023-10-02T12:24:01Z",
            ]
        ],
    )
    def test_cmd_get_all_success_when_time_equals_for_time_specification(self, init_db_instance, args, capfd):
        """Test that the CLI successfully retrieves all entries when
        the start and end times are exactly equal to the specified time range."""
        # Data adjustment before testing.
        applyid_1 = create_randomname(IdParameter.LENGTH)
        applyid_2 = create_randomname(IdParameter.LENGTH)
        applyid_3 = create_randomname(IdParameter.LENGTH)
        applyid_4 = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_3, vars=[applyid_1])
            cursor.execute(query=sql.get_list_insert_sql_4, vars=[applyid_2])
            cursor.execute(query=sql.get_list_insert_sql_5, vars=[applyid_3])
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid_4])
            init_db_instance.commit()
        get_list_assert_target_equal = {
            "totalCount": 2,
            "count": 2,
            "applyResults": [
                {
                    "status": "FAILED",
                    "applyID": applyid_2,
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "startedAt": "2023-10-02T00:00:01Z",
                    "endedAt": "2023-10-02T12:24:00Z",
                },
                {
                    "status": "CANCELED",
                    "applyID": applyid_3,
                    "procedures": {"procedures": "pre_test"},
                    "result": [{"test": "test"}, {"test": "test"}],
                    "rollbackProcedures": {"procedures": "test"},
                    "startedAt": "2023-10-02T00:00:02Z",
                    "endedAt": "2023-10-02T12:24:01Z",
                    "canceledAt": "2023-10-02T12:00:00Z",
                    "executeRollback": False,
                },
            ],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        res = json.loads(out)
        assert res["count"] == get_list_assert_target_equal["count"]
        assert res["totalCount"] == get_list_assert_target_equal["totalCount"]
        for a in res["applyResults"]:
            assert a in get_list_assert_target_equal["applyResults"]
        # There is no standard error output.
        assert err == ""


class TestGetFailure:
    """Test class for failure scenarios of the get command."""

    def test_cmd_get_failure_when_failed_file_output(self, mocker, init_db_instance, capfd, caplog):
        """Test failure when file output fails."""
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        # Ensure that IN_PROGRESS data exists before the test
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_1, vars=[applyid])
            init_db_instance.commit()
        # error occurs during file output.
        mocker.patch("json.dump", side_effect=Exception)

        with tempfile.TemporaryDirectory() as tempdir:
            arg_out = os.path.join(tempdir, "result.json")
            args = ["get", "--apply-id", applyid, "--output", arg_out]
            # act
            sys.argv = ["cli.py", *args]
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 13
            # assert
            _, err = capfd.readouterr()

            # error message is displayed in the standard error output.
            assert err == "[E40006]Failed to output file.\n"
            # error log contains the error message.
            assert "[E40006]Failed to output file." in caplog.text

    def test_cmd_get_failure_when_directory_specified(self, init_db_instance, capfd):  # pylint: disable=unused-argument
        """Test failure when the output path points to a directory."""
        # arrange

        for addition_path in ["", os.path.sep]:
            with tempfile.TemporaryDirectory() as tempdir:
                arg_out = tempdir + addition_path
                args = ["get", "--apply-id", "123456789e", "--output", arg_out]
                # act
                sys.argv = ["cli.py", *args]
                with pytest.raises(SystemExit) as excinfo:
                    main()
                assert excinfo.value.code == 1
                # assert
                out, err = capfd.readouterr()
                assert out == ""
                # error message is displayed in the standard error output.
                assert err == "[E40001]Out path points to a directory.\n"

    @pytest.mark.parametrize("args", [["get", "--apply-id", "123456789a"]])
    def test_cmd_get_failure_when_failed_db_connection(self, args, mocker, capfd):
        """Test failure when the database connection cannot be established."""
        mocker.patch.object(DbAccess, "get_apply_status", side_effect=psycopg2.OperationalError)
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 10
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""

        assert "[E40018]Could not connect to ApplyStatusDB." in err

    @pytest.mark.parametrize("args", [["get", "--apply-id", "123456789a"]])
    def test_cmd_get_failure_when_query_failure_occurred(self, args, mocker, capfd, caplog):
        """Test failure when a query failure occurs."""
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

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
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 11
        out, err = capfd.readouterr()

        # There is no standard output
        assert out == ""

        assert "[E40019]Query failed." in err
        assert "[E40019]Query failed." in caplog.text

    @pytest.mark.parametrize("args", [["get", "--apply-id", "a0b1c2d3ef"]])
    def test_cmd_get_failure_when_specified_config_id_not_found(
        self, args, mocker, init_db_instance, capfd, caplog
    ):  # pylint: disable=unused-argument
        """Test failure when the specified config ID is not found."""
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.DEBUG)

        # arrange

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 12
        out, err = capfd.readouterr()

        # There is no standard output
        assert out == ""

        assert err == "[E40020]Specified a0b1c2d3ef is not found.\n"
        assert "[E40020]Specified a0b1c2d3ef is not found." in caplog.text

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "-s", "IN_PROGRES"]),
            (["get", "--status", "IN_PROGRES"]),
            (["get", "--sort-by", "status"]),
            (["get", "--order-by", "new"]),
            (["get", "--order-by", "dsc"]),
            (["get", "--limit", "0"]),
            (["get", "--limit", "-1"]),
            (["get", "--offset", "-1"]),
        ],
    )
    def test_cmd_get_failure_when_specified_id_is_invalid(self, args, capfd):
        "Test that the CLI returns an error when an invalid ID is specified."
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert "[E40001]" in err

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "--apply-id", "g21bc21587"]),  # invalid character
            (["get", "--apply-id", "ABCDEF0123"]),  # invalid character type
            (["get", "--apply-id", "あBCDEF0123"]),  # invalid character type
            (["get", "--apply-id", "a21bc2158"]),  # invalid length
            (["get", "--apply-id", "a21bc215871"]),  # invalid length
            (["get", "--apply-id", "a"]),  # invalid length
        ],
    )
    def test_cmd_get_failure_when_invalid_config_id(self, args, capfd):
        """Test that the CLI returns an error when an invalid config ID is specified."""
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert err.startswith("[E40001]")

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "--apply-id", "123456789a", "-f", "procedures,result"]),
            (["get", "--apply-id", "123456789a", "--fields", "procedures,result"]),
            (["get", "--apply-id", "123456789a", "-s", "TEST"]),
            (["get", "--apply-id", "123456789a", "--status", "TEST"]),
            (["get", "--apply-id", "123456789a", "-ss", "2023-11-22T11:11:11Z"]),
            (
                [
                    "get",
                    "--apply-id",
                    "123456789a",
                    "--started-at-since",
                    "2023-11-22T11:11:11Z",
                ]
            ),
            (["get", "--apply-id", "123456789a", "-su", "2023-11-22T11:11:11Z"]),
            (
                [
                    "get",
                    "--apply-id",
                    "123456789a",
                    "--started-at-until",
                    "2023-11-22T11:11:11Z",
                ]
            ),
            (["get", "--apply-id", "123456789a", "-es", "2023-11-22T11:11:11Z"]),
            (
                [
                    "get",
                    "--apply-id",
                    "123456789a",
                    "--ended-at-since",
                    "2023-11-22T11:11:11Z",
                ]
            ),
            (["get", "--apply-id", "123456789a", "-eu", "2023-11-22T11:11:11Z"]),
            (
                [
                    "get",
                    "--apply-id",
                    "123456789a",
                    "--ended-at-until",
                    "2023-11-22T11:11:11Z",
                ]
            ),
            (
                [
                    "get",
                    "--apply-id",
                    "123456789a",
                    "-s",
                    "TEST",
                    "-ss",
                    "2023-11-22T11:11:11Z",
                    "-su",
                    "2023-11-22T11:11:11Z",
                    "-es",
                    "2023-11-22T11:11:11Z",
                    "-eu",
                    "2023-11-22T11:11:11Z",
                ]
            ),
            (
                [
                    "get",
                    "--apply-id",
                    "123456789a",
                    "--status",
                    "TEST",
                    "--started-at-since",
                    "2023-11-22T11:11:11Z",
                    "--started-at-until",
                    "2023-11-22T11:11:11Z",
                    "--ended-at-since",
                    "2023-11-22T11:11:11Z",
                    "--ended-at-until",
                    "2023-11-22T11:11:11Z",
                ]
            ),
            (["get", "--apply-id", "123456789a", "--sort-by", "startedAt"]),
            (["get", "--apply-id", "123456789a", "--order-by", "desc"]),
            (["get", "--apply-id", "123456789a", "--limit", "1"]),
            (["get", "--apply-id", "123456789a", "--offset", "0"]),
        ],
    )
    def test_cmd_get_failure_when_id_and_invalid_option(self, args, capfd):
        "Test that the CLI returns an error when an invalid option"
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert (
            "[E40001]Not allowed with argument --fields, --status, --started-at-since, "
            + "--started-at-until, --ended-at-since, --ended-at-until, --sort-by, --order-by, --limit, --offset."
        ) in err

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "-ss", "2023"]),
            (["get", "-ss", "2023-11"]),
            (["get", "-ss", "20231122"]),
            (["get", "-ss", "2023-11-22T11"]),
            (["get", "-ss", "2023-11-22T1122"]),
            (["get", "-ss", "2023-11-22T11:22"]),
            (["get", "-ss", "2023-11-22T112233.11"]),
            (["get", "-ss", "2023-11-22T11:22:33.11"]),
            (["get", "-ss", "20231122T11:11:11Z"]),
            (["get", "-ss", "2023-11-22"]),
            (["get", "-ss", "20231122T111111Z"]),
            (["get", "-ss", "2023-11-22 11:11:11"]),
            (["get", "-su", "20231122T11:11:11Z"]),
            (["get", "-su", "2023-11-22"]),
            (["get", "-su", "20231122T111111Z"]),
            (["get", "-su", "2023-11-22 11:11:11"]),
            (["get", "--ended-at-since", "20231122T11:11:11Z"]),
            (["get", "-es", "2023-11-22"]),
            (["get", "-es", "20231122T111111Z"]),
            (["get", "-es", "2023-11-22 11:11:11"]),
            (["get", "--ended-at-until", "20231122T11:11:11Z"]),
            (["get", "-eu", "2023-11-22"]),
            (["get", "-eu", "20231122T111111Z"]),
            (["get", "-eu", "2023-11-22 11:11:11"]),
            (["get", "-ss", "2023-11-22T11:11:11+09:00"]),
            (["get", "-ss", "2023-11-22T11:11:11-08:00"]),
            (["get", "-ss", "2023-11-22T11:11:11+0555"]),
            (["get", "-ss", "2023-11-22T11:11:11-11"]),
        ],
    )
    def test_cmd_get_all_success_when_valid_start_and_end_time_specified(
        self, init_db_instance, args, capfd
    ):  # pylint: disable=unused-argument
        "Test that the 'get' command succeeds when valid start and end times are specified."
        # Data adjustment before testing.
        assert_target = {
            "totalCount": 0,
            "count": 0,
            "applyResults": [],
        }

        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # standard output displays information about the list of configuration proposal reflection statuses.
        assert json.loads(out) == assert_target
        # There is no standard error output.
        assert err == ""

    def test_cmd_get_all_failure_when_failed_file_output(
        self, mocker, init_db_instance, capfd, caplog
    ):  # pylint: disable=unused-argument
        "Test that the 'get' command fails when file output encounters an error."
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.ERROR)
        # arrange
        # error occurs during file output.
        mocker.patch("json.dump", side_effect=Exception)

        with tempfile.TemporaryDirectory() as tempdir:
            arg_out = os.path.join(tempdir, "result.json")
            args = ["get", "--output", arg_out]
            # act
            sys.argv = ["cli.py", *args]
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 13
            # assert
            _, err = capfd.readouterr()
            # error message is displayed in the standard error output.
            assert err == "[E40006]Failed to output file.\n"
            # error log contains the error message.
            assert "[E40006]Failed to output file." in caplog.text

    def test_cmd_get_all_failure_when_directory_specified(
        self, init_db_instance, capfd
    ):  # pylint: disable=unused-argument
        "Test that the 'get' command fails when the output path points to a directory."

        for addition_path in ["", os.path.sep]:
            with tempfile.TemporaryDirectory() as tempdir:
                arg_out = tempdir + addition_path
                args = ["get", "--output", arg_out]
                # act
                sys.argv = ["cli.py", *args]
                with pytest.raises(SystemExit) as excinfo:
                    main()
                assert excinfo.value.code == 1
                # assert
                out, err = capfd.readouterr()
                assert out == ""
                # error message is displayed in the standard error output.
                assert err == "[E40001]Out path points to a directory.\n"

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "--started-at-since", "2023-11-2211:11:11Z"]),
            (["get", "-ss", "T11:11:11Z"]),
            (["get", "-ss", "2023/11/22T11:11:11Z"]),
            (["get", "--started-at-until", "2023-11-2211:11:11Z"]),
            (["get", "-su", "T11:11:11Z"]),
            (["get", "-su", "2023/11/22T11:11:11Z"]),
            (["get", "-es", "2023-11-2211:11:11Z"]),
            (["get", "-es", "T11:11:11Z"]),
            (["get", "-es", "2023/11/22T11:11:11Z"]),
            (["get", "-eu", "2023-11-2211:11:11Z"]),
            (["get", "-eu", "T11:11:11Z"]),
            (["get", "-eu", "2023/11/22T11:11:11Z"]),
            (["get", "-eu", "2023-11-22T11:11:11Z+09:00"]),
            (["get", "-eu", "0000-11-22T11:11:11Z+09:00"]),
        ],
    )
    def test_cmd_get_all_failure_when_invalid_start_and_end_time_specified(self, args, capfd):
        """Test that the command fails when invalid start and end time are specified."""
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert err.startswith("[E40001]")

    @pytest.mark.parametrize("args", [["get"]])
    def test_cmd_get_all_failure_when_failed_db_connection(self, args, mocker, capfd):
        """Test that the command fails when the database connection cannot be established."""
        mocker.patch.object(DbAccess, "get_apply_status_list", side_effect=psycopg2.OperationalError)
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 10
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""

        assert "[E40018]Could not connect to ApplyStatusDB." in err

    @pytest.mark.parametrize(
        "args",
        [
            (["get", "--fields", ","]),  # empty
            (["get", "--fields", "procedure"]),  # invalid value
            (["get", "--fields", "sresult"]),  # invalid value
            (["get", "--fields", "rollbackProcedure"]),  # invalid value
            (
                [
                    "get",
                    "--fields",
                    "procedures/result",
                ]
            ),  # invalid sperator
            (
                [
                    "get",
                    "--fields",
                    "procedure,sresult",
                ]
            ),  # invalid sperator
        ],
    )
    def test_cmd_get_all_failure_when_invalid_fields(self, args, capfd):
        """Test that the CLI fails when invalid fields are provided."""
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert err.startswith("[E40001]")
