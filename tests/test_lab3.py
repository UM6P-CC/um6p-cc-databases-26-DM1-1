"""
Lab 3 Autograder -- Relational Algebra, SQL and Functional Dependencies (RLMS)
================================================================================
Course : Data Management -- UM6P, College of Computing
Prof.  : Karima Echihabi
Session: Fall 2026

SCOPE
-----
This file grades ONLY Part 1 of Lab 3: the 15 SQL queries written against the
RLMS schema. The Relational Algebra expressions and the functional-dependency
list (Part 2) are NOT autogradable and must be graded by hand.

HOW THIS DIFFERS FROM THE LAB 0 TEST FILE
------------------------------------------
In Lab 0, students CREATE the schema and INSERT the data themselves, so the
test file builds everything from the student's own SQL. In Lab 3 the schema
and data already exist conceptually (from Labs 1-2): students write ONLY
SELECT queries. This harness therefore:
  1. Creates a fresh database (RLMS_LAB3) for the test session.
  2. Loads a FIXED instructor-provided schema (`schema.sql`).
  3. Loads a FIXED, hand-built adversarial seed dataset (`seed.sql`).
  4. Runs each student SELECT (pasted into the marked slot below) against
     that fixed data and compares the result to an expected answer that is
     imported from a SEPARATE, instructor-only file (see FILE LAYOUT below).

Because the data is fixed and known in advance, comparisons here use
order-insensitive SET comparison (sorted tuple multisets) -- none of the
15 Lab 3 queries specify an ORDER BY in their wording, so row order must
not affect the grade.

FILE LAYOUT -- what students see vs. what stays private
-----------------------------------------------------------
  Distributed to students (GitHub Classroom template repo):
    test_lab3.py   -- this file: fixtures, harness, 15 test stubs.
                       Contains NO expected answers.
    schema.sql     -- DDL for the 19 RLMS relations. Not a secret -- this is
                       the schema students already know from Labs 1-2.
    seed.sql       -- the fixed seed dataset. Also not a secret -- the data
                       itself doesn't reveal which rows answer which query;
                       only lab3_answers.py does that.

  INSTRUCTOR-ONLY, kept off the student repo:
    lab3_answers.py -- the EXPECTED_RESULTS dict. test_lab3.py imports this
                        at collection time. If a student's environment is
                        missing this file, pytest fails immediately with a
                        clear ImportError (see below) instead of silently
                        grading against nothing.

  On your grading runner (GitHub Actions, local machine, etc.), place
  lab3_answers.py in the same directory as test_lab3.py before running
  pytest. Do NOT add lab3_answers.py to the assignment template repository
  that gets forked/cloned into student repos.

If your official Lab 2 answer key uses different table/column names than the
ones in schema.sql, edit schema.sql + seed.sql (and lab3_answers.py) to
match -- the test bodies themselves only ever reference EXPECTED_RESULTS,
never table/column names directly, so no changes to this .py file should be
needed.

SCHEMA NOTE (please verify against your official Lab 2 answer key)
--------------------------------------------------------------------
The schema used here was reconstructed from the Lab 1 conceptual-design
requirements and prior course material. A few relations are flagged
"VERIFY" in schema.sql where the exact column name was uncertain
(ServiceProvider's primary key name, Maintenance's technician linkage,
and the unit for Maintenance.DowntimeDuration). These do not affect any
of the 15 graded queries below, but should be checked in case your official
answer key differs.

WHY THE EXPECTED RESULTS ARE HARDCODED VALUES (not embedded reference SQL)
-----------------------------------------------------------------------------
Hardcoding the expected *rows* (computed once against the fixed seed data)
means students must write their own correct SQL to reproduce those rows --
exactly like Lab 0's approach, just adapted to a SELECT-only lab, and with
the added step that the values themselves now live outside the student's
reach entirely.

THE None-SKIPS-SAFELY RULE
----------------------------
If EXPECTED_RESULTS[n] is None, that test is SKIPPED rather than silently
passed or failed. This prevents false positives from an instructor who
forgot to fill in an expected value -- a missing answer key entry must never
look like a correct submission.
"""

import os
import pymysql
import pytest


# ============================================================================
# CONFIG
# ============================================================================
DB_NAME = "RLMS_LAB3"
SHADOW_DB_NAME = "RLMS_LAB3_SHADOW"
HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(HERE, "schema.sql")
SEED_FILE = os.path.join(HERE, "seed.sql")
SHADOW_SEED_FILE = os.path.join(HERE, "seed_shadow.sql")


# ============================================================================
# FIXTURES (same style as the Lab 0 test file)
# ============================================================================
@pytest.fixture(scope="session")
def connection():
    conn = pymysql.connect(
        host="127.0.0.1",
        user="root",
        password="root",
        autocommit=True,
    )
    yield conn
    conn.close()


def _load_sql_file_into_db(cur, path, required_for_msg):
    """
    Reads `path`, strips '--' comments line-by-line (must happen BEFORE
    splitting on ';' or multi-line comment blocks get swallowed into one
    malformed "statement"), then executes each non-empty statement against
    the cursor's currently-selected database.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Required file not found: {path}\n{required_for_msg}"
        )
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
        if not statement:
            continue
        if statement.upper().startswith("USE "):
            continue
        cur.execute(statement)


@pytest.fixture(scope="session", autouse=True)
def setup_database(connection):
    """
    Runs once per test session: builds TWO independent databases --
    RLMS_LAB3 (from schema.sql + seed.sql, the public dataset) and
    RLMS_LAB3_SHADOW (from schema.sql + seed_shadow.sql, a second hidden
    dataset with a disjoint ID namespace). Every student query is later run
    against both (see assert_matches_expected) so that a query hardcoded to
    literal values from the public dataset will fail against the shadow
    dataset, while a genuinely correct, general-purpose query passes both.
    """
    cur = connection.cursor()

    for db_name, seed_file in ((DB_NAME, SEED_FILE), (SHADOW_DB_NAME, SHADOW_SEED_FILE)):
        cur.execute(f"DROP DATABASE IF EXISTS {db_name}")
        cur.execute(f"CREATE DATABASE {db_name}")
        cur.execute(f"USE {db_name}")

        _load_sql_file_into_db(
            cur, SCHEMA_FILE,
            "Lab 3 grading requires schema.sql to sit next to test_lab3.py.",
        )
        _load_sql_file_into_db(
            cur, seed_file,
            "Lab 3 grading requires seed.sql and seed_shadow.sql to sit "
            "next to test_lab3.py.",
        )

    cur.close()
    yield


@pytest.fixture
def cursor(connection):
    cur = connection.cursor()
    cur.execute(f"USE {DB_NAME}")
    yield cur
    cur.close()


@pytest.fixture
def shadow_cursor(connection):
    cur = connection.cursor()
    cur.execute(f"USE {SHADOW_DB_NAME}")
    yield cur
    cur.close()


# ============================================================================
# COMPARISON HELPER
# ============================================================================
def normalize(rows):
    """Order-insensitive comparison: sorted tuple multiset."""
    return sorted(tuple(row) for row in rows)


def assert_matches_expected(cursor, shadow_cursor, sql, expected, shadow_expected, query_label):
    """
    Runs `sql` against BOTH the public dataset (via `cursor`) and the
    shadow dataset (via `shadow_cursor`), comparing each to its own
    expected result as an order-insensitive multiset. Credit requires a
    match on BOTH -- a query that hardcodes literal values observed from
    the public dataset (e.g. by reading seed.sql or by brute-forcing
    pass/fail feedback) will reliably fail the shadow check, since none of
    seed_shadow.sql's IDs overlap with seed.sql's.

    If `expected` or `shadow_expected` is None, the test is SKIPPED rather
    than silently passed or failed -- a missing answer-key entry must never
    look like a correct submission.

    FAILURE MESSAGE ASYMMETRY (deliberate):
      - Public dataset mismatch -> shows the literal expected vs. actual
        rows. seed.sql is already visible to the student (it's committed to
        their repo), so showing its values costs nothing -- they could query
        that database directly anyway -- and the detail helps them debug.
      - Shadow dataset mismatch -> shows ROW COUNTS ONLY, never literal
        values. seed_shadow.sql is the actual hidden defense; printing its
        rows in a CI log a student can read would hand back exactly what
        hiding the file was meant to prevent.
    """
    if expected is None or shadow_expected is None:
        pytest.skip(
            f"{query_label}: no expected-results entry filled in yet for "
            f"one or both datasets -- skipping rather than risking a false pass."
        )

    cursor.execute(sql)
    actual_rows = normalize(cursor.fetchall())
    expected_rows = normalize(expected)

    shadow_cursor.execute(sql)
    shadow_actual_rows = normalize(shadow_cursor.fetchall())
    shadow_expected_rows = normalize(shadow_expected)

    public_ok = actual_rows == expected_rows
    shadow_ok = shadow_actual_rows == shadow_expected_rows

    if public_ok and shadow_ok:
        return

    details = []
    if not public_ok:
        # Safe to show literal values -- seed.sql is visible to the student.
        details.append(
            f"public dataset result mismatch:\n"
            f"    Expected ({len(expected_rows)} row(s)): {expected_rows}\n"
            f"    Got      ({len(actual_rows)} row(s)): {actual_rows}"
        )
    if not shadow_ok:
        # Counts only -- seed_shadow.sql must never be revealed.
        details.append(
            f"hidden verification dataset result mismatch: "
            f"expected {len(shadow_expected_rows)} row(s), "
            f"got {len(shadow_actual_rows)} row(s) "
            f"(values withheld -- this dataset is intentionally hidden)"
        )
        if public_ok:
            details.append(
                "    (this query matched the public dataset but NOT the hidden "
                "one -- if your SQL hardcodes specific ID values instead of "
                "expressing the join/filter logic the question asks for, this "
                "is the expected failure mode)"
            )

    pytest.fail(f"{query_label} result mismatch:\n  " + "\n  ".join(details))


# ============================================================================
# EXPECTED RESULTS (public + shadow)
# Imported from lab3_answers.py and lab3_answers_shadow.py, neither of which
# is distributed to students (see module docstring above). If either file is
# missing, this import fails loudly at collection time rather than silently
# grading against no expected values.
# ============================================================================
try:
    from lab3_answers import EXPECTED_RESULTS
except ImportError as exc:
    raise ImportError(
        "lab3_answers.py not found. This file holds the private expected "
        "results for Lab 3 (public dataset) and is intentionally NOT "
        "included in the student-facing repository. If you are the "
        "instructor running grading, place lab3_answers.py next to "
        "test_lab3.py (or anywhere on the Python path) before running "
        "pytest."
    ) from exc

try:
    from lab3_answers_shadow import EXPECTED_RESULTS as SHADOW_EXPECTED_RESULTS
except ImportError as exc:
    raise ImportError(
        "lab3_answers_shadow.py not found. This file holds the private "
        "expected results for Lab 3's SECOND, hidden verification dataset "
        "and is intentionally NOT included in the student-facing "
        "repository. If you are the instructor running grading, place "
        "lab3_answers_shadow.py next to test_lab3.py (or anywhere on the "
        "Python path) before running pytest."
    ) from exc


# ============================================================================
# TESTS -- one per Lab 3 Part 1 query, docstring lifted from the Lab 3 PDF
# ============================================================================
def test_01_research_users_with_reservation(cursor, shadow_cursor):
    """
    Query 1

    Find the names of research users who have made at least one reservation.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[1], SHADOW_EXPECTED_RESULTS[1], "Q1")


def test_02_users_attached_or_leading_project(cursor, shadow_cursor):
    """
    Query 2

    Find the IDs of research users who are either assigned to a laboratory
    or are leading at least one research project.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[2], SHADOW_EXPECTED_RESULTS[2], "Q2")


def test_03_labs_research_center_a_or_microscope(cursor, shadow_cursor):
    """
    Query 3

    Find the IDs of laboratories located in the building 'Research Center A'
    or having at least one equipment item of category 'Microscope'.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[3], SHADOW_EXPECTED_RESULTS[3], "Q3")


def test_04_labs_with_microscope_and_centrifuge(cursor, shadow_cursor):
    """
    Query 4

    Find the IDs of laboratories that contain both 'Microscope' and
    'Centrifuge' equipment.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[4], SHADOW_EXPECTED_RESULTS[4], "Q4")


def test_05_supervisors_of_every_north_wing_lab(cursor, shadow_cursor):
    """
    Query 5

    Find the research users who supervise every laboratory located in
    building 'North Wing'.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[5], SHADOW_EXPECTED_RESULTS[5], "Q5")


def test_06_participants_in_every_lab2_project(cursor, shadow_cursor):
    """
    Query 6

    Find the research users who participate in every research project
    supervised by laboratory with LabID = 2.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[6], SHADOW_EXPECTED_RESULTS[6], "Q6")


def test_07_pairs_more_reservations(cursor, shadow_cursor):
    """
    Query 7

    Find pairs of research users (r1, r2) such that r1 has made more
    reservations than r2.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[7], SHADOW_EXPECTED_RESULTS[7], "Q7")


def test_08_users_reserved_two_different_labs(cursor, shadow_cursor):
    """
    Query 8

    Find the IDs of research users who have reserved equipment units
    belonging to at least two different laboratories.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[8], SHADOW_EXPECTED_RESULTS[8], "Q8")


def test_09_september_2026_biolab_a_reservations(cursor, shadow_cursor):
    """
    Query 9

    Find the reservation IDs of reservations made in September 2026 for
    equipment units located in the laboratory named 'BioLab-A'.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[9], SHADOW_EXPECTED_RESULTS[9], "Q9")


def test_10_users_leading_more_than_one_project(cursor, shadow_cursor):
    """
    Query 10

    Find the IDs of research users who lead more than one research project.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[10], SHADOW_EXPECTED_RESULTS[10], "Q10")


def test_11_users_approved_in_multiple_labs(cursor, shadow_cursor):
    """
    Query 11

    List the IDs of research users who have approved reservations in more
    than one laboratory.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[11], SHADOW_EXPECTED_RESULTS[11], "Q11")


def test_12_users_no_reservation_nov_6_2026(cursor, shadow_cursor):
    """
    Query 12

    Find the IDs of research users who have no reservation on
    November 6, 2026.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[12], SHADOW_EXPECTED_RESULTS[12], "Q12")


def test_13_labs_below_average_equipment_count(cursor, shadow_cursor):
    """
    Query 13

    Find laboratories whose number of equipment units is below the average
    number of equipment units per laboratory.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[13], SHADOW_EXPECTED_RESULTS[13], "Q13")


def test_14_top_approver_per_lab(cursor, shadow_cursor):
    """
    Query 14

    For each laboratory, return the research user who has made the greatest
    number of approved reservations in that laboratory.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[14], SHADOW_EXPECTED_RESULTS[14], "Q14")


def test_15_users_three_plus_reservations_2025(cursor, shadow_cursor):
    """
    Query 15

    List the research users who made at least 3 reservations during the
    year 2025.
    """
    sql = """
    -- WRITE YOUR SQL HERE
    """
    assert_matches_expected(cursor, shadow_cursor, sql, EXPECTED_RESULTS[15], SHADOW_EXPECTED_RESULTS[15], "Q15")