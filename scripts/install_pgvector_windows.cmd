@echo off
setlocal

if "%~1"=="" (
  set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
  set "PGROOT=C:\Program Files\PostgreSQL\18"
  set "PGVECTOR_SOURCE=%TEMP%\xeon-pgvector-0.8.7"
) else (
  set "VCVARS=%~1"
  set "PGROOT=%~2"
  set "PGVECTOR_SOURCE=%~3"
)

if not exist "%VCVARS%" (
  echo vcvars64.bat no existe 1>&2
  exit /b 2
)
if not exist "%PGROOT%\bin\pg_config.exe" (
  echo La raiz de PostgreSQL no es valida 1>&2
  exit /b 3
)
if not exist "%PGVECTOR_SOURCE%\Makefile.win" (
  echo La fuente de pgvector no es valida 1>&2
  exit /b 4
)

call "%VCVARS%"
if errorlevel 1 exit /b %errorlevel%

pushd "%PGVECTOR_SOURCE%"
nmake /NOLOGO /F Makefile.win
if errorlevel 1 (
  popd
  exit /b %errorlevel%
)
nmake /NOLOGO /F Makefile.win install
set "RESULT=%errorlevel%"
popd
exit /b %RESULT%
