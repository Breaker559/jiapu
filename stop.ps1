$ErrorActionPreference='Stop'
$statePath=Join-Path $PSScriptRoot 'data\running.json'
if(-not (Test-Path -LiteralPath $statePath)){Write-Host 'No managed server was found.';exit 0}
$state=Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
if($state.workspace -ne $PSScriptRoot){throw 'The running server belongs to a different workspace.'}
$process=Get-CimInstance Win32_Process -Filter "ProcessId = $($state.pid)"
if($null -eq $process){Write-Host 'Server already stopped.';exit 0}
if($process.CommandLine -notlike '*server.app:app*' -or $process.CommandLine -notlike "*$PSScriptRoot*"){throw 'Process identity does not match Jiapu. Refusing to stop it.'}
# A Windows venv launcher may create a child Python process. Stop only this owned process tree.
$descendants=@(Get-CimInstance Win32_Process | Where-Object {$_.ParentProcessId -eq $state.pid -and $_.CommandLine -like '*server.app:app*'})
foreach($child in $descendants){Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue}
Stop-Process -Id $state.pid -ErrorAction SilentlyContinue
Write-Host 'Jiapu stopped. Family data remains in the data directory.'
