from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models.db import get_connection
from routes.permissions import role_required


teacher_portal_bp = Blueprint("teacher_portal", __name__, url_prefix="/teacher")


@teacher_portal_bp.route("/courses")
@role_required("teacher")
def my_courses():
    semester = request.args.get("semester", "").strip()
    courses = []

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT semester
                FROM teacher_course
                WHERE teacher_id = %s
                ORDER BY semester DESC
                """,
                (session.get("related_teacher_id"),),
            )
            semester_options = cursor.fetchall()

            if semester:
                cursor.execute(
                    """
                    SELECT c.course_id, c.course_code, c.course_name, c.class_hours,
                           c.credits, c.degree_level, d.department_name,
                           tc.semester, tc.teaching_role, tc.course_status
                    FROM teacher_course tc
                    JOIN course c ON tc.course_id = c.course_id
                    JOIN department d ON c.department_id = d.department_id
                    WHERE tc.teacher_id = %s
                      AND tc.semester = %s
                    ORDER BY c.course_code
                    """,
                    (session.get("related_teacher_id"), semester),
                )
                courses = cursor.fetchall()

    return render_template(
        "teacher/courses.html",
        courses=courses,
        semester=semester,
        semester_options=semester_options,
        has_query=bool(semester),
    )


@teacher_portal_bp.route("/students")
@role_required("teacher")
def course_students():
    course_id = request.args.get("course_id", "").strip()
    semester = request.args.get("semester", "").strip()

    if not course_id or not semester:
        flash("请先选择学期和课程。", "error")
        return redirect(url_for("teacher_portal.my_courses", semester=semester))

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.course_id, c.course_code, c.course_name, c.class_hours,
                       c.credits, c.degree_level, d.department_name,
                       tc.semester, tc.teaching_role, tc.course_status
                FROM teacher_course tc
                JOIN course c ON tc.course_id = c.course_id
                JOIN department d ON c.department_id = d.department_id
                WHERE tc.teacher_id = %s
                  AND tc.course_id = %s
                  AND tc.semester = %s
                """,
                (session.get("related_teacher_id"), course_id, semester),
            )
            course = cursor.fetchone()

            if not course:
                flash("只能查看本人授课课程的学生名单。", "error")
                return redirect(url_for("teacher_portal.my_courses", semester=semester))

            cursor.execute(
                """
                SELECT s.student_id, s.student_no, s.name, s.gender, s.grade_year,
                       d.department_name, m.major_name
                FROM student_course sc
                JOIN student s ON sc.student_id = s.student_id
                JOIN major m ON s.major_id = m.major_id
                JOIN department d ON m.department_id = d.department_id
                WHERE sc.course_id = %s
                  AND sc.semester = %s
                  AND sc.enroll_status <> '退课'
                ORDER BY s.student_no
                """,
                (course_id, semester),
            )
            students = cursor.fetchall()

    return render_template(
        "teacher/students.html",
        course=course,
        students=students,
    )
