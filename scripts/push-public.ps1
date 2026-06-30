# push-public.ps1
# Pushes a filtered snapshot (template only, no personal projects) to the public remote.

$ErrorActionPreference = "Stop"

$TEMP_BRANCH = "public-snapshot-$(Get-Date -Format 'yyyyMMddHHmmss')"
$CONFIG_PATH = Join-Path $PSScriptRoot "public-snapshot.private-projects.txt"

if (!(Test-Path -LiteralPath $CONFIG_PATH)) {
    throw "Missing private-projects config: $CONFIG_PATH"
}

$PRIVATE_PROJECTS = Get-Content -LiteralPath $CONFIG_PATH |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and !$_.StartsWith("#") }

if (!$PRIVATE_PROJECTS) {
    throw "No private projects configured in $CONFIG_PATH"
}

$PROJECTS_ROOT = Join-Path $PSScriptRoot "..\\projects"
if (!(Test-Path -LiteralPath $PROJECTS_ROOT)) {
    throw "Projects directory not found: $PROJECTS_ROOT"
}

$ACTUAL_PROJECTS = Get-ChildItem -LiteralPath $PROJECTS_ROOT -Directory |
    Select-Object -ExpandProperty Name |
    Where-Object { $_ -ne "_template" } |
    Sort-Object -Unique

$MISSING_FROM_PRIVATE_LIST = @($ACTUAL_PROJECTS | Where-Object { $_ -notin $PRIVATE_PROJECTS })
if ($MISSING_FROM_PRIVATE_LIST.Count -gt 0) {
    $missing = $MISSING_FROM_PRIVATE_LIST -join ", "
    throw "Refusing public snapshot. Add project(s) to scripts/public-snapshot.private-projects.txt first: $missing"
}

$confirmation = Read-Host "Push filtered snapshot to public remote main? (y/N)"
if ($confirmation -ne "y" -and $confirmation -ne "Y") {
    Write-Host "Cancelled."
    exit 0
}

Write-Host "Creating temp branch: $TEMP_BRANCH"
git checkout --orphan $TEMP_BRANCH

Write-Host "Staging all files..."
git add -A

Write-Host "Removing personal projects..."
foreach ($project in $PRIVATE_PROJECTS) {
    $path = "projects/$project"
    if (Test-Path -LiteralPath $path) {
        git rm -r --cached $path | Out-Null
    }
}

Write-Host "Committing public snapshot..."
git commit -m "public: template snapshot $(Get-Date -Format 'yyyy-MM-dd')"

Write-Host "Pushing to public remote..."
git push public "${TEMP_BRANCH}:main" --force-with-lease

Write-Host "Cleaning up..."
git checkout --force main
git branch -D $TEMP_BRANCH

Write-Host "Done. Public remote updated."
