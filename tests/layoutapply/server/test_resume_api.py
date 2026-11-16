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
from time import sleep

import psutil
import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extras import DictCursor
from werkzeug import Response

from layoutapply.const import Action, IdParameter
from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.db import DbAccess
from layoutapply.main import run
from layoutapply.server import app, main
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

client = TestClient(app)


@pytest.mark.usefixtures("httpserver_listen_address")
class TestResumeAPIServerSuccess:
    """Test class for successful resume API scenarios."""

    @pytest.mark.usefixtures("hardwaremgr_fixture")
    def test_resume_layoutapply_success(self, mocker, init_db_instance):
        """Test successful resume of layout apply."""
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
        """Test successful resume when rollback status is suspended."""
        # arrange
        mocker.patch("layoutapply.server._exec_subprocess", return_value=(None, "return_data", 1))
        mocker.patch.object(DbAccess, "update_subprocess", return_value=None)
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.insert_resumed_get_target_sql_4, vars=[applyid])
            cursor.execute(query=sql.insert_resumed_get_target_sql_r_4, vars=[applyid])
        init_db_instance.commit()
        # arrange

        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")
        # assert
        assert response.status_code == 202
        resume_response = json.loads(response.content.decode())
        assert resume_response["status"] == "CANCELED"
        assert resume_response["rollbackStatus"] == "IN_PROGRESS"

    def test_resume_layoutapply_success_when_rollbackstatus_completed(self, init_db_instance):
        """Test successful resume when rollback status is completed."""
        # arrange
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid])
            cursor.execute(query=sql.get_list_insert_sql_r_6, vars=[applyid])
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

    def test_resume_layoutapply_success_when_rollbackstatus_failed(self, init_db_instance):
        """Test successful resume when rollback status is failed."""
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_6, vars=[applyid])
            cursor.execute(query=sql.get_list_insert_sql_r_6_failed, vars=[applyid])
        init_db_instance.commit()

        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")

        assert response.status_code == 200
        resume_response = json.loads(response.content.decode())
        assert resume_response["status"] == "CANCELED"
        assert resume_response["rollbackStatus"] == "FAILED"

    def test_resume_layoutapply_success_when_status_canceled(self, init_db_instance):
        """Test successful resume when status is canceled."""
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

    def test_resume_layoutapply_success_when_status_completed(self, init_db_instance):
        """Test successful resume when status is completed."""
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

    def test_resume_layoutapply_success_when_status_failed(self, init_db_instance):
        """Test successful resume when status is failed."""
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


class TestResumeAPIServerFailure:
    """Test class for failure scenarios of the resume API."""

    def test_resume_layoutapply_failure_when_status_canceling(self, init_db_instance):
        """Test failure of resume when status is canceling."""
        applyid = create_randomname(IdParameter.LENGTH)
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=sql.get_list_insert_sql_2, vars=[applyid])
        init_db_instance.commit()

        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")

        assert response.status_code == 409
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40022"
        assert error_response["message"] == "This layoutapply has already executed."

    def test_resume_layoutapply_failure_when_rollbackstatus_in_progress(self, init_db_instance):
        """Test failure of resume when rollback status is in progress."""
        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="""
                    INSERT into applystatus (applyid, status, procedures, result, rollbackprocedures, startedat,\
                    endedat, canceledat, executerollback, resumeprocedures, processid,\
                    executioncommand, processstartedat, suspendedat, resumedat)
                    VALUES
                    ('300000011b','CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',\
                    '{"procedures": "pre_test"}','2023/10/02 00:00:00','2023/10/02 01:00:00','2023/10/02 00:30:00',\
                    TRUE,null,null,null,null,null,null);
                """)
            cursor.execute(query="""
                    INSERT into rollbackstatus (applyid, status, procedures, result, startedat, endedat, \
                    canceledat, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000011b','IN_PROGRESS','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',\
                    '2023/10/02 00:40:00',null,null,\
                    '[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',\
                    null,null,null,'2023/10/02 00:50:00',null);
                """)
        init_db_instance.commit()

        response = client.put("/cdim/api/v1/layout-apply/300000011b?action=resume")
        # assert
        assert response.status_code == 409
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40022"
        assert error_response["message"] == "This layoutapply has already executed."

    def test_resume_layoutapply_failure_when_status_in_progress(self, init_db_instance):
        """Test failure of resume when status is in progress."""
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
        """Test failure of resume when database connection fails."""
        mocker.patch.object(DbAccess, "proc_resume", side_effect=psycopg2.OperationalError)

        response = client.put("/cdim/api/v1/layout-apply/000000001a?action=resume")
        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40018"
        assert "Could not connect to ApplyStatusDB." in error_response["message"]

    def test_resume_layoutapply_failure_when_query_failure_occurred(self, mocker):
        """Test failure of resume when a query failure occurs."""
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

    def test_resume_layoutapply_failure_when_nonexistent_id(self, init_db_instance):  # pylint: disable=unused-argument
        """Test failure of resume when the specified layoutapply ID does not exist."""

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
        """Test failure of resume when an invalid parameter is provided."""
        request_uri = "/cdim/api/v1/layout-apply/"
        request_uri += parameter_uri

        response = client.put(request_uri)
        # assert
        assert response.status_code == 400
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    def test_resume_layoutapply_failure_when_action_parameter_missing(self):
        """Test failure of resume when action parameter is missing."""
        response = client.put("/cdim/api/v1/layout-apply/012345678a")

        assert response.status_code == 400
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40001"

    def test_resume_layoutapply_failure_when_failed_to_load_config_file(self, mocker):
        """Test failure of resume when failing to load the configuration file."""

        mocker.patch(
            "yaml.safe_load", side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")]
        )

        response = client.put("/cdim/api/v1/layout-apply/012345678a?action=resume")
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert "Failed to load layoutapply_config.yaml." in error_response["message"]

    def test_resume_layoutapply_failure_when_failed_to_load_log_config_file(self, mocker):
        """Test failure of resume when failing to load the log configuration file."""
        mocker.patch.object(LayoutApplyLogConfig, "_validate_log_dir", side_effect=[Exception("Dummy message")])

        # arrange
        response = client.put("/cdim/api/v1/layout-apply/012345678a?action=resume")
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E40002"
        assert error_response["message"] == "Failed to load layoutapply_log_config.yaml.\n('Dummy message',)"

    def test_resume_layoutapply_failure_when_failed_to_start_subprocess(self, mocker, init_db_instance, caplog):
        """Test failure of resume when failing to start the subprocess."""
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="""
                    INSERT into applystatus (applyid, status, procedures, result, rollbackprocedures, startedat,\
                    endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, \
                    processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000006d','SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,\
                    '2023/10/02 00:00:00',null,null,null,\
                    '{"procedures": [{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001",\
                    "dependencies": []}]}',null,null,null,'2023/10/02 12:23:59',null);
                """)
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
        """Test failure of resume when failing to start the subprocess in suspended state."""
        mocker.patch("logging.config.dictConfig")

        # Data adjustment before testing.
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query="""
                    INSERT into applystatus (applyid, status, procedures, result, rollbackprocedures, startedat, \
                    endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, \
                    processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000021a','CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',\
                    '{"procedures": "pre_test"}','2023/10/02 00:00:00','2023/10/02 01:00:00','2023/10/02 00:30:00',\
                    TRUE,'[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',\
                    null,null,null,'2023/10/02 00:50:00',null);
                """)
            cursor.execute(query="""
                    INSERT into rollbackstatus (applyid, status, procedures, result, startedat, endedat, canceledat, \
                    resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000021a','SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',\
                    '2023/10/02 00:50:00',null,null,\
                    '[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',\
                    null,null,null,null,null);
                """)
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
        """Test that the main function does not output traceback when the server is shut down."""
        # arrange
        mockup = mocker.patch("layoutapply.server.uvicorn.run", side_effect=KeyboardInterrupt)

        main()

        # assert
        # confirm that no unexpected exceptions have occurred during server shutdown.
        assert mockup.call_count == 1

    # @pytest.mark.parametrize("args", [["resume", "--apply-id", "300000004d"]])
    def test_resume_layoutapply_success_not_subprocess(self, init_db_instance, httpserver):
        """Test successful resume layout apply when not using subprocess."""
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
                    '[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]'\
                    ,null,null,null,'2023/10/02 12:23:59',null);
                """)
            init_db_instance.commit()

        # arrange
        applyid = "300000004d"
        procedures = {
            "procedures": [{"operationID": 1, "operation": "shutdown", "targetDeviceID": "0001", "dependencies": []}]
        }

        config = LayoutApplyConfig()
        config.load_log_configs()

        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa:W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{GET_INFORMATION_URI}\/{DEVICE_INFO_URL}"), method="GET"  # noqa:W605
        ).respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )

        # arrange
        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")
        run(procedures, config, applyid, Action.RESUME)

        # assert
        assert response.status_code == 202

        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()

        # assert
        # assert excinfo.value.code == 0
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
                        f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa:W605
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

    def test_resume_layoutapply_success_use_run_function(self, init_db_instance, httpserver):
        """Test resuming layout apply using the run function."""
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
                    {"operationID": 2, "operation": "shutdown", "targetDeviceID": "0002", "dependencies": [1]}]'\
                    ,null,null,null,'2023/10/02 12:23:59',null);
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

        config = LayoutApplyConfig()
        config.load_log_configs()

        # act
        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")

        # with httpserver.wait(stop_on_nohandler=False, timeout=0.1) as waiter:
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT"  # noqa:W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT"  # noqa:W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa:W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa:W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(  # noqa:W605
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        httpserver.expect_request(
            re.compile(f"\/{GET_INFORMATION_URI}\/{DEVICE_INFO_URL}"), method="GET"  # noqa:W605
        ).respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()

        # assert
        assert response.status_code == 202
        resume_response = json.loads(response.content.decode())
        assert resume_response["status"] == "IN_PROGRESS"

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
                        f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa:W605
                        detail["uri"],
                    )
                    assert "PUT" == detail["method"]
                    assert "queryParameter" not in detail
                    assert 200 == detail["statusCode"]
                    assert {"action": "off"} == detail["requestBody"]
                    get_information = detail["getInformation"]
                    assert {"powerState": "Off"} == get_information["responseBody"]

        # if procces_mock.return_value.is_alive():
        #     procces_mock.return_value.terminate()
        #     procces_mock.return_value.join()
        sleep(1)
        httpserver.clear()
        httpserver.clear_all_handlers()

    def test_resume_layoutapply_success_when_rollback_state_suspended_not_subprocess(
        self, init_db_instance, httpserver
    ):
        """Test resume layout apply success when rollback state is suspended and not a subprocess."""
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
                    null,'2023/10/02 00:00:00','2023/10/02 01:00:00','2023/10/02 00:30:00',TRUE,null,null,null,null,\
                    null,null);
                """)
            cursor.execute(query="""
                    INSERT into rollbackstatus (applyid, status, procedures, result, startedat, endedat, canceledat,\
                    resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
                    )
                    VALUES
                    ('300000013d','SUSPENDED','{"procedures": "pre_test"}','[{"operationID": 1, "status": "FAILED"}]',\
                    '2023/10/02 00:00:00',null,null,\
                    '[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',\
                    null,null,null,'2023/10/02 00:50:00',null);
                """)
            init_db_instance.commit()

        # arrange
        applyid = "300000013d"
        procedures = {
            "procedures": [{"operationID": 1, "operation": "shutdown", "targetDeviceID": "0001", "dependencies": []}]
        }

        config = LayoutApplyConfig()
        config.load_log_configs()

        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa:W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{GET_INFORMATION_URI}\/{DEVICE_INFO_URL}"), method="GET"  # noqa:W605
        ).respond_with_json(
            {"type": "CPU", "powerState": "Off", "powerCapability": False},
            status=200,
        )

        # arrange
        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")
        run(procedures, config, applyid, Action.ROLLBACK_RESUME)

        # assert
        assert response.status_code == 202

        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM rollbackstatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()

        # assert
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
                        f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa:W605
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

    def test_resume_layoutapply_success_when_rollback_state_suspended_use_run_function(
        self, init_db_instance, httpserver
    ):
        """Test resume layout apply success when rollback state is suspended using run function."""
        uri = HARDWARE_CONTROL_URI

        httpserver.clear()
        httpserver.clear_all_handlers()

        # with httpserver.wait(stop_on_nohandler=False, timeout=0.1) as waiter:
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT"  # noqa:W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT"  # noqa:W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa:W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"  # noqa:W605
        ).respond_with_response(Response("", status=200))
        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(  # noqa:W605
            {"status": True, "IPAddress": "192.168.122.11"}, status=200
        )
        httpserver.expect_request(
            re.compile(f"\/{GET_INFORMATION_URI}\/{DEVICE_INFO_URL}"), method="GET"  # noqa:W605
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

        config = LayoutApplyConfig()
        config.load_log_configs()

        # act
        response = client.put(f"/cdim/api/v1/layout-apply/{applyid}?action=resume")

        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM rollbackstatus WHERE applyid = '{applyid}'")
            init_db_instance.commit()
            row = cursor.fetchone()
        init_db_instance.commit()

        # assert
        assert response.status_code == 202
        resume_response = json.loads(response.content.decode())
        assert resume_response["rollbackStatus"] == "IN_PROGRESS"

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
                        f"http:\/\/{host}:{port}\/{uri}\/{POWER_OPERATION_URL}",  # noqa:W605
                        detail["uri"],
                    )
                    assert "PUT" == detail["method"]
                    assert "queryParameter" not in detail
                    assert 200 == detail["statusCode"]
                    assert {"action": "off"} == detail["requestBody"]
                    get_information = detail["getInformation"]
                    assert {"powerState": "Off"} == get_information["responseBody"]

        sleep(1)
        httpserver.clear()
        httpserver.clear_all_handlers()
