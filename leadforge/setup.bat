@echo off
echo === LeadForge Setup ===
echo.

python -m venv venv
call venv\Scripts\activate

pip install -r requirements.txt

if not exist .env (
    copy .env.example .env
    echo Created .env — please fill in your API keys.
)

echo.
echo Setup complete! Run the app with:
echo   venv\Scripts\activate
echo   streamlit run app.py
echo.
pause
