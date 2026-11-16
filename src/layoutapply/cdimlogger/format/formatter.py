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
import time

from .. import common

""" Class for original logging format.
Override logging.Formatter.formatTime().

"""


class Formatter(logging.Formatter):
    default_time_format = common.LOG_TIME_FORMAT
    default_msec_format = common.LOG_MSEC_FORMAT

    def formatTime(self, record, datefmt=None):
        """Format the date and time to the YYYY/MM/DD mm:dd:ss.xxxxxx format and return as a string.
        Args:
            record(LogRecord): LogRecord.
            datefmt(str)     : date format. (default:None)

        Returns:
            str: Date and Time.(YYYY/MM/DD mm:dd:ss.xxxxxx)
        """
        ct = self.converter(record.created)
        now = time.time()
        mlsec = repr(now).split(".")[1][:3]
        mcsec = repr(now).split(".")[1][-3:]
        if datefmt:
            s = time.strftime(datefmt.format(mcsec), ct)
        else:
            s = time.strftime(self.default_time_format.format(mlsec, mcsec), ct)
            if self.default_msec_format:
                s = self.default_msec_format % (s, record.msecs)
        return s
