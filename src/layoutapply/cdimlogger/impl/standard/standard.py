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
import logging
import logging.handlers
import os
import sys

from ... import common
from ...format import formatter
from .. import ilogger

""" Class for Python standard logger: logging
    Inheriting from ilogger.Ilogger.

    Args:
        tag (str): Tag for sorting log file.
        log_dir (str): Directory for output.
        log_file (str): Log file name.
        logging_level(int): Logger level. (default:INFO)
        rotation_size (int): Rotation size.
        backup_files(int): backup file's Count to allow the file to rollover at a predetermined size.
        stdout(bool): Whether to output to sys.stdout as well. (default:false)
"""


class Standard(ilogger.Ilogger):

    def __init__(
        self,
        tag="",
        log_dir="",
        log_file="",
        logging_level=common.INFO,
        rotation_size="",
        backup_files="",
        stdout=False,
    ):
        self._logdir = common.LOG_DIR if log_dir == "" else log_dir

        if log_file == "":
            if tag in common.LOG_FILES:
                self._log_file = common.LOG_FILES[tag]
            else:
                self._log_file = common.LOG_DEFAULT_FILE
        else:
            self._log_file = log_file

        self._rotation_size = common.LOG_ROTATION_SIZE if rotation_size == "" else rotation_size
        self._backup_files = common.LOG_BACKUP_FILES if backup_files == "" else backup_files

        self._log_format = common.LOG_FORMAT

        self.logger = logging.getLogger(os.path.basename(__file__))
        self._clearLoggerHandlers(self.logger)
        self.logger.setLevel(logging_level)

        self._fmt = formatter.Formatter(self._log_format)
        self._rh = logging.handlers.RotatingFileHandler(
            os.path.join(self._logdir, self._log_file),
            encoding=common.LOG_ENCODING,
            maxBytes=self._rotation_size,
            mode=common.LOG_MODE,
            backupCount=self._backup_files,
        )
        self._rh.setFormatter(self._fmt)
        self.logger.addHandler(self._rh)

        if stdout:
            self._sh = logging.StreamHandler(sys.stdout)
            self._sh.setFormatter(self._fmt)
            self.logger.addHandler(self._sh)

        """ Add level names (for trail logs and event logs) """
        logging.addLevelName(common.TRAIL_REQ, common.TAG_TRAIL + ".REQ")
        logging.addLevelName(common.TRAIL_RES, common.TAG_TRAIL + ".RES")
        logging.addLevelName(common.EVENT_PUB, common.TAG_EVENT + ".PUB")
        logging.addLevelName(common.EVENT_SUB, common.TAG_EVENT + ".SUB")

    def debug(self, message: str, stack_info=False):
        """Output debug logs
        Args:
            message (str)    : Message data.
            stack_info(bool) : Whether to output Stacktrace.(default: False)

        Returns:
            None
        """
        self.logger.debug(self._appLogToJson(message, self._getStacktrace(stack_info)))

    def info(self, message: str, stack_info=False):
        """Output info logs
        Args:
            message (str)    : Message data.
            stack_info(bool) : Whether to output Stacktrace.(default: False)

        Returns:
            None
        """
        self.logger.info(self._appLogToJson(message, self._getStacktrace(stack_info)))

    def warning(self, message: str, stack_info=False):
        """Output warning logs
        Args:
            message (str)    : Message data.
            stack_info(bool) : Whether to output Stacktrace.(default: False)

        Returns:
            None
        """
        self.logger.warning(self._appLogToJson(message, self._getStacktrace(stack_info)))

    def error(self, message: str, stack_info=True):
        """Output error logs
        Args:
            message (str)    : Message data.
            stack_info(bool) : Whether to output Stacktrace.(default: True)

        Returns:
            None
        """
        self.logger.error(self._appLogToJson(message, self._getStacktrace(stack_info)))

    def critical(self, message: str, stack_info=True):
        """Output critical logs
        Args:
            message (str)    : Message data.
            stack_info(bool) : Whether to output Stacktrace.(default: True)

        Returns:
            None
        """
        self.logger.critical(self._appLogToJson(message, self._getStacktrace(stack_info)))

    def trailReq(self, method: str, endpoint: str, user: str, message: str):
        """Generate audit log for request
        Args:
            method (str)   : HTTP method for REST API.
            endpoint (str) : Endpoint name for REST API.
            user (str)     : Login user(name or id..etc) to UI.
            message (str)  : Message data.

        Returns:
            None
        """
        self.logger.log(common.TRAIL_REQ, self._trailReqLogToJson(method, endpoint, user, message))

    def trailRes(self, status: int, message: str):
        """Generate audit log for response
        Args:
            status (int)   : HTTP response status code.
            message (str)  : Message data.

        Returns:
            None
        """
        self.logger.log(common.TRAIL_RES, self._trailResLogToJson(status, message))

    def eventPub(self, subject: str):
        """Generate event log during publish
        Args:
            subject (str)   : Subject to be Publish.

        Returns:
            None
        """
        self.logger.log(common.EVENT_PUB, self._eventPubLogToJson(subject))

    def eventSub(self, subject: str, consumer: str):
        """Generate event log for subscribing
        Args:
            subject (str)    : Subject to be Subscribe.
            consumer (str)   : Consumer to be Subscribe.

        Returns:
            None
        """
        self.logger.log(common.EVENT_SUB, self._eventSubLogToJson(subject, consumer))

    def _clearLoggerHandlers(self, logger):
        """Close the logger handler
        Args:
            logger (Logger)  : Logger for close handler.

        Returns:
            None
        """
        for h in logger.handlers[:]:
            logger.removeHandler(h)
            h.close()
