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
import datetime
import io
import json
import logging
import os
import re

import pytest

from layoutapply.common.logger import Logger, MicrosecondFormatter


class TestMicrosecondFormatter:
    """Test for MicrosecondFormatter"""

    @pytest.fixture
    def formatter(self):
        return MicrosecondFormatter()

    def test_formatTime_no_datefmt(self, formatter):
        """Verify that the time is formatted with the default format when datefmt is None"""
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1, msg="test message", args=(), exc_info=None
        )
        record.created = datetime.datetime(2023, 10, 27, 10, 30, 45, 123).timestamp()
        record.msecs = 123.0
        formatted_time = formatter.formatTime(record)
        dt = datetime.datetime(2023, 10, 27, 10, 30, 45, 123456)
        expected_time = dt.strftime("%Y-%m-%d %H:%M:%S,") + f"{dt.microsecond // 1000:03d}"

        assert formatted_time == expected_time

    def test_formatTime_with_datefmt_no_microseconds(self, formatter):
        """Verify that when datefmt is provided without microseconds, the time is formatted according to the given format."""
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1, msg="test message", args=(), exc_info=None
        )
        record.created = datetime.datetime(2023, 10, 27, 10, 30, 45, 123456).timestamp()

        formatted_time = formatter.formatTime(record, datefmt="%Y-%m-%d")
        expected_time = "2023-10-27"

        assert formatted_time == expected_time

    def test_formatTime_with_datefmt_with_microseconds(self, formatter):
        """Verify that microseconds are properly formatted if datefmt includes %f."""
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1, msg="test message", args=(), exc_info=None
        )
        record.created = datetime.datetime(2023, 10, 27, 10, 30, 45, 123456).timestamp()

        formatted_time = formatter.formatTime(record, datefmt="%Y-%m-%d %H:%M:%S.%f")
        expected_time = "2023-10-27 10:30:45.123456"

        assert formatted_time == expected_time

    def test_formatTime_with_strftime_directives(self, formatter):
        """Verify that all strftime directives in datefmt (excluding microseconds) are formatted properly."""
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1, msg="test message", args=(), exc_info=None
        )
        record.created = datetime.datetime(2023, 10, 27, 10, 30, 45, 123456).timestamp()

        formatted_time = formatter.formatTime(record, datefmt="%a, %d %b %Y %H:%M:%S %Z")
        expected_time = datetime.datetime(2023, 10, 27, 10, 30, 45, 123456).strftime("%a, %d %b %Y %H:%M:%S %Z")
        assert formatted_time == expected_time


class TestLogger:
    """Test for Logger"""

    TEST_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,  # Required parameters for testing
        "formatters": {
            "standard": {"format": "%(asctime)s %(levelname)s %(message)s", "datefmt": "%Y/%m/%d %H:%M:%S.%f"},
        },
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": "test.log",  # Log file for testing.
                "encoding": "utf-8",
            },
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",  # Use DEBUG logging level during testing.
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {"level": "DEBUG", "handlers": ["file", "console"]},  # Use DEBUG logging level during testing.
    }

    @pytest.fixture
    def logger(self):
        """Create a Logger instance for testing."""
        logger = Logger(self.TEST_CONFIG)
        yield logger
        # teardown: Delete the log file after testing.
        if os.path.exists("test.log"):
            os.remove("test.log")

    def assert_log_structure(self, log_dict, message):
        """Helper function to verify the basic structure of log output."""
        assert "file" in log_dict
        assert "line" in log_dict
        assert log_dict["message"] == message

    def capture_log_output(self, logger):
        """Helper function to capture log output."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger._logger.addHandler(handler)
        return stream, handler

    def test_logger_initialization(self, logger):
        """Verify that the logger attribute of the Logger class is a logging.Logger instance."""
        assert hasattr(logger, "_logger")
        assert isinstance(logger._logger, logging.Logger)

    def test_appLogToJson_no_stacktrace(self, logger):
        """Verify that the _appLogToJson method generates a properly formatted JSON log message without a stack trace."""
        message = "Test message without stacktrace"

        json_log = logger._appLogToJson(message)
        log_dict = json.loads(json_log)

        self.assert_log_structure(log_dict, message)
        assert "stacktrace" not in log_dict

    def test_appLogToJson_with_stacktrace(self, logger):
        """Verify that the _appLogToJson method generates a properly formatted JSON log message with a stack trace."""
        message = "Test message with stacktrace"
        stacktrace = "This is a sample stacktrace"

        json_log = logger._appLogToJson(message, stacktrace)
        log_dict = json.loads(json_log)

        self.assert_log_structure(log_dict, message)
        assert "stacktrace" in log_dict
        assert log_dict["stacktrace"] == stacktrace

    def test_appLogToJson_with_unicode(self, logger):
        """Verify that messages containing Unicode characters are correctly converted to JSON format."""
        message = "Unicode テスト メッセージ"

        json_log = logger._appLogToJson(message)
        log_dict = json.loads(json_log)

        self.assert_log_structure(log_dict, message)

    @pytest.mark.parametrize("stack_info", [True, False])
    def test_process_log_stack_info(self, logger, stack_info):
        """Verify that _process_log generates logs with or without a stack trace depending on the stack_info argument."""
        stream, handler = self.capture_log_output(logger)
        message = f"Test message with stack_info = {stack_info}"
        level = logging.DEBUG

        logger._process_log(level, message, stack_info=stack_info)
        handler.flush()
        json_output = stream.getvalue().strip()
        log_dict = json.loads(json_output)

        if stack_info:
            assert "stacktrace" in log_dict
        else:
            assert "stacktrace" not in log_dict
        assert log_dict["message"] == message

    @pytest.mark.parametrize(
        "log_level",
        [
            "debug",
            "info",
            "warning",
            "error",
            "critical",
        ],
    )
    def test_log_levels(self, logger, log_level):
        """Test to verify that each logging level functions correctly."""
        stream, handler = self.capture_log_output(logger)
        message = f"{log_level.capitalize()} message"

        getattr(logger, log_level)(message)
        handler.flush()
        log_line = stream.getvalue().strip()

        assert log_line != "", "ログが出力されていません"
        log_dict = json.loads(log_line)
        assert log_dict["message"] == message

    def test_log_file_output(self, logger):
        """Verify that logs are output to the log file."""
        log_message = "Test log message to file"
        log_file = "test.log"

        logger.info(log_message)
        for handler in logger._logger.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.flush()

        assert os.path.exists(log_file)

        with open(log_file, "r", encoding="utf-8") as f:
            log_content = f.read()
            assert re.search(
                r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\.\d{6} INFO .*" + re.escape(log_message), log_content
            )
