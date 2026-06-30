from functools import wraps

from flask import flash, redirect, request, session, url_for


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("请先登录。", "error")
            return redirect(url_for("auth.login"))
        if session.get("must_change_password") and request.endpoint != "auth.change_password":
            flash("请先修改初始密码。", "info")
            return redirect(url_for("auth.change_password"))
        return view_func(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("请先登录。", "error")
                return redirect(url_for("auth.login"))
            if session.get("must_change_password") and request.endpoint != "auth.change_password":
                flash("请先修改初始密码。", "info")
                return redirect(url_for("auth.change_password"))

            if session.get("role") not in roles:
                flash("当前账号没有访问该功能的权限。", "error")
                return redirect(url_for("dashboard.dashboard"))

            return view_func(*args, **kwargs)

        return wrapper

    return decorator
