"""
TRIGGERS cannot be graded by comparing a query result, because a trigger
has no "output" of its own -- it's a side effect of an INSERT/UPDATE/DELETE.
Each trigger test therefore:
  1. Creates the student's trigger(s) via their submitted SQL.
  2. PROVOKES the trigger with a specific INSERT/UPDATE/DELETE statement
     designed so a correct trigger produces an unambiguous, checkable
     outcome (either "this statement must be rejected with an error" or
     "this statement must succeed AND leave the database in a specific
     state").
  3. Asserts that outcome actually occurred.
Trigger tests run ONLY against the public dataset -- there is no
"hardcoded answer to hide" for a trigger (the correct behavior is fully
specified by the question itself: reject double bookings, flip a status,
etc.), so the shadow-dataset anti-hardcoding defense that matters for
Lab 3/4's query answers doesn't apply here in the same way. To still catch
a trigger hardcoded to one specific row's ID instead of expressing the
real condition, each trigger is provoked TWICE with two different,
non-overlapping scenarios (a fresh row pair each time) within the same
public dataset.


"""
import os
import pymysql
import pytest


DB_NAME = "RLMS_LAB5"
SHADOW_DB_NAME = "RLMS_LAB5_SHADOW"
HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(HERE, "schema.sql")
SEED_FILE = os.path.join(HERE, "lab5_seed.sql")
SHADOW_SEED_FILE = os.path.join(HERE, "lab5_seed_shadow.sql")


@pytest.fixture(scope="session")
def admin_connection():
    conn = pymysql.connect(host="127.0.0.1", user="root", password="root", autocommit=True)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def public_connection():
    conn = pymysql.connect(host="127.0.0.1", user="root", password="root", database=DB_NAME, autocommit=True)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def shadow_connection():
    conn = pymysql.connect(host="127.0.0.1", user="root", password="root", database=SHADOW_DB_NAME, autocommit=True)
    yield conn
    conn.close()


def _load_sql_file_into_db(cur, path, required_for_msg):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Required file not found: {path}\n{required_for_msg}")
    with open(path, "r", encoding="utf-8") as f:
        sql_text = f.read()
    clean_lines = []
    for line in sql_text.split("\n"):
        if "--" in line:
            line = line.split("--")[0]
        clean_lines.append(line)
    sql_text = "\n".join(clean_lines)
    for statement in sql_text.split(";"):
        statement = statement.strip()
        if not statement or statement.upper().startswith("USE "):
            continue
        cur.execute(statement)


@pytest.fixture(scope="session", autouse=True)
def setup_database(admin_connection):
    """Builds TWO independent databases, each freshly seeded."""
    cur = admin_connection.cursor()
    for db_name, seed_file in ((DB_NAME, SEED_FILE), (SHADOW_DB_NAME, SHADOW_SEED_FILE)):
        cur.execute(f"DROP DATABASE IF EXISTS {db_name}")
        cur.execute(f"CREATE DATABASE {db_name}")
        cur.execute(f"USE {db_name}")
        _load_sql_file_into_db(cur, SCHEMA_FILE, "Lab 5 grading requires schema.sql to sit next to test_lab5.py.")
        _load_sql_file_into_db(cur, seed_file, "Lab 5 grading requires lab5_seed.sql and lab5_seed_shadow.sql to sit next to test_lab5.py.")
    cur.close()
    yield


@pytest.fixture
def cursor(public_connection, setup_database):
    cur = public_connection.cursor()
    yield cur
    cur.close()


@pytest.fixture
def shadow_cursor(shadow_connection, setup_database):
    cur = shadow_connection.cursor()
    yield cur
    cur.close()


def normalize(rows):
    return sorted(tuple(str(v) if v is not None else None for v in row) for row in rows)


def _is_effectively_blank(sql):
    stripped_lines = []
    for line in sql.split("\n"):
        if "--" in line:
            line = line.split("--")[0]
        stripped_lines.append(line)
    return "".join(stripped_lines).strip() == ""


def _split_trigger_statements(sql):
    """
    Splits a student's trigger SQL into individual executable statements.
    Trigger bodies contain semicolons INSIDE BEGIN...END blocks (e.g. after
    each IF...END IF;), so naively splitting on ';' shreds a single
    CREATE TRIGGER into invalid fragments. Students are expected to follow
    the lab handout's MySQL client convention of wrapping multi-statement
    trigger bodies in `DELIMITER //` ... `END //` ... `DELIMITER ;` --
    but DELIMITER is a CLIENT command, not real SQL, and pymysql sends
    one statement at a time with no delimiter ambiguity to begin with, so
    this function strips DELIMITER lines and splits on '//' instead of ';'
    when '//' is present, falling back to ';'-splitting otherwise (so a
    student who *didn't* use DELIMITER, e.g. a single-statement trigger,
    still works).
    """
    if "DELIMITER" in sql.upper() or "//" in sql:
        # Strip DELIMITER lines entirely, then split remaining content on //
        lines = [l for l in sql.split("\n") if not l.strip().upper().startswith("DELIMITER")]
        cleaned = "\n".join(lines)
        statements = [s.strip() for s in cleaned.split("//")]
    else:
        statements = [s.strip() for s in sql.split(";")]
    return [s for s in statements if s]


def assert_view_matches_expected(cursor, shadow_cursor, view_sql, view_name, expected, shadow_expected, label):
    """Creates the view from `view_sql`, queries it on both datasets, and
    compares to hardcoded expected results (order-insensitive multiset)."""
    if expected is None or shadow_expected is None:
        pytest.skip(f"{label}: no expected-results entry filled in yet -- skipping.")

    assert not _is_effectively_blank(view_sql), (
        f"{label}: no SQL was written for this view's CREATE VIEW statement."
    )

    for cur in (cursor, shadow_cursor):
        cur.execute(f"DROP VIEW IF EXISTS {view_name}")
        cur.execute(view_sql)

    cursor.execute(f"SELECT * FROM {view_name}")
    actual_rows = normalize(cursor.fetchall())
    expected_rows = normalize(expected)

    shadow_cursor.execute(f"SELECT * FROM {view_name}")
    shadow_actual_rows = normalize(shadow_cursor.fetchall())
    shadow_expected_rows = normalize(shadow_expected)

    public_ok = actual_rows == expected_rows
    shadow_ok = shadow_actual_rows == shadow_expected_rows
    if public_ok and shadow_ok:
        return

    details = []
    if not public_ok:
        details.append(
            f"public dataset result mismatch:\n"
            f"    Expected ({len(expected_rows)} row(s)): {expected_rows}\n"
            f"    Got      ({len(actual_rows)} row(s)): {actual_rows}"
        )
    if not shadow_ok:
        details.append(
            f"hidden verification dataset result mismatch: "
            f"expected {len(shadow_expected_rows)} row(s), "
            f"got {len(shadow_actual_rows)} row(s) (values withheld)"
        )
        if public_ok:
            details.append(
                "    (matched public but not hidden dataset -- check your view "
                "doesn't hardcode specific ID values)"
            )
    pytest.fail(f"{label} result mismatch:\n  " + "\n  ".join(details))


def assert_view_matches_expected_with_offset(cursor, shadow_cursor, view_sql, view_name,
                                              expected_with_offset, shadow_expected_with_offset,
                                              date_col_index, label):
    """Same as assert_view_matches_expected, but one column (at
    `date_col_index`) is a DATE/DATETIME that must be compared as a
    CURDATE()-relative day-offset rather than a frozen absolute value."""
    if expected_with_offset is None or shadow_expected_with_offset is None:
        pytest.skip(f"{label}: no expected-results entry filled in yet -- skipping.")

    assert not _is_effectively_blank(view_sql), (
        f"{label}: no SQL was written for this view's CREATE VIEW statement."
    )

    for cur in (cursor, shadow_cursor):
        cur.execute(f"DROP VIEW IF EXISTS {view_name}")
        cur.execute(view_sql)

    def rows_with_offset(cur):
        cur.execute(f"SELECT * FROM {view_name}")
        cur.execute("SELECT CURDATE()")
        today = cur.fetchone()[0]
        cur.execute(f"SELECT * FROM {view_name}")
        raw_rows = cur.fetchall()
        converted = []
        for row in raw_rows:
            row = list(row)
            val = row[date_col_index]
            if val is not None:
                # val may be a date or datetime; normalize to date for DATEDIFF semantics
                try:
                    d = val.date() if hasattr(val, "date") else val
                except Exception:
                    d = val
                offset = (d - today).days
                row[date_col_index] = str(offset)
            converted.append(tuple(str(x) if x is not None else None for x in row))
        return normalize(converted)

    actual_rows = rows_with_offset(cursor)
    expected_rows = normalize(expected_with_offset)

    shadow_actual_rows = rows_with_offset(shadow_cursor)
    shadow_expected_rows = normalize(shadow_expected_with_offset)

    public_ok = actual_rows == expected_rows
    shadow_ok = shadow_actual_rows == shadow_expected_rows
    if public_ok and shadow_ok:
        return

    details = []
    if not public_ok:
        details.append(
            f"public dataset result mismatch (date column compared as day-offset "
            f"from CURDATE(), not an absolute date):\n"
            f"    Expected ({len(expected_rows)} row(s)): {expected_rows}\n"
            f"    Got      ({len(actual_rows)} row(s)): {actual_rows}"
        )
    if not shadow_ok:
        details.append(
            f"hidden verification dataset result mismatch: "
            f"expected {len(shadow_expected_rows)} row(s), "
            f"got {len(shadow_actual_rows)} row(s) (values withheld)"
        )
        if public_ok:
            details.append("    (matched public but not hidden dataset)")
    pytest.fail(f"{label} result mismatch:\n  " + "\n  ".join(details))


def assert_statement_rejected(cursor, sql, label, expected_error_substring=None):
    """Asserts that executing `sql` raises a MySQL error (e.g. from a
    SIGNAL in a trigger). If `expected_error_substring` is given, also
    checks the error message contains it (case-insensitive) -- this is
    intentionally a SUBSTRING check, not exact-match, since the lab only
    asks for "a clear error message", not one specific wording."""
    import pymysql.err
    try:
        cursor.execute(sql)
    except pymysql.err.OperationalError as e:
        if expected_error_substring:
            msg = str(e).lower()
            assert expected_error_substring.lower() in msg, (
                f"{label}: statement was correctly rejected, but the error "
                f"message doesn't mention '{expected_error_substring}'. "
                f"Got: {e}"
            )
        return
    pytest.fail(
        f"{label}: expected this statement to be REJECTED by a trigger, "
        f"but it succeeded:\n  {sql}"
    )


def assert_statement_succeeds(cursor, sql, label):
    """Asserts that executing `sql` does NOT raise -- i.e. the trigger
    correctly allows a valid statement through (catches an overly broad
    trigger that rejects everything)."""
    import pymysql.err
    try:
        cursor.execute(sql)
    except pymysql.err.OperationalError as e:
        pytest.fail(
            f"{label}: expected this statement to SUCCEED, but it was "
            f"rejected (your trigger may be too strict):\n  {sql}\n  Error: {e}"
        )


def _assert_trigger_exists(cursor, table_name, event, timing, label):
    """Confirms AT LEAST ONE trigger exists on `table_name` for the given
    event/timing (e.g. ('Reservation', 'INSERT', 'BEFORE')). Checks by
    table+event+timing, not by a specific trigger name, since students
    choose their own trigger names -- only the lab's required BEHAVIOR is
    specified, not naming. Used by the 'must still succeed' tests to fail
    loudly if no trigger was ever created, since otherwise a blank
    submission's INSERT/UPDATE/DELETE would trivially 'succeed' (nothing
    is there to reject it) and the test would falsely pass."""
    cursor.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TRIGGERS "
        "WHERE TRIGGER_SCHEMA = DATABASE() AND EVENT_OBJECT_TABLE = %s "
        "AND EVENT_MANIPULATION = %s AND ACTION_TIMING = %s",
        (table_name, event, timing),
    )
    count = cursor.fetchone()[0]
    assert count > 0, (
        f"{label}: no {timing} {event} trigger exists on {table_name} yet. "
        f"This test depends on an earlier test in this file having "
        f"created it -- if you're running tests individually rather than "
        f"the full file, run the corresponding 'reject' test first."
    )


# ============================================================================
# EXPECTED RESULTS (views only -- triggers have no hardcoded answer)
# ============================================================================
try:
    from lab5_answers import EXPECTED_RESULTS
except ImportError as exc:
    raise ImportError(
        "lab5_answers.py not found. This file holds the private expected "
        "view results for Lab 5 (public dataset) and is intentionally NOT "
        "included in the student-facing repository."
    ) from exc

try:
    from lab5_answers_shadow import EXPECTED_RESULTS as SHADOW_EXPECTED_RESULTS
except ImportError as exc:
    raise ImportError(
        "lab5_answers_shadow.py not found. This file holds the private "
        "expected view results for Lab 5's hidden verification dataset."
    ) from exc


def test_01_view_upcoming_reservations_by_lab(cursor, shadow_cursor):
    """
    View 1: UpcomingReservationsByLab

    Build a view that returns, for the next fourteen days, per laboratory
    and per date: LabName, ReservationDate, ApprovedCount.
    Use Reservation joined through EquipmentUnit -> Laboratory.
    Consider only rows with Reservation.Status = 'Approved'.
    """
    sql = """
    -- WRITE YOUR CREATE VIEW STATEMENT HERE
    """
    assert_view_matches_expected_with_offset(
        cursor, shadow_cursor, sql, "UpcomingReservationsByLab",
        EXPECTED_RESULTS[1], SHADOW_EXPECTED_RESULTS[1],
        date_col_index=1, label="View1",
    )


def test_02_view_equipment_usage_summary(cursor, shadow_cursor):
    """
    View 2: EquipmentUsageSummary

    Build a view that summarizes equipment usage per laboratory with the
    columns: LabID, LabName, EquipmentID, EquipmentName, TotalUnits,
    AvailableUnits, ReservedUnits, MaintenanceUnits.
    Use EquipmentModel, EquipmentUnit, and Laboratory.
    Group by laboratory and equipment.
    """
    sql = """
    -- WRITE YOUR CREATE VIEW STATEMENT HERE
    """
    assert_view_matches_expected(
        cursor, shadow_cursor, sql, "EquipmentUsageSummary",
        EXPECTED_RESULTS[2], SHADOW_EXPECTED_RESULTS[2], "View2",
    )


def test_03_view_research_user_reservation_thirty(cursor, shadow_cursor):
    """
    View 3: ResearchUserReservationThirty

    Build a view that returns per research user, over the last thirty
    days: UserID, FullName, TotalReservations, ApprovedCount,
    PendingCount, CancelledCount.
    Source from Reservation joined via ResearchUser.
    Treat missing counts as zero.
    """
    sql = """
    -- WRITE YOUR CREATE VIEW STATEMENT HERE
    """
    assert_view_matches_expected(
        cursor, shadow_cursor, sql, "ResearchUserReservationThirty",
        EXPECTED_RESULTS[3], SHADOW_EXPECTED_RESULTS[3], "View3",
    )


def test_04_view_project_next_reservation(cursor, shadow_cursor):
    """
    View 4: ProjectNextReservation

    Build a view that returns, for each research project, the next
    approved reservation with: ProjectID, ProjectTitle,
    NextReservationDate, LabName, EquipmentName, UnitID.
    Join ResearchProject -> Reservation -> EquipmentUnit and through
    EquipmentModel and Laboratory.
    Pick the minimum Reservation.PlannedStartTime strictly greater than
    today among rows with Status = 'Approved'.
    """
    sql = """
    -- WRITE YOUR CREATE VIEW STATEMENT HERE
    """
    assert_view_matches_expected_with_offset(
        cursor, shadow_cursor, sql, "ProjectNextReservation",
        EXPECTED_RESULTS[4], SHADOW_EXPECTED_RESULTS[4],
        date_col_index=2, label="View4",
    )


# ============================================================================
# TRIGGER 1 -- reject double booking
# ============================================================================
def test_05_trigger_no_double_booking_insert(cursor):
    """
    Trigger 1a: reject double booking on INSERT

    Create a trigger on Reservation that rejects an INSERT if it would
    schedule two approved reservations for the same SerialNumber with
    overlapping PlannedStartTime/PlannedEndTime intervals. Use SIGNAL
    with a clear error message.

    This test provokes the trigger with a new reservation on WN00001 that
    overlaps an existing Approved reservation (WR0001, 2026-06-28
    00:00-02:00) -- this INSERT must be rejected.
    """
    trigger_sql = """
    -- WRITE YOUR CREATE TRIGGER STATEMENT(S) HERE
    """
    assert not _is_effectively_blank(trigger_sql), (
        "Trigger 1: no SQL was written."
    )
    for stmt in _split_trigger_statements(trigger_sql):
        cursor.execute(stmt)

    overlap_insert = """
        INSERT INTO Reservation
            (ReservationID, SubmissionTimestamp, PlannedStartTime, PlannedEndTime,
             Purpose, Status, PersonID, SerialNumber, ProjectCode, ApprovedBy)
        VALUES
            ('WRTST1', NOW(), '2026-06-28 01:00:00', '2026-06-28 03:00:00',
             'Overlap test', 'Approved', 'W00001', 'WN00001', NULL, NULL)
    """
    assert_statement_rejected(cursor, overlap_insert, "Trigger1-insert", "double")


def test_06_trigger_no_double_booking_update(cursor):
    """
    Trigger 1b: reject double booking on UPDATE

    Same rule as Trigger 1a, but provoked via an UPDATE that moves an
    existing reservation (WR0011, currently on WN00002) onto WN00001's
    existing Approved time slot (2026-06-28 00:00-02:00, from WR0001).
    """
    overlap_update = """
        UPDATE Reservation
        SET SerialNumber = 'WN00001',
            PlannedStartTime = '2026-06-28 00:30:00',
            PlannedEndTime = '2026-06-28 01:30:00',
            Status = 'Approved'
        WHERE ReservationID = 'WR0011'
    """
    assert_statement_rejected(cursor, overlap_update, "Trigger1-update", "double")


def test_07_trigger_no_double_booking_allows_valid(cursor):
    """
    Trigger 1c: a genuinely non-overlapping reservation must still succeed

    Confirms Trigger 1 isn't overly strict -- a new Approved reservation
    on WN00001 far outside any existing reservation's time window must be
    accepted normally.
    """
    _assert_trigger_exists(cursor, "Reservation", "INSERT", "BEFORE", "Trigger1-valid")
    valid_insert = """
        INSERT INTO Reservation
            (ReservationID, SubmissionTimestamp, PlannedStartTime, PlannedEndTime,
             Purpose, Status, PersonID, SerialNumber, ProjectCode, ApprovedBy)
        VALUES
            ('WRTST2', NOW(), '2026-09-01 09:00:00', '2026-09-01 11:00:00',
             'Non-overlap test', 'Approved', 'W00001', 'WN00001', NULL, NULL)
    """
    assert_statement_succeeds(cursor, valid_insert, "Trigger1-valid")


# ============================================================================
# TRIGGER 2 -- maintenance status updates
# ============================================================================
def test_08_trigger_maintenance_sets_undermaintenance(cursor):
    """
    Trigger 2a: inserting a Maintenance record sets the unit to
    'UnderMaintenance'

    Create a trigger on Maintenance such that after inserting a
    maintenance record, the corresponding EquipmentUnit.CurrentStatus
    becomes 'UnderMaintenance'.

    Provoked on WN00004 (currently Operational, per lab5_seed.sql).
    """
    trigger_sql = """
    -- WRITE YOUR CREATE TRIGGER STATEMENT(S) HERE
    """
    assert not _is_effectively_blank(trigger_sql), (
        "Trigger 2: no SQL was written."
    )
    for stmt in _split_trigger_statements(trigger_sql):
        cursor.execute(stmt)

    cursor.execute("SELECT CurrentStatus FROM EquipmentUnit WHERE SerialNumber = 'WN00004'")
    before = cursor.fetchone()[0]
    assert before == "Operational", (
        f"Test precondition failed: WN00004 should start as 'Operational' "
        f"in this seed, found '{before}'."
    )

    cursor.execute("""
        INSERT INTO Maintenance
            (MaintenanceID, MaintenanceDate, MaintenanceType, Description,
             Cost, DowntimeDuration, Outcome, SerialNumber, TechnicianID)
        VALUES
            ('WTTST1', CURDATE(), 'Corrective', 'Trigger test', 50.00, 1,
             NULL, 'WN00004', 'W00009')
    """)

    cursor.execute("SELECT CurrentStatus FROM EquipmentUnit WHERE SerialNumber = 'WN00004'")
    after = cursor.fetchone()[0]
    assert after == "UnderMaintenance", (
        f"Trigger2-insert: expected WN00004.CurrentStatus to become "
        f"'UnderMaintenance' after a Maintenance record was inserted for "
        f"it, but found '{after}'."
    )


def test_09_trigger_maintenance_outcome_sets_operational(cursor):
    """
    Trigger 2b: setting a non-null Outcome sets the unit back to
    'Operational'

    Create a trigger on Maintenance such that after updating a
    maintenance record to set a non-null Outcome (the job is finished),
    the corresponding EquipmentUnit.CurrentStatus becomes 'Operational'.

    Continues from test_08: WN00004 is now UnderMaintenance with an open
    Maintenance record (WTTST1, Outcome still NULL).
    """
    _assert_trigger_exists(cursor, "Maintenance", "UPDATE", "AFTER", "Trigger2-update")
    cursor.execute("""
        UPDATE Maintenance SET Outcome = 'Repaired' WHERE MaintenanceID = 'WTTST1'
    """)
    cursor.execute("SELECT CurrentStatus FROM EquipmentUnit WHERE SerialNumber = 'WN00004'")
    after = cursor.fetchone()[0]
    assert after == "Operational", (
        f"Trigger2-update: expected WN00004.CurrentStatus to become "
        f"'Operational' after Maintenance.Outcome was set to a non-null "
        f"value, but found '{after}'."
    )


# ============================================================================
# TRIGGER 3 -- prevent invalid equipment unit state
# ============================================================================
def test_10_trigger_rejects_invalid_status(cursor):
    """
    Trigger 3a: reject an invalid CurrentStatus value

    Create BEFORE INSERT and BEFORE UPDATE triggers on EquipmentUnit that
    reject any row with an invalid CurrentStatus value. The allowed
    values in this schema are: 'Operational', 'Retired', 'UnderMaintenance'.
    Use SIGNAL to reject invalid rows with a clear error message.
    """
    trigger_sql = """
    -- WRITE YOUR CREATE TRIGGER STATEMENT(S) HERE
    """
    assert not _is_effectively_blank(trigger_sql), (
        "Trigger 3: no SQL was written."
    )
    for stmt in _split_trigger_statements(trigger_sql):
        cursor.execute(stmt)

    bad_status_insert = """
        INSERT INTO EquipmentUnit
            (SerialNumber, AcquisitionDate, PurchaseCost, CurrentStatus,
             IsPortable, LabID, ModelID)
        VALUES
            ('WNBAD1', '2024-01-01', 100.00, 'BrokenStatus', FALSE, 'V0001', 'U0001')
    """
    assert_statement_rejected(cursor, bad_status_insert, "Trigger3-status")


def test_11_trigger_rejects_missing_lab(cursor):
    """
    Trigger 3b: reject a missing laboratory assignment

    Same trigger set as test_10, provoked instead with a NULL LabID.
    """
    missing_lab_insert = """
        INSERT INTO EquipmentUnit
            (SerialNumber, AcquisitionDate, PurchaseCost, CurrentStatus,
             IsPortable, LabID, ModelID)
        VALUES
            ('WNBAD2', '2024-01-01', 100.00, 'Operational', FALSE, NULL, 'U0001')
    """
    assert_statement_rejected(cursor, missing_lab_insert, "Trigger3-nolab")


def test_12_trigger_allows_valid_equipment_unit(cursor):
    """
    Trigger 3c: a genuinely valid row must still be accepted

    Confirms Trigger 3 isn't overly strict.
    """
    _assert_trigger_exists(cursor, "EquipmentUnit", "INSERT", "BEFORE", "Trigger3-valid")
    valid_insert = """
        INSERT INTO EquipmentUnit
            (SerialNumber, AcquisitionDate, PurchaseCost, CurrentStatus,
             IsPortable, LabID, ModelID)
        VALUES
            ('WNGOOD', '2024-01-01', 100.00, 'Operational', FALSE, 'V0001', 'U0001')
    """
    assert_statement_succeeds(cursor, valid_insert, "Trigger3-valid")


# ============================================================================
# TRIGGER 4 -- protect referential integrity on laboratory delete
# ============================================================================
def test_13_trigger_blocks_delete_with_equipment(cursor):
    """
    Trigger 4a: block deleting a laboratory that has equipment units

    Create a BEFORE DELETE trigger on Laboratory that blocks deletion if
    any EquipmentUnit exists in the laboratory or if any reservation is
    linked to one of its units. Use SIGNAL to raise an error.

    Provoked on V0001 (PhotonicsLab), which has equipment units in this seed.
    """
    trigger_sql = """
    -- WRITE YOUR CREATE TRIGGER STATEMENT HERE
    """
    assert not _is_effectively_blank(trigger_sql), (
        "Trigger 4: no SQL was written."
    )
    for stmt in _split_trigger_statements(trigger_sql):
        cursor.execute(stmt)

    blocked_delete = "DELETE FROM Laboratory WHERE LabID = 'V0001'"
    assert_statement_rejected(cursor, blocked_delete, "Trigger4-blocked")


def test_14_trigger_allows_delete_of_empty_lab(cursor):
    """
    Trigger 4b: deleting a laboratory with NO dependent equipment or
    reservations must succeed

    Provoked on V0004 (EmptyLab), which has neither in this seed.
    """
    _assert_trigger_exists(cursor, "Laboratory", "DELETE", "BEFORE", "Trigger4-allowed")
    allowed_delete = "DELETE FROM Laboratory WHERE LabID = 'V0004'"
    assert_statement_succeeds(cursor, allowed_delete, "Trigger4-allowed")