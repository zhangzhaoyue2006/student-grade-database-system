SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

USE student_grade_system;

ALTER TABLE users
    ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0 AFTER is_active;

ALTER TABLE users
    ADD CONSTRAINT ck_users_must_change_password CHECK (must_change_password IN (0, 1));
