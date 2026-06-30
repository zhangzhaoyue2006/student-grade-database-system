from pymysql.err import IntegrityError, MySQLError
from flask import Blueprint, flash, redirect, render_template, request, url_for

from models.db import get_connection
from routes.permissions import role_required


teachers_bp = Blueprint("teachers", __name__, url_prefix="/teachers")


@teachers_bp.route("/")
@role_required("admin")
def list_teachers():
    keyword = request.args.get("keyword", "").strip()
    department_id = request.args.get("department_id", "").strip()
    title_id = request.args.get("title_id", "").strip()

    sql = """
        SELECT t.teacher_id, t.teacher_no, t.name, t.title_id, tt.title_name, t.phone,
               t.department_id, t.updated_at, d.department_name
        FROM teacher t
        JOIN department d ON t.department_id = d.department_id
        LEFT JOIN title tt ON t.title_id = tt.title_id
        WHERE 1 = 1
    """
    params = []

    if keyword:
        sql += " AND (t.teacher_no LIKE %s OR t.name LIKE %s)"
        like_keyword = f"%{keyword}%"
        params.extend([like_keyword, like_keyword])

    if department_id:
        sql += " AND t.department_id = %s"
        params.append(department_id)

    if title_id:
        sql += " AND t.title_id = %s"
        params.append(title_id)

    sql += " ORDER BY t.teacher_no"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            teachers = cursor.fetchall()
            departments = _list_departments(cursor)
            titles = _list_titles(cursor)

    return render_template(
        "teachers/list.html",
        teachers=teachers,
        departments=departments,
        titles=titles,
        keyword=keyword,
        selected_department_id=department_id,
        selected_title_id=title_id,
    )


@teachers_bp.route("/new", methods=["GET", "POST"])
@role_required("admin")
def create_teacher():
    departments, titles = _load_options()

    if request.method == "POST":
        form = _teacher_form()
        error = _validate_teacher(form)

        if error:
            flash(error, "error")
            return render_template("teachers/form.html", teacher=form, departments=departments, titles=titles, mode="new")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO teacher (teacher_no, name, department_id, title_id, phone)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            form["teacher_no"],
                            form["name"],
                            form["department_id"],
                            form["title_id"],
                            form["phone"],
                        ),
                    )
                conn.commit()
        except IntegrityError:
            flash("教师编号已存在。", "error")
            return render_template("teachers/form.html", teacher=form, departments=departments, titles=titles, mode="new")
        except MySQLError:
            flash("新增教师失败，请检查数据库连接。", "error")
            return render_template("teachers/form.html", teacher=form, departments=departments, titles=titles, mode="new")

        flash("教师新增成功。", "success")
        return redirect(url_for("teachers.list_teachers"))

    return render_template("teachers/form.html", teacher={}, departments=departments, titles=titles, mode="new")


@teachers_bp.route("/<int:teacher_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_teacher(teacher_id):
    departments, titles = _load_options()
    teacher = _get_teacher_or_none(teacher_id)

    if not teacher:
        flash("教师不存在。", "error")
        return redirect(url_for("teachers.list_teachers"))

    if request.method == "POST":
        form = _teacher_form()
        form["teacher_id"] = teacher_id
        error = _validate_teacher(form)

        if error:
            flash(error, "error")
            return render_template("teachers/form.html", teacher=form, departments=departments, titles=titles, mode="edit")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE teacher
                        SET teacher_no = %s,
                            name = %s,
                            department_id = %s,
                            title_id = %s,
                            phone = %s
                        WHERE teacher_id = %s
                        """,
                        (
                            form["teacher_no"],
                            form["name"],
                            form["department_id"],
                            form["title_id"],
                            form["phone"],
                            teacher_id,
                        ),
                    )
                conn.commit()
        except IntegrityError:
            flash("教师编号已存在。", "error")
            return render_template("teachers/form.html", teacher=form, departments=departments, titles=titles, mode="edit")
        except MySQLError:
            flash("修改教师失败，请检查数据库连接。", "error")
            return render_template("teachers/form.html", teacher=form, departments=departments, titles=titles, mode="edit")

        flash("教师修改成功。", "success")
        return redirect(url_for("teachers.list_teachers"))

    return render_template("teachers/form.html", teacher=teacher, departments=departments, titles=titles, mode="edit")


@teachers_bp.route("/<int:teacher_id>/delete", methods=["POST"])
@role_required("admin")
def delete_teacher(teacher_id):
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM teacher WHERE teacher_id = %s", (teacher_id,))
            conn.commit()
    except IntegrityError:
        flash("该教师已被授课或用户账号引用，不能直接删除。", "error")
        return redirect(url_for("teachers.list_teachers"))
    except MySQLError:
        flash("删除教师失败，请检查数据库连接。", "error")
        return redirect(url_for("teachers.list_teachers"))

    flash("教师删除成功。", "success")
    return redirect(url_for("teachers.list_teachers"))


def _teacher_form():
    return {
        "teacher_no": request.form.get("teacher_no", "").strip(),
        "name": request.form.get("name", "").strip(),
        "department_id": request.form.get("department_id", "").strip(),
        "title_id": request.form.get("title_id", "").strip() or None,
        "phone": request.form.get("phone", "").strip(),
    }


def _validate_teacher(form):
    if not form["teacher_no"]:
        return "请输入教师编号。"
    if not form["name"]:
        return "请输入教师姓名。"
    if len(form["teacher_no"]) > 30:
        return "教师编号不能超过 30 个字符。"
    if len(form["name"]) > 50:
        return "教师姓名不能超过 50 个字符。"
    if len(form["phone"]) > 30:
        return "电话不能超过 30 个字符。"
    if not form["department_id"]:
        return "请选择所属院系。"
    try:
        int(form["department_id"])
    except ValueError:
        return "所属院系不合法。"
    if form["title_id"]:
        try:
            int(form["title_id"])
        except ValueError:
            return "职称不合法。"
    return None


def _load_options():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            return _list_departments(cursor), _list_titles(cursor)


def _list_departments(cursor):
    cursor.execute("SELECT department_id, department_name FROM department ORDER BY department_name")
    return cursor.fetchall()


def _list_titles(cursor):
    cursor.execute("SELECT title_id, title_name FROM title ORDER BY title_level, title_id")
    return cursor.fetchall()


def _get_teacher_or_none(teacher_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT teacher_id, teacher_no, name, department_id, title_id, phone
                FROM teacher
                WHERE teacher_id = %s
                """,
                (teacher_id,),
            )
            return cursor.fetchone()
