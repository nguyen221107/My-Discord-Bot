@echo off
:: Chuyển đến thư mục chứa bot
cd /d "%~dp0"

:: Kiểm tra tồn tại venv
if not exist "venv\Scripts\activate" (
    echo ERROR: Thư mục venv không tồn tại!
    pause
    exit /b 1
)

:: Kích hoạt venv và chạy bot
call venv\Scripts\activate
python bot.py

:: Giữ cửa sổ mở sau khi kết thúc
pause