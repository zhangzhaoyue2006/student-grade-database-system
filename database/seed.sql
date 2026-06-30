SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

USE student_grade_system;

INSERT INTO department (department_code, department_name, office_location, phone) VALUES
('CS', '计算机科学与技术学院', '信息楼 A301', '010-10000001'),
('DATA', '大数据学院', '数据楼 B205', '010-10000002'),
('MATH', '数学学院', '理科楼 C402', '010-10000003');

INSERT INTO major (
    major_name, department_id, bachelor_credit_req, master_credit_req, doctor_credit_req
) VALUES
('计算机科学与技术', 1, 160, 36, 28),
('数据科学与大数据技术', 2, 165, 38, 30),
('信息与计算科学', 3, 155, 34, 26);

INSERT INTO title (title_name, title_level) VALUES
('教授', 1),
('副教授', 2),
('讲师', 3),
('助教', 4);

INSERT INTO teacher (teacher_no, name, department_id, title_id, phone) VALUES
('T2024001', '王明', 1, 1, '13800000001'),
('T2024002', '李芳', 2, 2, '13800000002'),
('T2024003', '张强', 3, 3, '13800000003');

INSERT INTO course (
    course_code, course_name, course_description, class_hours, credits, degree_level, department_id
) VALUES
('CS101', '数据库及实现', '关系数据库设计、SQL 与数据库系统实现', 64, 4.0, '本科', 1),
('DATA201', '数据结构', '线性表、树、图及查找排序算法', 64, 4.0, '本科', 2),
('MATH101', '高等数学', '微积分、级数与常微分方程基础', 80, 5.0, '本科', 3);

INSERT INTO student (
    student_no, name, id_card, gender, birth_date, dormitory, home_address, phone,
    grade_year, major_id, minor_id, degree_level, completed_credits
) VALUES
('S2024001', '赵一', '110101200501010011', '男', '2005-01-01', '1号楼 302', '北京市海淀区', '13900000001', 2024, 2, NULL, '本科', 24),
('S2024002', '钱二', '110101200502020022', '女', '2005-02-02', '2号楼 406', '北京市朝阳区', '13900000002', 2024, 1, 3, '本科', 28),
('S2024003', '孙三', '110101200503030033', '男', '2005-03-03', '3号楼 501', '天津市南开区', '13900000003', 2024, 3, NULL, '本科', 22);

INSERT INTO teacher_course (teacher_id, course_id, semester, teaching_role, course_status) VALUES
(1, 1, '2025-2026-1', '主讲', 'open'),
(2, 2, '2025-2026-1', '主讲', 'open'),
(3, 3, '2025-2026-1', '主讲', 'open'),
(2, 1, '2025-2026-1', '助教', 'open');

INSERT INTO student_course (student_id, course_id, semester, enroll_status) VALUES
(1, 1, '2025-2026-1', '已完成'),
(1, 2, '2025-2026-1', '已完成'),
(2, 1, '2025-2026-1', '已完成'),
(2, 3, '2025-2026-1', '已选'),
(3, 3, '2025-2026-1', '已完成');

INSERT INTO grade (student_id, course_id, semester, score, exam_type) VALUES
(1, 1, '2025-2026-1', 92.00, '正考'),
(1, 2, '2025-2026-1', 86.50, '正考'),
(2, 1, '2025-2026-1', 78.00, '正考'),
(3, 3, '2025-2026-1', 88.00, '正考');

INSERT INTO users (
    username, password_hash, role, related_student_id, related_teacher_id, is_active, must_change_password
) VALUES
('admin', 'scrypt:32768:8:1$NVIFbTrxuWD4VwXY$9543cf3e7f117361f966ef6ab96c348c9760b2934acef81d2f7254f7b2caa78b364cecefb9b42e4c161010746d381dd76dfc13cf30590e982a88b2423cc49ec0', 'admin', NULL, NULL, 1, 0),
('teacher01', 'scrypt:32768:8:1$cKt4dfZbstw8Anuy$b9cf7424226f5421d6ed090e672e2285b55ea8393dfeede5bb4e18bec618490608a8e033dc4083e6eacfca313f013f9b0952e7b268042b94adb386d6970a80a2', 'teacher', NULL, 1, 1, 0),
('student01', 'scrypt:32768:8:1$KJp5RzkmFnXAyU3B$581e48c5b777c34ba960a23b51902334a7aaff685f17f7e7d45001ad6eab42f7282a6d11fff54830243b5c883c53f369bfe1f72b1a0a0286ebf0be8565a890dd', 'student', 1, NULL, 1, 0);
