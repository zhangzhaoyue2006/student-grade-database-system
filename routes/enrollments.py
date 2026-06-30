from pymysql.err import IntegrityError, MySQLError
from flask import Blueprint, flash, redirect, render_template, request, url_for

from models.db import get_connection
from routes.permissions import role_required


enrollments_bp = Blueprint("enrollments", __name__, url_prefix="/enrollments")


@enrollments_bp.route("/")
@role_required("admin")
def list_enrollments():
    keyword = request.args.get("keyword", "").strip()
    semester = request.args.get("semester", "").strip()

    sql = """
        SELECT sc.student_id, sc.course_id, sc.semester, sc.enrolled_at,
               EXISTS (
                   SELECT 1
                   FROM grade g
                   WHERE g.student_id = sc.student_id
                     AND g.course_id = sc.course_id
                     AND g.semester = sc.semester
               ) AS has_grade,
               s.student_no, s.name AS student_name,
               c.course_code, c.course_name
        FROM student_course sc
        JOIN student s ON sc.student_id = s.student_id
        JOIN course c ON sc.course_id = c.course_id
        WHERE sc.enroll_status <> '退课'
    """
    params = []

    if keyword:
        sql += """
            AND (s.student_no LIKE %s OR s.name LIKE %s
                 OR c.course_code LIKE %s OR c.course_name LIKE %s)
        """
        like_keyword = f"%{keyword}%"
        params.extend([like_keyword, like_keyword, like_keyword, like_keyword])

    if semester:
        sql += " AND sc.semester = %s"
        params.append(semester)

    sql += " ORDER BY sc.semester DESC, s.student_no, c.course_code"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            records = cursor.fetchall()
            semester_options = _list_semesters(cursor)

    return render_template(
        "enrollments/list.html",
        records=records,
        keyword=keyword,
        semester=semester,
        semester_options=semester_options,
    )


@enrollments_bp.route("/new", methods=["GET", "POST"])
@role_required("admin")
def create_enrollment():
    students, courses = _load_options()

    if request.method == "POST":
        form = _enrollment_form()
        error = _validate_enrollment(form)
        if error:
            flash(error, "error")
            return render_template("enrollments/form.html", record=form, students=students, courses=courses, mode="new")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO student_course (student_id, course_id, semester, enroll_status)
                        VALUES (%s, %s, %s, '已选')
                        """,
                        (form["student_id"], form["course_id"], form["semester"]),
                    )
                conn.commit()
        except IntegrityError:
            flash("该学生在该学期已存在这门课程的选课记录。", "error")
            return render_template("enrollments/form.html", record=form, students=students, courses=courses, mode="new")
        except MySQLError:
            flash("新增选课记录失败，请检查数据库连接。", "error")
            return render_template("enrollments/form.html", record=form, students=students, courses=courses, mode="new")

        flash("选课记录新增成功。", "success")
        return redirect(url_for("enrollments.list_enrollments"))

    return render_template("enrollments/form.html", record={}, students=students, courses=courses, mode="new")


@enrollments_bp.route("/<int:student_id>/<int:course_id>/<path:semester>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_enrollment(student_id, course_id, semester):
    students, courses = _load_options()
    record = _get_enrollment_or_none(student_id, course_id, semester)
    if not record:
        flash("选课记录不存在。", "error")
        return redirect(url_for("enrollments.list_enrollments"))

    if request.method == "POST":
        if record["has_grade"]:
            flash("该选课记录已有成绩，只能查看，不能修改。", "error")
            return redirect(url_for("enrollments.edit_enrollment", student_id=student_id, course_id=course_id, semester=semester))

        form = _enrollment_form()
        error = _validate_enrollment(form)
        if error:
            flash(error, "error")
            return render_template("enrollments/form.html", record=form, students=students, courses=courses, mode="edit")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE student_course
                        SET student_id = %s, course_id = %s, semester = %s, enroll_status = '已选'
                        WHERE student_id = %s AND course_id = %s AND semester = %s
                        """,
                        (form["student_id"], form["course_id"], form["semester"], student_id, course_id, semester),
                    )
                conn.commit()
        except IntegrityError:
            flash("该选课记录已存在。", "error")
            return render_template("enrollments/form.html", record=form, students=students, courses=courses, mode="edit")
        except MySQLError:
            flash("修改选课记录失败，请检查数据库连接。", "error")
            return render_template("enrollments/form.html", record=form, students=students, courses=courses, mode="edit")

        flash("选课记录修改成功。", "success")
        return redirect(url_for("enrollments.list_enrollments"))

    mode = "view" if record["has_grade"] else "edit"
    return render_template("enrollments/form.html", record=record, students=students, courses=courses, mode=mode)


@enrollments_bp.route("/<int:student_id>/<int:course_id>/<path:semester>/delete", methods=["POST"])
@role_required("admin")
def delete_enrollment(student_id, course_id, semester):
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                if _has_grade(cursor, student_id, course_id, semester):
                    flash("该选课记录已有成绩，只能查看，不能删除。", "error")
                    return redirect(url_for("enrollments.list_enrollments"))
                cursor.execute(
                    """
                    DELETE FROM student_course
                    WHERE student_id = %s AND course_id = %s AND semester = %s
                    """,
                    (student_id, course_id, semester),
                )
            conn.commit()
    except MySQLError:
        flash("删除选课记录失败，请检查数据库连接。", "error")
        return redirect(url_for("enrollments.list_enrollments"))

    flash("选课记录删除成功。", "success")
    return redirect(url_for("enrollments.list_enrollments"))


def _enrollment_form():
    return {
        "student_id": request.form.get("student_id", "").strip(),
        "course_id": request.form.get("course_id", "").strip(),
        "semester": request.form.get("semester", "").strip(),
    }


def _validate_enrollment(form):
    if not form["student_id"]:
        return "请选择学生。"
    if not form["course_id"]:
        return "请选择课程。"
    if not form["semester"]:
        return "请输入学期。"
    return None


def _load_options():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT student_id, student_no, name FROM student ORDER BY student_no")
            students = cursor.fetchall()
            cursor.execute("SELECT course_id, course_code, course_name FROM course ORDER BY course_code")
            courses = cursor.fetchall()
    return students, courses


def _list_semesters(cursor):
    cursor.execute(
        """
        SELECT DISTINCT semester
        FROM student_course
        ORDER BY semester DESC
        """
    )
    return cursor.fetchall()


def _get_enrollment_or_none(student_id, course_id, semester):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT sc.student_id, sc.course_id, sc.semester,
                       EXISTS (
                           SELECT 1
                           FROM grade g
                           WHERE g.student_id = sc.student_id
                             AND g.course_id = sc.course_id
                             AND g.semester = sc.semester
                       ) AS has_grade,
                       s.student_no, s.name AS student_name,
                       c.course_code, c.course_name
                FROM student_course sc
                JOIN student s ON sc.student_id = s.student_id
                JOIN course c ON sc.course_id = c.course_id
                WHERE sc.student_id = %s AND sc.course_id = %s AND sc.semester = %s
                  AND sc.enroll_status <> '退课'
                """,
                (student_id, course_id, semester),
            )
            return cursor.fetchone()


def _has_grade(cursor, student_id, course_id, semester):
    cursor.execute(
        """
        SELECT 1
        FROM grade
        WHERE student_id = %s AND course_id = %s AND semester = %s
        LIMIT 1
        """,
        (student_id, course_id, semester),
    )
    return cursor.fetchone() is not None
