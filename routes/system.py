from pymysql.err import IntegrityError, MySQLError
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from models.db import get_connection
from routes.permissions import role_required


system_bp = Blueprint("system", __name__, url_prefix="/system")


@system_bp.route("/")
@role_required("admin")
def index():
    return render_template("system/index.html")


@system_bp.route("/users")
@role_required("admin")
def users():
    keyword = request.args.get("keyword", "").strip()
    role = request.args.get("role", "").strip()

    sql = """
        SELECT u.user_id, u.username, u.role, u.is_active, u.created_at, u.updated_at,
               u.must_change_password,
               s.student_no, s.name AS student_name,
               t.teacher_no, t.name AS teacher_name
        FROM users u
        LEFT JOIN student s ON u.related_student_id = s.student_id
        LEFT JOIN teacher t ON u.related_teacher_id = t.teacher_id
        WHERE 1 = 1
    """
    params = []

    if keyword:
        sql += """
            AND (u.username LIKE %s OR s.student_no LIKE %s OR s.name LIKE %s
                 OR t.teacher_no LIKE %s OR t.name LIKE %s)
        """
        like_keyword = f"%{keyword}%"
        params.extend([like_keyword, like_keyword, like_keyword, like_keyword, like_keyword])

    if role:
        sql += " AND u.role = %s"
        params.append(role)

    sql += " ORDER BY u.user_id"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            users = cursor.fetchall()

    return render_template(
        "system/users.html",
        users=users,
        keyword=keyword,
        selected_role=role,
        current_user_id=session.get("user_id"),
    )


@system_bp.route("/users/new", methods=["GET", "POST"])
@role_required("admin")
def create_user():
    students, teachers = _load_bind_options()

    if request.method == "POST":
        form = _user_form()
        error = _validate_user(form, is_new=True)
        if error:
            flash(error, "error")
            return render_template("system/user_form.html", user=form, students=students, teachers=teachers, mode="new")

        related_student_id, related_teacher_id = _binding_values(form)

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users
                            (username, password_hash, role, related_student_id,
                             related_teacher_id, is_active, must_change_password)
                        VALUES (%s, %s, %s, %s, %s, 1, 1)
                        """,
                        (
                            form["username"],
                            generate_password_hash(form["password"]),
                            form["role"],
                            related_student_id,
                            related_teacher_id,
                        ),
                    )
                conn.commit()
        except IntegrityError:
            flash("用户名已存在，或绑定对象不合法。", "error")
            return render_template("system/user_form.html", user=form, students=students, teachers=teachers, mode="new")
        except MySQLError:
            flash("新增用户失败，请检查数据库连接。", "error")
            return render_template("system/user_form.html", user=form, students=students, teachers=teachers, mode="new")

        flash("用户新增成功。", "success")
        return redirect(url_for("system.users"))

    return render_template("system/user_form.html", user={}, students=students, teachers=teachers, mode="new")


@system_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_user(user_id):
    students, teachers = _load_bind_options()
    user = _get_user_or_none(user_id)
    if not user:
        flash("用户不存在。", "error")
        return redirect(url_for("system.users"))

    if request.method == "POST":
        form = _user_form()
        form["user_id"] = user_id
        error = _validate_user(form, is_new=False)
        if not error and user_id == session.get("user_id") and form["role"] != "admin":
            error = "不能修改当前登录账号的管理员角色。"
        if (
            not error
            and user["role"] == "admin"
            and form["role"] != "admin"
            and user["is_active"]
            and _active_admin_count() <= 1
        ):
            error = "系统至少需要保留一个启用中的管理员账号。"
        if error:
            flash(error, "error")
            return render_template(
                "system/user_form.html",
                user=form,
                students=students,
                teachers=teachers,
                mode="edit",
                is_self=user_id == session.get("user_id"),
            )

        related_student_id, related_teacher_id = _binding_values(form)

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE users
                        SET username = %s,
                            role = %s,
                            related_student_id = %s,
                            related_teacher_id = %s
                        WHERE user_id = %s
                        """,
                        (
                            form["username"],
                            form["role"],
                            related_student_id,
                            related_teacher_id,
                            user_id,
                        ),
                    )
                conn.commit()
        except IntegrityError:
            flash("用户名已存在，或绑定对象不合法。", "error")
            return render_template("system/user_form.html", user=form, students=students, teachers=teachers, mode="edit")
        except MySQLError:
            flash("修改用户失败，请检查数据库连接。", "error")
            return render_template("system/user_form.html", user=form, students=students, teachers=teachers, mode="edit")

        flash("用户修改成功。", "success")
        return redirect(url_for("system.users"))

    return render_template(
        "system/user_form.html",
        user=user,
        students=students,
        teachers=teachers,
        mode="edit",
        is_self=user_id == session.get("user_id"),
    )


@system_bp.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
@role_required("admin")
def reset_password(user_id):
    user = _get_user_or_none(user_id)
    if not user:
        flash("用户不存在。", "error")
        return redirect(url_for("system.users"))
    if user_id == session.get("user_id"):
        flash("当前账号请通过右上角“修改密码”功能修改自己的密码。", "error")
        return redirect(url_for("system.users"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if len(password) < 6:
            flash("新密码长度不能少于 6 位。", "error")
            return render_template("system/reset_password.html", user=user)
        if password != confirm_password:
            flash("两次输入的密码不一致。", "error")
            return render_template("system/reset_password.html", user=user)

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE users
                    SET password_hash = %s,
                        must_change_password = 1
                    WHERE user_id = %s
                    """,
                    (generate_password_hash(password), user_id),
                )
            conn.commit()

        flash("密码重置成功。", "success")
        return redirect(url_for("system.users"))

    return render_template("system/reset_password.html", user=user)


@system_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@role_required("admin")
def toggle_user(user_id):
    user = _get_user_or_none(user_id)
    if not user:
        flash("用户不存在。", "error")
        return redirect(url_for("system.users"))
    if user_id == session.get("user_id"):
        flash("不能停用当前登录账号。", "error")
        return redirect(url_for("system.users"))
    if user["role"] == "admin" and user["is_active"] and _active_admin_count() <= 1:
        flash("系统至少需要保留一个启用中的管理员账号。", "error")
        return redirect(url_for("system.users"))

    new_status = 0 if user["is_active"] else 1
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET is_active = %s WHERE user_id = %s", (new_status, user_id))
        conn.commit()

    flash("账号状态已更新。", "success")
    return redirect(url_for("system.users"))


@system_bp.route("/permissions")
@role_required("admin")
def permissions():
    return render_template("system/permissions.html")


@system_bp.route("/logs")
@role_required("admin")
def logs():
    keyword = request.args.get("keyword", "").strip()
    sql = """
        SELECT l.log_id, l.action, l.detail, l.created_at, u.username
        FROM system_log l
        LEFT JOIN users u ON l.user_id = u.user_id
        WHERE 1 = 1
    """
    params = []

    if keyword:
        sql += " AND (u.username LIKE %s OR l.action LIKE %s OR l.detail LIKE %s)"
        like_keyword = f"%{keyword}%"
        params.extend([like_keyword, like_keyword, like_keyword])

    sql += " ORDER BY l.created_at DESC, l.log_id DESC LIMIT 200"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            logs = cursor.fetchall()

    return render_template("system/logs.html", logs=logs, keyword=keyword)


@system_bp.route("/backup")
@role_required("admin")
def backup():
    return render_template("system/backup.html")


def _user_form():
    return {
        "username": request.form.get("username", "").strip(),
        "password": request.form.get("password", ""),
        "confirm_password": request.form.get("confirm_password", ""),
        "role": request.form.get("role", "").strip(),
        "related_student_id": request.form.get("related_student_id", "").strip(),
        "related_teacher_id": request.form.get("related_teacher_id", "").strip(),
    }


def _validate_user(form, is_new):
    if not form["username"]:
        return "请输入用户名。"
    if len(form["username"]) > 50:
        return "用户名不能超过 50 个字符。"
    if form["role"] not in ("admin", "teacher", "student"):
        return "请选择合法的角色。"
    if is_new:
        if len(form["password"]) < 6:
            return "密码长度不能少于 6 位。"
        if form["password"] != form["confirm_password"]:
            return "两次输入的密码不一致。"
    if form["role"] == "teacher" and not form["related_teacher_id"]:
        return "教师账号必须绑定教师。"
    if form["role"] == "student" and not form["related_student_id"]:
        return "学生账号必须绑定学生。"
    return None


def _binding_values(form):
    related_student_id = form["related_student_id"] if form["role"] == "student" else None
    related_teacher_id = form["related_teacher_id"] if form["role"] == "teacher" else None
    return related_student_id, related_teacher_id


def _load_bind_options():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT student_id, student_no, name FROM student ORDER BY student_no")
            students = cursor.fetchall()
            cursor.execute("SELECT teacher_id, teacher_no, name FROM teacher ORDER BY teacher_no")
            teachers = cursor.fetchall()
    return students, teachers


def _get_user_or_none(user_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, username, role, related_student_id, related_teacher_id,
                       is_active, must_change_password
                FROM users
                WHERE user_id = %s
                """,
                (user_id,),
            )
            return cursor.fetchone()


def _active_admin_count():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM users
                WHERE role = 'admin' AND is_active = 1
                """
            )
            return cursor.fetchone()["total"]
