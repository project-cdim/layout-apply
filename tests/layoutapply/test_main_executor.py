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
"""Test of the Called Subprocess Package"""

import pickle
import secrets
import string
import sys
import tempfile
from logging import ERROR
from time import sleep

import psycopg2
import pytest
from psycopg2.extras import DictCursor

from layoutapply.cli import SubprocOpt
from layoutapply.common.dateutil import get_str_now
from layoutapply.const import Action
from layoutapply.main_executor import exec_run
from layoutapply.setting import LayoutApplyConfig
from tests.layoutapply.test_data import procedure


@pytest.fixture()
def get_applyID():
    return "".join([secrets.choice(string.hexdigits) for i in range(10)]).lower()


@pytest.mark.usefixtures("httpserver_listen_address")
@pytest.mark.usefixtures("hardwaremgr_fixture")
def test_run_success(init_db_instance, mocker, get_applyID, caplog):
    config = LayoutApplyConfig()
    proc = procedure.single_pattern[0][0]
    mocker.patch("layoutapply.db.create_randomname", return_value=get_applyID)

    with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
        cursor.execute(
            query="INSERT INTO applystatus (applyID, status, startedAt) VALUES (%s,%s,%s)",
            vars=[get_applyID, "IN_PROGRESS", get_str_now()],
        )
        init_db_instance.commit()

    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as fp:
        fp.write(pickle.dumps(SubprocOpt(proc, config, get_applyID, Action.REQUEST)).hex())
    sys.argv = ["file-name", fp.name]

    exec_run()

    assert "[E40026]Failed to start subprocess." not in caplog.text

    # To confirm the completion of the process, loop until the status changes from "IN_PROGRESS".
    for i in range(30):
        sleep(1)
        try:
            with init_db_instance.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query=f"SELECT * FROM applystatus WHERE applyid = '{get_applyID}'")
                row = cursor.fetchone()
        except psycopg2.ProgrammingError:
            break
        if row.get("status") != "IN_PROGRESS":
            break


def test_run_failure_when_loading_arguments_failed(mocker, capfd, caplog):
    caplog.set_level(ERROR)
    config = LayoutApplyConfig()
    proc = procedure.single_pattern[0][0]
    mocker.patch("pickle.loads", side_effect=pickle.PickleError("Parse argument error"))

    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as fp:
        fp.write(pickle.dumps(SubprocOpt(proc, config, get_applyID, Action.REQUEST)).hex())
    sys.argv = ["file-name", fp.name]

    with pytest.raises(SystemExit) as excinfo:
        exec_run()

    assert excinfo.value.code == 5
    out, _ = capfd.readouterr()
    # There is no standard output
    assert out == ""
    # There is an error message in the standard error output that starts with the specified error code
    assert "[E40026]Failed to start subprocess." in caplog.messages[0]
