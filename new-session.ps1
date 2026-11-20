param([Parameter(Mandatory)][string]$Path)

$ErrorActionPreference = 'Stop'
$directory = New-Item -ItemType Directory -Path $Path
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$acl = Get-Acl -LiteralPath $directory.FullName
$acl.SetAccessRuleProtection($true, $false)
$rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
    $sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
$acl.SetAccessRule($rule)
Set-Acl -LiteralPath $directory.FullName -AclObject $acl
$verified = Get-Acl -LiteralPath $directory.FullName
$rules = @($verified.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]))
if (!$verified.AreAccessRulesProtected -or $rules.Count -ne 1 -or
    $rules[0].IdentityReference -ne $sid -or
    $rules[0].FileSystemRights -ne 'FullControl' -or $rules[0].AccessControlType -ne 'Allow') {
    throw 'La ACL de la sesión no coincide con la cuenta actual.'
}
foreach ($name in 'request.txt', 'response.txt', 'lock') {
    $slot = New-Item -ItemType File -Path (Join-Path $directory.FullName $name)
    if ($name -eq 'lock') { [System.IO.File]::WriteAllBytes($slot.FullName, [byte[]]@(0)) }
}
$directory.FullName
