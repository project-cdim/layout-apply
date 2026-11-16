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
"""query"""

# Data for listing and deletion confirmation
get_list_insert_sql = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    ('000000001a', 'IN_PROGRESS', '{\"procedures\": \"pre_test\"}', null, null, '2023/10/02 00:00:00', null, null, null, null, null, null),
    ('000000002b', 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"procedures\": \"test\"}', '2023/10/01 23:59:59', '2023/10/02 12:23:58', '2023/10/02 12:00:00', TRUE, null, null, null),
    ('000000003c', 'COMPLETED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:00', '2023/10/02 12:23:59', null, null, null, null, null),
    ('000000004d', 'FAILED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:01', '2023/10/02 12:24:00', null, null, null, null, null),
    ('000000005e', 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"procedures\": \"test\"}', '2023/10/02 00:00:02', '2023/10/02 12:24:01', '2023/10/02 12:00:00', FALSE, null, null, null),
    ('000000006f', 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"procedures\": \"test\"}', '2023/10/03 00:00:00', '2023/10/04 12:23:59', '2023/10/03 12:00:00', TRUE, null, null, null),
    ('000000007a', 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"procedures\": \"test\"}', '2023/10/01 23:59:59', '2023/10/02 12:23:58', '2023/10/02 12:00:00', TRUE, null, null, null),
    ('000000008b', 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"procedures\": \"test\"}', '2023/10/01 23:59:59', '2023/10/02 12:23:58', '2023/10/02 12:00:00', FALSE, null, null, null),
    ('000000009c', 'SUSPENDED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:01', null, null, null, '{"procedures": "pre_test"}', '2024/01/02 12:23:00', null)
"""
get_list_insert_sql_06f_rb = """
    INSERT into rollbackstatus (
        applyid, status, procedures, result, startedat, endedat, canceledat, resumeprocedures, suspendedat, resumedat
    ) VALUES
    ('000000006f', 'COMPLETED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '2023/10/03 12:20:00', '2023/10/04 12:23:59', null, '{\"procedures\": \"pre_test\"}', '2024/10/04 12:00:00', '2024/10/04 12:23:00');
"""

# Data for listing and deletion confirmation
get_list_insert_sql_1 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'IN_PROGRESS', '{\"procedures\": \"pre_test\"}', null, null, '2023/10/02 00:00:00', null, null, null, null, null, null);
"""
get_list_insert_sql_r_1 = """
    INSERT into rollbackstatus (
        applyid, status, procedures, result, startedat, endedat, canceledat, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'IN_PROGRESS', '{\"procedures\": \"pre_test\"}', null, '2023/10/02 00:00:00', null, null, null, null, null);
"""
get_list_insert_sql_2 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"procedures\": \"test\"}', '2023/10/01 23:59:59', '2023/10/02 12:23:58', '2023/10/02 12:00:00', TRUE, null, null, null);
"""
get_list_insert_sql_r_2 = """
    INSERT INTO rollbackstatus (status, procedures, startedAt, applyid) VALUES(%s,%s,%s,%s)
"""  # use params: vars=[Result.IN_PROGRESS, "[]", get_str_now(), applyid]
get_list_insert_sql_r_2_without_startedat = """
    INSERT into rollbackstatus (
        applyid, status, procedures, result, startedat, endedat, canceledat, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'IN_PROGRESS', '{\"procedures\": \"pre_test\"}', null, null, null, null, null, null, null);
"""

get_list_insert_sql_3 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'COMPLETED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:00', '2023/10/02 12:23:59', null, null, null, null, null);
"""
get_list_insert_sql_4 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'FAILED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:01', '2023/10/02 12:24:00', null, null, null, null, null);
"""
get_list_insert_sql_5 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"procedures\": \"test\"}', '2023/10/02 00:00:02', '2023/10/02 12:24:01', '2023/10/02 12:00:00', FALSE, null, null, null);
"""
get_list_insert_sql_6 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"procedures\": \"test\"}', '2023/10/03 00:00:00', '2023/10/04 12:23:59', '2023/10/03 12:00:00', TRUE, null, null, null);
"""
get_list_insert_sql_11 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"procedures\": \"test\"}', '2023/10/03 00:00:00', null, '2023/10/03 12:00:00', TRUE, null, null, null);
"""
get_list_insert_sql_10 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'FAILED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/05 00:00:01', '2023/10/05 12:24:00', '2023/10/05 12:00:00', TRUE, null, null, null);
"""
get_list_insert_sql_r_6 = """
    INSERT into rollbackstatus (
        applyid, status, procedures, result, startedat, endedat, canceledat, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'COMPLETED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '2023/10/03 12:20:00', '2023/10/04 12:23:59', null, null, null, null);
"""
get_list_insert_sql_r_6_failed = """
    INSERT into rollbackstatus (
        applyid, status, procedures, result, startedat, endedat, canceledat, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'FAILED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '2023/10/03 12:20:00', '2023/10/04 12:23:59', null, null, null, null);
"""
get_list_insert_sql_r_6_suspended = """
    INSERT into rollbackstatus (
        applyid, status, procedures, result, startedat, endedat, canceledat, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'SUSPENDED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '2023/10/03 12:20:00', null, null, '{\"procedures\": \"pre_test\"}', '2023/10/04 12:23:59', null);
"""
get_list_insert_sql_7 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"procedures\": \"test\"}', '2023/10/01 23:59:59', null, '2023/10/02 12:00:00', TRUE, null, null, null);
"""
get_list_insert_sql_8 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"procedures\": \"test\"}', '2023/10/01 23:59:59', null, '2023/10/02 12:00:00', FALSE, null, null, null);
"""
get_list_insert_sql_9 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'SUSPENDED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:01', null, null, null, '{"procedures": "pre_test"}', '2024/01/02 12:23:00', null);
"""
# Data for verifying the fields option
get_fields_insert_sql_1 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s,'COMPLETED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00','2023/10/02 12:23:59',null,null,null,null,null,null,null,null);
"""
get_fields_insert_sql_2 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s,'IN_PROGRESS','{"procedures": "pre_test"}',null,null,'2023/10/02 00:00:00',null,null,null,null,null,null,null,null,null);
"""
get_fields_insert_sql_3 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s,'CANCELING','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,'2023/10/02 12:23:59',null,null,null,null,null,null,null);
"""
get_fields_insert_sql_4 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s,'FAILED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00','2023/10/02 12:23:59',null,null,null,null,null,null,null,null);
"""
get_fields_insert_sql_5 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s,'CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','{"procedures": "pre_test"}','2023/10/02 00:00:00' ,'2023/10/02 12:23:59','2023/10/02 12:00:00',FALSE,null,null,null,null,null,null);
"""
get_fields_insert_sql_6 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s,'CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','{"procedures": "test"}','2023/10/02 00:00:00' ,'2023/10/02 12:23:59','2023/10/02 12:00:00',TRUE,null,null,null,null,null,null);
"""
get_fields_insert_sql_r_6 = """
    INSERT into rollbackstatus (applyid, status, procedures, result, startedat, endedat, canceledat, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    )
    VALUES
    (%s,'COMPLETED','{"procedures": "test"}','[{"test": "test"}, {"test": "test"}]','2023/10/02 12:20:00','2023/10/02 12:23:59',null,null,null,null,null,null,null);
"""
get_fields_insert_sql_7 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s, 'SUSPENDED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:01', null, null, null, '{"procedures": "pre_test"}', null, null, null, '2024/01/02 12:23:00', null);
"""
# Data for status check after resumption
insert_resumed_get_target_sql_1 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s,'IN_PROGRESS','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,'{"procedures": "pre_test"}','2023/10/02 12:23:59','2023/10/03 12:23:59')
"""
insert_resumed_get_target_sql_2 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s,'CANCELING','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,'2023/10/02 00:00:01',TRUE,'{"procedures": "pre_test"}','2023/10/02 12:23:59','2023/10/03 12:23:59')
"""
insert_resumed_get_target_sql_3 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s,'COMPLETED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00','2023/10/02 12:23:59',null,null,'{"procedures": "pre_test"}','2023/10/02 12:23:59','2023/10/03 12:23:59')
"""
insert_resumed_get_target_sql_4 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s,'CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','{"procedures": "pre_test"}','2023/10/02 00:00:00','2023/10/02 01:00:00','2023/10/02 00:30:00',TRUE,'{"procedures": "pre_test"}',null,null,null,'2023/10/02 00:50:00',null);
"""
insert_resumed_get_target_sql_r_4 = """
    INSERT into rollbackstatus (applyid, status, procedures, result, startedat, endedat, canceledat,resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s,'SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','2023/10/02 00:40:00',null,null,'[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',null,null,null,null,null);
"""
insert_resumed_get_target_sql_5 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s,'IN_PROGRESS','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,'{"procedures": "pre_test"}','2023/10/02 12:23:59','2023/10/03 12:23:59')
"""
# Generic data
insert_status_suspended_sql = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s,'SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,'{"procedures": [{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]}',null,null,null,'2023/10/02 12:23:59',null);
"""

insert_status_completed_sql = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s,'COMPLETED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00','2023/10/02 12:23:59',null,null,null,null,null,null,null,null);
"""
insert_status_canceled_sql = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s,'CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','{"procedures": "test"}','2023/10/02 00:00:00' ,'2023/10/02 12:23:59','2023/10/02 12:00:00',FALSE,null,null,null,null,null,null);
"""
# Resumption confirmation data
insert_resumed_target_sql_1 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s,'SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,'[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',null,null,null,'2023/10/02 12:23:59',null);
"""
delete_for_applyid_sql = """
    DELETE FROM applystatus WHERE applyid = %s
"""
delete_for_applyid_r_sql = """
    DELETE FROM rollbackstatus WHERE applyid = %s
"""

insert_delete_target_sql_1 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'IN_PROGRESS', '{"procedures": "pre_test"}', null, null, '2023/10/02 00:00:00', null, null, null, null, null, null)
"""
insert_delete_target_sql_2 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"test\": \"test\"}', '2023/10/01 23:59:59', '2023/10/02 12:23:58', '2023/10/02 12:00:00', TRUE, null, null, null)
"""
insert_delete_target_sql_3 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'COMPLETED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:00', '2023/10/02 12:23:59', null, null, null, null, null)
"""
insert_delete_target_sql_4 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'FAILED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:01', '2023/10/02 12:24:00', null, null, null, null, null)
"""
insert_delete_target_sql_5 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"procedures\": \"test\"}', '2023/10/02 00:00:02', '2023/10/02 12:24:01', '2023/10/02 12:00:00', FALSE, null, null, null)
"""
insert_delete_target_sql_6 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"procedures\": \"test\"}', '2023/10/03 00:00:00', '2023/10/04 12:23:59', '2023/10/03 12:00:00', TRUE, null, null, null)
"""
insert_delete_target_sql_7 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'SUSPENDED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:01', null, null, null, '{"procedures": "pre_test"}', '2024/01/02 12:23:00', null)
"""
insert_delete_target_sql_8 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"procedures\": \"test\"}', '2023/10/03 00:00:00', '2023/10/04 12:23:59', '2023/10/03 12:00:00', TRUE, null, null, null)
"""
insert_delete_target_sql_r_8 = """
    INSERT into rollbackstatus (
        applyid, status, procedures, result, startedat, endedat, canceledat, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'IN_PROGRESS', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '2023/10/03 12:20:00', null, null, null, null, null)
"""
insert_delete_target_sql_9 = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"procedures\": \"pre_test\"}', '2023/10/03 00:00:00', '2023/10/04 12:23:59', '2023/10/03 12:00:00', TRUE, '{\"procedures\": \"pre_test\"}', null, null)
"""
insert_delete_target_sql_r_9 = """
    INSERT into rollbackstatus (
        applyid, status, procedures, result, startedat, endedat, canceledat, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'SUSPENDED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '2023/10/03 12:20:00', null, null, '{\"procedures\": \"pre_test\"}', '2023/10/04 12:24:00', null)
"""
# Data for get valid data
get_valid_insert_sql = """
    INSERT into applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback, resumeprocedures, suspendedat, resumedat
    ) VALUES
    (%s, 'COMPLETED', '[]', '[]', null, '2023/10/02 00:00:00', '2023/10/02 12:23:59', null, null, null, null, null);
"""

# Data for get api complex scenarios
get_applystatus_insert_sql_cancel_with_rollback_completed = """
    INSERT INTO applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback
    ) VALUES
    (%s, 'CANCELED', '{"procedures": "pre_test"}', '[{"test": "test"}, {"test": "test"}]',
    '{"procedures": "rollback_test"}', '2023-10-03 00:00:00', '2023-10-04 12:23:59', '2023-10-03 12:00:00', TRUE)
"""

get_applystatus_insert_sql_rollback_completed_for_cancel = """
    INSERT INTO rollbackstatus (
        applyid, status, procedures, result, startedat, endedat
    ) VALUES
    (%s, 'COMPLETED', '{"procedures": "rollback_test"}', '[{"test": "rollback_result"}]',
    '2023-10-03 12:20:00', '2023-10-04 12:23:59')
"""

get_applystatus_insert_sql_multiple_resume_with_rollback = """
    INSERT INTO applystatus (
        applyid, status, procedures, result, rollbackprocedures,
        startedat, endedat, canceledat, executerollback, resumeprocedures, resumedat, suspendedat
    ) VALUES
    (%s, 'CANCELED', '{"procedures": "apply_test"}',
    '[{"operationID": 1, "status": "FAILED", "startedAt": "2023-10-11T00:00:00Z", "endedAt": "2023-10-11T09:00:00Z"},
    {"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-11T10:00:00Z", "endedAt": "2023-10-11T14:50:00Z"},
    {"operationID": 2, "status": "FAILED", "startedAt": "2023-10-11T14:50:00Z", "endedAt": "2023-10-11T15:00:00Z"}]',
    '{"procedures": "rollback_test"}', '2023-10-11 00:00:00', '2023-10-11 16:00:00', '2023-10-11 15:00:00', TRUE,
    '[{"resume": 1, "procedure": "retry_after_suspend"}]', '2023-10-11 10:00:00', '2023-10-11 09:00:00')
"""

get_applystatus_insert_sql_rollback_for_multiple_resume = """
    INSERT INTO rollbackstatus (
        applyid, status, procedures, result, startedat, endedat, resumeprocedures, resumedat, suspendedat
    ) VALUES
    (%s, 'COMPLETED', '{"procedures": "rollback_test"}',
    '[{"operationID": 2, "status": "FAILED", "startedAt": "2023-10-11T15:10:00Z", "endedAt": "2023-10-11T15:30:00Z"},
    {"operationID": 2, "status": "COMPLETED", "startedAt": "2023-10-11T15:40:00Z", "endedAt": "2023-10-11T15:50:00Z"},
    {"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-11T15:50:00Z", "endedAt": "2023-10-11T16:00:00Z"}]',
    '2023-10-11 15:10:00', '2023-10-11 16:00:00', '[{"resume": 1, "procedure": "retry_rollback"}]',
    '2023-10-11 15:40:00', '2023-10-11 15:30:00')
"""

get_applystatus_insert_sql_rollback_suspended_and_resumed = """
    INSERT INTO applystatus (
        applyid, status, procedures, result, rollbackprocedures, startedat, endedat, canceledat, executerollback
    ) VALUES
    (%s, 'CANCELED', '{"procedures": "apply_test"}',
    '[{"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-15T10:00:00Z", "endedAt": "2023-10-15T11:00:00Z"},
    {"operationID": 2, "status": "COMPLETED", "startedAt": "2023-10-15T11:00:00Z", "endedAt": "2023-10-15T12:00:00Z"}]',
    '{"procedures": "rollback_test"}', '2023-10-15 10:00:00', '2023-10-15 16:00:00', '2023-10-15 12:30:00', TRUE)
"""

get_applystatus_insert_sql_rollback_for_suspended_and_resumed = """
    INSERT INTO rollbackstatus (
        applyid, status, procedures, result, startedat, endedat, resumeprocedures, resumedat, suspendedat
    ) VALUES
    (%s, 'COMPLETED', '{"procedures": "rollback_test"}',
    '[{"operationID": 2, "status": "FAILED", "startedAt": "2023-10-15T13:00:00Z", "endedAt": "2023-10-15T14:00:00Z"},
    {"operationID": 2, "status": "COMPLETED", "startedAt": "2023-10-15T15:00:00Z", "endedAt": "2023-10-15T15:30:00Z"},
    {"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-15T15:30:00Z", "endedAt": "2023-10-15T16:00:00Z"}]',
    '2023-10-15 13:00:00', '2023-10-15 16:00:00', '{"procedures": "retry_rollback_after_suspend"}',
    '2023-10-15 15:00:00', '2023-10-15 14:00:00')
"""

get_applystatus_insert_sql_resumed_then_canceled_with_rollback = """
    INSERT INTO applystatus (
        applyid, status, procedures, result, rollbackprocedures,
        startedat, endedat, canceledat, executerollback, resumeprocedures, resumedat, suspendedat
    ) VALUES
    (%s, 'CANCELED', '{"procedures": "apply_test"}',
    '[{"operationID": 1, "status": "FAILED", "startedAt": "2023-10-20T10:00:00Z", "endedAt": "2023-10-20T11:00:00Z"},
    {"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-20T14:00:00Z", "endedAt": "2023-10-20T15:00:00Z"},
    {"operationID": 2, "status": "CANCELED", "startedAt": "2023-10-20T15:00:00Z", "endedAt": "2023-10-20T15:30:00Z"}]',
    '{"procedures": "rollback_test"}', '2023-10-20 10:00:00', '2023-10-20 17:00:00', '2023-10-20 15:30:00', TRUE,
    '{"procedures": "resume_after_suspend"}', '2023-10-20 14:00:00', '2023-10-20 11:00:00')
"""

get_applystatus_insert_sql_rollback_for_resumed_then_canceled = """
    INSERT INTO rollbackstatus (
        applyid, status, procedures, result, startedat, endedat
    ) VALUES
    (%s, 'COMPLETED', '{"procedures": "rollback_test"}',
    '[{"operationID": 2, "status": "COMPLETED", "startedAt": "2023-10-20T15:40:00Z", "endedAt": "2023-10-20T16:00:00Z"},
    {"operationID": 1, "status": "COMPLETED", "startedAt": "2023-10-20T16:00:00Z", "endedAt": "2023-10-20T17:00:00Z"}]',
    '2023-10-20 15:40:00', '2023-10-20 17:00:00')
"""
