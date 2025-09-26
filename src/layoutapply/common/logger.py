# Copyright (C) 2025 NEC Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
#  under the License.
"""Common logger package"""

import datetime
import inspect
import json
import logging
import logging.config
import traceback


class MicrosecondFormatter(logging.Formatter):
    """Custom formatter to include microseconds in log timestamps"""

    def formatTime(self, record, datefmt=None):
        dt = datetime.datetime.fromtimestamp(record.created)
        if datefmt:
            s = dt.strftime(datefmt)
            if "%f" in datefmt:
                s = s.replace("%f", "{:06d}".format(dt.microsecond))  # pylint: disable=C0209
            return s
        else:
            return super().formatTime(record, datefmt)


class Logger:
    """Logger class for logging messages"""

    def __init__(self, config: dict):
        """Constructor

        Args:
            config (dict): Setting the logger from a log configuration file.
        """
        self._logger = self.setup_logger(config)

    def setup_logger(self, config: dict):
        """Set up the logger.

        Args:
            config (dict): Setting the logger from a log configuration file.
        Returns:
            logging.GetLogger: Logger
        """
        config["formatters"]["standard"]["()"] = MicrosecondFormatter
        logging.config.dictConfig(config)
        return logging.getLogger()

    def _appLogToJson(self, message: str, stacktrace: str = "") -> str:  # pylint: disable=C0103
        """Return the logs formatted as JSON.

        Args:
            message (str): Message for logging.
            stacktrace (str): Stack trace for logging.
        Returns:
            JSON (str): JSON formatted log message.
        """
        applog = {
            "file": inspect.stack()[3].filename,
            "line": inspect.stack()[3].lineno,
            "message": message,
        }
        if stacktrace:
            applog["stacktrace"] = stacktrace.replace("\n", "")
        return json.dumps(applog, separators=(",", ":"), ensure_ascii=False)

    def _process_log(self, level: int, message: str, *args, stack_info: bool = False, **kwargs) -> None:
        """Attach the stack trace to the message.

        Args:
            level (int): Log level.
            message (str): Message for logging.
            *args: Additional arguments for logging.
            stack_info (bool): If True, include stack trace information.
            **kwargs: Additional keyword arguments for logging.
        """
        stacktrace = ""
        if stack_info:
            stacktrace = "".join(traceback.extract_stack().format())[:-1]
        json_message = self._appLogToJson(message, stacktrace)
        self._logger.log(level, json_message, *args, **kwargs)

    def debug(self, message: str, *args, stack_info: bool = False, **kwargs):
        """Debug logging function

        Args:
            message (str): Message for logging.
            *args: Additional arguments for logging.
            stack_info (bool): If True, include stack trace information.
            **kwargs: Additional keyword arguments for logging.
        """
        self._process_log(logging.DEBUG, message, *args, stack_info=stack_info, **kwargs)

    def info(self, message: str, *args, stack_info: bool = False, **kwargs):
        """Info logging function

        Args:
            message (str): Message for logging.
            *args: Additional arguments for logging.
            stack_info (bool): If True, include stack trace information.
            **kwargs: Additional keyword arguments for logging.
        """
        self._process_log(logging.INFO, message, *args, stack_info=stack_info, **kwargs)

    def warning(self, message: str, *args, stack_info: bool = False, **kwargs):
        """Warning logging function

        Args:
            message (str): Message for logging.
            *args: Additional arguments for logging.
            stack_info (bool): If True, include stack trace information.
            **kwargs: Additional keyword arguments for logging.
        """
        self._process_log(logging.WARNING, message, *args, stack_info=stack_info, **kwargs)

    def error(self, message: str, *args, stack_info: bool = False, **kwargs):
        """Error logging function

        Args:
            message (str): Message for logging.
            *args: Additional arguments for logging.
            stack_info (bool): If True, include stack trace information.
            **kwargs: Additional keyword arguments for logging.
        """
        self._process_log(logging.ERROR, message, *args, stack_info=stack_info, **kwargs)

    def critical(self, message: str, *args, stack_info: bool = False, **kwargs):
        """Critical logging function

        Args:
            message (str): Message for logging.
            *args: Additional arguments for logging.
            stack_info (bool): If True, include stack trace information.
            **kwargs: Additional keyword arguments for logging.
        """
        self._process_log(logging.CRITICAL, message, *args, stack_info=stack_info, **kwargs)
