from pymysql.err import IntegrityError, MySQLError
from flask import Blueprint, flash, redirect, render_template, request, url_for

from models.db import get_connection
from routes.permissions import role_required


students_bp = Blueprint("students", __name__, url_prefix="/students")


@students_bp.route("/")
@role_required("admin")
def list_students():
    keyword = request.args.get("keyword", "").strip()
    grade_year = request.args.get("grade_year", "").strip()
    degree_level = request.args.get("degree_level", "").strip()

    sql = """
        SELECT s.student_id, s.student_no, s.name, s.gender, s.phone, s.grade_year,
               s.degree_level, s.updated_at,
               m.major_name, d.department_name,
               mm.major_name AS minor_name
        FROM student s
        JOIN major m ON s.major_id = m.major_id
        JOIN department d ON m.department_id = d.department_id
        LEFT JOIN major mm ON s.minor_id = mm.major_id
        WHERE 1 = 1
    """
    params = []

    if keyword:
        sql += " AND (s.student_no LIKE %s OR s.name LIKE %s OR d.department_name LIKE %s OR m.major_name LIKE %s)"
        like_keyword = f"%{keyword}%"
        params.extend([like_keyword, like_keyword, like_keyword, like_keyword])

    if grade_year:
        sql += " AND s.grade_year = %s"
        params.append(grade_year)

    if degree_level:
        sql += " AND s.degree_level = %s"
        params.append(degree_level)

    sql += " ORDER BY s.student_no"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            students = cursor.fetchall()
            for student in students:
                student["completed_credits"] = _calculate_completed_credits(cursor, student["student_id"])
            grade_options = _list_grade_years(cursor)

    return render_template(
        "students/list.html",
        students=students,
        grade_options=grade_options,
        keyword=keyword,
        selected_grade_year=grade_year,
        selected_degree_level=degree_level,
    )


@students_bp.route("/new", methods=["GET", "POST"])
@role_required("admin")
def create_student():
    majors = _load_majors()

    if request.method == "POST":
        form = _student_form()
        error = _validate_student(form)

        if error:
            flash(error, "error")
            return render_template("students/form.html", student=form, majors=majors, mode="new")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO student
                            (student_no, name, id_card, gender, birth_date, dormitory,
                             home_address, phone, grade_year, major_id, minor_id,
                             degree_level)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        _student_values(form),
                    )
                conn.commit()
        except IntegrityError:
            flash("学号或身份证号已存在，或所选专业不合法。", "error")
            return render_template("students/form.html", student=form, majors=majors, mode="new")
        except MySQLError:
            flash("新增学生失败，请检查数据库连接。", "error")
            return render_template("students/form.html", student=form, majors=majors, mode="new")

        flash("学生新增成功。", "success")
        return redirect(url_for("students.list_students"))

    return render_template("students/form.html", student={}, majors=majors, mode="new")


@students_bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_student(student_id):
    majors = _load_majors()
    student = _get_student_or_none(student_id)

    if not student:
        flash("学生不存在。", "error")
        return redirect(url_for("students.list_students"))

    if request.method == "POST":
        form = _student_form()
        form["student_id"] = student_id
        error = _validate_student(form)

        if error:
            flash(error, "error")
            return render_template("students/form.html", student=form, majors=majors, mode="edit")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE student
                        SET student_no = %s,
                            name = %s,
                            id_card = %s,
                            gender = %s,
                            birth_date = %s,
                            dormitory = %s,
                            home_address = %s,
                            phone = %s,
                            grade_year = %s,
                            major_id = %s,
                            minor_id = %s,
                            degree_level = %s
                        WHERE student_id = %s
                        """,
                        _student_values(form) + (student_id,),
                    )
                conn.commit()
        except IntegrityError:
            flash("学号或身份证号已存在，或所选专业不合法。", "error")
            return render_template("students/form.html", student=form, majors=majors, mode="edit")
        except MySQLError:
            flash("修改学生失败，请检查数据库连接。", "error")
            return render_template("students/form.html", student=form, majors=majors, mode="edit")

        flash("学生修改成功。", "success")
        return redirect(url_for("students.list_students"))

    return render_template("students/form.html", student=student, majors=majors, mode="edit")


@students_bp.route("/<int:student_id>/delete", methods=["POST"])
@role_required("admin")
def delete_student(student_id):
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM student WHERE student_id = %s", (student_id,))
            conn.commit()
    except IntegrityError:
        flash("该学生已被选课、成绩或用户账号引用，不能直接删除。", "error")
        return redirect(url_for("students.list_students"))
    except MySQLError:
        flash("删除学生失败，请检查数据库连接。", "error")
        return redirect(url_for("students.list_students"))

    flash("学生删除成功。", "success")
    return redirect(url_for("students.list_students"))


def _student_form():
    return {
        "student_no": request.form.get("student_no", "").strip(),
        "name": request.form.get("name", "").strip(),
        "id_card": request.form.get("id_card", "").strip(),
        "gender": request.form.get("gender", "").strip(),
        "birth_date": request.form.get("birth_date", "").strip() or None,
        "dormitory": request.form.get("dormitory", "").strip(),
        "home_address": request.form.get("home_address", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "grade_year": request.form.get("grade_year", "").strip(),
        "major_id": request.form.get("major_id", "").strip(),
        "minor_id": request.form.get("minor_id", "").strip() or None,
        "degree_level": request.form.get("degree_level", "").strip(),
    }


def _student_values(form):
    return (
        form["student_no"],
        form["name"],
        form["id_card"],
        form["gender"],
        form["birth_date"],
        form["dormitory"],
        form["home_address"],
        form["phone"],
        form["grade_year"],
        form["major_id"],
        form["minor_id"],
        form["degree_level"],
    )


def _validate_student(form):
    required = [
        ("student_no", "请输入学号。"),
        ("name", "请输入姓名。"),
        ("id_card", "请输入身份证号。"),
        ("gender", "请选择性别。"),
        ("grade_year", "请输入年级。"),
        ("major_id", "请选择主修专业。"),
        ("degree_level", "请选择学位等级。"),
    ]
    for field, message in required:
        if not form[field]:
            return message

    if form["gender"] not in ("男", "女"):
        return "请选择合法的性别。"
    if form["degree_level"] not in ("本科", "硕士", "博士"):
        return "请选择合法的学位等级。"

    try:
        year = int(form["grade_year"])
    except ValueError:
        return "年级必须是整数。"
    if year < 2000 or year > 2100:
        return "年级必须在 2000 到 2100 之间。"

    try:
        int(form["major_id"])
    except ValueError:
        return "主修专业不合法。"

    if form["minor_id"]:
        try:
            int(form["minor_id"])
        except ValueError:
            return "辅修专业不合法。"
        if form["minor_id"] == form["major_id"]:
            return "辅修专业不能和主修专业相同。"

    return None


def _load_majors():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            return _list_majors(cursor)


def _list_majors(cursor):
    cursor.execute(
        """
        SELECT m.major_id, m.major_name, d.department_name
        FROM major m
        JOIN department d ON m.department_id = d.department_id
        ORDER BY d.department_name, m.major_name
        """
    )
    return cursor.fetchall()


def _list_grade_years(cursor):
    cursor.execute(
        """
        SELECT DISTINCT grade_year
        FROM student
        ORDER BY grade_year DESC
        """
    )
    return cursor.fetchall()


def _get_student_or_none(student_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT student_id, student_no, name, id_card, gender, birth_date,
                       dormitory, home_address, phone, grade_year, major_id, minor_id,
                       degree_level
                FROM student
                WHERE student_id = %s
                """,
                (student_id,),
            )
            student = cursor.fetchone()
            if student:
                student["completed_credits"] = _calculate_completed_credits(cursor, student_id)
            return student


def _calculate_completed_credits(cursor, student_id):
    cursor.execute(
        """
        SELECT COALESCE(SUM(passed_course.credits), 0) AS completed_credits
        FROM (
            SELECT c.course_id, MAX(c.credits) AS credits
            FROM grade g
            JOIN course c ON g.course_id = c.course_id
            WHERE g.student_id = %s
              AND g.score >= 60
              AND EXISTS (
                  SELECT 1
                  FROM teacher_course tc
                  WHERE tc.course_id = g.course_id
                    AND tc.semester = g.semester
                    AND tc.course_status = 'closed'
              )
            GROUP BY c.course_id
        ) AS passed_course
        """,
        (student_id,),
    )
    return cursor.fetchone()["completed_credits"]
