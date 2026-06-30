SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS student_grade_system
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE student_grade_system;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS system_log;
DROP TABLE IF EXISTS grade;
DROP TABLE IF EXISTS student_course;
DROP TABLE IF EXISTS teacher_course;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS student;
DROP TABLE IF EXISTS teacher;
DROP TABLE IF EXISTS title;
DROP TABLE IF EXISTS course;
DROP TABLE IF EXISTS major;
DROP TABLE IF EXISTS department;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE department (
    department_id INT AUTO_INCREMENT PRIMARY KEY,
    department_code VARCHAR(20) NOT NULL,
    department_name VARCHAR(100) NOT NULL,
    office_location VARCHAR(100),
    phone VARCHAR(30),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_department_code UNIQUE (department_code),
    CONSTRAINT uq_department_name UNIQUE (department_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE major (
    major_id INT AUTO_INCREMENT PRIMARY KEY,
    major_name VARCHAR(100) NOT NULL,
    department_id INT NOT NULL,
    bachelor_credit_req DECIMAL(5,1) NOT NULL DEFAULT 0,
    master_credit_req DECIMAL(5,1) NOT NULL DEFAULT 0,
    doctor_credit_req DECIMAL(5,1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_major_department_name UNIQUE (department_id, major_name),
    CONSTRAINT fk_major_department FOREIGN KEY (department_id)
        REFERENCES department(department_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT ck_major_bachelor_credit CHECK (bachelor_credit_req >= 0),
    CONSTRAINT ck_major_master_credit CHECK (master_credit_req >= 0),
    CONSTRAINT ck_major_doctor_credit CHECK (doctor_credit_req >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    student_no VARCHAR(30) NOT NULL,
    name VARCHAR(50) NOT NULL,
    id_card VARCHAR(30) NOT NULL,
    gender VARCHAR(10) NOT NULL,
    birth_date DATE,
    dormitory VARCHAR(100),
    home_address VARCHAR(255),
    phone VARCHAR(30),
    grade_year INT NOT NULL,
    major_id INT NOT NULL,
    minor_id INT,
    degree_level VARCHAR(20) NOT NULL,
    completed_credits DECIMAL(6,1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_student_no UNIQUE (student_no),
    CONSTRAINT uq_student_id_card UNIQUE (id_card),
    CONSTRAINT fk_student_major FOREIGN KEY (major_id)
        REFERENCES major(major_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_student_minor FOREIGN KEY (minor_id)
        REFERENCES major(major_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,
    CONSTRAINT ck_student_gender CHECK (gender IN ('男', '女')),
    CONSTRAINT ck_student_degree_level CHECK (degree_level IN ('本科', '硕士', '博士')),
    CONSTRAINT ck_student_grade_year CHECK (grade_year BETWEEN 2000 AND 2100),
    CONSTRAINT ck_student_completed_credits CHECK (completed_credits >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE course (
    course_id INT AUTO_INCREMENT PRIMARY KEY,
    course_code VARCHAR(30) NOT NULL,
    course_name VARCHAR(100) NOT NULL,
    course_description TEXT,
    class_hours INT NOT NULL,
    credits DECIMAL(4,1) NOT NULL,
    degree_level VARCHAR(20) NOT NULL,
    department_id INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_course_code UNIQUE (course_code),
    CONSTRAINT fk_course_department FOREIGN KEY (department_id)
        REFERENCES department(department_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT ck_course_class_hours CHECK (class_hours > 0),
    CONSTRAINT ck_course_credits CHECK (credits > 0),
    CONSTRAINT ck_course_degree_level CHECK (degree_level IN ('本科', '硕士', '博士'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE title (
    title_id INT AUTO_INCREMENT PRIMARY KEY,
    title_name VARCHAR(50) NOT NULL,
    title_level INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_title_name UNIQUE (title_name),
    CONSTRAINT ck_title_level CHECK (title_level > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE teacher (
    teacher_id INT AUTO_INCREMENT PRIMARY KEY,
    teacher_no VARCHAR(30) NOT NULL,
    name VARCHAR(50) NOT NULL,
    department_id INT NOT NULL,
    title_id INT,
    phone VARCHAR(30),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_teacher_no UNIQUE (teacher_no),
    CONSTRAINT fk_teacher_department FOREIGN KEY (department_id)
        REFERENCES department(department_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_teacher_title FOREIGN KEY (title_id)
        REFERENCES title(title_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE teacher_course (
    teacher_id INT NOT NULL,
    course_id INT NOT NULL,
    semester VARCHAR(30) NOT NULL,
    teaching_role VARCHAR(20) NOT NULL DEFAULT '主讲',
    course_status VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (teacher_id, course_id, semester),
    CONSTRAINT fk_teacher_course_teacher FOREIGN KEY (teacher_id)
        REFERENCES teacher(teacher_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT fk_teacher_course_course FOREIGN KEY (course_id)
        REFERENCES course(course_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT ck_teacher_course_role CHECK (teaching_role IN ('主讲', '助教', '合上')),
    CONSTRAINT ck_teacher_course_status CHECK (course_status IN ('open', 'closed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_course (
    student_id INT NOT NULL,
    course_id INT NOT NULL,
    semester VARCHAR(30) NOT NULL,
    enroll_status VARCHAR(20) NOT NULL DEFAULT '已选',
    enrolled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (student_id, course_id, semester),
    CONSTRAINT fk_student_course_student FOREIGN KEY (student_id)
        REFERENCES student(student_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT fk_student_course_course FOREIGN KEY (course_id)
        REFERENCES course(course_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT ck_student_course_status CHECK (enroll_status IN ('已选', '退课', '已完成'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE grade (
    grade_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    course_id INT NOT NULL,
    semester VARCHAR(30) NOT NULL,
    score DECIMAL(5,2) NOT NULL,
    exam_type VARCHAR(20) NOT NULL DEFAULT '正考',
    record_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_grade_record UNIQUE (student_id, course_id, semester, exam_type),
    CONSTRAINT fk_grade_student FOREIGN KEY (student_id)
        REFERENCES student(student_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT fk_grade_course FOREIGN KEY (course_id)
        REFERENCES course(course_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT ck_grade_score CHECK (score >= 0 AND score <= 100),
    CONSTRAINT ck_grade_exam_type CHECK (exam_type IN ('正考', '补考', '重修'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    related_student_id INT,
    related_teacher_id INT,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    must_change_password TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT fk_users_student FOREIGN KEY (related_student_id)
        REFERENCES student(student_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,
    CONSTRAINT fk_users_teacher FOREIGN KEY (related_teacher_id)
        REFERENCES teacher(teacher_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,
    CONSTRAINT ck_users_role CHECK (role IN ('admin', 'teacher', 'student')),
    CONSTRAINT ck_users_active CHECK (is_active IN (0, 1)),
    CONSTRAINT ck_users_must_change_password CHECK (must_change_password IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE system_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(100) NOT NULL,
    detail VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_system_log_user FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
