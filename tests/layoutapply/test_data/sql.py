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
"""query"""

# Data for listing and deletion confirmation
get_list_insert_sql = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    ('000000001a', 'IN_PROGRESS', '{\"procedures\": \"pre_test\"}', null, null, '2023/10/02 00:00:00', null, null, null, null, null, null, null, null, null, null, null),
    ('000000002b', 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"test\": \"test\"}', '2023/10/01 23:59:59', '2023/10/02 12:23:58', '2023/10/02 12:00:00', TRUE, null, null, null, null, null, null, null, null),
    ('000000003c', 'COMPLETED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:00', '2023/10/02 12:23:59', null, null, null, null, null, null, null, null, null, null),
    ('000000004d', 'FAILED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:01', '2023/10/02 12:24:00', null, null, null, null, null, null, null, null, null, null),
    ('000000005e', 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"test\": \"test\"}', '2023/10/02 00:00:02', '2023/10/02 12:24:01', '2023/10/02 12:00:00', FALSE, null, null, null, null, null, null, null, null),
    ('000000006f', 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"test\": \"test\"}', '2023/10/03 00:00:00', '2023/10/04 12:23:59', '2023/10/03 12:00:00', TRUE, 'COMPLETED', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '2023/10/03 12:20:00', '2023/10/04 12:23:59', null, null, null, null),
    ('000000007a', 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"test\": \"test\"}', '2023/10/01 23:59:59', '2023/10/02 12:23:58', '2023/10/02 12:00:00', TRUE, null, null, '2023/10/02 12:20:00', null, null, null, null, null),
    ('000000008b', 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"test\": \"test\"}', '2023/10/01 23:59:59', '2023/10/02 12:23:58', '2023/10/02 12:00:00', FALSE, null, null, null, null, null, null, null, null),
    ('000000009c', 'SUSPENDED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:01', null, null, null, null, null, null, null, '{"test": "pre_test"}', null, '2024/01/02 12:23:00', null)
"""

# Data for listing and deletion confirmation
get_list_insert_sql_1 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'IN_PROGRESS', '{\"procedures\": \"pre_test\"}', null, null, '2023/10/02 00:00:00', null, null, null, null, null, null, null, null, null, null, null);
"""
get_list_insert_sql_2 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"test\": \"test\"}', '2023/10/01 23:59:59', '2023/10/02 12:23:58', '2023/10/02 12:00:00', TRUE, null, null, null, null, null, null, null, null);
"""
get_list_insert_sql_3 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'COMPLETED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:00', '2023/10/02 12:23:59', null, null, null, null, null, null, null, null, null, null);
"""
get_list_insert_sql_4 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'FAILED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:01', '2023/10/02 12:24:00', null, null, null, null, null, null, null, null, null, null);
"""
get_list_insert_sql_5 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"test\": \"test\"}', '2023/10/02 00:00:02', '2023/10/02 12:24:01', '2023/10/02 12:00:00', FALSE, null, null, null, null, null, null, null, null);
"""
get_list_insert_sql_6 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"test\": \"test\"}', '2023/10/03 00:00:00', '2023/10/04 12:23:59', '2023/10/03 12:00:00', TRUE, 'COMPLETED', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '2023/10/03 12:20:00', '2023/10/04 12:23:59', null, null, null, null);
"""
get_list_insert_sql_7 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"test\": \"test\"}', '2023/10/01 23:59:59', '2023/10/02 12:23:58', '2023/10/02 12:00:00', TRUE, null, null, '2023/10/02 12:20:00', null, null, null, null, null);
"""
get_list_insert_sql_8 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"test\": \"test\"}', '2023/10/01 23:59:59', '2023/10/02 12:23:58', '2023/10/02 12:00:00', FALSE, null, null, null, null, null, null, null, null);
"""
get_list_insert_sql_9 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'SUSPENDED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:01', null, null, null, null, null, null, null, '{"test": "pre_test"}', null, '2024/01/02 12:23:00', null);
"""
# Data for verifying the fields option
get_fields_insert_sql_1 = """
    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
    )
    VALUES
    (%s,'COMPLETED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00','2023/10/02 12:23:59',null,null,null,null,null,null,null,null,null,null,null,null,null);
"""
get_fields_insert_sql_2 = """
    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
    )
    VALUES
    (%s,'IN_PROGRESS','{"procedures": "pre_test"}',null,null,'2023/10/02 00:00:00',null,null,null,null,null,null,null,null,null,null,null,null,null,null);
"""
get_fields_insert_sql_3 = """
    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
    )
    VALUES
    (%s,'CANCELING','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,'2023/10/02 12:23:59',null,null,null,null,null,null,null,null,null,null,null,null);
"""
get_fields_insert_sql_4 = """
    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
    )
    VALUES
    (%s,'FAILED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00','2023/10/02 12:23:59',null,null,null,null,null,null,null,null,null,null,null,null,null);
"""
get_fields_insert_sql_5 = """
    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
    )
    VALUES
    (%s,'CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','{"test": "test"}','2023/10/02 00:00:00' ,'2023/10/02 12:23:59','2023/10/02 12:00:00',FALSE,null,null,null,null,null,null,null,null,null,null,null);
"""
get_fields_insert_sql_6 = """
    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
    )
    VALUES
    (%s,'CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','{"test": "test"}','2023/10/02 00:00:00' ,'2023/10/02 12:23:59','2023/10/02 12:00:00',TRUE,'COMPLETED','[{"test": "test"}, {"test": "test"}]','2023/10/02 12:20:00','2023/10/02 12:23:59',null,null,null,null,null,null,null);
"""
# Data for status check after resumption
insert_resumed_get_target_sql_1 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s,'IN_PROGRESS','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,null,null,null,null,'{"test": "pre_test"}',null,'2023/10/02 12:23:59','2023/10/03 12:23:59')
"""
insert_resumed_get_target_sql_2 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s,'CANCELING','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,'2023/10/02 00:00:01',TRUE,'IN_PROGRESS','[{"test": "test"}, {"test": "test"}]','2023/10/02 00:00:02',null,'{"test": "pre_test"}','[{"test": "test"}]','2023/10/02 12:23:59','2023/10/03 12:23:59')
"""
insert_resumed_get_target_sql_3 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s,'COMPLETED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00','2023/10/02 12:23:59',null,null,null,null,null,null,'{"test": "pre_test"}','[{"test": "test"}, {"test": "test"}]','2023/10/02 12:23:59','2023/10/03 12:23:59')
"""
insert_resumed_get_target_sql_4 = """
    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
    ) VALUES
    (%s,'CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','{"test": "pre_test"}','2023/10/02 00:00:00','2023/10/02 01:00:00','2023/10/02 00:30:00',TRUE,'SUSPENDED',null,'2023/10/02 00:40:00',null,'[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',null,null,null,null,'2023/10/02 00:50:00',null);
"""
insert_resumed_get_target_sql_5 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s,'IN_PROGRESS','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,null,null,null,null,'{"test": "pre_test"}','[{"test": "test"}]','2023/10/02 12:23:59','2023/10/03 12:23:59')
"""
# Generic data
insert_status_suspended_sql = """
    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
    )
    VALUES
    (%s,'SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,null,null,null,null,'{"procedures": [{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]}',null,null,null,null,'2023/10/02 12:23:59',null);
"""

insert_status_completed_sql = """
    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
    )
    VALUES
    (%s,'COMPLETED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00' ,'2023/10/02 12:23:59',null,null,null,null,null,null,null,null,null,null,null,null,null);
"""
insert_status_canceled_sql = """
    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
    )
    VALUES
    (%s,'CANCELED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]','{"test": "test"}','2023/10/02 00:00:00' ,'2023/10/02 12:23:59','2023/10/02 12:00:00',FALSE,null,null,null,null,null,null,null,null,null,null,null);
"""
# Resumption confirmation data
insert_resumed_target_sql_1 = """
    INSERT into applystatus (applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, processid, executioncommand, processstartedat, suspendedat, resumedat
    )
    VALUES
    (%s,'SUSPENDED','{"procedures": "pre_test"}','[{"test": "test"}, {"test": "test"}]',null,'2023/10/02 00:00:00',null,null,null,null,null,null,null,'[{"operationID": 1, "operation": "shutdown","targetDeviceID": "0001", "dependencies": []}]',null,null,null,null,'2023/10/02 12:23:59',null);
"""
delete_for_applyid_sql = """
    DELETE FROM applystatus WHERE applyid = %s
"""

insert_delete_target_sql_1 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'IN_PROGRESS', '{"procedures": "pre_test"}', null, null, '2023/10/02 00:00:00', null, null, null, null, null, null, null, null, null, null, null)
"""
insert_delete_target_sql_2 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELING', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]','{\"test\": \"test\"}', '2023/10/01 23:59:59', '2023/10/02 12:23:58', '2023/10/02 12:00:00', TRUE, null, null, null, null, null, null, null, null)
"""
insert_delete_target_sql_3 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'COMPLETED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:00', '2023/10/02 12:23:59', null, null, null, null, null, null, null, null, null, null)
"""
insert_delete_target_sql_4 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'FAILED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:01', '2023/10/02 12:24:00', null, null, null, null, null, null, null, null, null, null)
"""
insert_delete_target_sql_5 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"test\": \"test\"}', '2023/10/02 00:00:02', '2023/10/02 12:24:01', '2023/10/02 12:00:00', FALSE, null, null, null, null, null, null, null, null)
"""
insert_delete_target_sql_6 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"test\": \"test\"}', '2023/10/03 00:00:00', '2023/10/04 12:23:59', '2023/10/03 12:00:00', TRUE, 'COMPLETED', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '2023/10/03 12:20:00', '2023/10/04 12:23:59', null, null, null, null)
"""
insert_delete_target_sql_7 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'SUSPENDED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', null, '2023/10/02 00:00:01', null, null, null, null, null, null, null, '{"test": "pre_test"}', null, '2024/01/02 12:23:00', null)
"""
insert_delete_target_sql_8 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"test\": \"test\"}', '2023/10/03 00:00:00', '2023/10/04 12:23:59', '2023/10/03 12:00:00', TRUE, 'IN_PROGRESS', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '2023/10/03 12:20:00', '2023/10/04 12:23:59', null, null, null, null)
"""
insert_delete_target_sql_9 = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'CANCELED', '{\"procedures\": \"pre_test\"}', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '{\"test\": \"test\"}', '2023/10/03 00:00:00', '2023/10/04 12:23:59', '2023/10/03 12:00:00', TRUE, 'SUSPENDED', '[{\"test\": \"test\"}, {\"test\": \"test\"}]', '2023/10/03 12:20:00', '2023/10/04 12:23:59', null, null, null, null)
"""
# Data for get valid data
get_valid_insert_sql = """
    INSERT into applystatus (
        applyid, status, procedures, applyresult, rollbackprocedures, startedat, endedat, canceledat, executerollback, rollbackstatus, rollbackresult, rollbackstartedat, rollbackendedat, resumeprocedures, resumeresult, suspendedat, resumedat
    ) VALUES
    (%s, 'COMPLETED', '[]', '[]', null, '2023/10/02 00:00:00', '2023/10/02 12:23:59', null, null, null, null, null, null, null, null, null, null);
"""
