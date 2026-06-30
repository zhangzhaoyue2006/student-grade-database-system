from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Flask, request, session
from pymysql.err import MySQLError

from config import Config
from models.db import get_connection
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.departments import departments_bp
from routes.majors import majors_bp
from routes.courses import courses_bp
from routes.teachers import teachers_bp
from routes.students import students_bp
from routes.titles import titles_bp
from routes.teaching import teaching_bp
from routes.enrollments import enrollments_bp
from routes.grades import grades_bp
from routes.statistics import statistics_bp
from routes.teacher_portal import teacher_portal_bp
from routes.student_portal import student_portal_bp
from routes.system import system_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    @app.template_filter("score_int")
    def score_int(value):
        if value is None or value == "":
            return ""
        try:
            return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        except (InvalidOperation, ValueError, TypeError):
            return value

    @app.after_request
    def record_system_log(response):
        if request.method == "POST" and response.status_code in (302, 303):
            action = _audit_action_name(request.endpoint)
            if action:
                _write_system_log(
                    user_id=session.get("user_id"),
                    action=action,
                    detail=f"{request.method} {request.path}",
                )
        return response

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(departments_bp)
    app.register_blueprint(majors_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(teachers_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(titles_bp)
    app.register_blueprint(teaching_bp)
    app.register_blueprint(enrollments_bp)
    app.register_blueprint(grades_bp)
    app.register_blueprint(statistics_bp)
    app.register_blueprint(teacher_portal_bp)
    app.register_blueprint(student_portal_bp)
    app.register_blueprint(system_bp)

    return app


def _audit_action_name(endpoint):
    action_map = {
        "auth.login": "登录系统",
        "auth.change_password": "修改密码",
        "departments.create_department": "新增院系",
        "departments.edit_department": "修改院系",
        "departments.delete_department": "删除院系",
        "majors.create_major": "新增专业",
        "majors.edit_major": "修改专业",
        "majors.delete_major": "删除专业",
        "courses.create_course": "新增课程",
        "courses.edit_course": "修改课程",
        "courses.delete_course": "删除课程",
        "teachers.create_teacher": "新增教师",
        "teachers.edit_teacher": "修改教师",
        "teachers.delete_teacher": "删除教师",
        "titles.create_title": "新增职称",
        "titles.edit_title": "修改职称",
        "titles.delete_title": "删除职称",
        "students.create_student": "新增学生",
        "students.edit_student": "修改学生",
        "students.delete_student": "删除学生",
        "teaching.create_teaching": "新增授课安排",
        "teaching.edit_teaching": "修改授课安排",
        "teaching.delete_teaching": "删除授课安排",
        "enrollments.create_enrollment": "新增选课记录",
        "enrollments.edit_enrollment": "修改选课记录",
        "enrollments.delete_enrollment": "删除选课记录",
        "grades.create_grade": "录入成绩",
        "grades.edit_grade": "修改成绩",
        "grades.delete_grade": "删除成绩",
        "system.create_user": "新增用户账号",
        "system.edit_user": "修改用户账号",
        "system.reset_password": "重置用户密码",
        "system.toggle_user": "启用或停用用户账号",
    }
    return action_map.get(endpoint)


def _write_system_log(user_id, action, detail):
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO system_log (user_id, action, detail)
                    VALUES (%s, %s, %s)
                    """,
                    (user_id, action, detail[:255]),
                )
            conn.commit()
    except MySQLError:
        pass


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
