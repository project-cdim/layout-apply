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
import inspect
import json
import traceback
from abc import ABCMeta, abstractmethod

""" Class for logger base(interface)

"""


class Ilogger(metaclass=ABCMeta):

    @abstractmethod
    def debug(self, message: str, stack_info=False):
        raise NotImplementedError()

    @abstractmethod
    def info(self, message: str, stack_info=False):
        raise NotImplementedError()

    @abstractmethod
    def warning(self, message: str, stack_info=False):
        raise NotImplementedError()

    @abstractmethod
    def error(self, message: str, stack_info=True):
        raise NotImplementedError()

    @abstractmethod
    def critical(self, message: str, stack_info=True):
        raise NotImplementedError()

    @abstractmethod
    def trailReq(self, method: str, endpoint: str, user: str, message: str):
        raise NotImplementedError()

    @abstractmethod
    def trailRes(self, status: int, message: str):
        raise NotImplementedError()

    @abstractmethod
    def eventPub(self, subject: str):
        raise NotImplementedError()

    @abstractmethod
    def eventSub(self, subject: str, consumer: str):
        raise NotImplementedError()

    def _appLogToJson(self, message, stacktrace) -> str:
        """Converting and formatting application log data into a JSON string for output."""
        applog = {
            "file": inspect.stack()[2].filename,
            "line": inspect.stack()[2].lineno,
            "message": message,
        }
        if stacktrace != "":
            applog["stacktrace"] = stacktrace

        return json.dumps(applog, separators=(",", ":"), ensure_ascii=False)

    def _getStacktrace(self, stack_info) -> str:
        """If the stack_info(bool) function is called with True as an argument, retrieve stack trace information and return it as a string."""
        stacktrace = ""
        if stack_info == True:
            stacktrace = traceback.extract_stack().format()

        return stacktrace

    def _trailReqLogToJson(self, method, endpoint, user, message) -> str:
        """To return a processed JSON string of data for use as an audit log for request."""

        traillog = {
            "method": method,
            "endpoint": endpoint,
            "user": user,
            "message": message,
        }

        return json.dumps(traillog, separators=(",", ":"), ensure_ascii=False)

    def _trailResLogToJson(self, status, message) -> str:
        """To return a processed JSON string of data for use as an audit log for response."""
        traillog = {
            "status": status,
            "message": message,
        }

        return json.dumps(traillog, separators=(",", ":"), ensure_ascii=False)

    def _eventPubLogToJson(self, subject) -> str:
        """To return a processed JSON string of data for use as an audit log for publish."""
        eventlog = {
            "subject": subject,
        }

        return json.dumps(eventlog, separators=(",", ":"), ensure_ascii=False)

    def _eventSubLogToJson(self, subject, consumer) -> str:
        """To return a processed JSON string of data for use as an audit log for subscribe."""
        eventlog = {
            "subject": subject,
            "consumer": consumer,
        }

        return json.dumps(eventlog, separators=(",", ":"), ensure_ascii=False)
