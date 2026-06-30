@echo off
setlocal
cd /d "%~dp0\.."

echo Initializing student_grade_system database...
echo Please enter your MySQL root password when prompted.

mysql --default-character-set=utf8mb4 -u root -p < database\schema.sql
if errorlevel 1 (
    echo Failed to execute schema.sql
    exit /b 1
)

mysql --default-character-set=utf8mb4 -u root -p student_grade_system < database\seed.sql
if errorlevel 1 (
    echo Failed to execute seed.sql
    exit /b 1
)

echo Database initialized successfully.
