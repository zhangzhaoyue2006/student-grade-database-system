from pymysql.err import IntegrityError, MySQLError
from flask import Blueprint, flash, redirect, render_template, request, url_for

from models.db import get_connection
from routes.permissions import role_required


courses_bp = Blueprint("courses", __name__, url_prefix="/courses")


@courses_bp.route("/")
@role_required("admin")
def list_courses():
    keyword = request.args.get("keyword", "").strip()
    department_id = request.args.get("department_id", "").strip()

    sql = """
        SELECT c.course_id, c.course_code, c.course_name, c.course_description,
               c.class_hours, c.credits, c.degree_level, c.department_id,
               c.updated_at, d.department_name
        FROM course c
        JOIN department d ON c.department_id = d.department_id
        WHERE 1 = 1
    """
    params = []

    if keyword:
        sql += " AND (c.course_code LIKE %s OR c.course_name LIKE %s)"
        like_keyword = f"%{keyword}%"
        params.extend([like_keyword, like_keyword])

    if department_id:
        sql += " AND c.department_id = %s"
        params.append(department_id)

    sql += " ORDER BY c.course_code"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            courses = cursor.fetchall()
            departments = _list_departments(cursor)

    return render_template(
        "courses/list.html",
        courses=courses,
        departments=departments,
        keyword=keyword,
        selected_department_id=department_id,
    )


@courses_bp.route("/new", methods=["GET", "POST"])
@role_required("admin")
def create_course():
    departments = _load_departments()

    if request.method == "POST":
        form = _course_form()
        error = _validate_course(form)

        if error:
            flash(error, "error")
            return render_template("courses/form.html", course=form, departments=departments, mode="new")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO course
                            (course_code, course_name, course_description,
                             class_hours, credits, degree_level, department_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            form["course_code"],
                            form["course_name"],
                            form["course_description"],
                            form["class_hours"],
                            form["credits"],
                            form["degree_level"],
                            form["department_id"],
                        ),
                    )
                conn.commit()
        except IntegrityError:
            flash("课程编号已存在。", "error")
            return render_template("courses/form.html", course=form, departments=departments, mode="new")
        except MySQLError:
            flash("新增课程失败，请检查数据库连接。", "error")
            return render_template("courses/form.html", course=form, departments=departments, mode="new")

        flash("课程新增成功。", "success")
        return redirect(url_for("courses.list_courses"))

    return render_template("courses/form.html", course={}, departments=departments, mode="new")


@courses_bp.route("/<int:course_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_course(course_id):
    departments = _load_departments()
    course = _get_course_or_none(course_id)

    if not course:
        flash("课程不存在。", "error")
        return redirect(url_for("courses.list_courses"))

    if request.method == "POST":
        form = _course_form()
        form["course_id"] = course_id
        error = _validate_course(form)

        if error:
            flash(error, "error")
            return render_template("courses/form.html", course=form, departments=departments, mode="edit")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE course
                        SET course_code = %s,
                            course_name = %s,
                            course_description = %s,
                            class_hours = %s,
                            credits = %s,
                            degree_level = %s,
                            department_id = %s
                        WHERE course_id = %s
                        """,
                        (
                            form["course_code"],
                            form["course_name"],
                            form["course_description"],
                            form["class_hours"],
                            form["credits"],
                            form["degree_level"],
                            form["department_id"],
                            course_id,
                        ),
                    )
                conn.commit()
        except IntegrityError:
            flash("课程编号已存在。", "error")
            return render_template("courses/form.html", course=form, departments=departments, mode="edit")
        except MySQLError:
            flash("修改课程失败，请检查数据库连接。", "error")
            return render_template("courses/form.html", course=form, departments=departments, mode="edit")

        flash("课程修改成功。", "success")
        return redirect(url_for("courses.list_courses"))

    return render_template("courses/form.html", course=course, departments=departments, mode="edit")


@courses_bp.route("/<int:course_id>/delete", methods=["POST"])
@role_required("admin")
def delete_course(course_id):
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM course WHERE course_id = %s", (course_id,))
            conn.commit()
    except IntegrityError:
        flash("该课程已被授课、选课或成绩数据引用，不能直接删除。", "error")
        return redirect(url_for("courses.list_courses"))
    except MySQLError:
        flash("删除课程失败，请检查数据库连接。", "error")
        return redirect(url_for("courses.list_courses"))

    flash("课程删除成功。", "success")
    return redirect(url_for("courses.list_courses"))


def _course_form():
    return {
        "course_code": request.form.get("course_code", "").strip(),
        "course_name": request.form.get("course_name", "").strip(),
        "course_description": request.form.get("course_description", "").strip(),
        "class_hours": request.form.get("class_hours", "").strip(),
        "credits": request.form.get("credits", "").strip(),
        "degree_level": request.form.get("degree_level", "").strip(),
        "department_id": request.form.get("department_id", "").strip(),
    }


def _validate_course(form):
    if not form["course_code"]:
        return "请输入课程编号。"
    if not form["course_name"]:
        return "请输入课程名称。"
    if len(form["course_code"]) > 30:
        return "课程编号不能超过 30 个字符。"
    if len(form["course_name"]) > 100:
        return "课程名称不能超过 100 个字符。"
    if form["degree_level"] not in ("本科", "硕士", "博士"):
        return "请选择合法的学位等级。"
    if not form["department_id"]:
        return "请选择开课院系。"

    try:
        class_hours = int(form["class_hours"])
    except ValueError:
        return "学时必须是整数。"
    if class_hours <= 0:
        return "学时必须大于 0。"

    try:
        credits = float(form["credits"])
    except ValueError:
        return "学分必须是数字。"
    if credits <= 0:
        return "学分必须大于 0。"

    try:
        int(form["department_id"])
    except ValueError:
        return "开课院系不合法。"

    return None


def _load_departments():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            return _list_departments(cursor)


def _list_departments(cursor):
    cursor.execute(
        """
        SELECT department_id, department_name
        FROM department
        ORDER BY department_name
        """
    )
    return cursor.fetchall()


def _get_course_or_none(course_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT course_id, course_code, course_name, course_description,
                       class_hours, credits, degree_level, department_id
                FROM course
                WHERE course_id = %s
                """,
                (course_id,),
            )
            return cursor.fetchone()
