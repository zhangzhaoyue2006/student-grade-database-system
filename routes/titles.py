from pymysql.err import IntegrityError, MySQLError
from flask import Blueprint, flash, redirect, render_template, request, url_for

from models.db import get_connection
from routes.permissions import role_required


titles_bp = Blueprint("titles", __name__, url_prefix="/titles")


@titles_bp.route("/")
@role_required("admin")
def list_titles():
    keyword = request.args.get("keyword", "").strip()

    sql = """
        SELECT title_id, title_name, title_level, updated_at
        FROM title
    """
    params = []

    if keyword:
        sql += " WHERE title_name LIKE %s"
        params.append(f"%{keyword}%")

    sql += " ORDER BY title_level, title_id"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            titles = cursor.fetchall()

    return render_template("titles/list.html", titles=titles, keyword=keyword)


@titles_bp.route("/new", methods=["GET", "POST"])
@role_required("admin")
def create_title():
    if request.method == "POST":
        form = _title_form()
        error = _validate_title(form)

        if error:
            flash(error, "error")
            return render_template("titles/form.html", title=form, mode="new")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO title (title_name, title_level) VALUES (%s, %s)",
                        (form["title_name"], form["title_level"]),
                    )
                conn.commit()
        except IntegrityError:
            flash("职称名称已存在。", "error")
            return render_template("titles/form.html", title=form, mode="new")
        except MySQLError:
            flash("新增职称失败，请检查数据库连接。", "error")
            return render_template("titles/form.html", title=form, mode="new")

        flash("职称新增成功。", "success")
        return redirect(url_for("titles.list_titles"))

    return render_template("titles/form.html", title={}, mode="new")


@titles_bp.route("/<int:title_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_title(title_id):
    title = _get_title_or_none(title_id)
    if not title:
        flash("职称不存在。", "error")
        return redirect(url_for("titles.list_titles"))

    if request.method == "POST":
        form = _title_form()
        form["title_id"] = title_id
        error = _validate_title(form)

        if error:
            flash(error, "error")
            return render_template("titles/form.html", title=form, mode="edit")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE title
                        SET title_name = %s,
                            title_level = %s
                        WHERE title_id = %s
                        """,
                        (form["title_name"], form["title_level"], title_id),
                    )
                conn.commit()
        except IntegrityError:
            flash("职称名称已存在。", "error")
            return render_template("titles/form.html", title=form, mode="edit")
        except MySQLError:
            flash("修改职称失败，请检查数据库连接。", "error")
            return render_template("titles/form.html", title=form, mode="edit")

        flash("职称修改成功。", "success")
        return redirect(url_for("titles.list_titles"))

    return render_template("titles/form.html", title=title, mode="edit")


@titles_bp.route("/<int:title_id>/delete", methods=["POST"])
@role_required("admin")
def delete_title(title_id):
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM title WHERE title_id = %s", (title_id,))
            conn.commit()
    except IntegrityError:
        flash("该职称已被教师数据引用，不能直接删除。", "error")
        return redirect(url_for("titles.list_titles"))
    except MySQLError:
        flash("删除职称失败，请检查数据库连接。", "error")
        return redirect(url_for("titles.list_titles"))

    flash("职称删除成功。", "success")
    return redirect(url_for("titles.list_titles"))


def _title_form():
    return {
        "title_name": request.form.get("title_name", "").strip(),
        "title_level": request.form.get("title_level", "").strip(),
    }


def _validate_title(form):
    if not form["title_name"]:
        return "请输入职称名称。"
    if len(form["title_name"]) > 50:
        return "职称名称不能超过 50 个字符。"
    try:
        level = int(form["title_level"])
    except ValueError:
        return "职称级别必须是整数。"
    if level <= 0:
        return "职称级别必须大于 0。"
    return None


def _get_title_or_none(title_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT title_id, title_name, title_level
                FROM title
                WHERE title_id = %s
                """,
                (title_id,),
            )
            return cursor.fetchone()
