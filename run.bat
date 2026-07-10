@echo off
REM ============================================================
REM  محاسب DZ الذكي - تشغيل بنقرة واحدة على Windows
REM  انقر مرّتين على هذا الملف لبدء التطبيق.
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

REM التحقّق من وجود البيئة الافتراضية
if not exist ".venv\Scripts\activate.bat" (
  echo.
  echo [X] البيئة الافتراضية .venv غير موجودة.
  echo.
  echo نفّذ هذه الأوامر أوّلاً في PowerShell:
  echo.
  echo   python -m venv .venv
  echo   .\.venv\Scripts\Activate.ps1
  echo   pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

REM التحقّق من وجود .env
if not exist ".env" (
  echo.
  echo [!] ملف .env غير موجود.
  echo.
  echo 1. اذهب إلى: https://aistudio.google.com/app/apikey
  echo 2. اضغط "Create API Key" وانسخ المفتاح
  echo 3. أنشئ ملف .env في هذا المجلد بالمحتوى:
  echo    GEMINI_API_KEY=مفتاحك_هنا
  echo.
  pause
  exit /b 1
)

echo ================================================
echo  🚀 تشغيل محاسب DZ الذكي...
echo ================================================
call .venv\Scripts\activate.bat
python app.py
echo.
pause
