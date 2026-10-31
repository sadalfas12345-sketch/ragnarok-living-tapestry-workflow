$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
& python (Join-Path $root 'mix_from_timeline.py')
if ($LASTEXITCODE -ne 0) { throw 'Timeline soundtrack render failed' }
