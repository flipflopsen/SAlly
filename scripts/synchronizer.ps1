<# .SYNOPSIS
    Master synchronizer script for file synchronization.
    The "Target" counterpart runs on the target machine, which is my Linux server, thus the script is in Bash and not included here. (Though powershell can run on Linux too.)

.DESCRIPTION
    This script runs on the master machine to generate state files,
    serve them via HTTP, compute diffs with the target machine, and
    synchronize files using SCP.

.PARAMETER Mode
    The operation mode: 'state', 'serve', 'diff', or 'synchronize'.

.EXAMPLE
    .\synchronizer.ps1 -Mode state
    Generates the state file for the current directory.
    .\synchronizer.ps1 -Mode serve
    Starts an HTTP server to serve the state file. (normally not used on master)
    .\synchronizer.ps1 -Mode diff
    Generates the diff file by comparing with the target's state.
    .\synchronizer.ps1 -Mode synchronize
    Synchronizes files to the target machine.
#>

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('state','serve','diff','synchronize')]
    [string]$Mode
)

# ========== GLOBAL CONFIGURATION ==========
$Global:CONFIG = @{
    Role = "Master"
    IP = "bleepingbooth.de"  # Target IP
    SshPort = 22
    HttpPort = 8000  # Target's HTTP port
    Username = "flip"
    Password = "Raiketi1!asdfg"
    SyncFolder = (get-item $PWD.Path).parent.FullName
}

$StateFile = "Synchronizer.state"
$TargetStateFile = "Synchronizer.target.state"
$DiffFile = "Synchronizer.diff"

# ========== FUNCTIONS ==========

function Generate-State {
    Write-Host "[Master] Generating state file (PLINQ)..." -ForegroundColor Cyan

    $code = @"
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;

public class StateGenerator {
    public static List<string> Generate(string basePath) {
        var basePathLength = basePath.TrimEnd('\\', '/').Length;
        var unixEpoch = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);

        return Directory.EnumerateFiles(basePath, "*", SearchOption.AllDirectories)
            .AsParallel()
            .WithDegreeOfParallelism(Environment.ProcessorCount * 2)
            .Select(path => {
                try {
                    var info = new FileInfo(path);
                    var relPath = path.Substring(basePathLength).TrimStart('\\', '/');
                    var timestamp = (long)(info.LastWriteTimeUtc - unixEpoch).TotalSeconds;
                    return $"{relPath}|{timestamp}|{info.Length}";
                } catch {
                    return null;
                }
            })
            .Where(x => x != null)
            .ToList();
    }
}
"@

    Add-Type -TypeDefinition $code -Language CSharp

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $results = [StateGenerator]::Generate($CONFIG.SyncFolder)

    [System.IO.File]::WriteAllLines($StateFile, $results, [System.Text.Encoding]::UTF8)

    $stopwatch.Stop()
    Write-Host "[Master] State file created: $StateFile ($($results.Count) files in $($stopwatch.Elapsed.TotalSeconds.ToString('F2'))s)" -ForegroundColor Green
}


function Serve-State
{
    Write-Host "[Master] Starting HTTP server on port 8080..." -ForegroundColor Cyan
    Write-Host "[Master] Press Ctrl+C to stop" -ForegroundColor Yellow

    if (-not (Test-Path $StateFile))
    {
        Write-Host "[Master] State file not found. Generate it first with --state" -ForegroundColor Red
        exit 1
    }

    python -m http.server 8080
}

function Fetch-TargetState
{
    Write-Host "[Master] Fetching target state from http://$($CONFIG.IP):$($CONFIG.HttpPort)/$StateFile..." -ForegroundColor Cyan

    try
    {
        Invoke-WebRequest -Uri "http://$($CONFIG.IP):$($CONFIG.HttpPort)/$StateFile" -OutFile $TargetStateFile -UseBasicParsing
        Write-Host "[Master] Target state downloaded successfully" -ForegroundColor Green
        return $true
    } catch
    {
        Write-Host "[Master] Failed to fetch target state: $_" -ForegroundColor Red
        return $false
    }
}

function Generate-Diff
{
    Write-Host "[Master] Generating diff file..." -ForegroundColor Cyan

    if (-not (Test-Path $StateFile))
    {
        Write-Host "[Master] Local state file not found. Run --state first" -ForegroundColor Red
        exit 1
    }

    if (-not (Fetch-TargetState))
    {
        exit 1
    }

    # Parse states
    $localState = @{}
    Get-Content $StateFile | ForEach-Object {
        $parts = $_ -split '\|'
        if ($parts.Length -eq 3)
        {
            $localState[$parts[0]] = @{
                Timestamp = [long]$parts[1]
                Size = [long]$parts[2]
            }
        }
    }

    $targetState = @{}
    Get-Content $TargetStateFile | ForEach-Object {
        $parts = $_ -split '\|'
        if ($parts.Length -eq 3)
        {
            $targetState[$parts[0]] = @{
                Timestamp = [long]$parts[1]
                Size = [long]$parts[2]
            }
        }
    }

    # Find files to update
    $filesToUpdate = @()
    foreach ($file in $localState.Keys)
    {
        if (-not $targetState.ContainsKey($file))
        {
            # New file on master
            $filesToUpdate += $file
        } elseif ($localState[$file].Timestamp -gt $targetState[$file].Timestamp)
        {
            # Master version is newer
            $filesToUpdate += $file
        }
    }

    $filesToUpdate | Out-File -FilePath $DiffFile -Encoding UTF8
    Write-Host "[Master] Diff file created: $DiffFile ($($filesToUpdate.Count) files to sync)" -ForegroundColor Green

    if ($filesToUpdate.Count -gt 0)
    {
        Write-Host "[Master] Files to update:" -ForegroundColor Yellow
        $filesToUpdate | Select-Object -First 10 | ForEach-Object { Write-Host "  - $_" }
        if ($filesToUpdate.Count -gt 10)
        {
            Write-Host "  ... and $($filesToUpdate.Count - 10) more" -ForegroundColor Gray
        }
    }
}

function Synchronize-Files
{
    Write-Host "[Master] Starting synchronization..." -ForegroundColor Cyan

    if (-not (Test-Path $DiffFile))
    {
        Write-Host "[Master] Diff file not found. Run --diff first" -ForegroundColor Red
        exit 1
    }

    $filesToSync = Get-Content $DiffFile

    if ($filesToSync.Count -eq 0)
    {
        Write-Host "[Master] No files to synchronize" -ForegroundColor Green
        return
    }

    Write-Host "[Master] Synchronizing $($filesToSync.Count) files..." -ForegroundColor Cyan

    $env:SSHPASS = $CONFIG.Password
    $successCount = 0
    $errorCount = 0

    foreach ($file in $filesToSync)
    {
        $sourcePath = Join-Path $CONFIG.SyncFolder $file
        $targetPath = $file -replace '\\', '/'

        # Create remote directory structure
        $remoteDir = Split-Path $targetPath -Parent
        if ($remoteDir)
        {
            $remoteDirCmd = "mkdir -p `"$remoteDir`""
            & sshpass -e ssh -o StrictHostKeyChecking=no -p $($CONFIG.SshPort) "$($CONFIG.Username)@$($CONFIG.IP)" $remoteDirCmd 2>$null
        }

        # Transfer file
        Write-Host "  Uploading: $file" -ForegroundColor Gray
        $scpResult = & sshpass -e scp -o StrictHostKeyChecking=no -P $($CONFIG.SshPort) "$sourcePath" "$($CONFIG.Username)@$($CONFIG.IP):$targetPath" 2>&1

        if ($LASTEXITCODE -eq 0)
        {
            $successCount++
        } else
        {
            $errorCount++
            Write-Host "    ERROR: $scpResult" -ForegroundColor Red
        }
    }

    Write-Host "[Master] Synchronization complete: $successCount succeeded, $errorCount failed" -ForegroundColor Green
}

# ========== MAIN ==========

if (-not $Mode)
{
    Write-Host "Usage: .\synchronizer.ps1 -Mode <state|serve|diff|synchronize>" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Modes:"
    Write-Host "  state        - Generate state file of current directory"
    Write-Host "  serve        - Serve state file via HTTP"
    Write-Host "  diff         - Generate diff by comparing with target state"
    Write-Host "  synchronize  - Transfer files to target via SCP"
    exit 0
}

switch ($Mode)
{
    'state'
    { Generate-State
    }
    'serve'
    { Serve-State
    }
    'diff'
    { Generate-Diff
    }
    'synchronize'
    { Synchronize-Files
    }
}
