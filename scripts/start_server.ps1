Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Starting Personal Research Knowledge Base (LightRAG Server)" -ForegroundColor Cyan
Write-Host "Web UI: http://127.0.0.1:9621/webui" -ForegroundColor Green
Write-Host "Chat UI: http://127.0.0.1:9621/workspace" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

Set-Location "C:\Research-Knowledge-Base"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:HOST = "127.0.0.1"
$env:PORT = "9621"

# Ensure local embedding server (FastEmbed bge-small-en-v1.5) is running on port 9622
$embedPortActive = Get-NetTCPConnection -LocalPort 9622 -State Listen -ErrorAction SilentlyContinue
if (-not $embedPortActive) {
    Write-Host "Starting Local FastEmbed Embedding Server on http://127.0.0.1:9622 ..." -ForegroundColor Yellow
    Start-Process -FilePath "C:\Research-Knowledge-Base\.venv\Scripts\python.exe" `
        -ArgumentList "C:\Research-Knowledge-Base\scripts\local_embedding_server.py" `
        -WorkingDirectory "C:\Research-Knowledge-Base" `
        -WindowStyle Hidden
    Start-Sleep -Seconds 3
} else {
    Write-Host "Local FastEmbed Embedding Server is already running on port 9622." -ForegroundColor Green
}

& "C:\Research-Knowledge-Base\.venv\Scripts\lightrag-server.exe" `
    --host 127.0.0.1 `
    --port 9621 `
    --working-dir "C:\Research-Knowledge-Base\rag_storage" `
    --input-dir "C:\Research-Knowledge-Base\inputs" `
    --log-level INFO
