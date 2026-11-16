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
"""Schedule intermediate DB updates by time and completed count."""

from time import monotonic

from layoutapply.setting import LayoutApplyConfig


class DBUpdateCounter:
    """Control intermediate DB updates by time(seconds) and completed count."""

    def __init__(self, config: LayoutApplyConfig):
        """constructor

        Args:
            config (LayoutApplyConfig): Configuration object.
        """
        timing = config.db_update_timing
        self.time_sec = max(0, int(timing.get("time", 0) or 0))
        self.count_limit = max(0, int(timing.get("count", timing.get("number", 0)) or 0))
        # Cache whether each trigger is active to avoid repeating numeric checks.
        self.time_enabled = self.time_sec > 0
        # When count trigger is disabled, completion count should not trigger updates.
        self.count_enabled = self.count_limit > 0
        self.start_at = monotonic()
        self.last_update_at = self.start_at
        self.completed_count = 0

    def get_wait_timeout_sec(self):
        """Return timeout until next time-based update, or None when disabled."""
        if not self.time_enabled:
            # Defensive fallback: even if validation should prevent non-positive values,
            # keep time-based waiting disabled when the time trigger is not enabled.
            return None  # pragma: no cover
        elapsed = monotonic() - self.last_update_at
        return max(self.time_sec - elapsed, 0)

    def record_completed(self, count: int = 1) -> None:
        """Record completed request count since last DB update."""
        self.completed_count += count

    def consume_if_due(self) -> bool:
        """Return True when DB should be updated now, and consume schedule."""
        if self.time_enabled or self.count_enabled:
            now = monotonic()
            time_due = self.time_enabled and (now - self.last_update_at) >= self.time_sec
            count_due = self.count_enabled and self.completed_count >= self.count_limit
            if time_due or count_due:
                self.last_update_at = now
                self.completed_count = 0
                return True
            return False
        return True
