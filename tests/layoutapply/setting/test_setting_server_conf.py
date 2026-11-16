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
"""Test for setting server_connection"""

import copy

import pytest

from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.setting import LayoutApplyConfig
from tests.layoutapply.conftest import BASE_CONFIG, LOG_BASE_CONFIG


class TestLayoutApplyConfigServerConnection:
    """Tests for server_connection settings."""

    @pytest.mark.parametrize(
        "update_config",
        [
            {
                "server_connection": {
                    "retry": {
                        "intervals": 5,
                        "max_counts": 10,
                    },
                },
            },
            {
                "server_connection": {
                    "retryy": {
                        "interval": 6,
                        "max_count": 8,
                    },
                },
            },
        ],
    )
    def test_setting_config_default_value_applied_when_server_connection_config(self, mocker, update_config):
        """Test setting default values are applied correctly when server connection config is provided."""
        config = copy.deepcopy(BASE_CONFIG)
        config["server_connection"] = update_config["server_connection"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        server_connection_conf = LayoutApplyConfig().server_connection
        assert server_connection_conf.get("retry").get("interval") == 2
        assert server_connection_conf.get("retry").get("max_count") == 4

    @pytest.mark.parametrize(
        "update_config",
        [
            # Normal value
            {
                "server_connection": {
                    "retry": {
                        "interval": 30,
                        "max_count": 5,
                    },
                },
            },
            # Boundary value (minimum value)
            {
                "server_connection": {
                    "retry": {
                        "interval": 0,
                        "max_count": 0,
                    },
                },
            },
            # Boundary value (maximum value)
            {
                "server_connection": {
                    "retry": {
                        "interval": 60,
                        "max_count": 10,
                    },
                },
            },
        ],
    )
    def test_setting_config_update_value_applied_when_server_connection_config(self, mocker, update_config):
        """Test setting updated values are applied correctly when server connection config is provided."""
        config = copy.deepcopy(BASE_CONFIG)
        config["server_connection"] = update_config["server_connection"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        server_connection_conf = LayoutApplyConfig().server_connection
        expected_config = update_config["server_connection"]["retry"]
        assert server_connection_conf.get("retry").get("interval") == expected_config["interval"]
        assert server_connection_conf.get("retry").get("max_count") == expected_config["max_count"]

    @pytest.mark.parametrize(
        "update_config",
        [
            # server_connection is type mismatch
            {"server_connection": 1},
            # retry is type mismatch
            {
                "server_connection": {"retry": 1},
            },
            # retry.interval is type mismatch
            {
                "server_connection": {"retry": {"interval": "1", "max_count": 2}},
            },
            # retry.max_count is type mismatch
            {
                "server_connection": {"retry": {"interval": 1, "max_count": "2"}},
            },
            # retry.interval over min
            {
                "server_connection": {"retry": {"interval": -1, "max_count": 2}},
            },
            # retry.interval over max
            {
                "server_connection": {"retry": {"interval": 61, "max_count": 2}},
            },
            # retry.max_count over min
            {
                "server_connection": {"retry": {"interval": 1, "max_count": -1}},
            },
            # retry.max_count over max
            {
                "server_connection": {"retry": {"interval": 1, "max_count": 11}},
            },
        ],
    )
    def test_setting_failure_when_invalid_server_connection_config(self, mocker, update_config):
        """Test setting failure when the server connection config is invalid."""
        base_config = copy.deepcopy(BASE_CONFIG)
        config = {**base_config, **update_config}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        with pytest.raises(SettingFileLoadException):
            assert LayoutApplyConfig().server_connection is not None
