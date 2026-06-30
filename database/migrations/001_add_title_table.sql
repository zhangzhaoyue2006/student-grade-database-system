SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

USE student_grade_system;

CREATE TABLE IF NOT EXISTS title (
    title_id INT AUTO_INCREMENT PRIMARY KEY,
    title_name VARCHAR(50) NOT NULL,
    title_level INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_title_name UNIQUE (title_name),
    CONSTRAINT ck_title_level CHECK (title_level > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO title (title_name, title_level) VALUES
('教授', 1),
('副教授', 2),
('讲师', 3),
('助教', 4);

ALTER TABLE teacher ADD COLUMN title_id INT NULL AFTER department_id;

UPDATE teacher t
JOIN title tt ON t.title = tt.title_name
SET t.title_id = tt.title_id;

ALTER TABLE teacher DROP COLUMN title;

ALTER TABLE teacher
    ADD CONSTRAINT fk_teacher_title FOREIGN KEY (title_id)
    REFERENCES title(title_id)
    ON UPDATE CASCADE
    ON DELETE SET NULL;
