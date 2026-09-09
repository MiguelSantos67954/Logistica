$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

try {
    $configPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'config.json'
    $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
    $sql = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($sql)) {
        throw 'A consulta SQL esta vazia.'
    }

    $serverAddress = [string]$config.server
    if (-not [string]::IsNullOrWhiteSpace([string]$config.instanceName)) {
        $serverAddress += '\' + [string]$config.instanceName
    }
    if ($config.port) {
        $serverAddress += ',' + [string]$config.port
    }

    $builder = [System.Data.SqlClient.SqlConnectionStringBuilder]::new()
    $builder['Data Source'] = $serverAddress
    $builder['Initial Catalog'] = [string]$config.database
    $builder['User ID'] = [string]$config.user
    $builder['Password'] = [string]$config.password
    $builder['Integrated Security'] = $false
    $builder['Encrypt'] = [bool]$config.encrypt
    $builder['TrustServerCertificate'] = [bool]$config.trustServerCertificate
    $builder['Connect Timeout'] = 10

    $connection = [System.Data.SqlClient.SqlConnection]::new($builder.ConnectionString)
    try {
        $connection.Open()
        $command = $connection.CreateCommand()
        $command.CommandText = $sql
        $command.CommandTimeout = 90
        $reader = $command.ExecuteReader()
        try {
            $rows = [System.Collections.Generic.List[object]]::new()
            while ($reader.Read()) {
                $row = [ordered]@{}
                for ($index = 0; $index -lt $reader.FieldCount; $index++) {
                    $value = $reader.GetValue($index)
                    if ($value -is [System.DBNull]) { $value = $null }
                    $row[$reader.GetName($index)] = $value
                }
                $rows.Add([pscustomobject]$row)
            }
        } finally {
            $reader.Close()
        }
    } finally {
        if ($connection) { $connection.Dispose() }
    }

    ConvertTo-Json -InputObject @($rows) -Compress -Depth 5
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
