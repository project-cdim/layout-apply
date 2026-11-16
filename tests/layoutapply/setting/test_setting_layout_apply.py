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
"""Test for setting layout_apply"""

import copy

import pytest

from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.setting import LayoutApplyConfig, LayoutApplyLogConfig
from tests.layoutapply.conftest import BASE_CONFIG, LOG_BASE_CONFIG


class TestLayoutApplyConfigServer:
    """Tests for layout_apply and log config loading behavior."""

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host
            {
                "layout_apply": {"host": "0.0.0.0", "port": 8003, "request": {}},
            },
            {
                "layout_apply": {"host": "nec.test.com", "port": 8003, "request": {"max_workers": 1}},
            },
            # port
            {
                "layout_apply": {"host": "nec.test.com", "port": 0, "request": {"max_workers": 1}},
            },
            # request - max_workers min
            {
                "layout_apply": {"host": "nec.test.com", "port": 8003, "request": {"max_workers": 1}},
            },
            # request - max_workers max
            {
                "layout_apply": {"host": "nec.test.com", "port": 8003, "request": {"max_workers": 128}},
            },
        ],
    )
    def test_setting_success_when_server_config_normal(self, mocker, update_confg):
        """Test setting success when server config is normal."""
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["layout_apply"]
        config = {**base_config, **update_confg}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        layout_apply_config = LayoutApplyConfig().layout_apply
        assert layout_apply_config["host"] == update_confg["layout_apply"]["host"]
        assert layout_apply_config["port"] == update_confg["layout_apply"]["port"]
        assert layout_apply_config["request"] == update_confg["layout_apply"]["request"]

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host is type mismatch
            {
                "layout_apply": {"host": 0, "port": 8003, "request": {"max_workers": 2}},
            },
            # port is type mismatch
            {
                "layout_apply": {"host": "nec.test.com", "port": "0", "request": {"max_workers": 2}},
            },
            # request is type mismatch
            {
                "layout_apply": {"host": "nec.test.com", "port": "0", "request": 1},
            },
            # request.max_workers is type mismatch
            {
                "layout_apply": {"host": "nec.test.com", "port": "0", "request": {"max_workers": "2"}},
            },
            # request.max_workers over min
            {
                "layout_apply": {"host": "nec.test.com", "port": "0", "request": {"max_workers": 0}},
            },
            # request.max_workers over max
            {
                "layout_apply": {"host": "nec.test.com", "port": "0", "request": {"max_workers": 129}},
            },
            # request.max_workers minus
            {
                "layout_apply": {"host": "nec.test.com", "port": "0", "request": {"max_workers": -1}},
            },
            # empty
            {},
        ],
    )
    def test_setting_failure_when_invalid_server_config(self, mocker, update_confg):
        """Test setting failure when server config is invalid."""
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["layout_apply"]
        config = {**base_config, **update_confg}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        with pytest.raises(SettingFileLoadException):
            assert LayoutApplyConfig().layout_apply is not None

    def test_setting_log_config_none_before_loading_log_configs(self, mocker):
        """Test that log_config is None before calling load_log_configs."""
        base_config = copy.deepcopy(BASE_CONFIG)
        mocker.patch("yaml.safe_load").return_value = base_config
        mocker.patch("requests.get")

        config = LayoutApplyConfig()

        assert config.log_config is None

    def test_setting_log_config_set_after_loading_log_configs(self, mocker):
        """Test that log_config is available after calling load_log_configs."""
        base_config = copy.deepcopy(BASE_CONFIG)
        mocker.patch("yaml.safe_load").side_effect = [base_config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")

        config = LayoutApplyConfig()
        config.load_log_configs()

        assert config.log_config is not None
        assert config.log_config == LOG_BASE_CONFIG

    def test_setting_failure_when_load_log_configs_failed(self, mocker):
        """Test that load_log_configs raises SettingFileLoadException on log config load failure."""
        base_config = copy.deepcopy(BASE_CONFIG)
        mocker.patch("yaml.safe_load").return_value = base_config
        mocker.patch("requests.get")
        mocker.patch.object(
            LayoutApplyLogConfig,
            "__init__",
            side_effect=SettingFileLoadException("Dummy message", "layoutapply_log_config.yaml"),
        )

        config = LayoutApplyConfig()

        with pytest.raises(SettingFileLoadException):
            config.load_log_configs()
