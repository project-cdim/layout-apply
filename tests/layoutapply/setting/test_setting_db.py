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
"""Test for setting database"""

import copy

import pytest
import requests
from requests.exceptions import ConnectionError, RequestException, Timeout

from layoutapply.custom_exceptions import SecretInfoGetException, SettingFileLoadException
from layoutapply.setting import LayoutApplyConfig
from tests.layoutapply.conftest import BASE_CONFIG, LOG_BASE_CONFIG


class TestLayoutApplyConfigDatabase:
    """Tests for db config, secret retrieval, and db update timing."""

    @pytest.mark.parametrize(
        "update_confg",
        [
            # host is valid
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": "user01",
                    "password": "P@ssw0rd",
                    "host": "127.0.0.1",
                    "port": 5435,
                },
            },
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": "user01",
                    "password": "P@ssw0rd",
                    "host": "localhost",
                    "port": 5435,
                },
            },
            # port is valid
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": "user01",
                    "password": "P@ssw0rd",
                    "host": "localhost",
                    "port": 9999,
                },
            },
            # empty
            {},
        ],
    )
    def test_setting_success_when_db_config_normal(
        self, mocker, update_confg, docker_services  # pylint: disable=unused-argument
    ):
        """Test setting success when DB config is normal."""
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["db"]
        config = {**base_config, **update_confg}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        layout_apply_db_config = LayoutApplyConfig().db_config
        if "db" in update_confg:
            assert layout_apply_db_config == update_confg["db"]
        else:
            assert layout_apply_db_config == {}

    @pytest.mark.parametrize(
        "update_confg",
        [
            # dbname is type mismatch
            {
                "db": {
                    "dbname": 0,
                    "user": "user01",
                    "password": "P@ssw0rd",
                    "host": "127.0.0.1",
                    "port": 5435,
                },
            },
            # user is type mismatch
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": 0,
                    "password": "P@ssw0rd",
                    "host": "127.0.0.1",
                    "port": 5435,
                },
            },
            # password is type mismatch
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": "user01",
                    "password": 0,
                    "host": "127.0.0.1",
                    "port": 5435,
                },
            },
            # host is type mismatch
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": "user01",
                    "password": "P@ssw0rd",
                    "host": 0,
                    "port": 5435,
                },
            },
            # port is type mismatch
            {
                "db": {
                    "dbname": "layoutapply",
                    "user": "user01",
                    "password": "P@ssw0rd",
                    "host": "127.0.0.1",
                    "port": "5435",
                },
            },
            # empty
            #            {},
        ],
    )
    def test_setting_failure_when_invalid_db_config(self, mocker, update_confg):
        """Test setting failure when DB config is invalid."""
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["db"]
        config = {**base_config, **update_confg}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        with pytest.raises(SettingFileLoadException):
            assert LayoutApplyConfig().db_config is not None

    def test_setting_db_update_timing_when_layout_apply_has_time_and_count(self, mocker):
        """Test setting DB update timing when layout apply has both time and count."""
        base_config = copy.deepcopy(BASE_CONFIG)
        base_config["layout_apply"]["db_update_timing"] = {"time": 7, "count": 12}
        mocker.patch("yaml.safe_load").side_effect = [base_config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")

        timing = LayoutApplyConfig().db_update_timing
        assert timing["time"] == 7
        assert timing["count"] == 12

    def test_setting_db_update_timing_defaults_when_layout_apply_has_no_time_and_count(self, mocker):
        """Test setting DB update timing defaults when layout apply has no time and count."""
        base_config = copy.deepcopy(BASE_CONFIG)
        mocker.patch("yaml.safe_load").side_effect = [base_config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")

        timing = LayoutApplyConfig().db_update_timing
        assert timing["time"] == 3
        assert timing["count"] == 10

    @pytest.mark.parametrize(
        "db_timing",
        [
            {"time": 0, "count": 10},
            {"time": 3, "count": 0},
            {"time": 1, "count": 101},
            {"time": 61, "count": 1},
            {"time": -1, "count": 10},
            {"time": 3, "count": -1},
            {"time": "10", "count": 10},
            {"time": 3, "count": [10]},
        ],
    )
    def test_setting_failure_when_invalid_layout_apply_db_update_timing(self, mocker, db_timing):
        """Test setting failure when layout apply DB update timing is invalid."""
        base_config = copy.deepcopy(BASE_CONFIG)
        base_config["layout_apply"]["db_update_timing"] = {
            "time": db_timing["time"],
            "count": db_timing["count"],
        }
        mocker.patch("yaml.safe_load").side_effect = [base_config, LOG_BASE_CONFIG]

        with pytest.raises(SettingFileLoadException):
            assert LayoutApplyConfig().db_update_timing is not None

    @pytest.mark.parametrize(
        "db_timing",
        [
            {"time": 1, "count": 10},  # time lower boundary
            {"time": 60, "count": 10},  # time upper boundary
            {"time": 3, "count": 1},  # count lower boundary
            {"time": 3, "count": 100},  # count upper boundary
        ],
    )
    def test_setting_success_db_update_timing_boundaries(self, mocker, db_timing):
        """Test setting success when layout apply DB update timing is at boundary values."""
        base_config = copy.deepcopy(BASE_CONFIG)
        base_config["layout_apply"]["db_update_timing"] = {
            "time": db_timing["time"],
            "count": db_timing["count"],
        }
        mocker.patch("yaml.safe_load").side_effect = [base_config, LOG_BASE_CONFIG]

        timing = LayoutApplyConfig().db_update_timing
        assert timing["time"] == db_timing["time"]
        assert timing["count"] == db_timing["count"]

    def test_setting_failure_when_port_that_retrieved_from_secret_store_cannot_be_converted_int(self, mocker):
        """Test setting failure when the port retrieved from the secret store cannot be converted to an integer."""
        update_config = {
            "db": {
                "dbname": "ApplyStatusDB",
                "password": "P@ssword",
                "user": "user01",
                "host": "0.0.0.0",
            }
        }
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["db"]
        config = {**base_config, **update_config}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mock_connection = mocker.MagicMock()
        mock_connection.content = b'{"port": "XXXX"}'
        mocker.patch("requests.get", return_value=mock_connection)

        with pytest.raises(SecretInfoGetException):
            assert LayoutApplyConfig().db_config is not None

    def test_setting_failure_when_missing_required_items_from_secret_store(self, mocker):
        """Test setting failure when required items are missing from the secret store."""
        update_config = {
            "db": {
                "dbname": "ApplyStatusDB",
                "password": "P@ssword",
                "user": "user01",
                "host": "0.0.0.0",
            }
        }
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["db"]
        config = {**base_config, **update_config}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mock_connection = mocker.MagicMock()
        mock_connection.content = b"{}"
        mocker.patch("requests.get", return_value=mock_connection)

        with pytest.raises(SecretInfoGetException):
            assert LayoutApplyConfig().db_config is not None

    @pytest.mark.parametrize("exc", [{RequestException()}, {Timeout()}, {ConnectionError()}, {Exception()}])
    def test_setting_failure_when_failed_to_get_item_from_secret_store(self, mocker, exc):
        """Test setting failure when failed to get an item from the secret store."""
        update_config = {
            "db": {
                "dbname": "ApplyStatusDB",
                "user": "user01",
                "host": "0.0.0.0",
                "port": 5432,
            }
        }
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["db"]
        config = {**base_config, **update_config}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mocker.patch("requests.get")
        requests.get.side_effect = exc

        with pytest.raises(SecretInfoGetException):
            assert LayoutApplyConfig().db_config is not None

    def test_setting_success_when_db_items_are_merged_from_secret_store(self, mocker):
        """Test that missing DB items are merged from secret store values."""
        update_config = {
            "db": {
                "dbname": "ApplyStatusDB",
                "host": "0.0.0.0",
            }
        }
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["db"]
        config = {**base_config, **update_config}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mock_connection = mocker.MagicMock()
        mock_connection.content = b'{"user": "user01", "password": "P@ssword", "port": "5435"}'
        mocker.patch("requests.get", return_value=mock_connection)

        db_conf = LayoutApplyConfig().db_config

        assert db_conf["dbname"] == "ApplyStatusDB"
        assert db_conf["host"] == "0.0.0.0"
        assert db_conf["user"] == "user01"
        assert db_conf["password"] == "P@ssword"
        assert db_conf["port"] == 5435

    def test_setting_success_when_port_from_secret_store_is_converted_to_int(self, mocker):
        """Test that a string port from secret store is converted to int."""
        update_config = {
            "db": {
                "dbname": "ApplyStatusDB",
                "user": "user01",
                "password": "P@ssword",
                "host": "0.0.0.0",
            }
        }
        base_config = copy.deepcopy(BASE_CONFIG)
        del base_config["db"]
        config = {**base_config, **update_config}
        mocker.patch("yaml.safe_load").side_effect = [config, LOG_BASE_CONFIG]
        mock_connection = mocker.MagicMock()
        mock_connection.content = b'{"port": "5435"}'
        mocker.patch("requests.get", return_value=mock_connection)

        db_conf = LayoutApplyConfig().db_config

        assert db_conf["port"] == 5435
        assert isinstance(db_conf["port"], int)
