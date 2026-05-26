# Start LLM Gateway V7 on port 8107 (Windows)
Set-Location $PSScriptRoot

$port = 8107
if ($env:GATEWAY_V7_PORT) { $port = $env:GATEWAY_V7_PORT }

$url = "http://127.0.0.1:$port"
Write-Host ""
Write-Host "  LLM Gateway V7" -ForegroundColor Cyan
Write-Host "  Dashboard:  $url" -ForegroundColor Green
Write-Host "  Help:       $url/help" -ForegroundColor Green
Write-Host ""
Write-Host "  Run the agent in a SECOND terminal:" -ForegroundColor Yellow
Write-Host "    cd ..\S7code" -ForegroundColor Gray
Write-Host "    uv run agent7.py `"your question`"" -ForegroundColor Gray
Write-Host ""
Write-Host "  (This window shows API logs only - agent output appears in the other terminal.)" -ForegroundColor DarkGray
Write-Host ""

try { Start-Process $url } catch { Write-Host "  Open $url in your browser to see the dashboard." -ForegroundColor Yellow }

uv run python main.py
