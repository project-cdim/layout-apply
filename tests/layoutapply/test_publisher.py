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
"""test class for MessagePublisheClient"""
import logging
from http import HTTPStatus
from logging import WARN

import pytest
import requests  # pylint: disable=W0611
from requests import exceptions
from requests.models import Response

from src.layoutapply.common.logger import Logger
from src.layoutapply.publisher import MessagePublisheClient
from src.layoutapply.setting import LayoutApplyConfig


class TestMessage:
    """test class for MessagePublisheClient"""

    def test_publish_message_success(self, caplog, mocker, docker_services):
        """Test that a message is successfully published to the topic."""
        config = LayoutApplyConfig()
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.INFO)

        MessagePublisheClient(logger, config.message_broker).publish_message()

        assert "Published message to topic " in caplog.text

    @pytest.mark.parametrize(
        "error_config",
        [
            (  # host is mistake
                {
                    "host": "invalid_host",
                    "port": 3500,
                    "pubsub": "layout_apply_apply",
                    "topic": "layout_apply_apply.completed",
                }
            ),
            (
                # port is mistake
                {
                    "host": "localhost",
                    "port": 4222,
                    "pubsub": "layout_apply_apply",
                    "topic": "layout_apply_apply.completed",
                }
            ),
            (
                # pubsub is mistake
                {
                    "host": "localhost",
                    "port": 3500,
                    "pubsub": "layout_apply",
                    "topic": "layout_apply_apply.completed",
                }
            ),
            (
                # topic is mistake
                {
                    "host": "localhost",
                    "port": 3500,
                    "pubsub": "layout_apply_apply",
                    "topic": "layout_apply_apply",
                }
            ),
        ],
    )
    def test_publish_message_failed_publish_error(self, caplog, error_config, mocker):
        """Test that a message publishing fails with an error configuration."""

        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.WARN)

        MessagePublisheClient(logger, error_config).publish_message()
        assert "Failed to publish message" in caplog.text

    @pytest.mark.parametrize(
        "exc",
        [
            (exceptions.Timeout("time out error")),
            (exceptions.ConnectionError("connection error")),
            (exceptions.RequestException("error ocurred")),
            (Exception("unknown error")),
        ],
    )
    def test_publish_message_failed_request_error(self, caplog, mocker, exc, docker_services):
        """Test that a message publishing fails with various request errors."""
        mocker.patch("requests.post", side_effect=exc)

        config = LayoutApplyConfig()
        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.WARN)

        MessagePublisheClient(logger, config.message_broker).publish_message()
        assert "Failed to publish message" in caplog.text
        logger.removeHandler(caplog.handler)

    def test_publish_message_failed_request_error_in_status_code(self, caplog, mocker):
        """Test that a message publishing fails when the status code is not 204."""

        resp = Response()
        resp.status_code = HTTPStatus.GATEWAY_TIMEOUT.value

        mocker.patch("requests.post", side_effect=exceptions.Timeout("time out error", response=resp))

        mocker.patch("logging.config.dictConfig")
        logger = logging.getLogger("logger.py")
        logger.handlers.clear()
        logger.addHandler(caplog.handler)
        logger.setLevel(logging.WARN)

        MessagePublisheClient(logger, LayoutApplyConfig().message_broker).publish_message()
        assert "Failed to publish message" in caplog.text
        assert "status:[504]" in caplog.text
        assert "response[time out error]" in caplog.text
