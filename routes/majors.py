from pymysql.err import IntegrityError, MySQLError
from flask import Blueprint, flash, redirect, render_template, request, url_for

from models.db import get_connection
from routes.permissions import role_required


majors_bp = Blueprint("majors", __name__, url_prefix="/majors")


@majors_bp.route("/")
@role_required("admin")
def list_majors():
    keyword = request.args.get("keyword", "").strip()
    department_id = request.args.get("department_id", "").strip()

    sql = """
        SELECT m.major_id, m.major_name, m.department_id,
               m.bachelor_credit_req, m.master_credit_req, m.doctor_credit_req,
               m.updated_at, d.department_name
        FROM major m
        JOIN department d ON m.department_id = d.department_id
        WHERE 1 = 1
    """
    params = []

    if keyword:
        sql += " AND m.major_name LIKE %s"
        like_keyword = f"%{keyword}%"
        params.append(like_keyword)

    if department_id:
        sql += " AND m.department_id = %s"
        params.append(department_id)

    sql += " ORDER BY d.department_name, m.major_name"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            majors = cursor.fetchall()
            departments = _list_departments(cursor)

    return render_template(
        "majors/list.html",
        majors=majors,
        departments=departments,
        keyword=keyword,
        selected_department_id=department_id,
    )


@majors_bp.route("/new", methods=["GET", "POST"])
@role_required("admin")
def create_major():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            departments = _list_departments(cursor)

    if request.method == "POST":
        form = _major_form()
        error = _validate_major(form)

        if error:
            flash(error, "error")
            return render_template("majors/form.html", major=form, departments=departments, mode="new")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO major
                            (major_name, department_id, bachelor_credit_req,
                             master_credit_req, doctor_credit_req)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            form["major_name"],
                            form["department_id"],
                            form["bachelor_credit_req"],
                            form["master_credit_req"],
                            form["doctor_credit_req"],
                        ),
                    )
                conn.commit()
        except IntegrityError:
            flash("同一院系下已存在该专业名称。", "error")
            return render_template("majors/form.html", major=form, departments=departments, mode="new")
        except MySQLError:
            flash("新增专业失败，请检查数据库连接。", "error")
            return render_template("majors/form.html", major=form, departments=departments, mode="new")

        flash("专业新增成功。", "success")
        return redirect(url_for("majors.list_majors"))

    return render_template("majors/form.html", major={}, departments=departments, mode="new")


@majors_bp.route("/<int:major_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_major(major_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            major = _get_major_or_none(cursor, major_id)
            departments = _list_departments(cursor)

    if not major:
        flash("专业不存在。", "error")
        return redirect(url_for("majors.list_majors"))

    if request.method == "POST":
        form = _major_form()
        form["major_id"] = major_id
        error = _validate_major(form)

        if error:
            flash(error, "error")
            return render_template("majors/form.html", major=form, departments=departments, mode="edit")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE major
                        SET major_name = %s,
                            department_id = %s,
                            bachelor_credit_req = %s,
                            master_credit_req = %s,
                            doctor_credit_req = %s
                        WHERE major_id = %s
                        """,
                        (
                            form["major_name"],
                            form["department_id"],
                            form["bachelor_credit_req"],
                            form["master_credit_req"],
                            form["doctor_credit_req"],
                            major_id,
                        ),
                    )
                conn.commit()
        except IntegrityError:
            flash("同一院系下已存在该专业名称。", "error")
            return render_template("majors/form.html", major=form, departments=departments, mode="edit")
        except MySQLError:
            flash("修改专业失败，请检查数据库连接。", "error")
            return render_template("majors/form.html", major=form, departments=departments, mode="edit")

        flash("专业修改成功。", "success")
        return redirect(url_for("majors.list_majors"))

    return render_template("majors/form.html", major=major, departments=departments, mode="edit")


@majors_bp.route("/<int:major_id>/delete", methods=["POST"])
@role_required("admin")
def delete_major(major_id):
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM major WHERE major_id = %s", (major_id,))
            conn.commit()
    except IntegrityError:
        flash("该专业已被学生数据引用，不能直接删除。", "error")
        return redirect(url_for("majors.list_majors"))
    except MySQLError:
        flash("删除专业失败，请检查数据库连接。", "error")
        return redirect(url_for("majors.list_majors"))

    flash("专业删除成功。", "success")
    return redirect(url_for("majors.list_majors"))


def _major_form():
    return {
        "major_name": request.form.get("major_name", "").strip(),
        "department_id": request.form.get("department_id", "").strip(),
        "bachelor_credit_req": request.form.get("bachelor_credit_req", "0").strip(),
        "master_credit_req": request.form.get("master_credit_req", "0").strip(),
        "doctor_credit_req": request.form.get("doctor_credit_req", "0").strip(),
    }


def _validate_major(form):
    if not form["major_name"]:
        return "请输入专业名称。"
    if len(form["major_name"]) > 100:
        return "专业名称不能超过 100 个字符。"
    if not form["department_id"]:
        return "请选择所属院系。"

    try:
        int(form["department_id"])
    except ValueError:
        return "所属院系不合法。"

    for field, label in [
        ("bachelor_credit_req", "本科学分要求"),
        ("master_credit_req", "硕士学分要求"),
        ("doctor_credit_req", "博士学分要求"),
    ]:
        try:
            value = float(form[field])
        except ValueError:
            return f"{label}必须是数字。"
        if value < 0:
            return f"{label}不能小于 0。"

    return None


def _list_departments(cursor):
    cursor.execute(
        """
        SELECT department_id, department_name
        FROM department
        ORDER BY department_name
        """
    )
    return cursor.fetchall()


def _get_major_or_none(cursor, major_id):
    cursor.execute(
        """
        SELECT major_id, major_name, department_id,
               bachelor_credit_req, master_credit_req, doctor_credit_req
        FROM major
        WHERE major_id = %s
        """,
        (major_id,),
    )
    return cursor.fetchone()
