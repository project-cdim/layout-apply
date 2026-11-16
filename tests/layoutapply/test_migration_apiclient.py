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
"""Test of migration api client"""

import json
import re
from logging import ERROR

import pytest
from pytest_httpserver import HTTPServer
from requests import exceptions
from werkzeug import Response

from layoutapply.cdimlogger import Logger
from layoutapply.const import ApiUri
from layoutapply.migration_apiclient import ConfigManagerAPI, GetAvailableResourcesAPI, MigrationAPI
from layoutapply.setting import LayoutApplyConfig
from tests.layoutapply.test_data.migration import (
    CONF_NODES_API_RESP_DATA,
    GET_AVAILABLE_RESOURCES_API_RESP,
    GET_AVAILABLE_RESOURCES_API_RESP_MULTI,
    MIGRATION_API_RESP_DATA,
)


@pytest.fixture()
def get_migration_layout() -> dict:
    return {
        "currentLayout": {
            "nodes": [
                {
                    "device": {
                        "cpu": {"deviceIDs": ["3B4EBEEA-B6DD-45DA-8C8A-2CA2F8F728D6"]},
                        "memory": {"deviceIDs": ["A4D1A195-4A54-11EF-A1DC-000C29C8CA82"]},
                    }
                },
                {
                    "device": {
                        "cpu": {"deviceIDs": ["2CA6D4DF-2739-45BA-ACA4-6ABE93E81E15"]},
                        "memory": {"deviceIDs": ["035AA32D-6C3F-488E-9602-62286A509288"]},
                        "storage": {"deviceIDs": ["42243124-9655-4B12-B638-A15BFE021065"]},
                        "networkInterface": {"deviceIDs": ["0E9A2838-6AA9-40D2-B3E0-EA7B15E8F18D"]},
                    }
                },
            ]
        },
        "desiredLayout": {
            "nodes": [
                {
                    "device": {
                        "cpu": {"deviceIDs": ["3B4EBEEA-B6DD-45DA-8C8A-2CA2F8F728D6"]},
                        "memory": {"deviceIDs": ["A4D1A195-4A54-11EF-A1DC-000C29C8CA82"]},
                        "storage": {"deviceIDs": ["895DFB43-68CD-41D6-8996-EAC8D1EA1E3F"]},
                        "networkInterface": {"deviceIDs": ["5DFB4893-C16D-4968-89D6-8D1EAECEA31F"]},
                    }
                },
                {
                    "device": {
                        "cpu": {"deviceIDs": ["2CA6D4DF-2739-45BA-ACA4-6ABE93E81E15"]},
                        "memory": {"deviceIDs": ["035AA32D-6C3F-488E-9602-62286A509288"]},
                        "storage": {"deviceIDs": ["42243124-9655-4B12-B638-A15BFE021065"]},
                        "networkInterface": {"deviceIDs": ["0E9A2838-6AA9-40D2-B3E0-EA7B15E8F18D"]},
                    }
                },
            ]
        },
    }


class TestMigrationClient:
    def test_execute_migrationproc_success(self, httpserver: HTTPServer, get_migration_layout):
        # arrange
        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = MigrationAPI(logger, config.migration_procedure, config.server_connection, get_migration_layout)

        uri = config.migration_procedure.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/migration-procedures"), method="POST").respond_with_response(
            Response(bytes(json.dumps(MIGRATION_API_RESP_DATA), encoding="utf-8"), status=200)
        )

        code, body = api.execute()
        httpserver.clear()
        # assert
        assert code == 200
        assert body == MIGRATION_API_RESP_DATA

    def test_execute_migrationproc_failure_when_non_200_status_code(
        self, httpserver: HTTPServer, get_migration_layout, caplog
    ):
        caplog.set_level(ERROR)

        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = MigrationAPI(logger, config.migration_procedure, config.server_connection, get_migration_layout)

        uri = config.migration_procedure.get("uri")
        api_err_msg = {
            "code": "xxxx",
            "message": "desiredLayout is a required property.",
        }

        httpserver.expect_request(re.compile(f"\/{uri}\/migration-procedures"), method="POST").respond_with_response(
            Response(
                bytes(json.dumps(api_err_msg), encoding="utf-8"),
                status=500,
            )
        )

        code, body = api.execute()
        httpserver.clear()
        # assert
        assert code == 500
        assert body.get("code") == "E50004"
        assert body.get("message") == f"Failed to request: status:[500], response[{api_err_msg}]"
        assert json.loads(caplog.record_tuples[0][2]).get("message").startswith("[E50004]Failed to request: ")

    def test_execute_migrationproc_failure_when_timed_out(self, get_migration_layout, caplog, mocker):
        caplog.set_level(ERROR)

        mocker.patch.object(MigrationAPI, "_requests").side_effect = exceptions.ConnectTimeout("Log Error")

        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = MigrationAPI(logger, config.migration_procedure, config.server_connection, get_migration_layout)

        code, body = api.execute()
        # assert
        assert code == 504
        assert body.get("code") == "E50003"
        assert body.get("message") == "Timeout: Could not connect to server."
        assert (
            json.loads(caplog.record_tuples[0][2])
            .get("message")
            .startswith("[E50003]Timeout: Could not connect to server.")
        )

    def test_execute_migrationproc_failure_when_invalid_request_target(self, get_migration_layout, caplog, mocker):
        caplog.set_level(ERROR)

        mocker.patch.object(MigrationAPI, "_post").side_effect = exceptions.ConnectionError("Log Error")

        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = MigrationAPI(logger, config.migration_procedure, config.server_connection, get_migration_layout)

        host = config.migration_procedure.get("host")
        port = config.migration_procedure.get("port")
        uri = config.migration_procedure.get("uri")
        request_uri = ApiUri.MIGRATION_PROCEDURES_API.format(host, port, uri)

        code, body = api.execute()
        # assert
        assert code == 500
        assert body.get("code") == "E50006"
        assert body.get("message") == f"Connection error occurred. Please check if the URL is correct. {request_uri}"
        assert (
            json.loads(caplog.record_tuples[0][2]).get("message")
            == f"[E50006]Connection error occurred. Please check if the URL is correct. {request_uri}"
        )

    def test_execute_migrationproc_failure_when_request_failure_occurred(self, get_migration_layout, caplog, mocker):
        caplog.set_level(ERROR)

        mocker.patch.object(MigrationAPI, "_requests").side_effect = exceptions.RequestException("Log Error")

        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = MigrationAPI(logger, config.migration_procedure, config.server_connection, get_migration_layout)

        code, body = api.execute()
        # assert
        assert code == 500
        assert body.get("code") == "E50007"
        assert body.get("message") == "Unexpected requests error occurred.Log Error"
        assert (
            json.loads(caplog.record_tuples[0][2]).get("message")
            == "[E50007]Unexpected requests error occurred.Log Error"
        )

    def test_execute_configmgr_success(self, httpserver: HTTPServer):
        # arrange
        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = ConfigManagerAPI(logger, config.configuration_manager, config.server_connection)

        uri = config.configuration_manager.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/nodes"), method="GET").respond_with_response(
            Response(
                bytes(json.dumps(CONF_NODES_API_RESP_DATA), encoding="utf-8"),
                status=200,
            )
        )

        code, body = api.execute()
        httpserver.clear()
        # assert
        assert code == 200
        assert body == CONF_NODES_API_RESP_DATA

    def test_execute_configmgr_success_when_empty_response(self, httpserver: HTTPServer):
        # arrange
        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = ConfigManagerAPI(logger, config.configuration_manager, config.server_connection)

        uri = config.configuration_manager.get("uri")
        conf_empty_nodes = {
            "count": 0,
            "nodes": [],
        }

        httpserver.expect_request(re.compile(f"\/{uri}\/nodes"), method="GET").respond_with_response(
            Response(
                bytes(json.dumps(conf_empty_nodes), encoding="utf-8"),
                status=200,
            )
        )

        code, body = api.execute()
        httpserver.clear()
        # assert
        assert code == 200
        assert body == conf_empty_nodes

    @pytest.mark.parametrize(
        "resp_data",
        [
            (
                {
                    "count": [
                        {
                            "id": "string",
                            "resources": [
                                {
                                    "device": {
                                        "deviceID": "qwertyu123",
                                        "type": "CPU",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ),  # no nodes key
            (
                {
                    "count": 1,
                    "node": [
                        {
                            "id": "string",
                            "resources": [
                                {
                                    "device": {
                                        "deviceID": "qwertyu123",
                                        "type": "CPU",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ),  # nodes is invalid
            (
                {
                    "count": 1,
                    "nodes": [
                        {
                            "id": "string",
                            "test": [
                                {
                                    "device": {
                                        "deviceID": "qwertyu123",
                                        "type": "CPU",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ),  # no resources key
            (
                {
                    "count": 1,
                    "nodes": [
                        {
                            "id": "string",
                            "resource": [
                                {
                                    "device": {
                                        "deviceID": "qwertyu123",
                                        "type": "CPU",
                                    },
                                    "resourceGroupIDs": ["qwertyu123"],
                                    "annotation": {"available": True},
                                }
                            ],
                        }
                    ],
                }
            ),  # resources is invalid
            (
                {
                    "count": 1,
                    "nodes": [
                        {
                            "id": "string",
                            "resources": [
                                {
                                    "test": {
                                        "deviceID": "qwertyu123",
                                        "type": "CPU",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ),  # no device
            (
                {
                    "count": 1,
                    "nodes": [
                        {
                            "id": "string",
                            "resources": [
                                {
                                    "devices": {
                                        "deviceID": "qwertyu123",
                                        "type": "CPU",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ),  # device is invalid
            (
                {
                    "nodes": [
                        {
                            "id": "string",
                            "resources": [
                                {
                                    "device": {
                                        "unknown": "qwertyu123",
                                        "type": "CPU",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ),  # no deviceID
            (
                {
                    "nodes": [
                        {
                            "id": "string",
                            "resources": [
                                {
                                    "device": {
                                        "deviceIDs": "qwertyu123",
                                        "type": "CPU",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ),  # deviceID is invalid
            (
                {
                    "nodes": [
                        {
                            "id": "string",
                            "resources": [
                                {
                                    "device": {
                                        "deviceIDs": ["qwertyu123"],
                                        "type": "CPU",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ),  # deviceID: value type is invalid
            (
                {
                    "count": 1,
                    "nodes": [
                        {
                            "id": "string",
                            "resources": [
                                {
                                    "devices": {
                                        "deviceID": "qwertyu123",
                                        "proc": "CPU",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ),  # no type
            (
                {
                    "count": 1,
                    "nodes": [
                        {
                            "id": "string",
                            "resources": [
                                {
                                    "devices": {
                                        "deviceID": "qwertyu123",
                                        "types": "CPU",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ),  # type is invalid
            (
                {
                    "nodes": [
                        {
                            "resources": [
                                {
                                    "device": {
                                        "deviceID": "qwertyu123",
                                        "type": ["CPU", "MEMORY"],
                                    },
                                }
                            ],
                        }
                    ],
                }
            ),
        ],
    )
    def test_execute_configmgr_success_when_invalid_response(self, httpserver: HTTPServer, resp_data, caplog):
        caplog.set_level(ERROR)
        # arrange
        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = ConfigManagerAPI(logger, config.configuration_manager, config.server_connection)

        uri = config.configuration_manager.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/nodes"), method="GET").respond_with_response(
            Response(
                bytes(json.dumps(resp_data), encoding="utf-8"),
                status=200,
            )
        )

        code, body = api.execute()
        httpserver.clear()
        # assert
        assert code == 400
        assert body.get("code") == "E50001"
        assert json.loads(caplog.record_tuples[0][2]).get("message").startswith("[E50001]")

    def test_execute_configmgr_failure_when_non_200_status_code(self, httpserver: HTTPServer, caplog):
        caplog.set_level(ERROR)

        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = ConfigManagerAPI(logger, config.configuration_manager, config.server_connection)

        uri = config.configuration_manager.get("uri")
        api_err_msg = {
            "code": "xxxx",
            "message": "Failed to access to DB",
        }

        httpserver.expect_request(re.compile(f"\/{uri}\/nodes"), method="GET").respond_with_response(
            Response(
                bytes(json.dumps(api_err_msg), encoding="utf-8"),
                status=500,
            )
        )

        code, body = api.execute()
        httpserver.clear()
        # assert
        assert code == 500
        assert body.get("code") == "E50004"
        assert body.get("message") == f"Failed to request: status:[500], response[{api_err_msg}]"
        assert json.loads(caplog.record_tuples[0][2]).get("message").startswith("[E50004]Failed to request: ")

    def test_execute_configmgr_failure_when_timed_out(self, caplog, mocker):
        caplog.set_level(ERROR)

        mocker.patch.object(ConfigManagerAPI, "_requests").side_effect = exceptions.ConnectTimeout("Log Error")

        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = ConfigManagerAPI(logger, config.configuration_manager, config.server_connection)

        code, body = api.execute()
        # assert
        assert code == 504
        assert body.get("code") == "E50003"
        assert body.get("message") == "Timeout: Could not connect to server."
        assert (
            json.loads(caplog.record_tuples[0][2])
            .get("message")
            .startswith("[E50003]Timeout: Could not connect to server.")
        )

    def test_execute_configmgr_failure_when_invalid_request_target(self, caplog, mocker):
        caplog.set_level(ERROR)

        mocker.patch.object(ConfigManagerAPI, "_get").side_effect = exceptions.ConnectionError("Log Error")

        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = ConfigManagerAPI(logger, config.configuration_manager, config.server_connection)

        host = config.configuration_manager.get("host")
        port = config.configuration_manager.get("port")
        uri = config.configuration_manager.get("uri")
        request_uri = ApiUri.GET_ALLNODES_INFO_API.format(host, port, uri)

        code, body = api.execute()
        # assert
        assert code == 500
        assert body.get("code") == "E50006"
        assert body.get("message") == f"Connection error occurred. Please check if the URL is correct. {request_uri}"
        assert (
            json.loads(caplog.record_tuples[0][2]).get("message")
            == f"[E50006]Connection error occurred. Please check if the URL is correct. {request_uri}"
        )

    def test_execute_configmgr_failure_when_request_failure_occurred(self, caplog, mocker):
        caplog.set_level(ERROR)

        mocker.patch.object(ConfigManagerAPI, "_requests").side_effect = exceptions.RequestException("Log Error")

        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = ConfigManagerAPI(logger, config.configuration_manager, config.server_connection)

        code, body = api.execute()
        # assert
        assert code == 500
        assert body.get("code") == "E50007"
        assert body.get("message") == "Unexpected requests error occurred.Log Error"
        assert (
            json.loads(caplog.record_tuples[0][2]).get("message")
            == "[E50007]Unexpected requests error occurred.Log Error"
        )

    def test_execute_get_available_resources_success(self, httpserver: HTTPServer):
        # arrange
        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = GetAvailableResourcesAPI(logger, config.configuration_manager, config.server_connection)

        uri = config.configuration_manager.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/resources/available"), method="GET").respond_with_response(
            Response(
                bytes(json.dumps(GET_AVAILABLE_RESOURCES_API_RESP), encoding="utf-8"),
                status=200,
            )
        )

        code, body = api.execute()
        httpserver.clear()
        # assert
        assert code == 200
        assert body == GET_AVAILABLE_RESOURCES_API_RESP

    def test_execute_get_available_resources_success_multi(self, httpserver: HTTPServer):
        # arrange
        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = GetAvailableResourcesAPI(logger, config.configuration_manager, config.server_connection)

        uri = config.configuration_manager.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/resources/available"), method="GET").respond_with_response(
            Response(
                bytes(json.dumps(GET_AVAILABLE_RESOURCES_API_RESP_MULTI), encoding="utf-8"),
                status=200,
            )
        )

        code, body = api.execute()
        httpserver.clear()
        # assert
        assert code == 200
        assert body == GET_AVAILABLE_RESOURCES_API_RESP_MULTI

    def test_execute_get_available_resources_success_when_empty_response(self, httpserver: HTTPServer):
        # arrange
        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = GetAvailableResourcesAPI(logger, config.configuration_manager, config.server_connection)

        uri = config.configuration_manager.get("uri")
        conf_empty_nodes = {
            "count": 0,
            "resources": [],
        }

        httpserver.expect_request(re.compile(f"\/{uri}\/resources/available"), method="GET").respond_with_response(
            Response(
                bytes(json.dumps(conf_empty_nodes), encoding="utf-8"),
                status=200,
            )
        )

        code, body = api.execute()
        httpserver.clear()
        # assert
        assert code == 200
        assert body == conf_empty_nodes

    @pytest.mark.parametrize(
        "resp_data",
        [
            (
                {
                    "count": 1,
                    "resource": [
                        {
                            "device": {
                                "constraints": {
                                    "nonRemovableDevices": [
                                        {"deviceID": "ce89426d-cf11-4e84-8efa-c5145933a829"},
                                        {"deviceID": "42e46154-ac4b-4ad6-a76e-300249e28186"},
                                    ]
                                },
                                "deviceID": "00c9f066-eae2-4be0-bdd9-aac528d6416c",
                                "type": "CPU",
                            },
                        },
                    ],
                }
            ),  # no resources key
            ({"count": 1, "resources": "test"}),  # resources type is invalid
            (
                {
                    "count": 1,
                    "resources": [
                        {
                            "devices": {
                                "constraints": {
                                    "nonRemovableDevices": [
                                        {"deviceID": "ce89426d-cf11-4e84-8efa-c5145933a829"},
                                        {"deviceID": "42e46154-ac4b-4ad6-a76e-300249e28186"},
                                    ]
                                },
                                "deviceID": "00c9f066-eae2-4be0-bdd9-aac528d6416c",
                                "type": "CPU",
                            },
                        },
                    ],
                }
            ),  # no device key
            (
                {
                    "count": 1,
                    "resources": [
                        {
                            "device": [
                                {
                                    "constraints": {
                                        "nonRemovableDevices": [
                                            {"deviceID": "ce89426d-cf11-4e84-8efa-c5145933a829"},
                                            {"deviceID": "42e46154-ac4b-4ad6-a76e-300249e28186"},
                                        ]
                                    },
                                    "deviceID": "00c9f066-eae2-4be0-bdd9-aac528d6416c",
                                    "type": "CPU",
                                }
                            ],
                        },
                    ],
                }
            ),  # device type is invalid
            (
                {
                    "count": 1,
                    "resources": [
                        {
                            "device": {
                                "constraints": {
                                    "nonRemovableDevices": [
                                        {"deviceID": "ce89426d-cf11-4e84-8efa-c5145933a829"},
                                        {"deviceID": "42e46154-ac4b-4ad6-a76e-300249e28186"},
                                    ]
                                },
                                "deviceIDs": "00c9f066-eae2-4be0-bdd9-aac528d6416c",
                                "type": "CPU",
                            },
                        },
                    ],
                }
            ),  # no deviceID key
            (
                {
                    "count": 1,
                    "resources": [
                        {
                            "device": {
                                "constraints": {
                                    "nonRemovableDevices": [
                                        {"deviceID": "ce89426d-cf11-4e84-8efa-c5145933a829"},
                                        {"deviceID": "42e46154-ac4b-4ad6-a76e-300249e28186"},
                                    ]
                                },
                                "deviceID": 123456789,
                                "type": "CPU",
                            },
                        },
                    ],
                }
            ),  # deviceID type is invalid
            (
                {
                    "count": 1,
                    "resources": [
                        {
                            "device": {
                                "constraints": {
                                    "nonRemovableDevices": [
                                        {"deviceID": "ce89426d-cf11-4e84-8efa-c5145933a829"},
                                        {"deviceID": "42e46154-ac4b-4ad6-a76e-300249e28186"},
                                    ]
                                },
                                "deviceID": "00c9f066-eae2-4be0-bdd9-aac528d6416c",
                                "types": "CPU",
                            },
                        },
                    ],
                }
            ),  # no type key
            (
                {
                    "count": 1,
                    "resources": [
                        {
                            "device": {
                                "constraints": {
                                    "nonRemovableDevices": [
                                        {"deviceID": "ce89426d-cf11-4e84-8efa-c5145933a829"},
                                        {"deviceID": "42e46154-ac4b-4ad6-a76e-300249e28186"},
                                    ]
                                },
                                "deviceID": "00c9f066-eae2-4be0-bdd9-aac528d6416c",
                                "type": 123,
                            },
                        },
                    ],
                }
            ),  # type is invalid
            (
                {
                    "count": 1,
                    "resources": [
                        {
                            "device": {
                                "constraints": "test",
                                "deviceID": "00c9f066-eae2-4be0-bdd9-aac528d6416c",
                                "type": "CPU",
                            },
                        },
                    ],
                }
            ),  # constraints: value type is invalid
            (
                {
                    "count": 1,
                    "resources": [
                        {
                            "device": {
                                "constraints": {"nonRemovableDevices": "ce89426d-cf11-4e84-8efa-c5145933a829"},
                                "deviceID": "00c9f066-eae2-4be0-bdd9-aac528d6416c",
                                "type": "CPU",
                            },
                        },
                    ],
                }
            ),  # nonRemovableDevices: value type is invalid
            (
                {
                    "count": 1,
                    "resources": [
                        {
                            "device": {
                                "constraints": {
                                    "nonRemovableDevices": [
                                        {"deviceID": 111},
                                        {"deviceID": 222},
                                    ]
                                },
                                "deviceID": "00c9f066-eae2-4be0-bdd9-aac528d6416c",
                                "type": "CPU",
                            },
                        },
                    ],
                }
            ),  # nonRemovableDevices.deviceID: value type is invalid
        ],
    )
    def test_execute_get_available_resources_success_when_invalid_response(
        self, httpserver: HTTPServer, resp_data, caplog
    ):
        caplog.set_level(ERROR)
        # arrange
        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = GetAvailableResourcesAPI(logger, config.configuration_manager, config.server_connection)

        uri = config.configuration_manager.get("uri")

        httpserver.expect_request(re.compile(f"\/{uri}\/resources/available"), method="GET").respond_with_response(
            Response(
                bytes(json.dumps(resp_data), encoding="utf-8"),
                status=200,
            )
        )

        code, body = api.execute()
        httpserver.clear()
        # assert
        assert code == 400
        assert body.get("code") == "E50001"
        assert json.loads(caplog.record_tuples[0][2]).get("message").startswith("[E50001]")

    def test_execute_get_available_resources_failure_when_non_200_status_code(self, httpserver: HTTPServer, caplog):
        caplog.set_level(ERROR)

        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = GetAvailableResourcesAPI(logger, config.configuration_manager, config.server_connection)

        uri = config.configuration_manager.get("uri")
        api_err_msg = {
            "code": "xxxx",
            "message": "Failed to access to DB",
        }

        httpserver.expect_request(re.compile(f"\/{uri}\/resources/available"), method="GET").respond_with_response(
            Response(
                bytes(json.dumps(api_err_msg), encoding="utf-8"),
                status=500,
            )
        )

        code, body = api.execute()
        httpserver.clear()
        # assert
        assert code == 500
        assert body.get("code") == "E50004"
        assert body.get("message") == f"Failed to request: status:[500], response[{api_err_msg}]"
        assert json.loads(caplog.record_tuples[0][2]).get("message").startswith("[E50004]Failed to request: ")

    def test_execute_get_available_resources_failure_when_timed_out(self, caplog, mocker):
        caplog.set_level(ERROR)

        mocker.patch.object(GetAvailableResourcesAPI, "_requests").side_effect = exceptions.ConnectTimeout("Log Error")

        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = GetAvailableResourcesAPI(logger, config.configuration_manager, config.server_connection)

        code, body = api.execute()
        # assert
        assert code == 504
        assert body.get("code") == "E50003"
        assert body.get("message") == "Timeout: Could not connect to server."
        assert (
            json.loads(caplog.record_tuples[0][2])
            .get("message")
            .startswith("[E50003]Timeout: Could not connect to server.")
        )

    def test_execute_get_available_resources_failure_when_invalid_request_target(self, caplog, mocker):
        caplog.set_level(ERROR)

        mocker.patch.object(GetAvailableResourcesAPI, "_get").side_effect = exceptions.ConnectionError("Log Error")

        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = GetAvailableResourcesAPI(logger, config.configuration_manager, config.server_connection)

        host = config.configuration_manager.get("host")
        port = config.configuration_manager.get("port")
        uri = config.configuration_manager.get("uri")
        request_uri = ApiUri.GET_AVAILABLE_RESOURCES_API.format(host, port, uri)

        code, body = api.execute()
        # assert
        assert code == 500
        assert body.get("code") == "E50006"
        assert body.get("message") == f"Connection error occurred. Please check if the URL is correct. {request_uri}"
        assert (
            json.loads(caplog.record_tuples[0][2]).get("message")
            == f"[E50006]Connection error occurred. Please check if the URL is correct. {request_uri}"
        )

    def test_execute_get_available_resources_failure_when_request_failure_occurred(self, caplog, mocker):
        caplog.set_level(ERROR)

        mocker.patch.object(GetAvailableResourcesAPI, "_requests").side_effect = exceptions.RequestException(
            "Log Error"
        )

        config = LayoutApplyConfig()
        logger = Logger(**config.logger_args)
        api = GetAvailableResourcesAPI(logger, config.configuration_manager, config.server_connection)

        code, body = api.execute()
        # assert
        assert code == 500
        assert body.get("code") == "E50007"
        assert body.get("message") == "Unexpected requests error occurred.Log Error"
        assert (
            json.loads(caplog.record_tuples[0][2]).get("message")
            == "[E50007]Unexpected requests error occurred.Log Error"
        )
