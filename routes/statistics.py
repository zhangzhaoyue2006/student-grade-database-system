from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models.db import get_connection
from routes.permissions import login_required, role_required


statistics_bp = Blueprint("statistics", __name__, url_prefix="/statistics")


@statistics_bp.route("/")
@role_required("admin")
def statistics():
    semester = request.args.get("semester", "").strip()
    department_id = request.args.get("department_id", "").strip()
    has_filter = bool(semester or department_id)

    filters = []
    params = []
    if semester:
        filters.append("tc.semester = %s")
        params.append(semester)
    if department_id:
        filters.append("c.department_id = %s")
        params.append(department_id)

    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT semester FROM teacher_course ORDER BY semester DESC")
            semester_options = cursor.fetchall()
            cursor.execute("SELECT department_id, department_name FROM department ORDER BY department_name")
            departments = cursor.fetchall()

            course_rows = []
            if has_filter:
                cursor.execute(
                    f"""
                    SELECT DISTINCT c.course_id, c.course_code, c.course_name,
                           d.department_name, tc.semester
                    FROM teacher_course tc
                    JOIN course c ON tc.course_id = c.course_id
                    JOIN department d ON c.department_id = d.department_id
                    {where_clause}
                    ORDER BY tc.semester DESC, d.department_name, c.course_code
                    """,
                    params,
                )
                course_rows = cursor.fetchall()

    return render_template(
        "statistics/index.html",
        semester=semester,
        selected_department_id=department_id,
        has_filter=has_filter,
        semester_options=semester_options,
        departments=departments,
        courses=course_rows,
    )


@statistics_bp.route("/course/<int:course_id>/<path:semester>")
@role_required("admin")
def admin_course_statistics(course_id, semester):
    return_semester = request.args.get("return_semester", "").strip()
    return_department_id = request.args.get("return_department_id", "").strip()

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT c.course_id, c.course_code, c.course_name,
                       d.department_name, tc.semester
                FROM teacher_course tc
                JOIN course c ON tc.course_id = c.course_id
                JOIN department d ON c.department_id = d.department_id
                WHERE c.course_id = %s
                  AND tc.semester = %s
                """,
                (course_id, semester),
            )
            selected_course = cursor.fetchone()

            if not selected_course:
                flash("未找到该课程的统计数据。", "error")
                return redirect(
                    url_for(
                        "statistics.statistics",
                        semester=return_semester,
                        department_id=return_department_id,
                    )
                )

            stats = _build_course_stat(cursor, selected_course)

    return render_template(
        "statistics/detail.html",
        stats=stats,
        return_semester=return_semester,
        return_department_id=return_department_id,
    )


@statistics_bp.route("/teacher")
@login_required
def teacher_statistics():
    if session.get("role") != "teacher":
        return render_template("errors/403.html"), 403

    semester = request.args.get("semester", "").strip()

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

            courses_for_semester = []
            if semester:
                cursor.execute(
                    """
                    SELECT c.course_id, c.course_code, c.course_name,
                           d.department_name, tc.semester, tc.teaching_role, tc.course_status
                    FROM teacher_course tc
                    JOIN course c ON tc.course_id = c.course_id
                    JOIN department d ON c.department_id = d.department_id
                    WHERE tc.teacher_id = %s
                      AND tc.semester = %s
                    ORDER BY c.course_code
                    """,
                    (session.get("related_teacher_id"), semester),
                )
                courses_for_semester = cursor.fetchall()

    return render_template(
        "statistics/teacher.html",
        semester=semester,
        semester_options=semester_options,
        courses_for_semester=courses_for_semester,
    )


@statistics_bp.route("/teacher/course/<int:course_id>/<path:semester>")
@login_required
def teacher_course_statistics(course_id, semester):
    if session.get("role") != "teacher":
        return render_template("errors/403.html"), 403

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.course_id, c.course_code, c.course_name,
                       d.department_name, tc.semester, tc.teaching_role, tc.course_status
                FROM teacher_course tc
                JOIN course c ON tc.course_id = c.course_id
                JOIN department d ON c.department_id = d.department_id
                WHERE tc.teacher_id = %s
                  AND tc.course_id = %s
                  AND tc.semester = %s
                """,
                (session.get("related_teacher_id"), course_id, semester),
            )
            selected_course = cursor.fetchone()

            if not selected_course:
                flash("只能查看本人授课课程的成绩统计。", "error")
                return redirect(url_for("statistics.teacher_statistics", semester=semester))

            stats = _build_course_stat(cursor, selected_course)

    return render_template("statistics/teacher_detail.html", stats=stats)


def _build_course_stat(cursor, course):
    cursor.execute(
        """
        SELECT COUNT(DISTINCT student_id) AS enrolled_count
        FROM student_course
        WHERE course_id = %s
          AND semester = %s
          AND enroll_status <> '退课'
        """,
        (course["course_id"], course["semester"]),
    )
    enrolled_count = cursor.fetchone()["enrolled_count"] or 0

    cursor.execute(
        """
        SELECT g.student_id, MAX(g.score) AS best_score
        FROM grade g
        JOIN student_course sc
          ON sc.student_id = g.student_id
         AND sc.course_id = g.course_id
         AND sc.semester = g.semester
        WHERE g.course_id = %s
          AND g.semester = %s
          AND sc.enroll_status <> '退课'
        GROUP BY g.student_id
        """,
        (course["course_id"], course["semester"]),
    )
    scores = [_round_score(row["best_score"]) for row in cursor.fetchall() if row["best_score"] is not None]
    completed_count = len(scores)
    distribution = _distribution(scores)

    stat = dict(course)
    stat.update(
        {
            "enrolled_count": enrolled_count,
            "completed_count": completed_count,
            "completion_text": f"{completed_count}/{enrolled_count}",
            "pass_rate": _rate(sum(1 for score in scores if score >= 60), completed_count),
            "excellent_rate": _rate(sum(1 for score in scores if score >= 90), completed_count),
            "avg_score": _average(scores),
            "median_score": _median(scores),
            "max_score": _extreme(scores, max),
            "min_score": _extreme(scores, min),
            "distribution": distribution,
            "scores": scores,
        }
    )
    return stat


def _distribution(scores):
    total = len(scores)
    counts = {
        "score_90_100": sum(1 for score in scores if score >= 90),
        "score_80_89": sum(1 for score in scores if 80 <= score < 90),
        "score_70_79": sum(1 for score in scores if 70 <= score < 80),
        "score_60_69": sum(1 for score in scores if 60 <= score < 70),
        "score_0_59": sum(1 for score in scores if score < 60),
    }
    counts["total"] = total
    return counts


def _round_score(value):
    try:
        return float(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        return float(value)


def _average(scores):
    if not scores:
        return "-"
    return round(sum(scores) / len(scores), 1)


def _median(scores):
    if not scores:
        return "-"
    sorted_scores = sorted(scores)
    mid = len(sorted_scores) // 2
    if len(sorted_scores) % 2:
        return round(sorted_scores[mid], 1)
    return round((sorted_scores[mid - 1] + sorted_scores[mid]) / 2, 1)


def _extreme(scores, selector):
    if not scores:
        return "-"
    return int(selector(scores))


def _rate(count, total):
    if not total:
        return 0
    return round(count / total * 100, 2)
