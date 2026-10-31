$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$cfg = Get-Content (Join-Path $root 'story_config.json') -Raw | ConvertFrom-Json
$video = Join-Path $root 'ragnarok_v16.mp4'
$captions = Get-Content (Join-Path $root 'Captions_v18.srt') -Raw
$failures = [System.Collections.Generic.List[string]]::new()

function Gate($ok, $message) {
  if ($ok) { Write-Output "PASS  $message" } else { $failures.Add($message); Write-Output "FAIL  $message" }
}

Gate (Test-Path $video) 'final video exists'
Gate (Test-Path (Join-Path $root 'music_sources.json')) 'music license manifest exists'
Gate (Test-Path (Join-Path $root 'Audio_QA_Report_Mixkit.md')) 'audio QA report exists'

$probe = & ffprobe -v error -show_entries format=duration:stream=width,height,codec_type -of json $video | ConvertFrom-Json
$vstream = @($probe.streams | Where-Object codec_type -eq 'video')[0]
$duration = [double]$probe.format.duration
Gate ([math]::Abs($duration - [double]$cfg.duration_seconds) -lt 0.05) "duration is $duration seconds"
Gate (($vstream.width -eq $cfg.format.width) -and ($vstream.height -eq $cfg.format.height)) 'vertical dimensions match story config'

$hash1 = (Get-FileHash (Join-Path $root 'assets\P01.png') -Algorithm SHA256).Hash
$hash3 = (Get-FileHash (Join-Path $root 'assets\P03.png') -Algorithm SHA256).Hash
Gate ($hash1 -ne $hash3) 'scene assets are not duplicated'

$camera = Get-Content (Join-Path $root 'assemble_segments.py') -Raw
Gate (-not ($camera -match 'sin\(')) 'camera motion has no sinusoidal shake'
Gate ($camera -match 'cos\(') 'camera motion uses easing'
$badTimestampCount = [regex]::Matches($captions, '(?m)^\d{2}:\d{2},\d{3}').Count
Gate ($badTimestampCount -eq 0) 'all caption timestamps use SRT hour format'

foreach ($scene in $cfg.scenes) {
  Gate (Test-Path (Join-Path $root $scene.asset)) "$($scene.id) asset exists"
  $sceneSentences = [regex]::Split($scene.caption, '(?<=[.!?])\s+') | Where-Object { $_.Trim().Length -gt 0 }
  $sentenceMatch = $true
  foreach ($sentence in $sceneSentences) { if (-not $captions.Contains($sentence.Trim())) { $sentenceMatch = $false } }
  Gate $sentenceMatch "$($scene.id) caption sentences match current narration text"
}

if ($failures.Count -gt 0) {
  Write-Error ("QA gates failed: " + ($failures -join '; '))
  exit 1
}
Write-Output 'ALL QA GATES PASSED'
