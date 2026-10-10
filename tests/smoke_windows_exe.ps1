param(
    [Parameter(Mandatory = $true)]
    [string] $ExecutablePath
)

$path = (Resolve-Path -LiteralPath $ExecutablePath).Path
$before = @(Get-Process -Name PingScope -ErrorAction SilentlyContinue | ForEach-Object Id)
try {
    Start-Process -FilePath $path | Out-Null
    $deadline = (Get-Date).AddSeconds(15)
    $window = $null
    do {
        $window = Get-Process -Name PingScope -ErrorAction SilentlyContinue |
            Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like 'PingScope*' } |
            Select-Object -First 1
        if (-not $window) { Start-Sleep -Milliseconds 500 }
    } while (-not $window -and (Get-Date) -lt $deadline)

    if (-not $window) {
        throw 'The packaged executable did not show the PingScope main window within 15 seconds.'
    }
    "Window startup succeeded: $($window.MainWindowTitle) (PID $($window.Id))"
}
finally {
    Get-Process -Name PingScope -ErrorAction SilentlyContinue |
        Where-Object { $_.Id -notin $before } |
        Stop-Process -Force -ErrorAction SilentlyContinue
}
