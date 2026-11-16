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

import logging
import logging.config  # pylint:disable=unused-import
import os
import re
import sys
from multiprocessing import Process
from time import sleep

import psycopg2
import pytest
from psycopg2.extras import DictCursor
from werkzeug import Response

from layoutapply.cli import LayoutApplyCommandLine, main
from layoutapply.common.logger import Logger
from layoutapply.const import Action, ExitCode, IdParameter
from layoutapply.db import DbAccess
from layoutapply.main import run
from layoutapply.setting import LayoutApplyConfig, LayoutApplyLogConfig
from layoutapply.util import create_randomname
from tests.layoutapply.conftest import (
    DEVICE_INFO_URL,
    GET_INFORMATION_URI,
    HARDWARE_CONTROL_URI,
    OPERATION_URL,
    OS_BOOT_URL,
    POWER_OPERATION_URL,
)
from tests.layoutapply.test_data import sql


class TestHelp:
    """Test class for resume command help."""

    @pytest.mark.parametrize(
        "args",
        [
            (
                [
                    "resume",
                    "--help",
                ]
            ),
            (
                [
                    "resume",
                    "-h",
                ]
            ),
        ],
    )
    def test_cmd_resume_success_when_help(
        self,
        args,
        capfd,
    ):
        "Test that the resume command displays the help message successfully."
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
        assert "specified applyID for resume. applyID as a string." in out


@pytest.mark.usefixtures("httpserver_listen_address")
class TestResumeSuccess:
    """Test class for resume command success."""

    @pytest.mark.skip("When fix this test, please delete test_cmd_resume_success_use_run_function test.")
    @pytest.mark.parametrize("args", [["resume", "--apply-id", "300000004d"]])
    def test_cmd_resume_success(self, mocker, init_db_instance, args, httpserver):
        """Test for resume command success."""
        uri = HARDWARE_CONTROL_URI

        httpserver.clear()
        httpserver.clear_all_handlers()

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="""
                    INSERT into applystatus (applyid, status, procedures, result, rollbackprocedures, startedat, \
                    endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand,\
                    processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000004d','SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,\
                    '2023/10/02 00:00:00',null,null,null,\
                    '[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',\
                    null,null,null,'2023/10/02 12:23:59',null);
                """)
            init_db_instance.commit()
        # arrange

        applyid = "300000004d"

        sys.argv = ["cli.py", *args]

        config = LayoutApplyConfig()
        config.load_log_configs()
        # act
        procces_mock = mocker.patch(
            "subprocess.Popen",
            return_value=Process(
                target=run,
                args=(
                    {
                        "procedures": [
                            {
                                "operationID": 1,
                                "operation": "shutdown",
                                "targetDeviceID": "0001",
                                "dependencies": [],
                            }
                        ]
                    },
                    config,
                    applyid,
                    Action.RESUME,
                ),
            ),
        )
        with pytest.raises(SystemExit) as excinfo:
            procces_mock.return_value.start()
            main()

        # with httpserver.wait(stop_on_nohandler=False, timeout=0.1) as waiter:
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(  # noqa: W605
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        httpserver.expect_request(
            re.compile(f"\/{GET_INFORMATION_URI}\/{DEVICE_INFO_URL}"), method="GET"  # noqa: W605
        ).respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()

        # assert
        assert excinfo.value.code == 0

        # result of the operation completion list is 'IN_PROGRESS'
        if row.get("status") == "IN_PROGRESS":
            assert row.get("status") == "IN_PROGRESS"
            for i in range(15):
                sleep(0.5)
                try:
                    with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                        cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
                        init_db_instance.commit()
                        row = cursor.fetchone()
                except psycopg2.ProgrammingError:
                    break
                if row.get("status") == "COMPLETED":
                    break

        assert row.get("status") == "COMPLETED"
        assert row.get("rollbackprocedures") is None
        details = row.get("result")
        procedures = row.get("resumeprocedures")
        assert details is not None
        assert len(details) == len(procedures)
        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")
        for proc in procedures:
            # Search for items corresponding to the migration procedure from
            # result details using operationID as a condition
            id_cnt = sum(1 for n in details if n["operationID"] == proc["operationID"])
            detail = [i for i in details if i["operationID"] == proc["operationID"]][id_cnt - 1]
            assert proc["operationID"] == detail["operationID"]
            assert "COMPLETED" == detail["status"]
            # Check the URI, etc. of the hardware control API
            match proc["operation"]:
                case "shutdown":
                    assert re.fullmatch(
                        f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa: W605
                        detail["uri"],
                    )
                    assert "PUT" == detail["method"]
                    assert "queryParameter" not in detail
                    assert 200 == detail["statusCode"]
                    assert {"action": "off"} == detail["requestBody"]
                    get_information = detail["getInformation"]
                    assert {"powerState": "Off"} == get_information["responseBody"]

        if procces_mock.return_value.is_alive():
            procces_mock.return_value.terminate()
            procces_mock.return_value.join()
        sleep(1)
        httpserver.clear()
        httpserver.clear_all_handlers()

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "300000004d"]])
    def test_cmd_resume_success_not_subprocess(self, init_db_instance, args, httpserver):
        """Test the resume command when not running as a subprocess."""
        uri = HARDWARE_CONTROL_URI

        httpserver.clear()
        httpserver.clear_all_handlers()

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="""
                    INSERT into applystatus (applyid, status, procedures, result, rollbackprocedures, startedat,\
                    endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand,\
                    processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000004d','SUSPENDED','{"procedures": "pre_test"}','[{"operationID": 1, "status": "FAILED"}]',\
                    null,'2023/10/02 00:00:00',null,null,null,\
                    '[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',\
                    null,null,null,'2023/10/02 12:23:59',null);
                """)
            init_db_instance.commit()

        # arrange
        applyid = "300000004d"
        procedures = {
            "procedures": [{"operationID": 1, "operation": "shutdown", "targetDeviceID": "0001", "dependencies": []}]
        }

        sys.argv = ["cli.py", *args]

        config = LayoutApplyConfig()
        config.load_log_configs()

        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{GET_INFORMATION_URI}\/{DEVICE_INFO_URL}"), method="GET"  # noqa: W605
        ).respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )

        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        run(procedures, config, applyid, Action.RESUME)

        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()

        # assert
        assert excinfo.value.code == 0
        assert row.get("status") == "COMPLETED"
        assert row.get("rollbackprocedures") is None
        assert row.get("resumeresult") is None
        details = row.get("result")
        resume_procedures = row.get("resumeprocedures")
        assert details is not None
        assert len(details) == len(resume_procedures) + 1

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")

        for proc in resume_procedures:
            id_cnt = sum(1 for n in details if n["operationID"] == proc["operationID"])
            detail = [i for i in details if i["operationID"] == proc["operationID"]][id_cnt - 1]
            assert proc["operationID"] == detail["operationID"]
            assert "COMPLETED" == detail["status"]

            match proc["operation"]:
                case "shutdown":
                    assert re.fullmatch(
                        f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa: W605
                        detail["uri"],
                    )
                    assert "PUT" == detail["method"]
                    assert "queryParameter" not in detail
                    assert 200 == detail["statusCode"]
                    assert {"action": "off"} == detail["requestBody"]
                    get_information = detail["getInformation"]
                    assert {"powerState": "Off"} == get_information["responseBody"]

        httpserver.clear()
        httpserver.clear_all_handlers()

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "300000004d"]])
    def test_cmd_resume_success_use_run_function(self, mocker, init_db_instance, args, httpserver):
        """Test the resume command using the run function."""
        uri = HARDWARE_CONTROL_URI

        httpserver.clear()
        httpserver.clear_all_handlers()

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="""
                    INSERT into applystatus (applyid, status, procedures, result, rollbackprocedures, startedat,\
                    endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand,\
                    processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000004d','SUSPENDED','{"procedures": "pre_test"}','[{"operationID": 1, "status": "FAILED"},\
                    {"operationID": 2, "status": "SKIPPED"}]',null,'2023/10/02 00:00:00',null,null,null,\
                    '[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []},\
                    {"operationID": 2, "operation": "shutdown", "targetDeviceID": "0002", "dependencies": [1]}]',\
                    null,null,null,'2023/10/02 12:23:59',null);
                """)
            init_db_instance.commit()
        # arrange

        applyid = "300000004d"
        procedures = {
            "procedures": [
                {"operationID": 1, "operation": "shutdown", "targetDeviceID": "0001", "dependencies": []},
                {"operationID": 2, "operation": "shutdown", "targetDeviceID": "0002", "dependencies": [1]},
            ]
        }
        sys.argv = ["cli.py", *args]

        config = LayoutApplyConfig()
        config.load_log_configs()
        # act
        procces_mock = mocker.patch(
            "subprocess.Popen",
            return_value=Process(
                target=run,
                args=(
                    procedures,
                    config,
                    applyid,
                    Action.RESUME,
                ),
            ),
        )
        with pytest.raises(SystemExit) as excinfo:
            procces_mock.return_value.start()
            main()

        # with httpserver.wait(stop_on_nohandler=False, timeout=0.1) as waiter:
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(  # noqa: W605
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        httpserver.expect_request(
            re.compile(f"\/{GET_INFORMATION_URI}\/{DEVICE_INFO_URL}"), method="GET"  # noqa: W605
        ).respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()

        # assert
        assert excinfo.value.code == 0

        # result of the operation completion list is 'IN_PROGRESS'
        if row.get("status") == "IN_PROGRESS":
            assert row.get("status") == "IN_PROGRESS"
            for i in range(15):
                sleep(0.5)
                try:
                    with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                        cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
                        init_db_instance.commit()
                        row = cursor.fetchone()
                except psycopg2.ProgrammingError:
                    break
                if row.get("status") == "COMPLETED":
                    break

        if row.get("status") != "COMPLETED":
            run(procedure=procedures, config=config, applyID=applyid, action=Action.RESUME)
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
                init_db_instance.commit()
                row = cursor.fetchone()

        assert row.get("status") == "COMPLETED"
        assert row.get("rollbackprocedures") is None
        details = row.get("result")
        resume_procedures = row.get("resumeprocedures")
        assert details is not None
        assert row.get("resumeresult") is None
        assert len(details) == len(resume_procedures) + 1
        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")

        for proc in resume_procedures:
            # Search for items corresponding to the migration procedure from
            # result details using operationID as a condition
            id_cnt = sum(1 for n in details if n["operationID"] == proc["operationID"])
            detail = [i for i in details if i["operationID"] == proc["operationID"]][id_cnt - 1]
            assert proc["operationID"] == detail["operationID"]
            assert "COMPLETED" == detail["status"]
            # Check the URI, etc. of the hardware control API
            match proc["operation"]:
                case "shutdown":
                    assert re.fullmatch(
                        f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa: W605
                        detail["uri"],
                    )
                    assert "PUT" == detail["method"]
                    assert "queryParameter" not in detail
                    assert 200 == detail["statusCode"]
                    assert {"action": "off"} == detail["requestBody"]
                    get_information = detail["getInformation"]
                    assert {"powerState": "Off"} == get_information["responseBody"]

        if procces_mock.return_value.is_alive():
            procces_mock.return_value.terminate()
            procces_mock.return_value.join()
        sleep(1)
        httpserver.clear()
        httpserver.clear_all_handlers()

    @pytest.mark.skip("When fix this test, please delete \
            the test_cmd_resume_success_when_rollback_state_suspended_use_run_function test.")
    @pytest.mark.parametrize("args", [["resume", "--apply-id", "300000013d"]])
    def test_cmd_resume_success_when_rollback_state_suspended(self, mocker, init_db_instance, args, httpserver):
        """Test the resume command when the rollback state is suspended."""
        uri = HARDWARE_CONTROL_URI

        httpserver.clear()
        httpserver.clear_all_handlers()

        # with httpserver.wait(stop_on_nohandler=False, timeout=0.1) as waiter:
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(  # noqa: W605
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        httpserver.expect_request(
            re.compile(f"\/{GET_INFORMATION_URI}\/{DEVICE_INFO_URL}"), method="GET"  # noqa: W605
        ).respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="""
                    INSERT into applystatus (applyid, status, procedures, result, rollbackprocedures, startedat,\
                    endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand,\
                    processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000013d','CANCELED','{"procedures": "pre_test"}','[{"operationID": 1, "status": "CANCELED"}]',\
                    null,'2023/10/02 00:00:00',null,'2023/10/02 00:30:00',TRUE,null,null,null,null,null,null);
                """)
            cursor.execute(query="""
                    INSERT into rollbackstatus (applyid, status, procedures, result, startedat, endedat, canceledat,\
                    resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000013d','SUSPENDED','{"procedures": "pre_test"}','[{"operationID": 1, "status": "FAILED"}]',\
                    '2023/10/02 00:00:00',null,null,'[{"operationID": 1, "operation": "shutdown",\
                    "targetDeviceID": "0001","dependencies": []}]',null,null,null,'2023/10/02 00:50:00',null);
                """)
        init_db_instance.commit()
        # arrange

        applyid = "300000013d"

        sys.argv = ["cli.py", *args]

        config = LayoutApplyConfig()
        config.load_log_configs()
        # act
        procces_mock = mocker.patch(
            "subprocess.Popen",
            return_value=Process(
                target=run,
                args=(
                    {
                        "procedures": [
                            {
                                "operationID": 1,
                                "operation": "shutdown",
                                "targetDeviceID": "0001",
                                "dependencies": [],
                            }
                        ]
                    },
                    config,
                    applyid,
                    Action.ROLLBACK_RESUME,
                ),
            ),
        )
        with pytest.raises(SystemExit) as excinfo:
            procces_mock.return_value.start()
            main()
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()
        init_db_instance.commit()
        # assert
        assert excinfo.value.code == 0

        # result of the operation completion list is 'IN_PROGRESS'
        if row.get("rollbackstatus") == "IN_PROGRESS":
            assert row.get("rollbackstatus") == "IN_PROGRESS"
            for i in range(15):
                sleep(0.5)
                try:
                    with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                        cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
                        init_db_instance.commit()
                        row = cursor.fetchone()
                except psycopg2.ProgrammingError:
                    break
                if row.get("rollbackstatus") == "COMPLETED":
                    break

        assert row.get("rollbackstatus") == "COMPLETED"
        details = row.get("rollbackresult")
        procedures = row.get("resumeprocedures")
        assert details is not None
        assert row.get("resumeresult") is None
        assert len(details) == len(procedures) + 1
        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")
        for proc in procedures:
            # Search for items corresponding to the migration procedure from
            # result details using operationID as a condition
            detail = [i for i in details if i["operationID"] == proc["operationID"]][1]
            assert proc["operationID"] == detail["operationID"]
            assert "COMPLETED" == detail["status"]
            # Check the URI, etc. of the hardware control API
            match proc["operation"]:
                case "shutdown":
                    assert re.fullmatch(
                        f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa: W605
                        detail["uri"],
                    )
                    assert "PUT" == detail["method"]
                    assert "queryParameter" not in detail
                    assert 200 == detail["statusCode"]
                    assert {"action": "off"} == detail["requestBody"]
                    get_information = detail["getInformation"]
                    assert {"powerState": "Off"} == get_information["responseBody"]

        if procces_mock.return_value.is_alive():
            procces_mock.return_value.terminate()
            procces_mock.return_value.join()
        sleep(1)
        httpserver.clear()
        httpserver.clear_all_handlers()

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "300000013d"]])
    def test_cmd_resume_success_when_rollback_state_suspended_not_subprocess(self, init_db_instance, args, httpserver):
        """Test the resume command when the rollback state is suspended and not running as a subprocess."""
        uri = HARDWARE_CONTROL_URI

        httpserver.clear()
        httpserver.clear_all_handlers()

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="""
                    INSERT into applystatus (applyid, status, procedures, result, rollbackprocedures, startedat,\
                    endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand,\
                    processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000013d','CANCELED','{"procedures": "pre_test"}','[{"operationID": 1, "status": "CANCELED"}]',\
                    null,'2023/10/02 00:00:00','2023/10/02 01:00:00','2023/10/02 00:30:00',\
                    TRUE,null,null,null,null,null,null);
                """)
            cursor.execute(query="""
                    INSERT into rollbackstatus (applyid, status, procedures, result, startedat, endedat, canceledat,\
                    resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000013d','SUSPENDED','{"procedures": "pre_test"}','[{"operationID": 1, "status": "FAILED"}]',\
                    '2023/10/02 00:00:00',null,null,'[{"operationID": 1, "operation": "shutdown",\
                    "targetDeviceID": "0001","dependencies": []}]',null,null,null,'2023/10/02 00:50:00',null);
                """)
            init_db_instance.commit()

        # arrange
        applyid = "300000013d"
        procedures = {
            "procedures": [{"operationID": 1, "operation": "shutdown", "targetDeviceID": "0001", "dependencies": []}]
        }

        sys.argv = ["cli.py", *args]

        config = LayoutApplyConfig()
        config.load_log_configs()

        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{GET_INFORMATION_URI}\/{DEVICE_INFO_URL}"), method="GET"  # noqa: W605
        ).respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )

        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        run(procedures, config, applyid, Action.ROLLBACK_RESUME)

        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM rollbackstatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()

        # assert
        assert excinfo.value.code == 0
        assert row.get("status") == "COMPLETED"
        details = row.get("result")
        resum_procedures_list = row.get("resumeprocedures")
        assert details is not None
        assert row.get("resumeresult") is None
        assert len(details) == len(resum_procedures_list) + 1

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")

        for proc in resum_procedures_list:
            id_cnt = sum(1 for n in details if n["operationID"] == proc["operationID"])
            detail = [i for i in details if i["operationID"] == proc["operationID"]][id_cnt - 1]
            assert proc["operationID"] == detail["operationID"]
            assert "COMPLETED" == detail["status"]

            match proc["operation"]:
                case "shutdown":
                    assert re.fullmatch(
                        f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa: W605
                        detail["uri"],
                    )
                    assert "PUT" == detail["method"]
                    assert "queryParameter" not in detail
                    assert 200 == detail["statusCode"]
                    assert {"action": "off"} == detail["requestBody"]
                    get_information = detail["getInformation"]
                    assert {"powerState": "Off"} == get_information["responseBody"]

        httpserver.clear()
        httpserver.clear_all_handlers()

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "300000013d"]])
    def test_cmd_resume_success_when_rollback_state_suspended_use_run_function(
        self, mocker, args, init_db_instance, httpserver
    ):
        """Test the resume command when the rollback state is suspended and using the run function."""
        uri = HARDWARE_CONTROL_URI

        httpserver.clear()
        httpserver.clear_all_handlers()

        # with httpserver.wait(stop_on_nohandler=False, timeout=0.1) as waiter:
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa: W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(  # noqa: W605
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        httpserver.expect_request(
            re.compile(f"\/{GET_INFORMATION_URI}\/{DEVICE_INFO_URL}"), method="GET"  # noqa: W605
        ).respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="""
                    INSERT into applystatus (applyid, status, procedures, result, rollbackprocedures, startedat,\
                    endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand,\
                    processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000013d','CANCELED','{"procedures": "pre_test"}','[{"operationID": 1, "status": "COMPLETED"},\
                    {"operationID": 2, "status": "CANCELED"}]',null,'2023/10/02 00:00:00','2023/10/02 01:00:00',\
                    '2023/10/02 00:30:00',TRUE,null,null,null,null,null,null);
                """)
            cursor.execute(query="""
                    INSERT into rollbackstatus (applyid, status, procedures, result, startedat, endedat, canceledat,\
                    resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000013d','SUSPENDED','{"procedures": "pre_test"}','[{"operationID": 1, "status": "FAILED"},\
                    {"operationID": 2, "status": "SKIPPED"}]', '2023/10/02 00:00:00',null,null,\
                    '[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []},\
                    {"operationID": 2, "operation": "shutdown", "targetDeviceID": "0002", "dependencies": [1]}]',\
                    null,null,null,'2023/10/02 00:50:00',null);
                """)
        init_db_instance.commit()
        # arrange

        applyid = "300000013d"
        procedures = {
            "procedures": [
                {"operationID": 1, "operation": "shutdown", "targetDeviceID": "0001", "dependencies": []},
                {"operationID": 2, "operation": "shutdown", "targetDeviceID": "0002", "dependencies": [1]},
            ]
        }
        sys.argv = ["cli.py", *args]

        config = LayoutApplyConfig()
        config.load_log_configs()
        # act
        procces_mock = mocker.patch(
            "subprocess.Popen",
            return_value=Process(
                target=run,
                args=(
                    procedures,
                    config,
                    applyid,
                    Action.ROLLBACK_RESUME,
                ),
            ),
        )
        with pytest.raises(SystemExit) as excinfo:
            procces_mock.return_value.start()
            main()
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM rollbackstatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()
        init_db_instance.commit()
        # assert
        assert excinfo.value.code == 0

        # result of the operation completion list is 'IN_PROGRESS'
        if row.get("status") == "IN_PROGRESS":
            assert row.get("status") == "IN_PROGRESS"
            for i in range(15):
                sleep(0.5)
                try:
                    with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                        cursor.execute(query=f"SELECT * FROM rollbackstatus WHERE applyid = '{applyid}'")
                        init_db_instance.commit()
                        row = cursor.fetchone()
                except psycopg2.ProgrammingError:
                    break
                if row.get("status") == "COMPLETED":
                    break

        if row.get("status") != "COMPLETED":
            run(procedure=procedures, config=config, applyID=applyid, action=Action.ROLLBACK_RESUME)

            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=f"SELECT * FROM rollbackstatus WHERE applyid = '{applyid}'")
                init_db_instance.commit()
                row = cursor.fetchone()

        assert row.get("status") == "COMPLETED"
        details = row.get("result")
        resum_procedures = row.get("resumeprocedures")
        assert details is not None
        assert row.get("resumeresult") is None
        assert len(details) == len(resum_procedures) + 1

        host = config.hardware_control.get("host")
        port = config.hardware_control.get("port")
        uri = config.hardware_control.get("uri")

        for proc in resum_procedures:
            # Search for items corresponding to the migration procedure from
            # result details using operationID as a condition
            id_cnt = sum(1 for n in details if n["operationID"] == proc["operationID"])
            detail = [i for i in details if i["operationID"] == proc["operationID"]][id_cnt - 1]
            assert proc["operationID"] == detail["operationID"]
            assert "COMPLETED" == detail["status"]
            # Check the URI, etc. of the hardware control API
            match proc["operation"]:
                case "shutdown":
                    assert re.fullmatch(
                        f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa: W605
                        detail["uri"],
                    )
                    assert "PUT" == detail["method"]
                    assert "queryParameter" not in detail
                    assert 200 == detail["statusCode"]
                    assert {"action": "off"} == detail["requestBody"]
                    get_information = detail["getInformation"]
                    assert {"powerState": "Off"} == get_information["responseBody"]

        if procces_mock.return_value.is_alive():
            procces_mock.return_value.terminate()
            procces_mock.return_value.join()
        sleep(1)
        httpserver.clear()
        httpserver.clear_all_handlers()

    def test_cmd_resume_success_when_rollback_id_executed(self, init_db_instance, capfd):
        """Test that the resume command succeeds when the rollback ID has been executed."""
        # arrage
        applyid = create_randomname(IdParameter.LENGTH)
        # Ensure that IN_PROGRESS data exists before the test
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_fields_insert_sql_6, vars=[applyid])
            cursor.execute(query=sql.get_fields_insert_sql_r_6, vars=[applyid])
            init_db_instance.commit()

        args = ["resume", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]

        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # Ensure that a successful completion log is output to standard output.
        assert "Success" in out
        assert "status=CANCELED" in out
        assert "rollbackStatus=COMPLETED" in out
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "insert_sql",
        [
            (sql.get_list_insert_sql_3),  # COMPLETED
            (sql.get_list_insert_sql_4),  # FAILED
            (sql.get_list_insert_sql_5),  # CANCELED
        ],
    )
    def test_cmd_resume_success_when_executed_id(self, init_db_instance, insert_sql, capfd):
        """Test that the resume command succeeds when the layoutapply ID has already been executed."""
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()

        args = ["resume", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]

        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.NORMAL
        out, err = capfd.readouterr()
        # Ensure that a successful completion log is output to standard output.
        assert "Success" in out
        # There is no standard error output.
        assert err == ""

    @pytest.mark.parametrize(
        "insert_sql",
        [
            (sql.get_list_insert_sql_1),  # IN_PROGRESS
            (sql.get_list_insert_sql_2),  # CANCELING
        ],
    )
    def test_cmd_resume_success_when_id_in_execution(self, init_db_instance, insert_sql, capfd):
        """Test that the resume command succeeds when the layoutapply ID is currently in execution."""
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()

        args = ["resume", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # arrange
        # Data adjustment before testing.
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=insert_sql, vars=[applyid])
            init_db_instance.commit()

        args = ["resume", "--apply-id", applyid]
        sys.argv = ["cli.py", *args]

        # act
        with pytest.raises(SystemExit) as excinfo:
            main()

        # assert
        assert excinfo.value.code == ExitCode.MULTIPLE_RUN_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # error E40022 is output to the standard error.
        assert "[E40022]This layoutapply has already executed." in err


@pytest.mark.usefixtures("httpserver_listen_address")
class TestResumeFailure:
    """Test class for resume command failures."""

    @pytest.mark.parametrize(
        "args",
        [
            (["resume", "--apply-id", "g21bc21587"]),  # character type violation
            (["resume", "--apply-id", "ABCDEF0123"]),  # character type violation
            (["resume", "--apply-id", "あBCDEF0123"]),  # character type violation
            (["resume", "--apply-id", "a21bc2158"]),  # character length violation
            (["resume", "--apply-id", "a21bc215871"]),  # character length violation
            (["resume", "--apply-id", "a"]),  # character length violation
        ],
    )
    def test_cmd_resume_failure_when_invalid_id(self, args, capfd):
        "Test that the resume command fails when an invalid apply ID is provided."
        sys.argv = ["cli.py", *args]
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
        out, err = capfd.readouterr()
        # An error message is displayed.
        assert out == ""
        assert err.startswith("[E40001]")

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "012345678a"]])
    def test_cmd_resume_failure_when_invalid_config_file(self, mocker, args, capfd):
        "Test that the resume command fails when the configuration file is invalid."
        config = {
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

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "012345678d"]])
    def test_cmd_resume_failure_when_failed_db_connection(self, mocker, args, capfd):
        "Test that the resume command fails when the database connection cannot be established."
        assert_print = "[E40018]Could not connect to ApplyStatusDB."
        mocker.patch.object(DbAccess, "proc_resume", side_effect=psycopg2.OperationalError)
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

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "012345678d"]])
    def test_cmd_resume_failure_when_query_failure_occurred(self, mocker, args, capfd):
        "Test that the resume command fails when a query failure occurs."
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

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "abcdeabcde"]])
    def test_cmd_resume_failure_when_nonexistent_id(
        self, init_db_instance, args, capfd
    ):  # pylint: disable=unused-argument
        "Test that the resume command fails when a nonexistent apply ID is specified."
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

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "300000007b"]])
    def test_cmd_resume_failure_when_failed_to_start_subprocess(self, capfd, mocker, init_db_instance, args, caplog):
        "Test that the resume command fails when it fails to start a subprocess."
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="""
                    INSERT into applystatus (applyid, status, procedures, result, rollbackprocedures, startedat,\
                    endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand,\
                    processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000007b','SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,\
                    '2023/10/02 00:00:00',null,null,null,\
                    '{"procedures": [{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", \
                    "dependencies": []}]}',null,null,null,'2023/10/02 12:23:59',null);
                """)
            init_db_instance.commit()
        # arrange
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.ERROR)

        # arrange

        # Mock the subprocess
        mocker.patch(
            "subprocess.Popen",
            side_effect=Exception(),
        )

        sys.argv = ["cli.py", *args]

        # act
        with pytest.raises(SystemExit) as excinfo:
            main()
        out, err = capfd.readouterr()
        # assert
        assert excinfo.value.code == 5
        # There is no standard output
        assert out == ""

        assert "[E40026]Failed to start subprocess." in err
        assert "[E40026]Failed to start subprocess." in caplog.text

    @pytest.mark.parametrize("args", [["resume", "--apply-id", "300000012c"]])
    def test_cmd_resume_failure_when_rollback_id_in_progress(self, init_db_instance, args, capfd):
        """Test that the resume command fails when the rollback ID is currently in progress."""
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="""
                    INSERT into applystatus (applyid, status, procedures, result, rollbackprocedures, startedat,\
                    endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand,\
                    processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000012c','CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',\
                    '{"procedures": "pre_test"}','2023/10/02 00:00:00','2023/10/02 01:00:00','2023/10/02 00:30:00',\
                    TRUE,null,null,null,null,null,null);
                """)
            cursor.execute(query="""
                    INSERT into rollbackstatus (applyid, status, procedures, result, startedat, endedat, canceledat,\
                    resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000012c','IN_PROGRESS','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',\
                    '2023/10/02 00:00:00',null,null,\
                    '[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',\
                    null,null,null,'2023/10/02 00:50:00',null);
                """)
            init_db_instance.commit()
        assert_print = "[E40022]This layoutapply has already executed.\n"

        sys.argv = ["cli.py", *args]
        # act
        with pytest.raises(SystemExit) as excinfo:
            main()
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="DELETE FROM applystatus WHERE applyid = '300000012c'")
            init_db_instance.commit()
        # assert
        assert excinfo.value.code == ExitCode.MULTIPLE_RUN_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # error E40022 is output to the standard error.
        assert err == assert_print

    def test_cmd_resume_failure_when_db_access_failure_during_subprocess_registration(self, mocker, capfd):
        """Test failure when database access fails during subprocess registration."""
        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = psycopg2.OperationalError
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)
        config = LayoutApplyLogConfig().log_config
        logger = Logger(config)
        db = DbAccess(logger)
        # act
        sys.argv = ["cli.py", "resume", "--apply-id", "dummy"]
        with pytest.raises(SystemExit) as excinfo:
            LayoutApplyCommandLine()._update_subporcess_info(db, os.getpid(), "dummy", Action.RESUME)

        # assert
        assert excinfo.value.code == ExitCode.DB_CONNECT_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # Ensure that the E40018 error is output to the standard error.
        assert "[E40018]Could not connect to ApplyStatusDB." in err

    def test_cmd_resume_failure_when_query_failure_during_subprocess_registration(
        self, mocker, capfd, docker_services
    ):  # pylint: disable=unused-argument
        """Test failure when a query fails during subprocess registration."""

        mock_cursor = mocker.MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError
        # Create a connection object for testing.
        mock_connection = mocker.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # psycopg2.connect is mocked
        mocker.patch("psycopg2.connect", return_value=mock_connection)
        config = LayoutApplyLogConfig()
        logger = Logger(config.log_config)
        db = DbAccess(logger)
        # act
        sys.argv = ["cli.py", "resume", "--apply-id", "123456789a"]
        with pytest.raises(SystemExit) as excinfo:
            LayoutApplyCommandLine()._update_subporcess_info(db, os.getpid(), "123456789a", Action.RESUME)

        # assert
        assert excinfo.value.code == ExitCode.QUERY_ERR
        out, err = capfd.readouterr()
        # There is no standard output
        assert out == ""
        # error E40019 is output to the standard error.
        assert "[E40019]Query failed." in err
