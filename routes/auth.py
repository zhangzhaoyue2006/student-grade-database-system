from pymysql.err import MySQLError
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from models.db import get_connection


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("请输入用户名和密码。", "error")
            return render_template("login.html")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT user_id, username, password_hash, role,
                               related_student_id, related_teacher_id, is_active,
                               must_change_password
                        FROM users
                        WHERE username = %s
                        """,
                        (username,),
                    )
                    user = cursor.fetchone()
        except MySQLError:
            flash("数据库连接失败，请先确认 MySQL 已启动并完成初始化。", "error")
            return render_template("login.html", username=username)

        if not user or not user["is_active"]:
            flash("用户名不存在或账号已停用。", "error")
            return render_template("login.html", username=username)

        if not check_password_hash(user["password_hash"], password):
            flash("密码错误。", "error")
            return render_template("login.html", username=username)

        session["user_id"] = user["user_id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["related_student_id"] = user["related_student_id"]
        session["related_teacher_id"] = user["related_teacher_id"]
        session["must_change_password"] = user["must_change_password"]

        if user["must_change_password"]:
            flash("请先修改初始密码。", "info")
            return redirect(url_for("auth.change_password"))

        flash("登录成功。", "success")
        return redirect(url_for("dashboard.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("已退出登录。", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    if "user_id" not in session:
        flash("请先登录。", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(new_password) < 6:
            flash("新密码长度不能少于 6 位。", "error")
            return render_template("change_password.html")
        if new_password != confirm_password:
            flash("两次输入的新密码不一致。", "error")
            return render_template("change_password.html")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT password_hash FROM users WHERE user_id = %s",
                        (session["user_id"],),
                    )
                    user = cursor.fetchone()

                    if not user or not check_password_hash(user["password_hash"], old_password):
                        flash("原密码错误。", "error")
                        return render_template("change_password.html")

                    cursor.execute(
                        """
                        UPDATE users
                        SET password_hash = %s,
                            must_change_password = 0
                        WHERE user_id = %s
                        """,
                        (generate_password_hash(new_password), session["user_id"]),
                    )
                conn.commit()
        except MySQLError:
            flash("修改密码失败，请检查数据库连接。", "error")
            return render_template("change_password.html")

        session["must_change_password"] = 0
        flash("密码修改成功。", "success")
        return redirect(url_for("dashboard.dashboard"))

    return render_template("change_password.html")
