from pymysql.err import IntegrityError, MySQLError
from flask import Blueprint, flash, redirect, render_template, request, url_for

from models.db import get_connection
from routes.permissions import role_required


departments_bp = Blueprint("departments", __name__, url_prefix="/departments")


@departments_bp.route("/")
@role_required("admin")
def list_departments():
    keyword = request.args.get("keyword", "").strip()

    sql = """
        SELECT department_id, department_code, department_name,
               office_location, phone, created_at, updated_at
        FROM department
    """
    params = []

    if keyword:
        sql += """
            WHERE department_code LIKE %s
               OR department_name LIKE %s
               OR office_location LIKE %s
               OR phone LIKE %s
        """
        like_keyword = f"%{keyword}%"
        params = [like_keyword, like_keyword, like_keyword, like_keyword]

    sql += " ORDER BY department_id"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            departments = cursor.fetchall()

    return render_template(
        "departments/list.html",
        departments=departments,
        keyword=keyword,
    )


@departments_bp.route("/new", methods=["GET", "POST"])
@role_required("admin")
def create_department():
    if request.method == "POST":
        form = _department_form()
        error = _validate_department(form)

        if error:
            flash(error, "error")
            return render_template("departments/form.html", department=form, mode="new")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO department
                            (department_code, department_name, office_location, phone)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            form["department_code"],
                            form["department_name"],
                            form["office_location"],
                            form["phone"],
                        ),
                    )
                conn.commit()
        except IntegrityError:
            flash("院系代码或院系名称已存在。", "error")
            return render_template("departments/form.html", department=form, mode="new")
        except MySQLError:
            flash("新增院系失败，请检查数据库连接。", "error")
            return render_template("departments/form.html", department=form, mode="new")

        flash("院系新增成功。", "success")
        return redirect(url_for("departments.list_departments"))

    return render_template("departments/form.html", department={}, mode="new")


@departments_bp.route("/<int:department_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_department(department_id):
    department = _get_department_or_none(department_id)
    if not department:
        flash("院系不存在。", "error")
        return redirect(url_for("departments.list_departments"))

    if request.method == "POST":
        form = _department_form()
        form["department_id"] = department_id
        error = _validate_department(form)

        if error:
            flash(error, "error")
            return render_template("departments/form.html", department=form, mode="edit")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE department
                        SET department_code = %s,
                            department_name = %s,
                            office_location = %s,
                            phone = %s
                        WHERE department_id = %s
                        """,
                        (
                            form["department_code"],
                            form["department_name"],
                            form["office_location"],
                            form["phone"],
                            department_id,
                        ),
                    )
                conn.commit()
        except IntegrityError:
            flash("院系代码或院系名称已存在。", "error")
            return render_template("departments/form.html", department=form, mode="edit")
        except MySQLError:
            flash("修改院系失败，请检查数据库连接。", "error")
            return render_template("departments/form.html", department=form, mode="edit")

        flash("院系修改成功。", "success")
        return redirect(url_for("departments.list_departments"))

    return render_template("departments/form.html", department=department, mode="edit")


@departments_bp.route("/<int:department_id>/delete", methods=["POST"])
@role_required("admin")
def delete_department(department_id):
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM department WHERE department_id = %s",
                    (department_id,),
                )
            conn.commit()
    except IntegrityError:
        flash("该院系已被专业、课程、教师等数据引用，不能直接删除。", "error")
        return redirect(url_for("departments.list_departments"))
    except MySQLError:
        flash("删除院系失败，请检查数据库连接。", "error")
        return redirect(url_for("departments.list_departments"))

    flash("院系删除成功。", "success")
    return redirect(url_for("departments.list_departments"))


def _department_form():
    return {
        "department_code": request.form.get("department_code", "").strip(),
        "department_name": request.form.get("department_name", "").strip(),
        "office_location": request.form.get("office_location", "").strip(),
        "phone": request.form.get("phone", "").strip(),
    }


def _validate_department(form):
    if not form["department_code"]:
        return "请输入院系代码。"
    if not form["department_name"]:
        return "请输入院系名称。"
    if len(form["department_code"]) > 20:
        return "院系代码不能超过 20 个字符。"
    if len(form["department_name"]) > 100:
        return "院系名称不能超过 100 个字符。"
    if len(form["office_location"]) > 100:
        return "办公地点不能超过 100 个字符。"
    if len(form["phone"]) > 30:
        return "电话不能超过 30 个字符。"
    return None


def _get_department_or_none(department_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT department_id, department_code, department_name,
                       office_location, phone
                FROM department
                WHERE department_id = %s
                """,
                (department_id,),
            )
            return cursor.fetchone()
