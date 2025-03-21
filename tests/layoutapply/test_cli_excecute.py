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
"""Test for the command to apply configuration proposal"""

import json
import os
import re
import secrets
import string
import sys
from multiprocessing import Process
from time import sleep
from uuid import uuid4

import pytest
from psycopg2.extras import DictCursor
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from layoutapply.cli import main
from layoutapply.const import Action
from layoutapply.main import run
from layoutapply.setting import LayoutApplyConfig
from tests.layoutapply.conftest import DEVICE_INFO_URL, OPERATION_URL, OS_BOOT_URL, POWER_OPERATION_URL

SELECT_SQL = "SELECT * FROM applystatus"
SELECT_ORDER_SQL = "SELECT * FROM applystatus ORDER BY endedat desc"
CHANGE_CANCEL_SQL = "UPDATE applystatus SET status='CANCELING', canceledat='2023/10/02 12:23:59', executerollback=FALSE WHERE applyid = %s"
CHANGE_CANCEL_ROLLBACK_SQL = "UPDATE applystatus SET status='CANCELING', canceledat='2023/10/02 12:23:59', executerollback=TRUE WHERE applyid = %s"


@pytest.fixture()
def get_applyID():
    return "".join([secrets.choice(string.hexdigits) for i in range(10)]).lower()


class TestCliExcecute:
    """Command test class.
    Since the httpserver_listen_address is valid per session, using httpserver.expect_ordered_request for
    mockup in the test will result in an error. Therefore, the relevant test will be conducted here.
    """

    @pytest.mark.parametrize(
        ("procedures"),
        [
            (
                # no API for parallel execution.
                {
                    "procedures": [
                        {
                            "operationID": 1,
                            "operation": "disconnect",
                            "targetCPUID": str(uuid4()),
                            "targetDeviceID": str(uuid4()),
                            "dependencies": [],
                        },
                        {
                            "operationID": 2,
                            "operation": "shutdown",
                            "targetDeviceID": str(uuid4()),
                            "dependencies": [1],
                        },
                        {
                            "operationID": 3,
                            "operation": "connect",
                            "targetCPUID": str(uuid4()),
                            "targetDeviceID": str(uuid4()),
                            "dependencies": [2],
                        },
                        {
                            "operationID": 4,
                            "operation": "boot",
                            "targetDeviceID": str(uuid4()),
                            "dependencies": [3],
                        },
                    ]
                }
            ),
        ],
    )
    def test_cmd_apply_cancel_executed_when_received_cancel_request(
        self,
        tmp_path,
        httpserver: HTTPServer,
        capfd,
        procedures,
        mocker,
        get_applyID,
        init_db_instance,
    ):
        # arrange
        arg_procedure = os.path.join(str(tmp_path), "procedure.json")
        with open(arg_procedure, "w", encoding="utf-8") as file:
            json.dump(procedures, file)
        sys.argv = ["cli.py", "request", "-p", arg_procedure]
        config = LayoutApplyConfig()

        def _change_cancel_status_func(request: Request):
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=CHANGE_CANCEL_SQL, vars=[id_])
            init_db_instance.commit()
            return Response("", status=200)

        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")

        httpserver.clear()
        httpserver.clear_all_handlers()

        mocker.patch("layoutapply.db.create_randomname", return_value=get_applyID)

        # act
        procces_mock = mocker.patch(
            "subprocess.Popen",
            return_value=Process(target=run, args=(procedures, config, get_applyID, Action.CANCEL)),
        )
        with pytest.raises(SystemExit):
            main()

        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(
            Response(
                response='{"type": "CPU", "powerState": "Off", "powerCapability": false}',
                status=200,
            )
        )
        httpserver.expect_oneshot_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_handler(
            _change_cancel_status_func
        )
        httpserver.expect_oneshot_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_response(Response("", status=200))

        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"IpAddress": "xxx.xxx.xxx.xxx", "status": True}, status=200
        )

        out, err = capfd.readouterr()
        assert "Request was successful. Start applying" in err
        id_ = json.loads(out).get("applyID")
        procces_mock.return_value.start()
        with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{id_}'")
            init_db_instance.commit()
            row = cursor.fetchone()

        if row.get("status") == "IN_PROGRESS":
            assert row.get("status") == "IN_PROGRESS"
            while True:
                sleep(1)
                with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                    cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{id_}'")
                    init_db_instance.commit()
                    row = cursor.fetchone()
                if row.get("status") != "IN_PROGRESS":
                    break

        # assert
        out, err = capfd.readouterr()

        assert row.get("status") in ["CANCELED", "CANCELING"]
        details = row.get("applyresult")
        assert len(details) == len(procedures["procedures"])
        for procedure in procedures["procedures"]:
            detail = [i for i in details if i["operationID"] == procedure["operationID"]][0]
            assert procedure["operationID"] == detail["operationID"]
            match procedure["operation"]:
                case "boot":
                    assert "CANCELED" == detail["status"]
                case _:
                    assert "COMPLETED" == detail["status"]
        sleep(0.8)
        httpserver.clear()

    # @pytest.mark.skip
    @pytest.mark.parametrize(
        ("procedures"),
        [
            (
                # no API for parallel execution.
                {
                    "procedures": [
                        {
                            "operationID": 1,
                            "operation": "disconnect",
                            "targetCPUID": str(uuid4()),
                            "targetDeviceID": str(uuid4()),
                            "dependencies": [],
                        },
                        {
                            "operationID": 2,
                            "operation": "shutdown",
                            "targetDeviceID": str(uuid4()),
                            "dependencies": [1],
                        },
                        {
                            "operationID": 3,
                            "operation": "connect",
                            "targetCPUID": str(uuid4()),
                            "targetDeviceID": str(uuid4()),
                            "dependencies": [2],
                        },
                        {
                            "operationID": 4,
                            "operation": "boot",
                            "targetDeviceID": str(uuid4()),
                            "dependencies": [3],
                        },
                    ]
                }
            ),
        ],
    )
    def test_cmd_apply_rollback_executed_when_received_cancel_request_with_rollback(
        self,
        tmp_path,
        httpserver: HTTPServer,
        capfd,
        procedures,
        mocker,
        get_applyID,
        init_db_instance,
        docker_services,
    ):
        # arrange
        httpserver.clear()
        httpserver.clear_all_handlers()
        cursor = init_db_instance.cursor(cursor_factory=DictCursor)
        arg_procedure = os.path.join(str(tmp_path), "procedure.json")
        with open(arg_procedure, "w", encoding="utf-8") as file:
            json.dump(procedures, file)
        sys.argv = ["cli.py", "request", "-p", arg_procedure]
        config = LayoutApplyConfig()

        def sleeping(request: Request):
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=CHANGE_CANCEL_ROLLBACK_SQL, vars=[id_])
            init_db_instance.commit()
            return Response("", status=200)

        uri = config.hardware_control.get("uri")
        get_information_uri = config.get_information.get("uri")

        mocker.patch("layoutapply.db.create_randomname", return_value=get_applyID)

        # act
        procces_mock = mocker.patch(
            "subprocess.Popen",
            return_value=Process(target=run, args=(procedures, config, get_applyID, Action.REQUEST)),
        )
        with pytest.raises(SystemExit):
            main()

        httpserver.expect_request(
            re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
        ).respond_with_response(
            Response(
                response='{"type": "CPU", "powerState": "Off", "powerCapability": false}',
                status=200,
            )
        )
        httpserver.expect_oneshot_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )
        httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
            Response("", status=200)
        )

        httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_handler(sleeping)
        httpserver.expect_oneshot_request(
            re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT"
        ).respond_with_response(Response("", status=200))

        httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
            {"IpAddress": "xxx.xxx.xxx.xxx", "status": True}, status=200
        )
        out, err = capfd.readouterr()
        assert "Request was successful. Start applying" in err
        id_ = json.loads(out).get("applyID")
        procces_mock.return_value.start()

        cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{id_}'")
        init_db_instance.commit()
        row = cursor.fetchone()

        if row.get("status") in ("IN_PROGRESS", "CANCELING"):
            for i in range(15):
                sleep(0.5)
                cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{id_}'")
                init_db_instance.commit()
                row = cursor.fetchone()
                if row.get("status") not in ("IN_PROGRESS", "CANCELING"):
                    break
        httpserver.clear()
        # assert
        assert row.get("applyid") == id_
        assert row.get("status") in ["CANCELED", "CANCELLING"]
        assert row.get("procedures") == procedures["procedures"]
        details = row.get("applyresult")
        assert len(details) == len(procedures["procedures"])
        for procedure in procedures["procedures"]:
            detail = [i for i in details if i["operationID"] == procedure["operationID"]][0]
            assert procedure["operationID"] == detail["operationID"]
            match procedure["operation"]:
                case "boot":
                    assert "CANCELED" == detail["status"]
                case _:
                    assert "COMPLETED" == detail["status"]
        assert row.get("rollbackstatus") == "COMPLETED"

        sleep(0.8)
