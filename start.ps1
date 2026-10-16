param([ValidateRange(1024,65535)][int]$Port=8765,[switch]$Rebuild,[switch]$OpenBrowser)
$ErrorActionPreference='Stop'
$workspacePath=$PSScriptRoot
Set-Location -LiteralPath $workspacePath
$env:PYTHONUTF8='1'
$pythonPath=Join-Path $workspacePath '.venv\Scripts\python.exe'
if(-not (Test-Path -LiteralPath $pythonPath)){
    & python -m venv .venv
    if($LASTEXITCODE -ne 0){throw 'Python environment creation failed.'}
    & $pythonPath -m pip install -r requirements.txt
    if($LASTEXITCODE -ne 0){throw 'Python dependency installation failed.'}
}
if($Rebuild -or -not (Test-Path -LiteralPath (Join-Path $workspacePath 'dist\index.html'))){
    & npm.cmd ci
    if($LASTEXITCODE -ne 0){throw 'Frontend dependency installation failed.'}
    & npm.cmd run build
    if($LASTEXITCODE -ne 0){throw 'Frontend build failed.'}
}
$dataPath=Join-Path $workspacePath 'data'
New-Item -ItemType Directory -Path $dataPath -Force | Out-Null
$baseUrl="http://127.0.0.1:$Port"
function Show-Ready {
    Write-Host "Jiapu is ready: $baseUrl"
    Write-Host "Demo: $baseUrl/?demo=1"
    if($OpenBrowser){
        try { Start-Process -FilePath $baseUrl }
        catch { Write-Warning "Could not open your browser. Open $baseUrl manually." }
    }
}
try {
    $status=Invoke-RestMethod -Uri "$baseUrl/api/health" -TimeoutSec 2
    if($status.ok -and $status.version){Show-Ready;exit 0}
}catch{}
$startArgs=@('-m','uvicorn','server.app:app','--app-dir',('"'+$workspacePath+'"'),'--host','127.0.0.1','--port',$Port)
$process=Start-Process -FilePath $pythonPath -ArgumentList $startArgs -WorkingDirectory $workspacePath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $dataPath 'server.log') -RedirectStandardError (Join-Path $dataPath 'server-error.log') -PassThru
@{pid=$process.Id;port=$Port;workspace=$workspacePath} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $dataPath 'running.json') -Encoding UTF8
for($attempt=0;$attempt -lt 25;$attempt++){
    Start-Sleep -Milliseconds 400
    try{$status=Invoke-RestMethod -Uri "$baseUrl/api/health" -TimeoutSec 2;if($status.ok){Show-Ready;exit 0}}catch{}
}
throw 'Startup failed. See data/server-error.log.'
