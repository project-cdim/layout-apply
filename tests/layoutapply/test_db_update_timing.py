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
"""Tests for DB update timing counter."""

import pytest

from layoutapply.counter import DBUpdateCounter


class _DummyConfig:
    def __init__(self, time, count):
        self._timing = {"time": time, "count": count}

    @property
    def db_update_timing(self):
        return self._timing


def test_db_update_counter_consume_always_true_when_time_and_count_are_zero():
    counter = DBUpdateCounter(_DummyConfig(time=0, count=0))

    assert counter.consume_if_due() is True
    assert counter.consume_if_due() is True


def test_db_update_counter_get_wait_timeout_returns_none_when_time_is_disabled():
    counter = DBUpdateCounter(_DummyConfig(time=0, count=3))

    assert counter.get_wait_timeout_sec() is None


def test_db_update_counter_consume_by_completed_request_count(mocker):
    mocker.patch("layoutapply.counter.monotonic", side_effect=[100.0, 100.0, 100.0, 100.0])
    counter = DBUpdateCounter(_DummyConfig(time=0, count=3))

    counter.record_completed()
    assert counter.consume_if_due() is False

    counter.record_completed()
    assert counter.consume_if_due() is False

    counter.record_completed()
    assert counter.consume_if_due() is True


def test_db_update_counter_timeout_and_consume_by_time_seconds(mocker):
    mocker.patch(
        "layoutapply.counter.monotonic",
        side_effect=[100.0, 100.0, 101.0, 102.0, 103.0, 104.0],
    )
    counter = DBUpdateCounter(_DummyConfig(time=2, count=0))

    assert counter.get_wait_timeout_sec() == 2
    assert counter.consume_if_due() is False
    assert counter.consume_if_due() is True
    assert counter.consume_if_due() is False
    assert counter.consume_if_due() is True


def test_db_update_counter_resets_completed_count_after_consume(mocker):
    mocker.patch("layoutapply.counter.monotonic", side_effect=[100.0, 100.0, 100.0, 100.0, 100.0])
    counter = DBUpdateCounter(_DummyConfig(time=0, count=2))

    counter.record_completed(2)
    assert counter.consume_if_due() is True

    counter.record_completed(1)
    assert counter.consume_if_due() is False


@pytest.mark.parametrize(
    "elapsed,completed_count,expected",
    [
        (1.0, 1, False),
        (3.0, 1, True),
        (1.0, 2, True),
        (3.0, 2, True),
    ],
)
def test_db_update_counter_condition_matrix_for_time_and_count(mocker, elapsed, completed_count, expected):
    base_time = 100.0
    mocker.patch("layoutapply.counter.monotonic", side_effect=[base_time, base_time + elapsed])
    counter = DBUpdateCounter(_DummyConfig(time=2, count=2))

    counter.record_completed(completed_count)
    assert counter.consume_if_due() is expected
