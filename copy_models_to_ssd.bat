@echo off
REM ═══════════════════════════════════════════════════════
REM TuminhAGI — Copy 3 models sang E:\ModelAI
REM Models: qwen2.5-coder:7b, phi3:mini, nomic-embed-text
REM ═══════════════════════════════════════════════════════

echo.
echo ═══════════════════════════════════════════════
echo   COPY MODELS SANG SSD E:\ModelAI
echo ═══════════════════════════════════════════════
echo.

REM Tạo folder đích
if not exist "E:\ModelAI\blobs"     mkdir "E:\ModelAI\blobs"
if not exist "E:\ModelAI\manifests" mkdir "E:\ModelAI\manifests"

set SRC=C:\Users\Admim\.ollama\models
set DST=E:\ModelAI

REM ─── nomic-embed-text (274MB) ───────────────────
echo [1/3] Copying nomic-embed-text...
if not exist "%DST%\manifests\registry.ollama.ai\library\nomic-embed-text" (
    mkdir "%DST%\manifests\registry.ollama.ai\library\nomic-embed-text"
)
xcopy "%SRC%\manifests\registry.ollama.ai\library\nomic-embed-text" ^
      "%DST%\manifests\registry.ollama.ai\library\nomic-embed-text\" ^
      /E /I /H /Y /Q
echo    Done: nomic-embed-text manifest

REM ─── phi3:mini (2.2GB) ──────────────────────────
echo [2/3] Copying phi3:mini...
if not exist "%DST%\manifests\registry.ollama.ai\library\phi3" (
    mkdir "%DST%\manifests\registry.ollama.ai\library\phi3"
)
xcopy "%SRC%\manifests\registry.ollama.ai\library\phi3" ^
      "%DST%\manifests\registry.ollama.ai\library\phi3\" ^
      /E /I /H /Y /Q
echo    Done: phi3 manifest

REM ─── qwen2.5-coder:7b (4.7GB) ──────────────────
echo [3/3] Copying qwen2.5-coder:7b...
if not exist "%DST%\manifests\registry.ollama.ai\library\qwen2.5-coder" (
    mkdir "%DST%\manifests\registry.ollama.ai\library\qwen2.5-coder"
)
xcopy "%SRC%\manifests\registry.ollama.ai\library\qwen2.5-coder" ^
      "%DST%\manifests\registry.ollama.ai\library\qwen2.5-coder\" ^
      /E /I /H /Y /Q
echo    Done: qwen2.5-coder manifest

REM ─── Copy blobs (file thật của models) ──────────
echo.
echo Copying model blobs (7-8GB, co the mat vai phut)...
echo Dang chay...

REM Copy tất cả blobs — Ollama dùng content-addressable storage
REM Các blob được share giữa models nên copy hết blobs là an toàn
xcopy "%SRC%\blobs" "%DST%\blobs\" /E /I /H /Y /Q

echo.
echo ═══════════════════════════════════════════════
echo   XONG! Ket qua:
echo ═══════════════════════════════════════════════
dir "E:\ModelAI\blobs" | find "File(s)"
dir "E:\ModelAI\manifests" /S | find "File(s)"
echo.
echo   Buoc tiep theo:
echo   1. Set bien moi truong:
echo      setx OLLAMA_MODELS "E:\ModelAI"
echo   2. Restart Ollama
echo   3. Kiem tra: ollama list
echo ═══════════════════════════════════════════════
pause
