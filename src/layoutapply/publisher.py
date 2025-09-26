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
"""message publisher for layoutapply"""
from http import HTTPStatus

import requests

from layoutapply.common.logger import Logger
from layoutapply.const import PublishRequestParameter
from layoutapply.custom_exceptions import MessagePublishException


class MessagePublisheClient:
    """Client for publishing messages to a Dapr pub topic."""

    def __init__(self, logger: Logger, config: dict) -> None:
        """Constructor

        Args:
            logger (Logger): logger instance for logging
            config (dict): layout apply configuration
        """
        self.uri: str = PublishRequestParameter.URL.format(
            config.get("host"), config.get("port"), config.get("pubsub"), config.get("topic")
        )

        self.logger: Logger = logger

    def publish_message(self) -> None:
        """Publish a message to the specified topic."""
        try:
            response = requests.post(self.uri, timeout=100, headers={"Content-Type": "application/json"})
            if response.status_code != HTTPStatus.NO_CONTENT.value:
                raise MessagePublishException(response=response)
            self.logger.info(f"Published message to topic '{self.uri}")
        except Exception as e:  # pylint: disable=broad-except
            exc = MessagePublishException(exc=e)
            self.logger.warning(exc.message)
