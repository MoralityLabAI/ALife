param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(6, 7, 8, 9)]
    [int]$Version,

    [Parameter(Mandatory = $true)]
    [string]$ArtifactDirectory,

    [switch]$FullReport
)

$workspace = Split-Path -Parent $PSScriptRoot
$python = Join-Path $workspace '.recovery_runtime\python311\python.exe'
$verifier = Join-Path $workspace 'src\verify_stegohive_recovered_artifacts.py'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Portable Python 3.11 runtime is missing at $python"
}

$arguments = @(
    $verifier,
    $ArtifactDirectory,
    '--workspace-root', $workspace,
    '--version', $Version
)
if (-not $FullReport) {
    $arguments += '--compact'
}

& $python @arguments
exit $LASTEXITCODE
