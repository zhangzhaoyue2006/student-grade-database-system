from pymysql.err import IntegrityError, MySQLError
from flask import Blueprint, flash, redirect, render_template, request, url_for

from models.db import get_connection
from routes.permissions import role_required


teaching_bp = Blueprint("teaching", __name__, url_prefix="/teaching")


@teaching_bp.route("/")
@role_required("admin")
def list_teaching():
    keyword = request.args.get("keyword", "").strip()
    semester = request.args.get("semester", "").strip()
    course_status = request.args.get("course_status", "").strip()

    sql = """
        SELECT tc.teacher_id, tc.course_id, tc.semester, tc.teaching_role, tc.course_status,
               t.teacher_no, t.name AS teacher_name,
               c.course_code, c.course_name
        FROM teacher_course tc
        JOIN teacher t ON tc.teacher_id = t.teacher_id
        JOIN course c ON tc.course_id = c.course_id
        WHERE 1 = 1
    """
    params = []

    if keyword:
        sql += """
            AND (t.teacher_no LIKE %s OR t.name LIKE %s
                 OR c.course_code LIKE %s OR c.course_name LIKE %s)
        """
        like_keyword = f"%{keyword}%"
        params.extend([like_keyword, like_keyword, like_keyword, like_keyword])

    if semester:
        sql += " AND tc.semester = %s"
        params.append(semester)

    if course_status:
        sql += " AND tc.course_status = %s"
        params.append(course_status)

    sql += " ORDER BY tc.semester DESC, c.course_code, t.teacher_no"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            records = cursor.fetchall()
            semester_options = _list_semesters(cursor)

    return render_template(
        "teaching/list.html",
        records=records,
        keyword=keyword,
        semester=semester,
        selected_course_status=course_status,
        semester_options=semester_options,
    )


@teaching_bp.route("/new", methods=["GET", "POST"])
@role_required("admin")
def create_teaching():
    teachers, courses = _load_options()

    if request.method == "POST":
        form = _teaching_form()
        error = _validate_teaching(form)
        if error:
            flash(error, "error")
            return render_template("teaching/form.html", record=form, teachers=teachers, courses=courses, mode="new")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO teacher_course (teacher_id, course_id, semester, teaching_role, course_status)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            form["teacher_id"],
                            form["course_id"],
                            form["semester"],
                            form["teaching_role"],
                            form["course_status"],
                        ),
                    )
                conn.commit()
        except IntegrityError:
            flash("该教师在该学期已分配过这门课程。", "error")
            return render_template("teaching/form.html", record=form, teachers=teachers, courses=courses, mode="new")
        except MySQLError:
            flash("新增授课安排失败，请检查数据库连接。", "error")
            return render_template("teaching/form.html", record=form, teachers=teachers, courses=courses, mode="new")

        flash("授课安排新增成功。", "success")
        return redirect(url_for("teaching.list_teaching"))

    return render_template("teaching/form.html", record={}, teachers=teachers, courses=courses, mode="new")


@teaching_bp.route("/<int:teacher_id>/<int:course_id>/<path:semester>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_teaching(teacher_id, course_id, semester):
    teachers, courses = _load_options()
    record = _get_teaching_or_none(teacher_id, course_id, semester)
    if not record:
        flash("授课安排不存在。", "error")
        return redirect(url_for("teaching.list_teaching"))

    if request.method == "POST":
        form = _teaching_form()
        error = _validate_teaching(form)
        if error:
            flash(error, "error")
            return render_template("teaching/form.html", record=form, teachers=teachers, courses=courses, mode="edit")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE teacher_course
                        SET teacher_id = %s, course_id = %s, semester = %s,
                            teaching_role = %s, course_status = %s
                        WHERE teacher_id = %s AND course_id = %s AND semester = %s
                        """,
                        (
                            form["teacher_id"], form["course_id"], form["semester"],
                            form["teaching_role"], form["course_status"],
                            teacher_id, course_id, semester,
                        ),
                    )
                    cursor.execute(
                        """
                        UPDATE teacher_course
                        SET course_status = %s
                        WHERE course_id = %s AND semester = %s
                        """,
                        (form["course_status"], form["course_id"], form["semester"]),
                    )
                conn.commit()
        except IntegrityError:
            flash("该授课安排已存在。", "error")
            return render_template("teaching/form.html", record=form, teachers=teachers, courses=courses, mode="edit")
        except MySQLError:
            flash("修改授课安排失败，请检查数据库连接。", "error")
            return render_template("teaching/form.html", record=form, teachers=teachers, courses=courses, mode="edit")

        flash("授课安排修改成功。", "success")
        return redirect(url_for("teaching.list_teaching"))

    return render_template("teaching/form.html", record=record, teachers=teachers, courses=courses, mode="edit")


@teaching_bp.route("/<int:teacher_id>/<int:course_id>/<path:semester>/delete", methods=["POST"])
@role_required("admin")
def delete_teaching(teacher_id, course_id, semester):
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM teacher_course
                    WHERE teacher_id = %s AND course_id = %s AND semester = %s
                    """,
                    (teacher_id, course_id, semester),
                )
            conn.commit()
    except MySQLError:
        flash("删除授课安排失败，请检查数据库连接。", "error")
        return redirect(url_for("teaching.list_teaching"))

    flash("授课安排删除成功。", "success")
    return redirect(url_for("teaching.list_teaching"))


def _teaching_form():
    return {
        "teacher_id": request.form.get("teacher_id", "").strip(),
        "course_id": request.form.get("course_id", "").strip(),
        "semester": request.form.get("semester", "").strip(),
        "teaching_role": request.form.get("teaching_role", "").strip(),
        "course_status": request.form.get("course_status", "").strip() or "open",
    }


def _validate_teaching(form):
    if not form["teacher_id"]:
        return "请选择教师。"
    if not form["course_id"]:
        return "请选择课程。"
    if not form["semester"]:
        return "请输入学期。"
    if form["teaching_role"] not in ("主讲", "助教", "合上"):
        return "请选择合法的授课角色。"
    if form["course_status"] not in ("open", "closed"):
        return "请选择合法的课程状态。"
    return None


def _load_options():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT teacher_id, teacher_no, name FROM teacher ORDER BY teacher_no")
            teachers = cursor.fetchall()
            cursor.execute("SELECT course_id, course_code, course_name FROM course ORDER BY course_code")
            courses = cursor.fetchall()
    return teachers, courses


def _list_semesters(cursor):
    cursor.execute(
        """
        SELECT DISTINCT semester
        FROM teacher_course
        ORDER BY semester DESC
        """
    )
    return cursor.fetchall()


def _get_teaching_or_none(teacher_id, course_id, semester):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT teacher_id, course_id, semester, teaching_role, course_status
                FROM teacher_course
                WHERE teacher_id = %s AND course_id = %s AND semester = %s
                """,
                (teacher_id, course_id, semester),
            )
            return cursor.fetchone()
