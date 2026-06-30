from flask import Blueprint, render_template, session

from routes.permissions import login_required


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    role = session.get("role")
    modules = {
        "admin": [
            ("院系管理", "/departments/"),
            ("专业管理", "/majors/"),
            ("课程管理", "/courses/"),
            ("教师管理", "/teachers/"),
            ("学生管理", "/students/"),
            ("授课管理", "/teaching/"),
            ("选课管理", "/enrollments/"),
            ("成绩查询", "/grades/"),
            ("统计分析", "/statistics/"),
            ("用户与系统管理", "/system/"),
        ],
        "teacher": [
            ("授课课程与学生名单", "/teacher/courses"),
            ("成绩录入与修改", "/grades/"),
            ("课程成绩统计", "/statistics/teacher"),
        ],
        "student": [
            ("个人信息", "/student/profile"),
            ("我的选课", "/student/courses"),
            ("我的成绩", "/grades/"),
        ],
    }.get(role, [])

    return render_template("dashboard.html", role=role, modules=modules)
