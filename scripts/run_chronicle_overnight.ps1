[CmdletBinding()]
param(
    [int]$Episodes = 500,
    [int]$Steps = 8,
    [int]$ReplaySample = 24,
    [double]$WallSeconds = 7200,
    [double]$EpisodeWallSeconds = 120,
    [string]$DateStamp = (Get-Date -Format 'yyyyMMdd')
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ResultsPath = Join-Path $RepoRoot 'results'
$ResultsItem = Get-Item -LiteralPath $ResultsPath -Force
$Targets = @($ResultsItem.Target) | ForEach-Object { [string]$_ }

if ($ResultsItem.LinkType -notin @('Junction', 'SymbolicLink') -or
    -not ($Targets | Where-Object { $_ -like 'D:\*' })) {
    throw "Expected $ResultsPath to be a junction or symlink targeting D:\; found LinkType=$($ResultsItem.LinkType) Target=$($Targets -join ',')"
}

$Output = Join-Path $ResultsPath "chronicle_corpus_$DateStamp"
$Bundle = Join-Path $ResultsPath "chronicle_corpus_$DateStamp.zip"
if (Test-Path -LiteralPath $Output) {
    throw "Refusing to overwrite existing corpus directory: $Output"
}
if (Test-Path -LiteralPath $Bundle) {
    throw "Refusing to overwrite existing corpus bundle: $Bundle"
}

Push-Location $RepoRoot
try {
    & python 'src\chronicle\campaign.py' `
        --manifest 'experiments\chronicle_v1\manifest.json' `
        --output $Output `
        --episodes $Episodes `
        --steps $Steps `
        --max-cells-per-world 4096 `
        --wall-seconds $WallSeconds `
        --episode-wall-seconds $EpisodeWallSeconds
    if ($LASTEXITCODE -ne 0) {
        throw "Chronicle campaign failed with exit code $LASTEXITCODE"
    }

    & python 'src\chronicle\verify_chronicle.py' $Output `
        --sample $ReplaySample `
        --bundle $Bundle
    if ($LASTEXITCODE -ne 0) {
        throw "Chronicle verifier failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

Write-Output "Corpus: $Output"
Write-Output "Bundle: $Bundle"
