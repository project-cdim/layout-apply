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
import json
import logging.config
import os
import re
import uuid

import psycopg2
import pytest
from psycopg2.extras import DictCursor
from pytest_httpserver import HTTPServer
from werkzeug import Response

from layoutapply.common.logger import Logger
from layoutapply.db import DbAccess
from layoutapply.setting import LayoutApplyLogConfig
from tests.layoutapply.test_data.migration import (
    CONF_NODES_API_RESP_DATA,
    CONF_NODES_API_RESP_DATA_MULTIDEVICE,
    CONF_NODES_API_RESP_DATA_MULTIDEVICE_WITH_NODEID,
    GET_AVAILABLE_RESOURCES_API_RESP,
    GET_AVAILABLE_RESOURCES_API_RESP_MULTI,
    MIGRATION_API_RESP_DATA,
    NOTHING_NON_REMOVABLE_DEVICES_RESP,
)

OPERATION_URL = "cpu\/(.*)\/aggregations"
POWER_OPERATION_URL = "devices\/(.*)\/power"
DEVICE_INFO_URL = "devices\/(.*)\/specs"
CONF_NODES_URL = "nodes"
GET_AVAILABLE_RESOURCES_URL = "resources\/available"
MIGRATION_URL = "migration-procedures"
OS_BOOT_URL = "cpu\/(.*)\/is\-os\-ready"

# Set according to the values in the layoutapply_config.yaml configuration
HARDWARE_CONTROL_HOST = "localhost"
HARDWARE_CONTROL_PORT = 48889
WORKFLOW_MANAGER_HOST = "localhost"
WORKFLOW_MANAGER_PORT = 8008
HARDWARE_CONTROL_URI = "cdim/api/v1"
GET_INFORMATION_URI = "cdim/api/v1"
CONFIG_MANAGER_URI = "cdim/api/v1"
MIGRATION_PROCEDURE_URI = "cdim/api/v1"
WORKFLOW_MANAGER_URI = "cdim/api/v1"
GET_WORKFLOW_MANAGER_URI = "cdim/api/v1"

EXTENDED_PROCEDURE_URI = "extended-procedure"
EXTENDED_PROCEDURE_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


@pytest.fixture(scope="session")
def httpserver_listen_address():
    """Change the IP and Port of the dummy server created with pytest-httpserver.
    By default, the IP is localhost, and the port is randomly selected from available ports above 1024.
    If it is necessary to fix the Port, such as when the test subject has a specification to read the
    Port settings from the configuration file, define it in conftest.py.
    Ref: https://pytest-httpserver.readthedocs.io/en/latest/howto.html#customizing-host-and-port

    Returns:
        tuple : (IP, Port)
    """
    #    config = LayoutApplyConfig()
    #    host = config.hardware_control.get("host")
    #    port = config.hardware_control.get("port")
    host = HARDWARE_CONTROL_HOST
    port = HARDWARE_CONTROL_PORT
    no_proxy = os.environ.get("no_proxy", "")  # Get the current value of no_proxy
    new_no_proxy = host
    if no_proxy:
        os.environ["no_proxy"] = f"{no_proxy},{new_no_proxy}"  # Add if already set.
    else:
        os.environ["no_proxy"] = new_no_proxy  # If not already set, set a new value.
    return (host, port)


@pytest.fixture(scope="function")
def hardwaremgr_fixture(httpserver: HTTPServer):
    """Create a mockup of the hardware control API.
    Everything completes successfully.

    Args:
        httpserver (HTTPServer): Dummy server object
    """
    #    config = LayoutApplyConfig()
    #    uri = config.hardware_control.get("uri")
    #    get_information_uri = config.get_information.get("uri")
    uri = HARDWARE_CONTROL_URI
    get_information_uri = GET_INFORMATION_URI

    # httpserver.clear()
    # httpserver.clear_all_handlers()

    # with httpserver.wait(stop_on_nohandler=False, timeout=0.1) as waiter:
    httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
        Response("", status=200)
    )
    httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_response(
        Response("", status=200)
    )
    httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
        Response("", status=200)
    )
    httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_response(
        Response("", status=200)
    )
    httpserver.expect_request(re.compile(f"\/{uri}\/{OS_BOOT_URL}"), method="GET").respond_with_json(
        {"status": True, "IPAddress": "192.168.122.11"}, status=200
    )
    httpserver.expect_request(
        re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
    ).respond_with_json(
        {"type": "CPU", "powerState": "Off", "powerCapability": False},
        status=200,
    )

    yield

    httpserver.clear()


@pytest.fixture(scope="function")
def extended_procedure_fixture():
    """Mock up the workflow manager API
    Everything completes successfully.

    Args:
        httpserver (HTTPServer): Dummy server object
    """
    workflow_manager_uri = GET_WORKFLOW_MANAGER_URI
    workflow_manager_server = HTTPServer(host=WORKFLOW_MANAGER_HOST, port=WORKFLOW_MANAGER_PORT)
    workflow_manager_server.start()

    workflow_manager_server.expect_request(
        re.compile(f"\/{workflow_manager_uri}\/{EXTENDED_PROCEDURE_URI}"), method="POST"
    ).respond_with_json({"extendedProcedureID": EXTENDED_PROCEDURE_ID}, status=202)
    workflow_manager_server.expect_request(
        re.compile(f"\/{workflow_manager_uri}\/{EXTENDED_PROCEDURE_URI}\/{EXTENDED_PROCEDURE_ID}"), method="GET"
    ).respond_with_json(
        {
            "applyID": str(uuid.uuid4()),
            "targetCPUID": str(uuid.uuid4()),
            "targetRequestInstanceID": str(uuid.uuid4()),
            "operation": "stop",
            "id": EXTENDED_PROCEDURE_ID,
            "status": "COMPLETED",
            "serviceInstanceID": str(uuid.uuid4()),
        },
        status=200,
    )

    yield

    workflow_manager_server.stop()
    workflow_manager_server.clear()


@pytest.fixture(scope="function")
def migration_server_fixture(httpserver: HTTPServer):
    """Mock up the migration procedure generation API
    Everything completes successfully.

    Args:
        httpserver (HTTPServer): Dummy server object
    """
    #    config = LayoutApplyConfig()
    #    migration_uri = config.migration_procedure.get("uri")
    #    config_manager_uri = config.configuration_manager.get("uri")
    migration_uri = MIGRATION_PROCEDURE_URI
    config_manager_uri = CONFIG_MANAGER_URI

    httpserver.clear()
    httpserver.clear_all_handlers()

    httpserver.expect_request(re.compile(f"\/{migration_uri}\/{MIGRATION_URL}"), method="POST").respond_with_response(
        Response(bytes(json.dumps(MIGRATION_API_RESP_DATA), encoding="utf-8"), status=200)
    )
    httpserver.expect_request(
        re.compile(f"\/{config_manager_uri}\/{CONF_NODES_URL}"),
        method="GET",
    ).respond_with_response(
        Response(
            bytes(json.dumps(CONF_NODES_API_RESP_DATA), encoding="utf-8"),
            status=200,
        )
    )
    httpserver.expect_request(
        re.compile(f"\/{config_manager_uri}\/{GET_AVAILABLE_RESOURCES_URL}"),
        method="GET",
    ).respond_with_response(
        Response(
            bytes(json.dumps(GET_AVAILABLE_RESOURCES_API_RESP), encoding="utf-8"),
            status=200,
        )
    )

    yield

    httpserver.clear()


@pytest.fixture(scope="function")
def migration_server_fixture_multi(httpserver: HTTPServer):
    """Mock up the migration procedure generation API
    Everything completes successfully.

    Args:
        httpserver (HTTPServer): Dummy server object
    """
    #    config = LayoutApplyConfig()
    #    migration_uri = config.migration_procedure.get("uri")
    #    config_manager_uri = config.configuration_manager.get("uri")
    migration_uri = MIGRATION_PROCEDURE_URI
    config_manager_uri = CONFIG_MANAGER_URI

    httpserver.clear()
    httpserver.clear_all_handlers()

    httpserver.expect_request(re.compile(f"\/{migration_uri}\/{MIGRATION_URL}"), method="POST").respond_with_response(
        Response(bytes(json.dumps(MIGRATION_API_RESP_DATA), encoding="utf-8"), status=200)
    )
    httpserver.expect_request(
        re.compile(f"\/{config_manager_uri}\/{CONF_NODES_URL}"),
        method="GET",
    ).respond_with_response(
        Response(
            bytes(json.dumps(CONF_NODES_API_RESP_DATA_MULTIDEVICE), encoding="utf-8"),
            status=200,
        )
    )
    httpserver.expect_request(
        re.compile(f"\/{config_manager_uri}\/{GET_AVAILABLE_RESOURCES_URL}"),
        method="GET",
    ).respond_with_response(
        Response(
            bytes(json.dumps(GET_AVAILABLE_RESOURCES_API_RESP_MULTI), encoding="utf-8"),
            status=200,
        )
    )

    yield

    httpserver.clear()


@pytest.fixture(scope="function")
def migration_server_fixture_nodeid_specified(httpserver: HTTPServer):
    """Mock up the migration procedure generation API
    Everything completes successfully.

    Args:
        httpserver (HTTPServer): Dummy server object
    """
    #    config = LayoutApplyConfig()
    #    migration_uri = config.migration_procedure.get("uri")
    #    config_manager_uri = config.configuration_manager.get("uri")
    migration_uri = MIGRATION_PROCEDURE_URI
    config_manager_uri = CONFIG_MANAGER_URI

    httpserver.clear()
    httpserver.clear_all_handlers()

    httpserver.expect_request(re.compile(f"\/{migration_uri}\/{MIGRATION_URL}"), method="POST").respond_with_response(
        Response(bytes(json.dumps(MIGRATION_API_RESP_DATA), encoding="utf-8"), status=200)
    )
    httpserver.expect_request(
        re.compile(f"\/{config_manager_uri}\/{CONF_NODES_URL}"),
        method="GET",
    ).respond_with_response(
        Response(
            bytes(json.dumps(CONF_NODES_API_RESP_DATA_MULTIDEVICE_WITH_NODEID), encoding="utf-8"),
            status=200,
        )
    )
    httpserver.expect_request(
        re.compile(f"\/{config_manager_uri}\/{GET_AVAILABLE_RESOURCES_URL}"),
        method="GET",
    ).respond_with_response(
        Response(
            bytes(json.dumps(GET_AVAILABLE_RESOURCES_API_RESP_MULTI), encoding="utf-8"),
            status=200,
        )
    )

    yield

    httpserver.clear()


@pytest.fixture(scope="function")
def get_available_resources_nothing_bound_devices(httpserver: HTTPServer):
    """Mock up the get available resources API
    Everything completes successfully.

    Args:
        httpserver (HTTPServer): Dummy server object
    """
    migration_uri = MIGRATION_PROCEDURE_URI
    config_manager_uri = CONFIG_MANAGER_URI

    httpserver.clear()
    httpserver.clear_all_handlers()

    httpserver.expect_request(re.compile(f"\/{migration_uri}\/{MIGRATION_URL}"), method="POST").respond_with_response(
        Response(bytes(json.dumps(MIGRATION_API_RESP_DATA), encoding="utf-8"), status=200)
    )
    httpserver.expect_request(
        re.compile(f"\/{config_manager_uri}\/{CONF_NODES_URL}"),
        method="GET",
    ).respond_with_response(
        Response(
            bytes(json.dumps(CONF_NODES_API_RESP_DATA_MULTIDEVICE), encoding="utf-8"),
            status=200,
        )
    )
    httpserver.expect_request(
        re.compile(f"\/{config_manager_uri}\/{GET_AVAILABLE_RESOURCES_URL}"),
        method="GET",
    ).respond_with_response(
        Response(
            bytes(json.dumps(NOTHING_NON_REMOVABLE_DEVICES_RESP), encoding="utf-8"),
            status=200,
        )
    )

    yield

    httpserver.clear()


@pytest.fixture(scope="function")
def hardwaremgr_error_fixture(httpserver: HTTPServer):
    """Mock up the hardware control API
    Everything ends failed.
    Args:
        httpserver (HTTPServer): Dummy server object
    """
    #    config = LayoutApplyConfig()
    #    uri = config.hardware_control.get("uri")
    #    get_information_uri = config.get_information.get("uri")
    uri = HARDWARE_CONTROL_URI
    get_information_uri = GET_INFORMATION_URI
    err_msg = {"code": "xxxx", "message": "Internal Server Error."}
    err_code = 500

    httpserver.clear()
    httpserver.clear_all_handlers()

    httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_json(
        err_msg, status=err_code
    )
    httpserver.expect_request(re.compile(f"\/{uri}\/{OPERATION_URL}"), method="PUT").respond_with_json(
        err_msg, status=err_code
    )
    httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_json(
        err_msg, status=err_code
    )
    httpserver.expect_request(re.compile(f"\/{uri}\/{POWER_OPERATION_URL}"), method="PUT").respond_with_json(
        err_msg, status=err_code
    )
    httpserver.expect_request(
        re.compile(f"\/{get_information_uri}\/{DEVICE_INFO_URL}"), method="GET"
    ).respond_with_json(
        {"type": "CPU", "powerState": "Off", "powerCapability": False},
        status=200,
    )
    yield
    httpserver.clear()


@pytest.fixture(scope="function")
def extended_procedure_error_fixture():
    """Mock up the workflow manager API
    Everything ends failed.

    Args:
        httpserver (HTTPServer): Dummy server object
    """
    err_msg = {"code": "xxxx", "message": "Internal Server Error."}
    err_code = 500
    workflow_manager_uri = GET_WORKFLOW_MANAGER_URI
    workflow_manager_server = HTTPServer(host=WORKFLOW_MANAGER_HOST, port=WORKFLOW_MANAGER_PORT)
    workflow_manager_server.start()

    workflow_manager_server.expect_request(re.compile(f"\/{workflow_manager_uri}"), method="POST").respond_with_json(
        err_msg, err_code
    )
    workflow_manager_server.expect_request(
        re.compile(f"\/{workflow_manager_uri}\/{EXTENDED_PROCEDURE_URI}\/{EXTENDED_PROCEDURE_ID}"), method="GET"
    ).respond_with_json({}, status=503)

    yield

    workflow_manager_server.stop()
    workflow_manager_server.clear()


@pytest.fixture(scope="function")
def migration_server_err_fixture(httpserver: HTTPServer):
    """Mock up the abnormal migration procedure generation API

    Args:
        httpserver (HTTPServer): Dummy server object
    """
    #    config = LayoutApplyConfig()

    #    uri = config.migration_procedure.get("uri")
    migration_uri = MIGRATION_PROCEDURE_URI
    config_manager_uri = CONFIG_MANAGER_URI
    api_err_msg = {
        "code": "xxxx",
        "message": "desiredLayout is a required property.",
    }

    httpserver.clear()
    httpserver.clear_all_handlers()

    httpserver.expect_request(
        re.compile(f"\/{config_manager_uri}\/{CONF_NODES_URL}"),
        method="GET",
    ).respond_with_response(
        Response(
            bytes(json.dumps(CONF_NODES_API_RESP_DATA), encoding="utf-8"),
            status=200,
        )
    )
    httpserver.expect_request(
        re.compile(f"\/{config_manager_uri}\/{GET_AVAILABLE_RESOURCES_URL}"),
        method="GET",
    ).respond_with_response(
        Response(
            bytes(json.dumps(GET_AVAILABLE_RESOURCES_API_RESP), encoding="utf-8"),
            status=200,
        )
    )

    httpserver.expect_request(re.compile(f"\/{migration_uri}\/{MIGRATION_URL}"), method="POST").respond_with_response(
        Response(
            bytes(json.dumps(api_err_msg), encoding="utf-8"),
            status=500,
        )
    )

    yield

    httpserver.clear()


@pytest.fixture(scope="function")
def conf_manager_server_err_fixture(httpserver: HTTPServer):
    """Mock up the anomaly scenarios for the configuration information management API.

    Args:
        httpserver (HTTPServer): Dummy server object
    """
    #    config = LayoutApplyConfig()
    #    uri = config.configuration_manager.get("uri")
    uri = CONFIG_MANAGER_URI

    api_err_msg = {
        "code": "xxxx",
        "message": "Failed to access to DB",
    }

    httpserver.expect_request(re.compile(f"\/{uri}\/{CONF_NODES_URL}"), method="GET").respond_with_response(
        Response(
            bytes(json.dumps(api_err_msg), encoding="utf-8"),
            status=500,
        )
    )

    yield

    httpserver.clear()


@pytest.fixture(scope="function")
def get_available_resources_err_fixture(httpserver: HTTPServer):
    """Mock up the anomaly scenarios for the get available resources API.

    Args:
        httpserver (HTTPServer): Dummy server object
    """
    config_manager_uri = CONFIG_MANAGER_URI
    api_err_msg = {
        "code": "xxxx",
        "message": "Failed to access to DB",
    }

    httpserver.clear()
    httpserver.clear_all_handlers()

    httpserver.expect_request(
        re.compile(f"\/{config_manager_uri}\/{CONF_NODES_URL}"),
        method="GET",
    ).respond_with_response(
        Response(
            bytes(json.dumps(CONF_NODES_API_RESP_DATA), encoding="utf-8"),
            status=200,
        )
    )
    httpserver.expect_request(
        re.compile(f"\/{config_manager_uri}\/{GET_AVAILABLE_RESOURCES_URL}"), method="GET"
    ).respond_with_response(
        Response(
            bytes(json.dumps(api_err_msg), encoding="utf-8"),
            status=500,
        )
    )

    yield

    httpserver.clear()


DB_CONNECT = None


def is_postgresql_ready():
    try:
        db_config = {
            "dbname": "ApplyStatusDB",
            "user": "user01",
            "password": "P@ssw0rd",
            "host": "localhost",
            "port": 5435,
        }
        global DB_CONNECT
        DB_CONNECT = psycopg2.connect(**db_config)
        return True
    except Exception:
        return False


@pytest.fixture
def get_db_instance():

    logger = logging.getLogger("logger.py")
    return DbAccess(logger)


@pytest.fixture
def init_db_instance(docker_services, mocker):
    docker_services.wait_until_responsive(timeout=30.0, pause=0.1, check=lambda: is_postgresql_ready())
    global DB_CONNECT
    with DB_CONNECT.cursor(cursor_factory=DictCursor) as cursor:
        cursor.execute(query="TRUNCATE TABLE applystatus;")
    DB_CONNECT.commit()
    mocker.patch("psycopg2.connect", return_value=DB_CONNECT)
    mocker.patch.object(DbAccess, "close", return_value=None)
    yield DB_CONNECT
    with DB_CONNECT.cursor(cursor_factory=DictCursor) as cursor:
        cursor.execute(query="TRUNCATE TABLE applystatus;")
    DB_CONNECT.commit()
    DB_CONNECT.close()
    DB_CONNECT = None


@pytest.fixture(autouse=True)
def log_setting():
    log_config = LayoutApplyLogConfig().log_config
    log_config["disable_existing_loggers"] = False
    logging.config.dictConfig(log_config)
