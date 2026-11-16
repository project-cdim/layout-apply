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
"""Test for setting message_broker"""

import copy

import pytest

from layoutapply.custom_exceptions import SettingFileLoadException
from layoutapply.setting import LayoutApplyConfig
from tests.layoutapply.conftest import BASE_CONFIG, LOG_BASE_CONFIG


class TestLayoutApplyConfigMessageBroker:
    """Tests for message_broker settings."""

    @pytest.mark.parametrize(
        "update_config",
        [
            {
                "message_broker": {
                    "host": "localhost",
                    "port": 3500,
                    "pubsub": "layout_apply_apply",
                    "topic": "layout_apply_apply.completed",
                }
            }
        ],
    )
    def test_setting_config_update_value_applied_when_message_broker_config(self, mocker, update_config):
        """Test setting updated values are applied correctly when message broker config is provided."""
        config = copy.deepcopy(BASE_CONFIG)
        config["message_broker"] = update_config["message_broker"]
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        message_broker_conf = LayoutApplyConfig().message_broker
        assert message_broker_conf.get("host") == "localhost"
        assert message_broker_conf.get("port") == 3500
        assert message_broker_conf.get("pubsub") == "layout_apply_apply"
        assert message_broker_conf.get("topic") == "layout_apply_apply.completed"

    @pytest.mark.parametrize(
        "update_config",
        [
            # message broker is type mismatch
            {"message_broker": 1},
            # host is not found
            {
                "message_broker": {
                    "port": 3500,
                    "pubsub": "layout_apply_apply",
                    "topic": "layout_apply_apply.completed",
                }
            },
            # port is not found
            {
                "message_broker": {
                    "host": "localhost",
                    "pubsub": "layout_apply_apply",
                    "topic": "layout_apply_apply.completed",
                }
            },
            # pubsub is not found
            {
                "message_broker": {
                    "host": "localhost",
                    "port": 3500,
                    "topic": "layout_apply_apply.completed",
                }
            },
            # topic is not found
            {
                "message_broker": {
                    "host": "localhost",
                    "port": 3500,
                    "pubsub": "layout_apply_apply",
                }
            },
            # host is type mismatch
            {
                "message_broker": {
                    "host": [1],
                    "port": 3500,
                    "pubsub": "layout_apply_apply",
                    "topic": "layout_apply_apply.completed",
                }
            },
            # port is type mismatch
            {
                "message_broker": {
                    "host": "localhost",
                    "port": [1],
                    "pubsub": "layout_apply_apply",
                    "topic": "layout_apply_apply.completed",
                }
            },
            # pubsub is type mismatch
            {
                "message_broker": {
                    "host": "localhost",
                    "port": 3500,
                    "pubsub": ["layout_apply_apply"],
                    "topic": "layout_apply_apply.completed",
                }
            },
            # topic is type mismatch
            {
                "message_broker": {
                    "host": "localhost",
                    "port": 3500,
                    "pubsub": "layout_apply_apply",
                    "topic": ["layout_apply_apply.completed"],
                }
            },
        ],
    )
    def test_setting_failure_when_invalid_message_broker_config(self, mocker, update_config):
        """Test setting failure when the message broker config is invalid."""
        base_config = copy.deepcopy(BASE_CONFIG)
        config = {**base_config, **update_config}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        with pytest.raises(SettingFileLoadException):
            assert LayoutApplyConfig().message_broker is not None
