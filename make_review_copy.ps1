param(
  [Parameter(Mandatory=$true)][string]$InputFile,
  [double]$Speed = 1.15,
  [string]$OutputFile = ''
)
$ErrorActionPreference = 'Stop'
if ($Speed -le 0) { throw 'Speed must be positive' }
if ([string]::IsNullOrWhiteSpace($OutputFile)) {
  $resolved = Resolve-Path $InputFile
  $stem = [IO.Path]::GetFileNameWithoutExtension($resolved)
  $dir = [IO.Path]::GetDirectoryName($resolved)
  $tag = $Speed.ToString('0.##') -replace '\.','p'
  $OutputFile = Join-Path $dir ("{0}_review_{1}x.mp4" -f $stem, $tag)
}
$filter = "[0:v]setpts=PTS/$Speed[v];[0:a]atempo=$Speed[a]"
& ffmpeg -y -hide_banner -loglevel error -i $InputFile -filter_complex $filter -map '[v]' -map '[a]' -c:v libx264 -preset veryfast -c:a aac -b:a 192k -movflags +faststart $OutputFile
if ($LASTEXITCODE -ne 0) { throw 'Review export failed' }
Write-Output $OutputFile
