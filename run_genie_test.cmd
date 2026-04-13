@echo off
setlocal
cd /d "%~dp0"

if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /I "%%~A"=="DATABRICKS_TOKEN" set "DATABRICKS_TOKEN=%%~B"
  )
)

echo Running Genie MCP connectivity + query test...
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 test_mcp_connection.py --query "What is the monthly trend of total incidents reported at Allianz?"
) else (
  python test_mcp_connection.py --query "What is the monthly trend of total incidents reported at Allianz?"
)

echo.
pause
endlocal
