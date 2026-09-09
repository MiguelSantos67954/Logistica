@echo off
cd /d "%~dp0"
title Portal Logistica - NAO FECHE ESTA JANELA

where python >nul 2>&1
if errorlevel 1 (
    echo ============================================================
    echo  ERRO: o comando "python" nao foi encontrado neste computador.
    echo  Instale o Python (https://www.python.org/downloads/) marcando
    echo  a opcao "Add Python to PATH" durante a instalacao, e tente de novo.
    echo ============================================================
    pause
    exit /b 1
)

echo Verificando/instalando bibliotecas necessarias (so' na primeira vez isso demora)...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo ============================================================
    echo  Aviso: nao consegui instalar automaticamente as bibliotecas.
    echo  Tente rodar manualmente:  python -m pip install -r requirements.txt
    echo ============================================================
    pause
)

for /f "tokens=2 delims=:, " %%A in ('findstr /i "porta_do_sistema" config.json') do set "PORTA=%%A"
if "%PORTA%"=="" set "PORTA=3010"

echo Liberando porta %PORTA% no Firewall do Windows (pode pedir permissao de administrador)...
netsh advfirewall firewall delete rule name="Identificacao de Pallets" >nul 2>&1
netsh advfirewall firewall add rule name="Identificacao de Pallets" protocol=TCP dir=in localport=%PORTA% action=allow >nul 2>&1

echo Iniciando o sistema em http://localhost:%PORTA% ...
start "" http://localhost:%PORTA%
python iniciar.py

echo ------------------------------------------------------------
echo O sistema foi encerrado.
pause
