CREATE TABLE IF NOT EXISTS applystatus(
applyid varchar(10) PRIMARY KEY,
status varchar(12),
procedures jsonb,
result jsonb,
rollbackprocedures jsonb,
startedat timestamp,
endedat timestamp,
canceledat timestamp,
executerollback boolean,
resumeprocedures jsonb,
processid int,
executioncommand text,
processstartedat text,
suspendedat timestamp,
resumedat timestamp
);

CREATE TABLE IF NOT EXISTS rollbackstatus(
applyid varchar(10) PRIMARY KEY,
status varchar(12),
procedures jsonb,
result jsonb,
startedat timestamp,
endedat timestamp,
canceledat timestamp,
resumeprocedures jsonb,
processid int,
executioncommand text,
processstartedat text,
suspendedat timestamp,
resumedat timestamp
);
