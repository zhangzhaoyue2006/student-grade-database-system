SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

USE student_grade_system;

ALTER TABLE teacher_course
    ADD COLUMN course_status VARCHAR(20) NOT NULL DEFAULT 'open' AFTER teaching_role;

ALTER TABLE teacher_course
    ADD CONSTRAINT ck_teacher_course_status CHECK (course_status IN ('open', 'closed'));
