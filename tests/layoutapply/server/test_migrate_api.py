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
"""Test for migration api"""

import copy
import json
import logging  # pylint: disable=W0611 # noqa: F401
import re
from logging.config import dictConfig  # pylint: disable=W0611 # noqa: F401

import pytest
from fastapi.testclient import TestClient
from werkzeug import Response

from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.server import _create_bound_devices, app
from layoutapply.setting import LayoutApplyConfig, LayoutApplyLogConfig
from tests.layoutapply.conftest import CONF_NODES_URL
from tests.layoutapply.test_data import checkvalid, migration

client = TestClient(app)


def _rename_gpu_key(migration_in_data: dict, new_key: str) -> dict:
    data = copy.deepcopy(migration_in_data)

    nodes = data.get("desiredLayout", {}).get("nodes", [])
    for node in nodes:
        device = node.get("device")
        if "gpu" in device:
            device[new_key] = device.pop("gpu")
    return data


@pytest.mark.usefixtures("httpserver_listen_address")
class TestMigrateAPIServerSuccess:
    """Successful response patterns for migration API."""

    @pytest.mark.usefixtures("migration_server_fixture")
    @pytest.mark.parametrize("gpu_key", ["gpu", "GPU", "gpU"], ids=["gpu", "GPU", "gpU"])
    def test_execute_migration_success(self, init_db_instance, httpserver, gpu_key):  # pylint: disable=W0613
        """Test for migration API when valid request body is provided."""
        # arrange
        req_json = (
            migration.MIGRATION_IN_DATA if gpu_key == "gpu" else _rename_gpu_key(migration.MIGRATION_IN_DATA, gpu_key)
        )

        response = client.post("/cdim/api/v1/migration-procedures", json=req_json)
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

        migration_req = httpserver.log[2][0]
        assert migration_req.json["desiredLayout"]["nodes"] == req_json["desiredLayout"]["nodes"]

    @pytest.mark.usefixtures("migration_server_fixture_multi")
    def test_execute_migration_success_when_multiple_current_nodes(self, init_db_instance):  # pylint: disable=W0613
        """Test for migration API when multiple current nodes are provided in the request body."""
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("migration_server_fixture")
    def test_execute_migration_success_when_node_empty(self, init_db_instance):  # pylint: disable=W0613
        """Test for migration API when nodes is empty in the request body."""
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA_EMPTY)
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("migration_server_fixture_nodeid_specified")
    def test_execute_migration_success_when_nodeid_specified(self, init_db_instance):  # pylint: disable=W0613
        """Test for migration API when targetNodeId is specified in the request body."""
        # arrange
        response = client.post(
            "/cdim/api/v1/migration-procedures",
            json=migration.MIGRATION_IN_DATA_WITH_TARGETNODEID,
        )
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("migration_server_fixture_nodeid_specified")
    def test_execute_migration_success_when_nodeid_specified_multi(self, init_db_instance):  # pylint: disable=W0613
        """Test for migration API when multiple targetNodeId is specified in the request body."""
        # arrange
        response = client.post(
            "/cdim/api/v1/migration-procedures",
            json=migration.MIGRATION_IN_DATA_WITH_TARGETNODEID_MULTIPLE,
        )
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("migration_server_fixture_nodeid_specified")
    def test_execute_migration_success_when_targetnodeids_contains_duplicate_id(
        self, init_db_instance  # pylint: disable=W0613
    ):
        """Test for migration API when targetNodeIDs contains duplicated IDs."""
        # arrange
        duplicated_target_nodeids_data = copy.deepcopy(migration.MIGRATION_IN_DATA_WITH_TARGETNODEID)
        target_node_id = duplicated_target_nodeids_data["targetNodeIDs"][0]
        duplicated_target_nodeids_data["targetNodeIDs"] = [target_node_id, target_node_id]

        response = client.post(
            "/cdim/api/v1/migration-procedures",
            json=duplicated_target_nodeids_data,
        )
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("migration_server_fixture_nodeid_specified")
    def test_execute_migration_success_when_nodeid_empty(self, init_db_instance):  # pylint: disable=W0613
        """Test for migration API when targetNodeId is empty in the request body."""
        # arrange
        response = client.post(
            "/cdim/api/v1/migration-procedures",
            json=migration.MIGRATION_IN_DATA_WITH_TARGETNODEID_EMPTY,
        )
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("get_available_resources_nothing_bound_devices")
    def test_execute_migration_success_when_bound_device_nothing(self, init_db_instance):  # pylint: disable=W0613
        """Test for migration API when no bound device is found in the request body."""
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        resp_data = json.loads(response.content)

        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None
        assert resp_data.get("procedures") == migration.MIGRATION_API_RESP_DATA

    @pytest.mark.usefixtures("migration_server_fixture")
    @pytest.mark.parametrize("layout", checkvalid.newLayout_unkown_device)
    def test_execute_migration_success_when_unknown_device(self, layout, init_db_instance):  # pylint: disable=W0613
        """Test for migration API when unknown device is provided in the request body."""
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=layout)
        resp_data = json.loads(response.content)
        # assert
        assert response.status_code == 200
        assert resp_data.get("procedures") is not None


@pytest.mark.usefixtures("httpserver_listen_address")
class TestMigrateAPIServerValidation:
    """Input validation patterns for migration API."""

    @pytest.mark.usefixtures("migration_server_fixture_nodeid_specified")
    def test_execute_migration_failure_when_nodeid_invalid(self, init_db_instance):  # pylint: disable=W0613
        """Test for migration API when targetNodeId is invalid in the request body."""
        # arrange
        response = client.post(
            "/cdim/api/v1/migration-procedures",
            json=migration.MIGRATION_IN_DATA_WITH_TARGETNODEID_INVALID,
        )

        # assert
        assert response.status_code == 404
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50010"

    @pytest.mark.usefixtures("migration_server_fixture_nodeid_specified")
    def test_execute_migration_failure_when_gpu_format_invalid(self):
        """Test for migration API when GPU format is invalid in the request body."""
        # arrange
        response = client.post(
            "/cdim/api/v1/migration-procedures",
            json=migration.MIGRATION_IN_DATA_WITH_INVALID_GPU_FORMAT,
        )

        # assert
        assert response.status_code == 400
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50001"
        assert (
            error_response["message"]
            == "Unexpected strings {'deviceIDs': ['f6d7c8a9-b0c1-2d3e-4f5a-6b7c8d9e0f1a']} is not of type 'array'"
        )

    @pytest.mark.parametrize("layout", checkvalid.newLayout_without_required_key)
    def test_execute_migration_failure_when_no_required_key(self, layout):
        """Test for migration API when required key is missing in the request body."""
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=layout)
        # assert
        assert response.status_code == 400
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50001"

    @pytest.mark.parametrize("layout", checkvalid.newLayout_invalid_data_type)
    def test_execute_migration_failure_when_invalid_data_type(self, layout):
        """Test for migration API when invalid data type is provided in the request body."""
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=layout)

        # assert
        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50001"

    @pytest.mark.parametrize("layout", checkvalid.newLayout_invalid_value)
    def test_execute_migration_failure_when_invalid_value(self, layout):
        """Test for migration API when invalid value is provided in the request body."""
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=layout)

        assert response.status_code == 400

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50001"


@pytest.mark.usefixtures("httpserver_listen_address")
class TestMigrateAPIServerConfigFailure:
    """Configuration and initialization failures for migration API."""

    def test_execute_migration_failure_when_failed_to_load_config_file(self, mocker):
        """Test for migration API when failed to load config file."""
        mocker.patch(
            "yaml.safe_load",
            side_effect=[SettingFileLoadException("Dummy message", "layoutapply_config.yaml")],
        )
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        # assert
        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50002"
        assert "Failed to load layoutapply_config.yaml." in error_response["message"]

    def test_execute_migration_failure_when_failed_to_load_log_config_file(
        self, mocker, init_db_instance
    ):  # pylint: disable=W0613
        """Test for migration API when failed to load log config file."""
        mocker.patch.object(LayoutApplyLogConfig, "_validate_log_dir", side_effect=[Exception("Dummy message")])

        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        # assert

        assert response.status_code == 500
        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50002"
        assert "Failed to load layoutapply_log_config.yaml." in error_response["message"]

    def test_execute_migration_failure_when_failed_to_load_secret_file(self, mocker):
        """Test for migration API when failed to load secret file."""
        # arrange
        mocker.patch.object(LayoutApplyConfig, "_get_secret", side_effect=[Exception("Dummy message")])

        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50008"

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
    def test_execute_migration_failure_when_failed_to_initialize_logger(
        self, mocker, log_config, docker_services, init_db_instance  # pylint: disable=W0613
    ):
        """Test for migration API when logger initialization fails."""
        mocker.patch.object(LayoutApplyLogConfig, "log_config", log_config)

        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        # assert

        assert response.status_code == 500

        error_response = json.loads(response.content.decode())
        assert error_response["code"] == "E50009"


@pytest.mark.usefixtures("httpserver_listen_address")
class TestMigrateAPIServerExternalApiError:
    """External dependency failure patterns for migration API."""

    @pytest.mark.usefixtures("conf_manager_server_err_fixture")
    def test_execute_migration_failure_when_config_info_management_api_failure(
        self, mocker, caplog, init_db_instance
    ):  # pylint: disable=W0613
        """Test for migration API when config info management API fails."""
        mocker.patch("logging.config.dictConfig")

        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        body = json.loads(response.content.decode())
        api_err_msg = {
            "code": "xxxx",
            "message": "Failed to access to DB",
        }

        # assert
        assert body.get("code") == "E50004"
        assert body.get("message") == f"Failed to request: status:[500], response[{api_err_msg}]"
        assert "[E50004]Failed to request:" in caplog.text

    @pytest.mark.usefixtures("migration_server_err_fixture")
    def test_execute_migration_failure_when_migration_step_generation_api_failure(
        self, httpserver, docker_services, init_db_instance, mocker, caplog  # pylint: disable=W0613
    ):
        """Test for migration API when migration step generation API fails."""
        mocker.patch("logging.config.dictConfig")

        httpserver.expect_request(
            re.compile(rf"\/cdim/api\/v1\/{CONF_NODES_URL}"),
            method="GET",
        ).respond_with_response(
            Response(
                bytes(json.dumps(migration.CONF_NODES_API_RESP_DATA), encoding="utf-8"),
                status=200,
            )
        )
        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        body = json.loads(response.content.decode())
        api_err_msg = {
            "code": "xxxx",
            "message": "desiredLayout is a required property.",
        }
        httpserver.clear()

        # assert
        assert body.get("code") == "E50004"
        assert body.get("message") == f"Failed to request: status:[500], response[{api_err_msg}]"
        assert "[E50004]Failed to request:" in caplog.text

    @pytest.mark.usefixtures("get_available_resources_err_fixture")
    def test_execute_migration_failure_when_get_available_resources_api_failure(
        self, docker_services, mocker, caplog  # pylint: disable=W0613
    ):
        """Test for migration API when get_available_resources API fails."""
        mocker.patch("logging.config.dictConfig")

        # arrange
        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        body = json.loads(response.content.decode())
        api_err_msg = {
            "code": "xxxx",
            "message": "Failed to access to DB",
        }

        # assert
        assert body.get("code") == "E50004"
        assert body.get("message") == f"Failed to request: status:[500], response[{api_err_msg}]"
        assert "[E50004]Failed to request:" in caplog.text

    def test_execute_migration_failure_when_config_manager_timeout_is_propagated(
        self, mocker, init_db_instance  # pylint: disable=W0613
    ):
        """Test for migration API when config manager returns timeout response."""
        mocker.patch(
            "layoutapply.server.ConfigManagerAPI.execute",
            return_value=(504, {"code": "E50003", "message": "Timeout: Could not connect to server."}),
        )

        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        body = json.loads(response.content.decode())

        assert response.status_code == 504
        assert body["code"] == "E50003"
        assert "Timeout: Could not connect to server." in body["message"]

    def test_execute_migration_failure_when_get_available_resources_connection_error_is_propagated(
        self, mocker, init_db_instance  # pylint: disable=W0613
    ):
        """Test for migration API when get_available_resources returns connection error response."""
        mocker.patch(
            "layoutapply.server.ConfigManagerAPI.execute",
            return_value=(200, migration.CONF_NODES_API_RESP_DATA),
        )
        mocker.patch(
            "layoutapply.server.GetAvailableResourcesAPI.execute",
            return_value=(
                500,
                {
                    "code": "E50006",
                    "message": "Connection error occurred. Please check if the URL is correct.",
                },
            ),
        )

        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        body = json.loads(response.content.decode())

        assert response.status_code == 500
        assert body["code"] == "E50006"
        assert "Connection error occurred" in body["message"]

    def test_execute_migration_failure_when_migration_api_request_exception_is_propagated(
        self, mocker, init_db_instance  # pylint: disable=W0613
    ):
        """Test for migration API when migration API returns unexpected request error response."""
        mocker.patch(
            "layoutapply.server.ConfigManagerAPI.execute",
            return_value=(200, migration.CONF_NODES_API_RESP_DATA),
        )
        mocker.patch(
            "layoutapply.server.GetAvailableResourcesAPI.execute",
            return_value=(200, migration.GET_AVAILABLE_RESOURCES_API_RESP),
        )
        mocker.patch(
            "layoutapply.server.MigrationAPI.execute",
            return_value=(500, {"code": "E50007", "message": "Unexpected requests error occurred.Log Error"}),
        )

        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        body = json.loads(response.content.decode())

        assert response.status_code == 500
        assert body["code"] == "E50007"
        assert "Unexpected requests error occurred" in body["message"]

    @pytest.mark.parametrize(
        ("status_code", "code", "message"),
        [
            (500, "E50006", "Connection error occurred. Please check if the URL is correct."),
            (500, "E50007", "Unexpected requests error occurred.Log Error"),
        ],
        ids=["connection_error", "request_exception"],
    )
    def test_execute_migration_failure_when_config_manager_error_is_propagated(
        self,
        mocker,
        init_db_instance,
        status_code,
        code,
        message,
    ):  # pylint: disable=W0613
        """Test for migration API when config manager returns non-timeout errors."""
        mocker.patch(
            "layoutapply.server.ConfigManagerAPI.execute",
            return_value=(status_code, {"code": code, "message": message}),
        )

        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        body = json.loads(response.content.decode())

        assert response.status_code == status_code
        assert body["code"] == code
        assert message in body["message"]

    @pytest.mark.parametrize(
        ("status_code", "code", "message"),
        [
            (504, "E50003", "Timeout: Could not connect to server."),
            (500, "E50007", "Unexpected requests error occurred.Log Error"),
        ],
        ids=["timeout", "request_exception"],
    )
    def test_execute_migration_failure_when_get_available_resources_error_is_propagated(
        self,
        mocker,
        init_db_instance,
        status_code,
        code,
        message,
    ):  # pylint: disable=W0613
        """Test for migration API when get_available_resources returns non-covered errors."""
        mocker.patch(
            "layoutapply.server.ConfigManagerAPI.execute",
            return_value=(200, migration.CONF_NODES_API_RESP_DATA),
        )
        mocker.patch(
            "layoutapply.server.GetAvailableResourcesAPI.execute",
            return_value=(status_code, {"code": code, "message": message}),
        )

        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        body = json.loads(response.content.decode())

        assert response.status_code == status_code
        assert body["code"] == code
        assert message in body["message"]

    @pytest.mark.parametrize(
        ("status_code", "code", "message"),
        [
            (504, "E50003", "Timeout: Could not connect to server."),
            (500, "E50006", "Connection error occurred. Please check if the URL is correct."),
        ],
        ids=["timeout", "connection_error"],
    )
    def test_execute_migration_failure_when_migration_api_error_is_propagated(
        self,
        mocker,
        init_db_instance,
        status_code,
        code,
        message,
    ):  # pylint: disable=W0613
        """Test for migration API when migration API returns non-covered errors."""
        mocker.patch(
            "layoutapply.server.ConfigManagerAPI.execute",
            return_value=(200, migration.CONF_NODES_API_RESP_DATA),
        )
        mocker.patch(
            "layoutapply.server.GetAvailableResourcesAPI.execute",
            return_value=(200, migration.GET_AVAILABLE_RESOURCES_API_RESP),
        )
        mocker.patch(
            "layoutapply.server.MigrationAPI.execute",
            return_value=(status_code, {"code": code, "message": message}),
        )

        response = client.post("/cdim/api/v1/migration-procedures", json=migration.MIGRATION_IN_DATA)
        body = json.loads(response.content.decode())

        assert response.status_code == status_code
        assert body["code"] == code
        assert message in body["message"]


class TestBoundDevicesBoundary:
    """Boundary tests for boundDevices creation."""

    def test_create_bound_devices_ignores_constraint_without_deviceid(self):
        """Skip malformed constraints where nonRemovableDevices entries have no deviceID."""
        response = {
            "resources": [
                {
                    "device": {
                        "deviceID": "cpu-1",
                        "type": "cpu",
                        "constraints": {"nonRemovableDevices": [{}]},
                    }
                },
                {
                    "device": {
                        "deviceID": "gpu-1",
                        "type": "gpu",
                        "constraints": {"nonRemovableDevices": [{"deviceID": "cpu-1"}]},
                    }
                },
            ]
        }
        nodes = [
            {
                "id": "node-1",
                "resources": [
                    {"device": {"deviceID": "cpu-1", "type": "cpu"}},
                    {"device": {"deviceID": "gpu-1", "type": "gpu"}},
                ],
            }
        ]

        bound_devices = _create_bound_devices(response, nodes, None)

        assert bound_devices == {"cpu-1": {"gpu": ["gpu-1"]}}

    def test_create_bound_devices_returns_empty_when_nonremovabledevices_empty(self):
        """Return empty boundDevices when nonRemovableDevices is present but empty."""
        response = {
            "resources": [
                {
                    "device": {
                        "deviceID": "cpu-1",
                        "type": "cpu",
                        "constraints": {"nonRemovableDevices": []},
                    }
                },
                {
                    "device": {
                        "deviceID": "gpu-1",
                        "type": "gpu",
                        "constraints": {"nonRemovableDevices": []},
                    }
                },
            ]
        }
        nodes = [
            {
                "id": "node-1",
                "resources": [
                    {"device": {"deviceID": "cpu-1", "type": "cpu"}},
                    {"device": {"deviceID": "gpu-1", "type": "gpu"}},
                ],
            }
        ]

        bound_devices = _create_bound_devices(response, nodes, None)

        assert bound_devices == {}
