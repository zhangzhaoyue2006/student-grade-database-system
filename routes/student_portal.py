from flask import Blueprint, render_template, request, session

from models.db import get_connection
from routes.permissions import role_required


student_portal_bp = Blueprint("student_portal", __name__, url_prefix="/student")


@student_portal_bp.route("/profile")
@role_required("student")
def profile():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.student_id, s.student_no, s.name, s.id_card, s.gender,
                       s.birth_date, s.dormitory, s.home_address, s.phone,
                       s.grade_year, s.degree_level, s.completed_credits,
                       m.major_name, d.department_name,
                       mm.major_name AS minor_name, md.department_name AS minor_department_name
                FROM student s
                JOIN major m ON s.major_id = m.major_id
                JOIN department d ON m.department_id = d.department_id
                LEFT JOIN major mm ON s.minor_id = mm.major_id
                LEFT JOIN department md ON mm.department_id = md.department_id
                WHERE s.student_id = %s
                """,
                (session.get("related_student_id"),),
            )
            student = cursor.fetchone()
            if student:
                student["completed_credits"] = _calculate_completed_credits(cursor, session.get("related_student_id"))

    return render_template("student/profile.html", student=student)


@student_portal_bp.route("/courses")
@role_required("student")
def my_courses():
    semester = request.args.get("semester", "").strip()
    courses = []
    selected_credits = 0

    with get_connection() as conn:
        with conn.cursor() as cursor:
            total_completed_credits = _calculate_completed_credits(cursor, session.get("related_student_id"))
            semester_options = _list_student_course_semesters(cursor, session.get("related_student_id"))

            if semester:
                cursor.execute(
                    """
                    SELECT c.course_id, c.course_code, c.course_name, c.class_hours,
                           c.credits, c.degree_level, d.department_name,
                           sc.semester
                    FROM student_course sc
                    JOIN course c ON sc.course_id = c.course_id
                    JOIN department d ON c.department_id = d.department_id
                    WHERE sc.student_id = %s
                      AND sc.semester = %s
                      AND sc.enroll_status <> '退课'
                    ORDER BY c.course_code
                    """,
                    (session.get("related_student_id"), semester),
                )
                courses = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT COALESCE(SUM(c.credits), 0) AS selected_credits
                    FROM student_course sc
                    JOIN course c ON sc.course_id = c.course_id
                    WHERE sc.student_id = %s
                      AND sc.semester = %s
                      AND sc.enroll_status <> '退课'
                    """,
                    (session.get("related_student_id"), semester),
                )
                selected_credits = cursor.fetchone()["selected_credits"]

    return render_template(
        "student/courses.html",
        courses=courses,
        semester=semester,
        semester_options=semester_options,
        selected_credits=selected_credits,
        total_completed_credits=total_completed_credits,
        has_query=bool(semester),
    )


def _list_student_course_semesters(cursor, student_id):
    cursor.execute(
        """
        SELECT DISTINCT semester
        FROM student_course
        WHERE student_id = %s
          AND enroll_status <> '退课'
        ORDER BY semester DESC
        """,
        (student_id,),
    )
    return cursor.fetchall()


def _calculate_completed_credits(cursor, student_id):
    cursor.execute(
        """
        SELECT COALESCE(SUM(passed_course.credits), 0) AS total_completed_credits
        FROM (
            SELECT c.course_id, MAX(c.credits) AS credits
            FROM grade g
            JOIN course c ON g.course_id = c.course_id
            WHERE g.student_id = %s
              AND g.score >= 60
              AND EXISTS (
                  SELECT 1
                  FROM teacher_course tc
                  WHERE tc.course_id = g.course_id
                    AND tc.semester = g.semester
                    AND tc.course_status = 'closed'
              )
            GROUP BY c.course_id
        ) AS passed_course
        """,
        (student_id,),
    )
    return cursor.fetchone()["total_completed_credits"]
