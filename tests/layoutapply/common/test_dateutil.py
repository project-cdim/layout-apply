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
"""Common Time Package Test"""

import re
from datetime import datetime

from layoutapply.common.dateutil import get_now, get_str_now


class TestDateUtil:
    """Test for Common Time Package"""

    def test_get_str_now_return_the_date_in_the_specified_format(self):
        # arrange

        # act
        utc_now_str = get_str_now()

        # assert
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", utc_now_str) is not None

    def test_get_now_return_the_datetime_object(self):
        # arrange

        # act
        utc_now = get_now()

        # assert
        assert isinstance(utc_now, datetime)
