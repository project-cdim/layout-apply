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
"""Test for setting"""

import copy

import pytest

from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.setting import LayoutApplyConfig
from tests.layoutapply.conftest import BASE_CONFIG, LOG_BASE_CONFIG


class TestLayoutApplyConfigGetInformation:
    """Tests for get_information and related defaults/validation."""

    @pytest.mark.parametrize(
        "update_confg",
        [
            # count is min
            {
                "polling": {
                    "count": 1,
                    "interval": 1,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # count is max
            {
                "polling": {
                    "count": 240,
                    "interval": 1,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # interval is min
            {
                "polling": {
                    "count": 8,
                    "interval": 0,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # interval is max
            {
                "polling": {
                    "count": 8,
                    "interval": 240,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # request.timeout is min
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 1},
                "timeout": 10,
            },
            # request.timeout is max
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 600},
                "timeout": 10,
            },
            # request.timeout is not exist
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                # "request": {"timeout": 3},
                "timeout": 10,
            },
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {},
                "timeout": 10,
            },
            # request.timeout is None
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": None},
                "timeout": 10,
            },
            # timeout is min
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 3},
                "timeout": 1,
            },
            # timeout is max
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 3},
                "timeout": 600,
            },
        ],
    )
    def test_setting_success_when_os_boot_check_api_config_normal(self, mocker, update_confg):
        """Test setting success when OS boot check API config is normal."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["hardware_control"]["isosboot"]
        config["hardware_control"]["isosboot"] = update_confg
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        layout_apply_isosboot_conf = LayoutApplyConfig().isosboot
        assert layout_apply_isosboot_conf["polling"] == update_confg["polling"]
        if "request" in update_confg:
            if "timeout" in update_confg["request"]:
                assert layout_apply_isosboot_conf["request"]["timeout"] == update_confg["request"]["timeout"]
            else:
                assert layout_apply_isosboot_conf["request"] == {"timeout": None}
        assert layout_apply_isosboot_conf["timeout"] == update_confg["timeout"]

    @pytest.mark.parametrize(
        "update_confg",
        [
            # count is min-1
            {
                "polling": {
                    "count": 0,
                    "interval": 1,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # count is max+1
            {
                "polling": {
                    "count": 241,
                    "interval": 1,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # count is minus
            {
                "polling": {
                    "count": -1,
                    "interval": 1,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # count is type error
            {
                "polling": {
                    "count": "240",
                    "interval": 1,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # interval is min-1
            {
                "polling": {
                    "count": 8,
                    "interval": -1,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # interval is max+1
            {
                "polling": {
                    "count": 8,
                    "interval": 241,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # interval is type error
            {
                "polling": {
                    "count": 8,
                    "interval": "240",
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 2},
                "timeout": 10,
            },
            # request.timeout is min-1
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 0},
                "timeout": 10,
            },
            # request.timeout is max+1
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 601},
                "timeout": 10,
            },
            # request.timeout minus
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": -1},
                "timeout": 10,
            },
            # request.timeout is type error
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": "3"},
                "timeout": 10,
            },
            # timeout is None
            {
                "polling": {
                    "count": 8,
                    "interval": 0,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 3},
                "timeout": None,
            },
            # timeout is min-1
            {
                "polling": {
                    "count": 8,
                    "interval": 0,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 3},
                "timeout": 0,
            },
            # timeout is max+1
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 3},
                "timeout": 601,
            },
            # timeout is minus
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 3},
                "timeout": -1,
            },
            # timeout is type error
            {
                "polling": {
                    "count": 8,
                    "interval": 3,
                    "skip": [
                        {"status_code": 400, "code": "EF003BAS010"},
                    ],
                },
                "request": {"timeout": 3},
                "timeout": "600",
            },
            # polling is not exist
            {
                "request": {"timeout": 3},
                "timeout": 601,
            },
        ],
    )
    def test_setting_failure_when_invalid_os_boot_check_api_config(self, mocker, update_confg):
        """Test setting failure when OS boot check API config is invalid."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["hardware_control"]["isosboot"]
        config["hardware_control"]["isosboot"] = update_confg
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        with pytest.raises(SettingFileLoadException):
            assert LayoutApplyConfig().isosboot is not None

    @pytest.mark.parametrize(
        "update_confg",
        [
            {
                "polling": {
                    # "count": 10,
                    # "interval": 11,
                },
                "request": {"timeout": 2},
                # "timeout": 13,
            },
        ],
    )
    def test_setting_default_set_when_no_optional_os_boot_check_api_item(self, mocker, update_confg):
        """Test setting default values when no optional OS boot check API items are provided."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["hardware_control"]["isosboot"]
        config["hardware_control"]["isosboot"] = update_confg
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        is_os_boot_conf = LayoutApplyConfig().isosboot
        assert is_os_boot_conf.get("polling").get("count") == 8
        assert is_os_boot_conf.get("polling").get("interval") == 30
        assert is_os_boot_conf.get("timeout") == 60

    @pytest.mark.parametrize(
        ("update_confg", "operation"),
        [
            (
                {
                    "polling": {
                        "test_count": 0,
                        "test_interval": 0,
                    }
                },
                "poweroff",
            ),
            (
                {
                    "polling": {
                        "test_count": 0,
                        "test_interval": 0,
                    }
                },
                "connect",
            ),
            (
                {
                    "polling": {
                        "test_count": 0,
                        "test_interval": 0,
                    }
                },
                "disconnect",
            ),
        ],
    )
    def test_setting_get_information_default_set_when_invalid_item(self, mocker, update_confg, operation):
        """Test setting default values for get_information when an invalid item is provided."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["get_information"]["specs"][operation]
        del config["get_information"]["specs"]["timeout"]
        config["get_information"]["specs"][operation] = update_confg
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        get_info_conf = LayoutApplyConfig().get_information
        assert get_info_conf["specs"][operation].get("polling").get("count") == 8
        assert get_info_conf["specs"][operation].get("polling").get("interval") == 30
        assert get_info_conf["specs"].get("timeout") == 60

    @pytest.mark.parametrize(
        "update_confg",
        [
            {
                "polling": {
                    "count": 10,
                    "interval": 11,
                },
                "request": {"timeout": 2},
                "timeout": 13,
            },
        ],
    )
    def test_setting_config_value_applied_when_os_boot_check_api_config(self, mocker, update_confg):
        """Test setting config values are applied correctly when OS boot check API config is provided."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["hardware_control"]["isosboot"]
        config["hardware_control"]["isosboot"] = update_confg
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        is_os_boot_conf = LayoutApplyConfig().isosboot
        assert is_os_boot_conf.get("polling").get("count") == 10
        assert is_os_boot_conf.get("polling").get("interval") == 11
        assert is_os_boot_conf.get("request").get("timeout") == 2
        assert is_os_boot_conf.get("timeout") == 13

    @pytest.mark.parametrize(
        "update_confg",
        [
            # Normal value
            {
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
            },
            # Boundary value (minimum value)
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 1,
                                "interval": 0,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 1,
                                "interval": 0,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 1,
                                "interval": 0,
                            },
                        },
                        "timeout": 1,
                    },
                },
            },
            # Boundary value (maximum value)
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 240,
                                "interval": 240,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 240,
                                "interval": 240,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 240,
                                "interval": 240,
                            },
                        },
                        "timeout": 600,
                    },
                },
            },
        ],
    )
    def test_setting_config_value_applied_when_device_info_api_config(self, mocker, update_confg):
        """Test setting config values are applied correctly when device info API config is provided."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["get_information"]
        config["get_information"] = update_confg["get_information"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        get_information_conf = LayoutApplyConfig().get_information
        assert get_information_conf.get("host") == "localhost"
        assert get_information_conf.get("port") == 48889
        assert get_information_conf.get("uri") == "api/v1"
        specs_conf = get_information_conf.get("specs")
        expected_specs = update_confg["get_information"]["specs"]
        assert specs_conf.get("poweroff").get("polling").get("count") == expected_specs["poweroff"]["polling"]["count"]
        assert (
            specs_conf.get("poweroff").get("polling").get("interval")
            == expected_specs["poweroff"]["polling"]["interval"]
        )
        assert specs_conf.get("connect").get("polling").get("count") == expected_specs["connect"]["polling"]["count"]
        assert (
            specs_conf.get("connect").get("polling").get("interval") == expected_specs["connect"]["polling"]["interval"]
        )
        assert (
            specs_conf.get("disconnect").get("polling").get("count") == expected_specs["disconnect"]["polling"]["count"]
        )
        assert (
            specs_conf.get("disconnect").get("polling").get("interval")
            == expected_specs["disconnect"]["polling"]["interval"]
        )
        assert specs_conf.get("timeout") == expected_specs["timeout"]

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host is valid
            {
                "get_information": {
                    "host": "127.0.0.1",
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
            },
            # port is valid
            {
                "get_information": {
                    "host": "localhost",
                    "port": 8000,
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
            },
            # uri is correct
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "cdim/api/v1",
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
            },
            # count is min
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 1,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 1,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 1,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # count is max
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 240,
                                "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 240,
                                "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 240,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # interval is min
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 0,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 5,
                                "interval": 0,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 5,
                                "interval": 0,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # interval is max
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 240,
                            },
                        },
                        "connect": {
                            "polling": {
                                "count": 5,
                                "interval": 240,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                "count": 5,
                                "interval": 240,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # timeout is min
            {
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
                        "timeout": 1,
                    },
                },
            },
            # timeout is max
            {
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
                        "timeout": 600,
                    },
                },
            },
        ],
    )
    def test_setting_success_when_device_info_api_config_normal(self, mocker, update_confg):
        """Test setting success when device info API config is normal."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["get_information"]
        config["get_information"] = update_confg["get_information"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        get_info_conf = LayoutApplyConfig().get_information
        assert get_info_conf["host"] == update_confg["get_information"]["host"]
        assert get_info_conf["port"] == update_confg["get_information"]["port"]
        assert get_info_conf["uri"] == update_confg["get_information"]["uri"]
        assert get_info_conf["specs"] == update_confg["get_information"]["specs"]

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host is type error
            {
                "get_information": {
                    "host": 127001,
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # port is type error
            {
                "get_information": {
                    "host": "localhost",
                    "port": "port",
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # uri is type error
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": 654321,
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # count is min-1
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 0,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # count is max+1
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 241,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # count is minus
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": -1,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # count is type error
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": "a",
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # interval is min-1
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": -1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # interval is max+1
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 241,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # interval is type error
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": "a",
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # timeout is max+1
            {
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
                        "timeout": 601,
                    },
                },
            },
            # timeout is min-1
            {
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
                        "timeout": 0,
                    },
                },
            },
            # timeout is minus
            {
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
                        "timeout": -1,
                    },
                },
            },
            # timeout is type error
            {
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
                        "timeout": "a",
                    },
                },
            },
            # host is not exist
            {
                "get_information": {
                    # "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                "count": 5,
                                "interval": 1,
                            },
                        },
                        "timeout": 10,
                    },
                },
            },
            # specs is not exist
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    # "specs":{
                    #     "poweroff": {
                    #         "polling": {
                    #             "count": 5,
                    #             "interval": 1,
                    #         },
                    #     },
                    #     "timeout": 10
                    # }
                },
            },
            # poweroff is not exist
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        # "poweroff": {
                        #     "polling": {
                        #         "count": 5,
                        #         "interval": 1,
                        #     },
                        # },
                        "timeout": 10
                    },
                },
            },
            # polling is not exist
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            # "polling": {
                            #     "count": 5,
                            #     "interval": 1,
                            # },
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
            },
        ],
    )
    def test_setting_failure_when_invalid_device_info_api_config(self, mocker, update_confg):
        """Test setting failure when device info API config is invalid."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["get_information"]
        config["get_information"] = update_confg["get_information"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        with pytest.raises((SettingFileLoadException, AttributeError, TypeError)):
            assert LayoutApplyConfig().get_information is not None

    @pytest.mark.parametrize(
        "update_confg",
        [
            # polling: timeout
            {
                "get_information": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "specs": {
                        "poweroff": {
                            "polling": {
                                # "count": 5,
                                # "interval": 1,
                            },
                        },
                        "connect": {
                            "polling": {
                                # "count": 5,
                                # "interval": 1,
                            },
                        },
                        "disconnect": {
                            "polling": {
                                # "count": 5,
                                # "interval": 1,
                            },
                        },
                        # "timeout": 10
                    },
                },
            },
        ],
    )
    def test_setting_default_set_when_no_optional_device_info_api_item(self, mocker, update_confg):
        """Test setting default values when no optional device info API items are provided."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["get_information"]
        config["get_information"] = update_confg["get_information"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        get_information_conf = LayoutApplyConfig().get_information
        specs_conf = get_information_conf.get("specs")
        assert specs_conf.get("poweroff").get("polling").get("count") == 8
        assert specs_conf.get("poweroff").get("polling").get("interval") == 30
        assert specs_conf.get("timeout") == 60
