"""
Lab 3 Autograder -- SOLUTION FILE (instructor reference, NOT for students)
================================================================================
Course : Data Management -- UM6P, College of Computing
Prof.  : Karima Echihabi
Session: Fall 2026

!!! THIS FILE IS A CANONICAL-ANSWER REFERENCE, NOT THE STUDENT TEMPLATE !!!
------------------------------------------------------------------------------
Every "-- WRITE YOUR SQL HERE" slot in the blank test_lab3.py has been
filled in here with correct, verified SQL for all 15 Lab 3 Part 1 queries.
Running this file with pytest should produce 15/15 PASSED, and is a useful
sanity check that schema.sql + seed.sql + lab3_answers.py are all mutually
consistent.

DO NOT distribute this file to students or commit it to the GitHub Classroom
template repository -- doing so hands them the answer key directly. Keep it
alongside lab3_answers.py, off the student-facing repo entirely.

Each query's SQL below was independently executed against seed.sql (via a
SQLite port of the schema for fast iteration) before being copied here, and
the resulting rows were verified to match lab3_answers.py's EXPECTED_RESULTS
exactly -- see the original build conversation for the verification trace.
Some queries admit more than one correct SQL formulation (e.g. Q5/Q6's
universal-quantification pattern can be written as a double NOT EXISTS or
as a HAVING COUNT(*) = (subquery count) division-style query); the versions
below are one valid formulation each, not necessarily the only one a correct
student submission could take.

SCOPE
-----
This file grades ONLY Part 1 of Lab 3: the 15 SQL queries written against the
RLMS schema. The Relational Algebra expressions and the functional-dependency
list (Part 2) are NOT autogradable and must be graded by hand.

FILE LAYOUT
------------
  schema.sql       -- DDL for the 19 RLMS relations
  seed.sql         -- the fixed seed dataset
  lab3_answers.py  -- EXPECTED_RESULTS, imported below (instructor-only)
  This file        -- instructor-only solved reference, never given to students

THE None-SKIPS-SAFELY RULE
----------------------------
If EXPECTED_RESULTS[n] is None, that test is SKIPPED rather than silently
passed or failed. (Not expected to trigger in this file, since every query
below has a real answer, but kept identical to the student harness for
consistency.)
"""

import os
import pymysql
import pytest


# ============================================================================
# CONFIG
# ============================================================================
DB_NAME = "RLMS_LAB3"
HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(HERE, "schema.sql")
SEED_FILE = os.path.join(HERE, "seed.sql")


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


@pytest.fixture(scope="session", autouse=True)
def setup_database(connection):
    """
    Runs once per test session: drops and recreates RLMS_LAB3, then loads
    the fixed schema and fixed seed data from schema.sql / seed.sql.
    """
    cur = connection.cursor()

    cur.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
    cur.execute(f"CREATE DATABASE {DB_NAME}")
    cur.execute(f"USE {DB_NAME}")

    for path in (SCHEMA_FILE, SEED_FILE):
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Required file not found: {path}\n"
                f"Lab 3 grading requires schema.sql and seed.sql to sit "
                f"next to test_lab3.py."
            )
        with open(path, "r", encoding="utf-8") as f:
            sql_text = f.read()

        # Strip '--' comments line-by-line BEFORE splitting on ';'. Doing the
        # split first (and only checking statement.startswith("--")) breaks
        # on multi-line comment blocks, since everything after the first
        # comment line up to the next ';' would otherwise be swallowed into
        # one malformed "statement".
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
            # skip any USE <db>; the instructor's file may contain, since
            # we already USE'd DB_NAME above
            if statement.upper().startswith("USE "):
                continue
            cur.execute(statement)

    cur.close()
    yield


@pytest.fixture
def cursor(connection):
    cur = connection.cursor()
    cur.execute(f"USE {DB_NAME}")
    yield cur
    cur.close()


# ============================================================================
# COMPARISON HELPER
# ============================================================================
def normalize(rows):
    """Order-insensitive comparison: sorted tuple multiset."""
    return sorted(tuple(row) for row in rows)


def assert_matches_expected(cursor, sql, expected, query_label):
    """
    Runs `sql`, compares to `expected` as an order-insensitive multiset.
    If `expected` is None, the test is SKIPPED (never silently passes).
    """
    if expected is None:
        pytest.skip(
            f"{query_label}: no EXPECTED_RESULTS entry filled in yet -- "
            f"skipping rather than risking a false pass."
        )

    cursor.execute(sql)
    actual_rows = cursor.fetchall()

    assert normalize(actual_rows) == normalize(expected), (
        f"{query_label} result mismatch.\n"
        f"  Expected ({len(expected)} rows): {sorted(tuple(r) for r in expected)}\n"
        f"  Got      ({len(actual_rows)} rows): {normalize(actual_rows)}"
    )


# ============================================================================
# EXPECTED RESULTS
# Imported from lab3_answers.py, which is NOT distributed to students (see
# module docstring above). If that file is missing, this import fails loudly
# at collection time rather than silently grading against no expected values.
# ============================================================================
try:
    from lab3_answers import EXPECTED_RESULTS
except ImportError as exc:
    raise ImportError(
        "lab3_answers.py not found. This file holds the private expected "
        "results for Lab 3 and is intentionally NOT included in the "
        "student-facing repository. If you are the instructor running "
        "grading, place lab3_answers.py next to test_lab3.py (or anywhere "
        "on the Python path) before running pytest."
    ) from exc


# ============================================================================
# TESTS -- one per Lab 3 Part 1 query, docstring lifted from the Lab 3 PDF
# ============================================================================
def test_01_research_users_with_reservation(cursor):
    """
    Query 1

    Find the names of research users who have made at least one reservation.
    """
    sql = """
    SELECT DISTINCT p.FullName
    FROM Person p
    JOIN ResearchUser ru ON p.PersonID = ru.PersonID
    JOIN Reservation r ON r.PersonID = p.PersonID
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[1], "Q1")


def test_02_users_attached_or_leading_project(cursor):
    """
    Query 2

    Find the IDs of research users who are either assigned to a laboratory
    or are leading at least one research project.
    """
    sql = """
    SELECT DISTINCT ru.PersonID
    FROM ResearchUser ru
    WHERE ru.PersonID IN (SELECT PersonID FROM AttachedTo)
       OR ru.PersonID IN (
           SELECT PersonID FROM ProjectParticipation WHERE ProjectRole = 'PI'
       )
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[2], "Q2")


def test_03_labs_research_center_a_or_microscope(cursor):
    """
    Query 3

    Find the IDs of laboratories located in the building 'Research Center A'
    or having at least one equipment item of category 'Microscope'.
    """
    sql = """
    SELECT DISTINCT l.LabID
    FROM Laboratory l
    WHERE l.Building = 'Research Center A'
       OR l.LabID IN (
           SELECT eu.LabID
           FROM EquipmentUnit eu
           JOIN EquipmentModel em ON eu.ModelID = em.ModelID
           WHERE em.Category = 'Microscope'
       )
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[3], "Q3")


def test_04_labs_with_microscope_and_centrifuge(cursor):
    """
    Query 4

    Find the IDs of laboratories that contain both 'Microscope' and
    'Centrifuge' equipment.
    """
    sql = """
    SELECT eu.LabID
    FROM EquipmentUnit eu
    JOIN EquipmentModel em ON eu.ModelID = em.ModelID
    WHERE em.Category IN ('Microscope', 'Centrifuge')
    GROUP BY eu.LabID
    HAVING COUNT(DISTINCT em.Category) = 2
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[4], "Q4")


def test_05_supervisors_of_every_north_wing_lab(cursor):
    """
    Query 5

    Find the research users who supervise every laboratory located in
    building 'North Wing'.
    """
    sql = """
    SELECT ru.PersonID
    FROM ResearchUser ru
    WHERE NOT EXISTS (
        SELECT 1 FROM Laboratory l
        WHERE l.Building = 'North Wing'
          AND (l.SupervisorID IS NULL OR l.SupervisorID <> ru.PersonID)
    )
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[5], "Q5")


def test_06_participants_in_every_lab2_project(cursor):
    """
    Query 6

    Find the research users who participate in every research project
    supervised by laboratory with LabID = 2.
    """
    sql = """
    SELECT ru.PersonID
    FROM ResearchUser ru
    WHERE NOT EXISTS (
        SELECT 1 FROM ProjectParticipation pp_lead
        WHERE pp_lead.PersonID = (SELECT SupervisorID FROM Laboratory WHERE LabID = 'L0002')
          AND pp_lead.ProjectRole = 'PI'
          AND NOT EXISTS (
              SELECT 1 FROM ProjectParticipation pp_self
              WHERE pp_self.PersonID = ru.PersonID
                AND pp_self.ProjectCode = pp_lead.ProjectCode
          )
    )
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[6], "Q6")


def test_07_pairs_more_reservations(cursor):
    """
    Query 7

    Find pairs of research users (r1, r2) such that r1 has made more
    reservations than r2.
    """
    sql = """
    SELECT a.PersonID, b.PersonID
    FROM (SELECT PersonID, COUNT(*) AS c FROM Reservation GROUP BY PersonID) a,
         (SELECT PersonID, COUNT(*) AS c FROM Reservation GROUP BY PersonID) b
    WHERE a.c > b.c
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[7], "Q7")


def test_08_users_reserved_two_different_labs(cursor):
    """
    Query 8

    Find the IDs of research users who have reserved equipment units
    belonging to at least two different laboratories.
    """
    sql = """
    SELECT r.PersonID
    FROM Reservation r
    JOIN EquipmentUnit eu ON r.SerialNumber = eu.SerialNumber
    GROUP BY r.PersonID
    HAVING COUNT(DISTINCT eu.LabID) >= 2
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[8], "Q8")


def test_09_september_2026_biolab_a_reservations(cursor):
    """
    Query 9

    Find the reservation IDs of reservations made in September 2026 for
    equipment units located in the laboratory named 'BioLab-A'.
    """
    sql = """
    SELECT r.ReservationID
    FROM Reservation r
    JOIN EquipmentUnit eu ON r.SerialNumber = eu.SerialNumber
    JOIN Laboratory l ON eu.LabID = l.LabID
    WHERE l.Name = 'BioLab-A'
      AND r.PlannedStartTime >= '2026-09-01 00:00:00'
      AND r.PlannedStartTime <  '2026-10-01 00:00:00'
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[9], "Q9")


def test_10_users_leading_more_than_one_project(cursor):
    """
    Query 10

    Find the IDs of research users who lead more than one research project.
    """
    sql = """
    SELECT PersonID
    FROM ProjectParticipation
    WHERE ProjectRole = 'PI'
    GROUP BY PersonID
    HAVING COUNT(*) > 1
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[10], "Q10")


def test_11_users_approved_in_multiple_labs(cursor):
    """
    Query 11

    List the IDs of research users who have approved reservations in more
    than one laboratory.
    """
    sql = """
    SELECT r.ApprovedBy
    FROM Reservation r
    JOIN EquipmentUnit eu ON r.SerialNumber = eu.SerialNumber
    WHERE r.ApprovedBy IS NOT NULL
    GROUP BY r.ApprovedBy
    HAVING COUNT(DISTINCT eu.LabID) > 1
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[11], "Q11")


def test_12_users_no_reservation_nov_6_2026(cursor):
    """
    Query 12

    Find the IDs of research users who have no reservation on
    November 6, 2026.
    """
    sql = """
    SELECT ru.PersonID
    FROM ResearchUser ru
    WHERE ru.PersonID NOT IN (
        SELECT PersonID FROM Reservation
        WHERE PlannedStartTime >= '2026-11-06 00:00:00'
          AND PlannedStartTime <  '2026-11-07 00:00:00'
    )
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[12], "Q12")


def test_13_labs_below_average_equipment_count(cursor):
    """
    Query 13

    Find laboratories whose number of equipment units is below the average
    number of equipment units per laboratory.
    """
    sql = """
    SELECT l.LabID
    FROM Laboratory l
    LEFT JOIN EquipmentUnit eu ON l.LabID = eu.LabID
    GROUP BY l.LabID
    HAVING COUNT(eu.SerialNumber) < (
        SELECT AVG(cnt) FROM (
            SELECT COUNT(*) AS cnt FROM EquipmentUnit GROUP BY LabID
        ) t
    )
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[13], "Q13")


def test_14_top_approver_per_lab(cursor):
    """
    Query 14

    For each laboratory, return the research user who has made the greatest
    number of approved reservations in that laboratory.
    """
    sql = """
    SELECT eu.LabID, r.PersonID
    FROM Reservation r
    JOIN EquipmentUnit eu ON r.SerialNumber = eu.SerialNumber
    WHERE r.Status = 'Approved'
    GROUP BY eu.LabID, r.PersonID
    HAVING COUNT(*) = (
        SELECT MAX(c) FROM (
            SELECT COUNT(*) AS c
            FROM Reservation r2
            JOIN EquipmentUnit eu2 ON r2.SerialNumber = eu2.SerialNumber
            WHERE r2.Status = 'Approved' AND eu2.LabID = eu.LabID
            GROUP BY r2.PersonID
        ) sub
    )
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[14], "Q14")


def test_15_users_three_plus_reservations_2025(cursor):
    """
    Query 15

    List the research users who made at least 3 reservations during the
    year 2025.
    """
    sql = """
    SELECT PersonID
    FROM Reservation
    WHERE PlannedStartTime >= '2025-01-01 00:00:00'
      AND PlannedStartTime <  '2026-01-01 00:00:00'
    GROUP BY PersonID
    HAVING COUNT(*) >= 3
    """
    assert_matches_expected(cursor, sql, EXPECTED_RESULTS[15], "Q15")