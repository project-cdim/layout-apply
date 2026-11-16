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
"""Test for setting hardware_control"""

import copy

import pytest

from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.setting import LayoutApplyConfig, LayoutApplyLogConfig
from tests.layoutapply.conftest import BASE_CONFIG, LOG_BASE_CONFIG


class TestLayoutApplyConfigHardwareControl:
    """Tests for hardware_control related settings."""

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # port
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": 0,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # uri is correct
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": 8888,
                    "uri": "cdim/api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - interval min
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 0,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - interval max
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 60,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - max_count min
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 1,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - max_count max
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 10,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - targets
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS002",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # default - interval min
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 0,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # default - interval max
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 60,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # default - max_count min
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 1,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # default - max_count max
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 10,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # timeout - min
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 1,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # timeout - max
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 600,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
        ],
    )
    def test_setting_success_when_hardware_api_config_normal(self, mocker, update_confg):
        """Test setting success when hardware API config is normal."""
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["hardware_control"]
        config = {**base_config, **update_confg}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        layout_apply_hard_conf = LayoutApplyConfig().hardware_control
        assert layout_apply_hard_conf == config["hardware_control"]

    def test_setting_default_set_when_no_retry_setting(self, mocker):
        """Test setting default values when no retry setting is provided."""
        config = {
            "layout_apply": {"host": "0.0.0.0", "port": 8003, "request": {}},
            "db": {
                "dbname": "layoutapply",
                "user": "user01",
                "password": "P@ssw0rd",
                "host": "localhost",
                "port": 5435,
            },
            "get_information": {
                "host": "localhost",
                "port": 48889,
                "uri": "api/v1",
                "specs": {
                    "poweroff": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                        },
                    },
                    "connect": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                        },
                    },
                    "disconnect": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                        },
                    },
                    "timeout": 10,
                },
            },
            "workflow_manager": {
                "host": "0.0.0.0",
                "port": 8008,
                "uri": "cdim/api/v1",
                "extended-procedure": {
                    "retry": {
                        "default": {
                            "interval": 5,
                            "max_count": 5,
                        },
                    },
                    "polling": {
                        "count": 5,
                        "interval": 5,
                    },
                },
                "timeout": 30,
            },
            "hardware_control": {
                "host": "localhost",
                "port": 8888,
                "uri": "api/v1",
                "disconnect": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                            },
                        ],
                        "default": {
                            "interval": 5,
                            "max_count": 5,
                        },
                    },
                    "timeout": 10,
                },
                "connect": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "interval": 5,
                                "max_count": 5,
                            },
                        ],
                    },
                    "timeout": 10,
                },
                "poweroff": {
                    "retry": {
                        "targets": [
                            {
                                "status_code": 503,
                                "code": "ER005BAS001",
                                "max_count": 5,
                            },
                        ],
                        "default": {
                            "interval": 5,
                        },
                    },
                    "timeout": 10,
                },
                "poweron": {
                    "retry": {
                        "default": {
                            "max_count": 5,
                        },
                    },
                },
                "isosboot": {
                    "polling": {
                        "count": 5,
                        "interval": 1,
                        "targets": [
                            {
                                "status_code": 204,
                            },
                        ],
                        "skip": [
                            {"status_code": 400, "code": "EF003BAS010"},
                        ],
                    },
                    "request": {"timeout": 2},
                    "timeout": 10,
                },
            },
            "migration_procedure_generator": {
                "host": "localhost",
                "port": 48889,
                "uri": "cdim/api/v1",
                "timeout": 30,
            },
            "configuration_manager": {
                "host": "localhost",
                "port": 48889,
                "uri": "cdim/api/v1",
                "timeout": 30,
            },
            "message_broker": {
                "host": "localhost",
                "port": 3500,
                "pubsub": "layout_apply_apply",
                "topic": "layout_apply_apply.completed",
            },
        }
        # unset values will default.
        mocker.patch("yaml.safe_load").return_value = config
        mocker.patch("requests.get")
        conf = LayoutApplyConfig().disconnect
        assert conf["retry"]["targets"] == [
            {
                "status_code": 503,
                "code": "ER005BAS001",
                "interval": 5,
                "max_count": 5,
            },
        ]
        assert conf["retry"]["default"]["interval"] == 5
        assert conf["retry"]["default"]["max_count"] == 5
        assert conf["timeout"] == 10

        conf = LayoutApplyConfig().connect
        assert conf["retry"]["targets"] == [
            {
                "status_code": 503,
                "code": "ER005BAS001",
                "interval": 5,
                "max_count": 5,
            },
        ]
        assert conf["retry"]["default"]["interval"] == 5
        assert conf["retry"]["default"]["max_count"] == 5
        assert conf["timeout"] == 10

        conf = LayoutApplyConfig().poweroff
        assert conf["retry"]["targets"] == [
            {
                "status_code": 503,
                "code": "ER005BAS001",
                "interval": 5,
                "max_count": 5,
            },
        ]
        assert conf["retry"]["default"]["interval"] == 5
        assert conf["retry"]["default"]["max_count"] == 5
        assert conf["timeout"] == 10

        conf = LayoutApplyConfig().poweron
        assert not conf["retry"]["targets"]
        assert conf["retry"]["default"]["interval"] == 5
        assert conf["retry"]["default"]["max_count"] == 5
        assert conf["timeout"] == 60

    def test_setting_default_set_when_no_retry_config(self, mocker):
        """Test setting default values when no retry configuration is provided."""
        config = {
            "layout_apply": {"host": "0.0.0.0", "port": 8003, "request": {}},
            "db": {
                "dbname": "layoutapply",
                "user": "user01",
                "password": "P@ssw0rd",
                "host": "localhost",
                "port": 5435,
            },
            "get_information": {
                "host": "localhost",
                "port": 48889,
                "uri": "api/v1",
                "specs": {
                    "poweroff": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                        },
                    },
                    "connect": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                        },
                    },
                    "disconnect": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                        },
                    },
                    "timeout": 10,
                },
            },
            "workflow_manager": {
                "host": "localhost",
                "port": 8008,
                "uri": "cdim/api/v1",
                "extended-procedure": {"retry": {"default": {}}, "polling": {}},
            },
            "hardware_control": {
                "host": "localhost",
                "port": 8888,
                "uri": "api/v1",
                "disconnect": {},
                "isosboot": {
                    "polling": {
                        "count": 5,
                        "interval": 1,
                        "targets": [
                            {
                                "status_code": 204,
                            },
                        ],
                        "skip": [
                            {"status_code": 400, "code": "EF003BAS010"},
                        ],
                    },
                    "request": {"timeout": 2},
                    "timeout": 10,
                },
            },
            "migration_procedure_generator": {
                "host": "localhost",
                "port": 48889,
                "uri": "cdim/api/v1",
                "timeout": 30,
            },
            "configuration_manager": {
                "host": "localhost",
                "port": 48889,
                "uri": "cdim/api/v1",
                "timeout": 30,
            },
            "message_broker": {
                "host": "localhost",
                "port": 3500,
                "pubsub": "layout_apply_apply",
                "topic": "layout_apply_apply.completed",
            },
        }
        # all values will default.
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        conf = LayoutApplyConfig().disconnect
        assert not conf["retry"]["targets"]
        assert conf["retry"]["default"]["interval"] == 5
        assert conf["retry"]["default"]["max_count"] == 5
        assert conf["timeout"] == 60

    def test_setting_default_set_when_no_polling_config(self, mocker):
        """Test setting default values when no polling configuration is provided."""
        config = {
            "layout_apply": {"host": "0.0.0.0", "port": 8003, "request": {}},
            "db": {
                "dbname": "layoutapply",
                "user": "user01",
                "password": "P@ssw0rd",
                "host": "localhost",
                "port": 5435,
            },
            "get_information": {
                "host": "localhost",
                "port": 48889,
                "uri": "api/v1",
                "specs": {
                    "poweroff": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                        },
                    },
                    "connect": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                        },
                    },
                    "disconnect": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                        },
                    },
                    "timeout": 10,
                },
            },
            "workflow_manager": {
                "host": "localhost",
                "port": 8008,
                "uri": "cdim/api/v1",
                "extended-procedure": {
                    "retry": {"default": {}},
                    "polling": {},
                },
                "timeout": None,
            },
            "hardware_control": {
                "host": "localhost",
                "port": 8888,
                "uri": "api/v1",
                "disconnect": {},
                "isosboot": {
                    "polling": {
                        "count": 5,
                        "interval": 1,
                        "targets": [
                            {
                                "status_code": 204,
                            },
                        ],
                        "skip": [
                            {"status_code": 400, "code": "EF003BAS010"},
                        ],
                    },
                    "request": {"timeout": 2},
                    "timeout": 10,
                },
            },
            "migration_procedure_generator": {
                "host": "localhost",
                "port": 48889,
                "uri": "cdim/api/v1",
                "timeout": 30,
            },
            "configuration_manager": {
                "host": "localhost",
                "port": 48889,
                "uri": "cdim/api/v1",
                "timeout": 30,
            },
            "message_broker": {
                "host": "localhost",
                "port": 3500,
                "pubsub": "layout_apply_apply",
                "topic": "layout_apply_apply.completed",
            },
        }
        # all values will default.
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        extended_conf = LayoutApplyConfig().workflow_manager
        assert extended_conf["extended-procedure"]["polling"]["count"] == 60
        assert extended_conf["extended-procedure"]["polling"]["interval"] == 30
        assert extended_conf["timeout"] == 60
        assert extended_conf["extended-procedure"]["retry"]["default"]["interval"] == 5
        assert extended_conf["extended-procedure"]["retry"]["default"]["max_count"] == 5

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host is type error & None
            {
                "hardware_control": {
                    "host": 1,
                    "port": 8888,
                    "uri": "api/v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": None,
                    "port": 8888,
                    "uri": "api/v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # port is type error & None
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": "0",
                    "uri": "api/v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": None,
                    "uri": "api/v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # uri is type error & None
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": 8888,
                    "uri": 89398398,
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": "127.0.0.1",
                    "port": 8888,
                    "uri": None,
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - interval min-1
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": -1,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - interval max + 1
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 61,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - interval is type error
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": "5",
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - interval max is None
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": None,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - max_count min - 1
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 0,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - max_count max + 1
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 11,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - max_count minus
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": -11,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - max_count is type error
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": "11",
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - max_count is None
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": None,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # retry - targets
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": "503",
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": 8988,
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # default - interval min - 1
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": -1,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # default - interval max + 1
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 61,
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # default - interval is type error
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": "a",
                                "max_count": 5,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # default - max_count min - 1
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 0,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # default - max_count max + 1
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 11,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # default - max_count minus
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": -1,
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # default - max_count type error
            {
                "hardware_control": {
                    "host": "localhost",
                    "port": 8888,
                    "uri": "v1",
                    "timeout": 10,
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": "a",
                            },
                        },
                        "timeout": 10,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # timeout - min -1
            {
                "hardware_control": {
                    "host": 1,
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 0,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # timeout - max + 1
            {
                "hardware_control": {
                    "host": 1,
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": 601,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # timeout is minus
            {
                "hardware_control": {
                    "host": 1,
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": -1,
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # timeout is type error
            {
                "hardware_control": {
                    "host": 1,
                    "port": 8888,
                    "uri": "api/v1",
                    "disconnect": {
                        "retry": {
                            "targets": [
                                {
                                    "status_code": 503,
                                    "code": "ER005BAS001",
                                    "interval": 5,
                                    "max_count": 5,
                                },
                            ],
                            "default": {
                                "interval": 5,
                                "max_count": 5,
                            },
                        },
                        "timeout": "0",
                    },
                    "isosboot": {
                        "polling": {
                            "count": 5,
                            "interval": 1,
                            "skip": [
                                {"status_code": 400, "code": "EF003BAS010"},
                            ],
                        },
                        "request": {"timeout": 2},
                        "timeout": 10,
                    },
                },
            },
            # empty
            {},
        ],
    )
    def test_setting_failure_when_invalid_hardware_api_config(self, mocker, update_confg):
        """Test setting failure when hardware API config is invalid."""
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["hardware_control"]
        config = {**base_config, **update_confg}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        with pytest.raises(SettingFileLoadException):
            assert LayoutApplyConfig().hardware_control is not None

    def test_setting_default_set_when_invalid_logging_level(self, mocker):
        """Test setting default values when logging level is invalid."""
        mocker.patch("yaml.safe_load").return_value = LOG_BASE_CONFIG

        obj = LayoutApplyLogConfig().log_config
        assert obj["handlers"]["file"]["level"] == "INFO"
        assert obj["handlers"]["console"]["level"] == "INFO"
        assert obj["root"]["level"] == "INFO"
