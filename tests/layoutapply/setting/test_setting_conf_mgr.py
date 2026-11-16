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
"""Test for setting configuration_manager"""

import copy

import pytest

from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.setting import LayoutApplyConfig
from tests.layoutapply.conftest import BASE_CONFIG, LOG_BASE_CONFIG


class TestLayoutApplyConfigConfigurationManager:
    """Tests for configuration_manager settings."""

    @pytest.mark.parametrize(
        "update_confg",
        [
            # Normal value
            {
                "configuration_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "cdim/api/v1",
                    "timeout": 30,
                },
            },
            # Boundary value (minimum value)
            {
                "configuration_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "cdim/api/v1",
                    "timeout": 1,
                },
            },
            # Boundary value (maximum value)
            {
                "configuration_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "cdim/api/v1",
                    "timeout": 600,
                },
            },
        ],
    )
    def test_setting_success_when_config_info_management_api_config_normal(self, mocker, update_confg):
        """Test setting success when configuration info management API config is normal."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["configuration_manager"]
        config["configuration_manager"] = update_confg["configuration_manager"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        configuration_manager_conf = LayoutApplyConfig().configuration_manager
        assert configuration_manager_conf.get("host") == "localhost"
        assert configuration_manager_conf.get("port") == 48889
        assert configuration_manager_conf.get("uri") == "cdim/api/v1"
        assert configuration_manager_conf.get("timeout") == update_confg["configuration_manager"]["timeout"]

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host is no existent
            {
                "configuration_manager": {
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": 10,
                },
            },
            # port is no existent
            {
                "configuration_manager": {
                    "host": "localhost",
                    "uri": "api/v1",
                    "timeout": 10,
                },
            },
            # uri is no existent
            {
                "configuration_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "timeout": 10,
                },
            },
            # host is type error
            {
                "configuration_manager": {
                    "host": 127001,
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": 10,
                },
            },
            # port is type error
            {
                "configuration_manager": {
                    "host": "localhost",
                    "port": "port",
                    "uri": "api/v1",
                    "timeout": 10,
                },
            },
            # uri is type error
            {
                "configuration_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": 654321,
                    "timeout": 10,
                },
            },
            # timeout max +1
            {
                "configuration_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": 601,
                },
            },
            # timeout min -1
            {
                "configuration_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": 0,
                },
            },
            # timeout is minus
            {
                "configuration_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": -1,
                },
            },
            # timeout is type error
            {
                "configuration_manager": {
                    "host": "localhost",
                    "port": 48889,
                    "uri": "api/v1",
                    "timeout": "timeout",
                },
            },
        ],
    )
    def test_setting_failure_when_invalid_config_info_management_api_config(self, mocker, update_confg):
        """Test setting failure when the configuration info management API config is invalid."""
        config = copy.deepcopy(BASE_CONFIG)
        del config["configuration_manager"]
        config["configuration_manager"] = update_confg["configuration_manager"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        with pytest.raises(SettingFileLoadException):
            assert LayoutApplyConfig().configuration_manager is not None
