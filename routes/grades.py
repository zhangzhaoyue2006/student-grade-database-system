from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from pymysql.err import IntegrityError, MySQLError
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models.db import get_connection
from routes.permissions import login_required


grades_bp = Blueprint("grades", __name__, url_prefix="/grades")


@grades_bp.route("/")
@login_required
def list_grades():
    role = session.get("role")

    if role == "teacher":
        closed_semester = request.args.get("closed_semester", "").strip()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                open_courses = _list_teacher_courses(cursor, status="open")
                closed_semesters = _list_teacher_closed_semesters(cursor)
                closed_courses = (
                    _list_teacher_courses(cursor, status="closed", semester=closed_semester)
                    if closed_semester
                    else []
                )
        return render_template(
            "grades/list.html",
            role=role,
            open_courses=open_courses,
            closed_semesters=closed_semesters,
            closed_semester=closed_semester,
            closed_courses=closed_courses,
        )

    if role == "student":
        semester = request.args.get("semester", "").strip()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                semester_options = _list_student_closed_semesters(cursor, session.get("related_student_id"))
                grades = _list_student_closed_course_grades(cursor, session.get("related_student_id"), semester) if semester else []

        return render_template(
            "grades/list.html",
            role=role,
            grades=grades,
            semester=semester,
            semester_options=semester_options,
        )

    keyword = request.args.get("keyword", "").strip()
    semester = request.args.get("semester", "").strip()
    sql = """
        SELECT g.grade_id, g.student_id, g.course_id, g.semester, g.score, g.exam_type,
               s.student_no, s.name AS student_name,
               c.course_code, c.course_name
        FROM grade g
        JOIN student s ON g.student_id = s.student_id
        JOIN course c ON g.course_id = c.course_id
        WHERE 1 = 1
    """
    params = []

    if keyword:
        sql += """
            AND (s.student_no LIKE %s OR s.name LIKE %s
                 OR c.course_code LIKE %s OR c.course_name LIKE %s)
        """
        like_keyword = f"%{keyword}%"
        params.extend([like_keyword, like_keyword, like_keyword, like_keyword])

    if semester:
        sql += " AND g.semester = %s"
        params.append(semester)

    sql += " ORDER BY g.semester DESC, c.course_code, s.student_no"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            grades = cursor.fetchall()
            semester_options = _list_grade_semesters(cursor)

    return render_template(
        "grades/list.html",
        role=role,
        grades=grades,
        keyword=keyword,
        semester=semester,
        semester_options=semester_options,
    )


@grades_bp.route("/course/<int:course_id>/<path:semester>")
@login_required
def course_grades(course_id, semester):
    if session.get("role") != "teacher":
        flash("当前账号没有访问课程成绩管理的权限。", "error")
        return redirect(url_for("grades.list_grades"))
    if not _teacher_has_course(course_id, semester):
        flash("教师只能查看本人授课课程的成绩。", "error")
        return redirect(url_for("grades.list_grades"))

    keyword = request.args.get("keyword", "").strip()
    course = _get_teacher_course_or_none(course_id, semester)
    is_closed = course and course["course_status"] == "closed"

    sql = """
        SELECT g.grade_id, g.student_id, g.course_id, g.semester, g.score, g.exam_type,
               s.student_no, s.name AS student_name,
               c.course_code, c.course_name
        FROM grade g
        JOIN student s ON g.student_id = s.student_id
        JOIN course c ON g.course_id = c.course_id
        WHERE g.course_id = %s AND g.semester = %s
    """
    params = [course_id, semester]
    if keyword:
        sql += " AND (s.student_no LIKE %s OR s.name LIKE %s)"
        like_keyword = f"%{keyword}%"
        params.extend([like_keyword, like_keyword])
    sql += " ORDER BY s.student_no, g.exam_type"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            grades = cursor.fetchall()

    return render_template(
        "grades/course.html",
        course=course,
        grades=grades,
        keyword=keyword,
        is_closed=is_closed,
    )


@grades_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_grade():
    if session.get("role") != "teacher":
        flash("当前账号没有录入成绩的权限。", "error")
        return redirect(url_for("grades.list_grades"))

    preset_course_id = request.args.get("course_id", "").strip()
    preset_semester = request.args.get("semester", "").strip()
    if not preset_course_id or not preset_semester:
        flash("请先选择课程，再录入成绩。", "error")
        return redirect(url_for("grades.list_grades"))
    if not _teacher_has_course(preset_course_id, preset_semester):
        flash("教师只能录入本人授课课程的成绩。", "error")
        return redirect(url_for("grades.list_grades"))
    if _course_is_closed(preset_course_id, preset_semester):
        flash("该课程已结课，不能再录入成绩。", "error")
        return redirect(url_for("grades.course_grades", course_id=preset_course_id, semester=preset_semester))

    students = _load_enrolled_students(preset_course_id, preset_semester)
    course = _get_teacher_course_or_none(preset_course_id, preset_semester)

    if request.method == "POST":
        form = _grade_form()
        form["course_id"] = preset_course_id
        form["semester"] = preset_semester
        error = _validate_grade(form)
        if not error and not _student_has_course(form["student_id"], preset_course_id, preset_semester):
            error = "该学生在该学期没有这门课程的有效选课记录。"

        if error:
            flash(error, "error")
            return render_template("grades/form.html", grade=form, students=students, course=course, mode="new")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO grade (student_id, course_id, semester, score, exam_type)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (form["student_id"], preset_course_id, preset_semester, form["score"], form["exam_type"]),
                    )
                    _sync_enrollment_status_after_grade_change(
                        cursor,
                        form["student_id"],
                        preset_course_id,
                        preset_semester,
                    )
                conn.commit()
        except IntegrityError:
            flash("该学生该课程该学期该考试类型已有成绩记录。", "error")
            return render_template("grades/form.html", grade=form, students=students, course=course, mode="new")
        except MySQLError:
            flash("录入成绩失败，请检查数据库连接。", "error")
            return render_template("grades/form.html", grade=form, students=students, course=course, mode="new")

        flash("成绩录入成功。", "success")
        return redirect(url_for("grades.course_grades", course_id=preset_course_id, semester=preset_semester))

    return render_template(
        "grades/form.html",
        grade={"course_id": preset_course_id, "semester": preset_semester},
        students=students,
        course=course,
        mode="new",
    )


@grades_bp.route("/<int:grade_id>/edit", methods=["GET", "POST"])
@login_required
def edit_grade(grade_id):
    if session.get("role") != "teacher":
        flash("当前账号没有修改成绩的权限。", "error")
        return redirect(url_for("grades.list_grades"))

    grade = _get_grade_or_none(grade_id)
    if not grade:
        flash("成绩记录不存在。", "error")
        return redirect(url_for("grades.list_grades"))
    if not _teacher_has_course(grade["course_id"], grade["semester"]):
        flash("教师只能修改本人授课课程的成绩。", "error")
        return redirect(url_for("grades.list_grades"))
    if _course_is_closed(grade["course_id"], grade["semester"]):
        flash("该课程已结课，不能再修改成绩。", "error")
        return redirect(url_for("grades.course_grades", course_id=grade["course_id"], semester=grade["semester"]))

    students = _load_enrolled_students(grade["course_id"], grade["semester"])
    course = _get_teacher_course_or_none(grade["course_id"], grade["semester"])

    if request.method == "POST":
        form = _grade_form()
        form["course_id"] = str(grade["course_id"])
        form["semester"] = grade["semester"]
        old_student_id = grade["student_id"]
        error = _validate_grade(form)
        if not error and not _student_has_course(form["student_id"], grade["course_id"], grade["semester"]):
            error = "该学生在该学期没有这门课程的有效选课记录。"

        if error:
            flash(error, "error")
            return render_template("grades/form.html", grade=form, students=students, course=course, mode="edit")

        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE grade
                        SET student_id = %s, score = %s, exam_type = %s
                        WHERE grade_id = %s
                        """,
                        (form["student_id"], form["score"], form["exam_type"], grade_id),
                    )
                    _sync_enrollment_status_after_grade_change(
                        cursor,
                        old_student_id,
                        grade["course_id"],
                        grade["semester"],
                    )
                    _sync_enrollment_status_after_grade_change(
                        cursor,
                        form["student_id"],
                        grade["course_id"],
                        grade["semester"],
                    )
                conn.commit()
        except IntegrityError:
            flash("该成绩记录已存在。", "error")
            return render_template("grades/form.html", grade=form, students=students, course=course, mode="edit")
        except MySQLError:
            flash("修改成绩失败，请检查数据库连接。", "error")
            return render_template("grades/form.html", grade=form, students=students, course=course, mode="edit")

        flash("成绩修改成功。", "success")
        return redirect(url_for("grades.course_grades", course_id=grade["course_id"], semester=grade["semester"]))

    return render_template("grades/form.html", grade=grade, students=students, course=course, mode="edit")


@grades_bp.route("/<int:grade_id>/delete", methods=["POST"])
@login_required
def delete_grade(grade_id):
    if session.get("role") != "teacher":
        flash("当前账号没有删除成绩的权限。", "error")
        return redirect(url_for("grades.list_grades"))

    grade = _get_grade_or_none(grade_id)
    if not grade:
        flash("成绩记录不存在。", "error")
        return redirect(url_for("grades.list_grades"))
    if not _teacher_has_course(grade["course_id"], grade["semester"]):
        flash("教师只能删除本人授课课程的成绩。", "error")
        return redirect(url_for("grades.list_grades"))
    if _course_is_closed(grade["course_id"], grade["semester"]):
        flash("该课程已结课，不能再删除成绩。", "error")
        return redirect(url_for("grades.course_grades", course_id=grade["course_id"], semester=grade["semester"]))

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM grade WHERE grade_id = %s", (grade_id,))
                _sync_enrollment_status_after_grade_change(
                    cursor,
                    grade["student_id"],
                    grade["course_id"],
                    grade["semester"],
                )
            conn.commit()
    except MySQLError:
        flash("删除成绩失败，请检查数据库连接。", "error")
        return redirect(url_for("grades.course_grades", course_id=grade["course_id"], semester=grade["semester"]))

    flash("成绩删除成功。", "success")
    return redirect(url_for("grades.course_grades", course_id=grade["course_id"], semester=grade["semester"]))


def _grade_form():
    return {
        "student_id": request.form.get("student_id", "").strip(),
        "course_id": request.form.get("course_id", "").strip(),
        "semester": request.form.get("semester", "").strip(),
        "score": request.form.get("score", "").strip(),
        "exam_type": request.form.get("exam_type", "").strip(),
    }


def _validate_grade(form):
    if not form["student_id"]:
        return "请选择学生。"
    if not form["score"]:
        return "请输入成绩。"
    if form["exam_type"] not in ("正考", "补考", "重修"):
        return "请选择合法的考试类型。"
    try:
        score = Decimal(form["score"])
    except InvalidOperation:
        return "成绩必须是数字。"
    if score < 0 or score > 100:
        return "成绩必须在 0 到 100 之间。"
    form["score"] = str(score.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return None


def _list_teacher_courses(cursor, status, semester=None):
    sql = """
        SELECT DISTINCT c.course_id, c.course_code, c.course_name,
               tc.semester, tc.course_status
        FROM teacher_course tc
        JOIN course c ON tc.course_id = c.course_id
        WHERE tc.teacher_id = %s
          AND tc.course_status = %s
    """
    params = [session.get("related_teacher_id"), status]
    if semester:
        sql += " AND tc.semester = %s"
        params.append(semester)
    sql += " ORDER BY tc.semester DESC, c.course_code"
    cursor.execute(sql, params)
    return cursor.fetchall()


def _list_teacher_closed_semesters(cursor):
    cursor.execute(
        """
        SELECT DISTINCT semester
        FROM teacher_course
        WHERE teacher_id = %s
          AND course_status = 'closed'
        ORDER BY semester DESC
        """,
        (session.get("related_teacher_id"),),
    )
    return cursor.fetchall()


def _list_grade_semesters(cursor):
    cursor.execute("SELECT DISTINCT semester FROM grade ORDER BY semester DESC")
    return cursor.fetchall()


def _list_student_closed_semesters(cursor, student_id):
    cursor.execute(
        """
        SELECT DISTINCT sc.semester
        FROM student_course sc
        WHERE sc.student_id = %s
          AND sc.enroll_status <> '退课'
          AND EXISTS (
              SELECT 1
              FROM teacher_course tc
              WHERE tc.course_id = sc.course_id
                AND tc.semester = sc.semester
                AND tc.course_status = 'closed'
          )
        ORDER BY sc.semester DESC
        """,
        (student_id,),
    )
    return cursor.fetchall()


def _list_student_closed_course_grades(cursor, student_id, semester):
    cursor.execute(
        """
        SELECT sc.student_id, sc.course_id, sc.semester,
               c.course_code, c.course_name,
               best.best_score AS score
        FROM student_course sc
        JOIN course c ON sc.course_id = c.course_id
        LEFT JOIN (
            SELECT student_id, course_id, semester, MAX(score) AS best_score
            FROM grade
            WHERE student_id = %s
            GROUP BY student_id, course_id, semester
        ) best ON best.student_id = sc.student_id
              AND best.course_id = sc.course_id
              AND best.semester = sc.semester
        WHERE sc.student_id = %s
          AND sc.semester = %s
          AND sc.enroll_status <> '退课'
          AND EXISTS (
              SELECT 1
              FROM teacher_course tc
              WHERE tc.course_id = sc.course_id
                AND tc.semester = sc.semester
                AND tc.course_status = 'closed'
          )
        ORDER BY c.course_code
        """,
        (student_id, student_id, semester),
    )
    return cursor.fetchall()


def _load_enrolled_students(course_id, semester):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.student_id, s.student_no, s.name
                FROM student_course sc
                JOIN student s ON sc.student_id = s.student_id
                WHERE sc.course_id = %s
                  AND sc.semester = %s
                  AND sc.enroll_status <> '退课'
                ORDER BY s.student_no
                """,
                (course_id, semester),
            )
            return cursor.fetchall()


def _student_has_course(student_id, course_id, semester):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM student_course
                WHERE student_id = %s AND course_id = %s AND semester = %s
                  AND enroll_status <> '退课'
                """,
                (student_id, course_id, semester),
            )
            return cursor.fetchone() is not None


def _teacher_has_course(course_id, semester):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM teacher_course
                WHERE teacher_id = %s AND course_id = %s AND semester = %s
                """,
                (session.get("related_teacher_id"), course_id, semester),
            )
            return cursor.fetchone() is not None


def _course_is_closed(course_id, semester):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM teacher_course
                WHERE course_id = %s
                  AND semester = %s
                  AND course_status = 'closed'
                LIMIT 1
                """,
                (course_id, semester),
            )
            return cursor.fetchone() is not None


def _get_teacher_course_or_none(course_id, semester):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.course_id, c.course_code, c.course_name,
                       tc.semester, tc.teaching_role, tc.course_status
                FROM teacher_course tc
                JOIN course c ON tc.course_id = c.course_id
                WHERE tc.teacher_id = %s
                  AND tc.course_id = %s
                  AND tc.semester = %s
                """,
                (session.get("related_teacher_id"), course_id, semester),
            )
            return cursor.fetchone()


def _get_grade_or_none(grade_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT grade_id, student_id, course_id, semester, score, exam_type
                FROM grade
                WHERE grade_id = %s
                """,
                (grade_id,),
            )
            return cursor.fetchone()


def _sync_enrollment_status_after_grade_change(cursor, student_id, course_id, semester):
    cursor.execute(
        """
        SELECT 1
        FROM grade
        WHERE student_id = %s AND course_id = %s AND semester = %s
        LIMIT 1
        """,
        (student_id, course_id, semester),
    )
    target_status = "已完成" if cursor.fetchone() else "已选"
    cursor.execute(
        """
        UPDATE student_course
        SET enroll_status = %s
        WHERE student_id = %s AND course_id = %s AND semester = %s
          AND enroll_status <> '退课'
        """,
        (target_status, student_id, course_id, semester),
    )
