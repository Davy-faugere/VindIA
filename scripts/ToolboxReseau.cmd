@echo off
setlocal
echo ============================================
echo   Outils Reseau - demarrage
echo ============================================
echo.

net file >nul 2>&1
if errorlevel 1 (
    echo Elevation administrateur necessaire...
    powershell -NoProfile -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)
echo [1/3] Droits admin : OK

set "PS=%temp%\netbox_%random%.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$all=@(Get-Content -LiteralPath '%~f0'); for($n=0;$n -lt $all.Count;$n++){ if($all[$n].Trim() -ceq 'ZZ_PSSTART_ZZ'){ $all[($n+1)..($all.Count-1)] | Set-Content -LiteralPath '%PS%' -Encoding UTF8; break } }"

if not exist "%PS%" (
    echo [2/3] Extraction : ECHEC
    pause
    exit /b 1
)
echo [2/3] Extraction : OK

echo [3/3] Ouverture de l'interface...
echo.
powershell -STA -NoProfile -ExecutionPolicy Bypass -File "%PS%" -SrcCmd "%~f0"
set "RC=%errorlevel%"
del "%PS%" >nul 2>&1

if not "%RC%"=="0" (
    echo.
    echo   Erreur ^(code %RC%^) - message ci-dessus.
    pause
)
exit /b

ZZ_PSSTART_ZZ
param([string]$SrcCmd)

# ── Icone embarquee (reseau, cohérente avec l'outil) ─────────────
$IcoB64 = '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'
function Write-Ico { param($icoDir)
    $path = Join-Path $icoDir 'toolbox.ico'
    try { [IO.File]::WriteAllBytes($path, [Convert]::FromBase64String($IcoB64)) } catch {}
    if (Test-Path $path) { return $path } else { return $null }
}


# ── Intercepteur global d'erreurs ────────────────────────────────
trap {
    try {
        Add-Type -AssemblyName System.Windows.Forms 2>$null
        [System.Windows.Forms.MessageBox]::Show(
            "Erreur au demarrage :`n`n$($_.Exception.Message)`n`n$($_.InvocationInfo.ScriptLineNumber) : $($_.InvocationInfo.Line)",
            "Erreur", 'OK', 'Error') | Out-Null
    } catch {
        Write-Host "ERREUR : $($_.Exception.Message)" -ForegroundColor Red
        Read-Host "Appuyer sur Entree"
    }
    exit 1
}

# ── Assemblies ───────────────────────────────────────────────────
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName Microsoft.VisualBasic
[System.Windows.Forms.Application]::EnableVisualStyles()

$AppVersion = "1.1"

# ── Chemins : determines selon le mode (portable vs installe) ─────
# $SrcCmd = chemin du .cmd lance. En portable, tout est a cote du .cmd.
$SrcDir     = Split-Path -Parent $SrcCmd
$InstallDir = "$env:ProgramData\.itops"
$InstallCmd = Join-Path $InstallDir "Toolbox-Reseau.cmd"

# Determiner si on tourne DEJA depuis l'emplacement installe
$runFromInstall = $false
try { $runFromInstall = ((Resolve-Path $SrcCmd).Path -eq (Resolve-Path $InstallCmd -EA SilentlyContinue).Path) } catch {}

if ($runFromInstall) {
    # Mode installe : donnees dans ProgramData
    $Dir = $InstallDir
} else {
    # Mode portable par defaut : donnees a cote du .cmd
    $Dir = $SrcDir
}
$Cfg = Join-Path $Dir "toolbox-config.json"
$Log = Join-Path $Dir "toolbox.log"
$IcoPath = Write-Ico $Dir   # icone ecrite a cote (fenetre + reference)

function Write-Log { param([string]$M)
    try { Add-Content $Log ("$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $env:USERNAME@$env:COMPUTERNAME | $M") -EA SilentlyContinue } catch {}
}
function Read-Cfg {
    if (Test-Path $Cfg) { try { return (Get-Content $Cfg -Raw -Encoding UTF8 | ConvertFrom-Json) } catch {} }
    return [PSCustomObject]@{ dns = @(); lecteurs = @() }
}
function Save-Cfg { param($C)
    try { $C | ConvertTo-Json -Depth 4 | Set-Content $Cfg -Encoding UTF8 } catch {
        [System.Windows.Forms.MessageBox]::Show("Impossible d'ecrire la config ici :`n$Cfg`n`nSupport en lecture seule ?","Attention",'OK','Warning') | Out-Null
    }
}
function Test-IPv4 { param([string]$s)
    # 4 octets exiges : .NET accepte sinon les formes abregees ('192.168.1' -> 192.168.0.1)
    if ($s -notmatch '^\d{1,3}(\.\d{1,3}){3}$') { return $false }
    $ip = $null
    return ([Net.IPAddress]::TryParse($s, [ref]$ip) -and $ip.AddressFamily -eq 'InterNetwork')
}

# ── Admin check ───────────────────────────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process cmd -Verb RunAs -ArgumentList "/c `"$SrcCmd`""
    exit
}

# ── Choix mode : uniquement si PAS deja installe ─────────────────
if (-not $runFromInstall) {
    $btn = [System.Windows.Forms.MessageBox]::Show(
        "Mode de fonctionnement`n`n" +
        "OUI  = Installer sur ce poste (dossier cache ProgramData + raccourci Bureau)`n" +
        "NON  = Mode PORTABLE (rien n'est installe, tout reste a cote du fichier)`n" +
        "ANNULER = Quitter",
        "Outils Reseau", 'YesNoCancel', 'Question')

    if ($btn -eq 'Cancel') { exit }

    if ($btn -eq 'Yes') {
        # ── Installation ──
        try {
            $null = New-Item $InstallDir -ItemType Directory -Force -EA SilentlyContinue
            Copy-Item $SrcCmd $InstallCmd -Force
            attrib +h +s "$InstallDir" 2>$null
            try {
                $acl = Get-Acl $InstallDir; $acl.SetAccessRuleProtection($true, $false)
                $acl.Access | ForEach-Object { [void]$acl.RemoveAccessRule($_) }
                foreach ($sid in 'S-1-5-32-544','S-1-5-18') {
                    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
                        [Security.Principal.SecurityIdentifier]$sid,
                        'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
                }
                # Utilisateurs : lecture + execution (indispensable pour lancer via le raccourci)
                $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
                    [Security.Principal.SecurityIdentifier]'S-1-5-32-545',
                    'ReadAndExecute','ContainerInherit,ObjectInherit','None','Allow'))
                Set-Acl $InstallDir $acl
            } catch {}
            # Icone dans le dossier installe (pour le raccourci)
            $InstallIco = Write-Ico $InstallDir
            # Raccourci Bureau
            $wsh = New-Object -ComObject WScript.Shell
            $sc  = $wsh.CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\Outils Reseau.lnk")
            $sc.TargetPath = "$env:SystemRoot\System32\cmd.exe"
            $sc.Arguments  = "/c `"$InstallCmd`""
            $sc.WorkingDirectory = $InstallDir
            $sc.Description = "Outils Reseau - intervenant IT/OT"
            if ($InstallIco) { $sc.IconLocation = "$InstallIco,0" }
            $sc.Save()
            Write-Log "INSTALLATION"
            [System.Windows.Forms.MessageBox]::Show(
                "Installe.`nRaccourci 'Outils Reseau' cree sur le Bureau.`n`nRelance depuis l'emplacement installe...",
                "Installation terminee", 'OK', 'Information') | Out-Null
            Start-Process cmd -ArgumentList "/c `"$InstallCmd`""
            exit
        } catch {
            [System.Windows.Forms.MessageBox]::Show("Echec installation :`n$($_.Exception.Message)`n`nPassage en mode portable.","Erreur",'OK','Error') | Out-Null
        }
    }
    # Si NON (ou echec install) : on continue en portable, $Dir reste = $SrcDir
    Write-Log "DEMARRAGE PORTABLE"
}

# ────────────────────────────────────────────────────────────────
#  HELPERS WINFORMS
# ────────────────────────────────────────────────────────────────
# --- Theme industriel sombre neutre ---
$Blue  = [Drawing.Color]::FromArgb(45, 140, 220)    # accent bleu technique
$BGray = [Drawing.Color]::FromArgb(30, 33, 39)       # fond principal anthracite
$White = [Drawing.Color]::White                       # texte sur surfaces colorees
$CardBg  = [Drawing.Color]::FromArgb(42, 46, 54)        # fond des panneaux / cartes
$TxtBg = [Drawing.Color]::FromArgb(48, 52, 60)        # fond des champs de saisie
$TxtFg = [Drawing.Color]::FromArgb(224, 227, 232)     # texte clair
$LGray = [Drawing.Color]::FromArgb(52, 56, 64)        # champs readonly / separateurs
$Dark  = [Drawing.Color]::FromArgb(224, 227, 232)     # texte clair (compat)
$Green = [Drawing.Color]::FromArgb(78, 201, 128)
$Red   = [Drawing.Color]::FromArgb(232, 100, 90)
$Mute  = [Drawing.Color]::FromArgb(150, 154, 162)     # texte attenue

$FN  = [Drawing.Font]::new("Segoe UI", 9)
$FNB = [Drawing.Font]::new("Segoe UI", 9,  [Drawing.FontStyle]::Bold)
$FNH = [Drawing.Font]::new("Segoe UI", 11, [Drawing.FontStyle]::Bold)

function New-Label { param($txt,$x,$y,$w=130,$h=24,$bold=$false)
    $c = [System.Windows.Forms.Label]::new()
    $c.Text = $txt; $c.Location = [Drawing.Point]::new($x,$y)
    $c.Size = [Drawing.Size]::new($w,$h); $c.TextAlign = 'MiddleLeft'
    $c.Font = if ($bold) { $FNB } else { $FN }
    $c.ForeColor = $TxtFg
    return $c
}
function New-Txt { param($x,$y,$w=230,$v="",$ro=$false)
    $c = [System.Windows.Forms.TextBox]::new()
    $c.Location = [Drawing.Point]::new($x,$y); $c.Size = [Drawing.Size]::new($w,26)
    $c.Text = $v; $c.Font = $FN; $c.ReadOnly = $ro
    $c.BorderStyle = 'FixedSingle'
    if ($ro) { $c.BackColor = $LGray; $c.ForeColor = [Drawing.Color]::FromArgb(200,203,208) }
    else     { $c.BackColor = $TxtBg; $c.ForeColor = $TxtFg }
    return $c
}
function New-Btn { param($txt,$x,$y,$w=110,$h=30,$bg="",$fg="")
    $c = [System.Windows.Forms.Button]::new()
    $c.Text = $txt; $c.Location = [Drawing.Point]::new($x,$y)
    $c.Size = [Drawing.Size]::new($w,$h)
    $c.BackColor = if ($bg) { $bg } else { $Blue }
    $c.ForeColor = if ($fg) { $fg } else { $White }
    $c.FlatStyle = 'Flat'; $c.FlatAppearance.BorderSize = 0
    $c.Font = $FNB; $c.Cursor = 'Hand'
    return $c
}
function New-Sep { param($x,$y,$w=840,$h=1)
    $c = [System.Windows.Forms.Panel]::new()
    $c.Location = [Drawing.Point]::new($x,$y)
    $c.Size = [Drawing.Size]::new($w,$h); $c.BackColor = $LGray
    return $c
}
function New-Tab { param($name)
    $t = [System.Windows.Forms.TabPage]::new()
    $t.Text = "  $name  "; $t.BackColor = $BGray
    $t.Padding = [Windows.Forms.Padding]::new(16,12,16,12)
    return $t
}
function Dlg-OK  { param($m,$t="Information")
    [System.Windows.Forms.MessageBox]::Show($m,$t,'OK','Information') | Out-Null }
function Dlg-Err { param($m)
    [System.Windows.Forms.MessageBox]::Show($m,"Erreur",'OK','Error') | Out-Null }
function Dlg-YN  { param($m,$t="Confirmer")
    return [System.Windows.Forms.MessageBox]::Show($m,$t,'YesNo','Question') -eq 'Yes' }

# ────────────────────────────────────────────────────────────────
#  FENETRE PRINCIPALE
# ────────────────────────────────────────────────────────────────
$F = [System.Windows.Forms.Form]::new()
$F.Text = "Outils Reseau v$AppVersion  -  $env:COMPUTERNAME  " + $(if($runFromInstall){"[Installe]"}else{"[Portable]"})
$F.Size = [Drawing.Size]::new(1040, 748)
$F.StartPosition = 'CenterScreen'
$F.BackColor = $BGray
$F.Font = $FN
$F.FormBorderStyle = 'Sizable'
$F.MaximizeBox = $true
$F.MinimumSize = [Drawing.Size]::new(1056, 787)
if ($IcoPath -and (Test-Path $IcoPath)) { try { $F.Icon = [System.Drawing.Icon]::new($IcoPath) } catch {} }

# Barre titre - charbon avec lisere bleu technique
$hdr = [System.Windows.Forms.Panel]::new()
$hdr.Dock = 'Top'; $hdr.Height = 50; $hdr.BackColor = [Drawing.Color]::FromArgb(36, 40, 48)
$F.Controls.Add($hdr)

# Lisere d'accent en bas du bandeau
$hAccent = [System.Windows.Forms.Panel]::new()
$hAccent.Location = [Drawing.Point]::new(0,48); $hAccent.Size = [Drawing.Size]::new(940,2)
$hAccent.BackColor = $Blue
$hdr.Controls.Add($hAccent)

$hL = New-Label "  Outils Reseau  -  Intervenant IT/OT" 0 0 650 48 $true
$hL.ForeColor = $White; $hL.Font = $FNH; $hdr.Controls.Add($hL)

$hR = New-Label "$env:COMPUTERNAME  |  $(Get-Date -Format 'dd/MM/yyyy HH:mm')" 500 0 320 48
$hR.ForeColor = [Drawing.Color]::FromArgb(150,175,205)
$hR.TextAlign = 'MiddleRight'; $hR.Anchor = 'Top,Right'; $hdr.Controls.Add($hR)
$hClock = [System.Windows.Forms.Timer]::new()
$hClock.Interval = 30000
$hClock.Add_Tick({ $hR.Text = "$env:COMPUTERNAME  |  $(Get-Date -Format 'dd/MM/yyyy HH:mm')" })
$hClock.Start()

# TabControl
$TC = [System.Windows.Forms.TabControl]::new()
$TC.Location = [Drawing.Point]::new(0,50)
$TC.Size = [Drawing.Size]::new(1040, 668); $TC.Anchor = 'Top,Bottom,Left,Right'
$TC.Font = $FN
# Onglets dessines a la main pour un rendu sombre coherent
$TC.DrawMode = 'OwnerDrawFixed'
$TC.SizeMode = 'Fixed'
$TC.ItemSize = [Drawing.Size]::new(80, 28)
$TC.Add_DrawItem({
    param($sender,$e)
    $page = $sender.TabPages[$e.Index]
    $rect = $sender.GetTabRect($e.Index)
    $selected = ($e.Index -eq $sender.SelectedIndex)
    $bg = if ($selected) { [Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(45,140,220)) }
          else           { [Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(38,42,50)) }
    $e.Graphics.FillRectangle($bg, $rect)
    $fg = if ($selected) { [Drawing.Color]::White } else { [Drawing.Color]::FromArgb(190,194,202) }
    $sf = [Drawing.StringFormat]::new()
    $sf.Alignment = 'Center'; $sf.LineAlignment = 'Center'
    $e.Graphics.DrawString($page.Text.Trim(), $sender.Font,
        [Drawing.SolidBrush]::new($fg), [Drawing.RectangleF]::new($rect.X,$rect.Y,$rect.Width,$rect.Height), $sf)
    $bg.Dispose()
})
$F.Controls.Add($TC)

# ════════════════════════════════════════════════════════════════
#  ONGLET  MACHINE
# ════════════════════════════════════════════════════════════════
$tM = New-Tab "Machine"
$TC.TabPages.Add($tM)

$cs   = Get-CimInstance Win32_ComputerSystem
$bios = Get-CimInstance Win32_BIOS
$os   = Get-CimInstance Win32_OperatingSystem
$up   = (Get-Date) - $os.LastBootUpTime
$dsk  = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" -EA SilentlyContinue
$lic  = Get-CimInstance SoftwareLicensingProduct `
    -Filter "PartialProductKey IS NOT NULL AND ApplicationID='55c92734-d682-4d71-983e-d6ec3f16059f'" `
    -EA SilentlyContinue | Select-Object -First 1

$tM.Controls.Add((New-Label "Identification" 0 4 300 22 $true))
$tM.Controls.Add((New-Sep 0 28 880))

$rowsL = @("Nom machine","Fabricant","Modele","N. serie (ST)","BIOS")
$valsL = @($env:COMPUTERNAME, $cs.Manufacturer, $cs.Model, $bios.SerialNumber, $bios.SMBIOSBIOSVersion)
$rowsR = @("OS","Build","Uptime","Disque C:","Domaine")
$valsR = @($os.Caption, $os.BuildNumber,
    ("{0}j {1}h {2}m" -f $up.Days,$up.Hours,$up.Minutes),
    $(if($dsk){"{0:N1}/{1:N1} Go" -f ($dsk.FreeSpace/1GB),($dsk.Size/1GB)}else{"-"}),
    $cs.Domain)

$y = 40
for ($i=0; $i -lt $rowsL.Count; $i++) {
    $tM.Controls.Add((New-Label "$($rowsL[$i]) :" 0   $y))
    $tM.Controls.Add((New-Txt 135 $y 260 $valsL[$i] $true))
    $tM.Controls.Add((New-Label "$($rowsR[$i]) :" 440 $y))
    $tM.Controls.Add((New-Txt 575 $y 280 $valsR[$i] $true))
    $y += 36
}
$actTxt = switch ($lic.LicenseStatus) {1{"ACTIVE"};0{"NON ACTIVE"};2{"GRACE"};default{"Inconnu"}}
$actCol = if ($lic.LicenseStatus -eq 1) { $Green } else { $Red }
$tM.Controls.Add((New-Label "Activation :" 440 $y))
$tAct = New-Txt 575 $y 280 $actTxt $true; $tAct.ForeColor = $actCol; $tM.Controls.Add($tAct)

$tM.Controls.Add((New-Sep 0 270 880))
$tM.Controls.Add((New-Label "Renommer ce poste" 0 282 300 22 $true))
$tM.Controls.Add((New-Label "Nouveau nom :" 0 314))
$txRen = New-Txt 135 311 280 $env:COMPUTERNAME; $tM.Controls.Add($txRen)
$bRen  = New-Btn "Renommer" 428 310 120; $tM.Controls.Add($bRen)
$bRen.Add_Click({
    $nn = $txRen.Text.Trim()
    if ([string]::IsNullOrEmpty($nn) -or $nn -eq $env:COMPUTERNAME) { return }
    if ($nn.Length -gt 15 -or $nn -notmatch '^[A-Za-z0-9][A-Za-z0-9-]*$' -or $nn -match '^[0-9]+$') {
        Dlg-Err "Nom invalide : 15 caracteres max, lettres/chiffres/tirets, et pas uniquement des chiffres."; return }
    if (Dlg-YN "Renommer '$env:COMPUTERNAME' en '$nn' ?`n(redemarrage requis)") {
        try { Rename-Computer -NewName $nn -Force; Write-Log "RENAME $env:COMPUTERNAME->$nn"
              Dlg-OK "Renomme en '$nn'. Redemarrez pour appliquer." }
        catch { Dlg-Err $_.Exception.Message }
    }
})

# ════════════════════════════════════════════════════════════════
#  ONGLET  MATERIEL  (RAM, CPU/noyau, temperatures, ventilateurs)
# ════════════════════════════════════════════════════════════════
$tHw = New-Tab "Materiel"
$TC.TabPages.Add($tHw)

$tHw.Controls.Add((New-Label "Informations materielles detaillees" 0 4 500 22 $true))
$tHw.Controls.Add((New-Sep 0 28 940))

$bHwRef = New-Btn "Rafraichir" 0 40 120 30; $tHw.Controls.Add($bHwRef)
$bHwSave = New-Btn "Exporter (fichier)" 130 40 160 30 $LGray; $tHw.Controls.Add($bHwSave)

$rtHw = [System.Windows.Forms.RichTextBox]::new()
$rtHw.Anchor = 'Top,Bottom,Left,Right'
$rtHw.Location=[Drawing.Point]::new(0,80); $rtHw.Size=[Drawing.Size]::new(940,490)
$rtHw.Font=[Drawing.Font]::new("Consolas",9); $rtHw.ReadOnly=$true
$rtHw.BackColor=[Drawing.Color]::FromArgb(24,26,31); $rtHw.ForeColor=$TxtFg; $rtHw.BorderStyle='FixedSingle'
$tHw.Controls.Add($rtHw)

function HwW { param($t,$col='n')
    $c = switch($col){ 'ok'{$Green} 'hi'{$Blue} 'warn'{[Drawing.Color]::DarkOrange} 'ko'{$Red} 'ttl'{[Drawing.Color]::FromArgb(120,200,255)} default{$TxtFg} }
    $rtHw.SelectionColor=$c; $rtHw.AppendText("$t`r`n")
}
function RamTypeName { param($code)
    switch ([int]$code) { 20{"DDR"} 21{"DDR2"} 22{"DDR2 FB-DIMM"} 24{"DDR3"} 26{"DDR4"} 34{"DDR5"} default{"Type $code"} }
}

function Load-Hardware {
    $rtHw.Clear()
    # --- Processeur ---
    HwW "=== PROCESSEUR (noyau) ===" 'ttl'
    foreach ($cpu in (Get-CimInstance Win32_Processor -EA SilentlyContinue)) {
        HwW ("  {0}" -f $cpu.Name.Trim())
        HwW ("  Coeurs physiques : {0}    Threads logiques : {1}" -f $cpu.NumberOfCores, $cpu.NumberOfLogicalProcessors)
        HwW ("  Frequence        : {0} MHz (base {1} MHz)" -f $cpu.CurrentClockSpeed, $cpu.MaxClockSpeed)
        $load = $cpu.LoadPercentage
        if ($null -ne $load) {
            $lc = if ($load -ge 85){'ko'}elseif($load -ge 60){'warn'}else{'ok'}
            HwW ("  Charge actuelle  : {0}%" -f $load) $lc
        }
        if ($cpu.L2CacheSize) { HwW ("  Cache L2 / L3     : {0} Ko / {1} Ko" -f $cpu.L2CacheSize, $cpu.L3CacheSize) }
        HwW ("  Socket           : {0}" -f $cpu.SocketDesignation)
    }
    HwW ""
    # --- Memoire ---
    HwW "=== MEMOIRE (RAM) ===" 'ttl'
    $os = Get-CimInstance Win32_OperatingSystem -EA SilentlyContinue
    $totKo = $os.TotalVisibleMemorySize; $freeKo = $os.FreePhysicalMemory
    $usedPct = [int]((($totKo - $freeKo) / $totKo) * 100)
    $uc = if ($usedPct -ge 90){'ko'}elseif($usedPct -ge 75){'warn'}else{'ok'}
    HwW ("  Total : {0:N1} Go    Utilisee : {1}%    Libre : {2:N1} Go" -f ($totKo/1MB),$usedPct,($freeKo/1MB)) $uc
    HwW ""
    $slots = Get-CimInstance Win32_PhysicalMemory -EA SilentlyContinue
    $arr = Get-CimInstance Win32_PhysicalMemoryArray -EA SilentlyContinue | Select-Object -First 1
    if ($arr) { HwW ("  Emplacements : {0} occupe(s) sur {1}" -f @($slots).Count, $arr.MemoryDevices) }
    foreach ($m in $slots) {
        HwW ("   - {0} : {1:N0} Go  {2} MHz  {3}  {4}  [{5}]" -f `
            $m.DeviceLocator, ($m.Capacity/1GB), $m.Speed, (RamTypeName $m.SMBIOSMemoryType), `
            ($m.Manufacturer -replace '\s+$',''), ($m.PartNumber -replace '\s+$',''))
    }
    HwW ""
    # --- Temperatures ---
    HwW "=== TEMPERATURES ===" 'ttl'
    try {
        $tz = Get-CimInstance -Namespace "root/WMI" -ClassName MSAcpi_ThermalZoneTemperature -EA Stop
        $any=$false
        foreach ($z in $tz) {
            $celsius = [math]::Round(($z.CurrentTemperature / 10) - 273.15, 1)
            $tc = if ($celsius -ge 80){'ko'}elseif($celsius -ge 60){'warn'}else{'ok'}
            HwW ("  Zone {0} : {1} C" -f ($z.InstanceName -replace '.*\\',''), $celsius) $tc
            $any=$true
        }
        if (-not $any) { HwW "  Aucune zone thermique exposee." 'warn' }
    } catch {
        HwW "  Capteurs ACPI non exposes par cette machine." 'warn'
        HwW "  (temperature CPU/GPU precise = outil dedie type HWiNFO)"
    }
    HwW ""
    # --- Ventilateurs ---
    HwW "=== VENTILATEURS ===" 'ttl'
    $fans = Get-CimInstance Win32_Fan -EA SilentlyContinue
    $fanInfo=$false
    foreach ($f in $fans) {
        if ($f.DesiredSpeed -and $f.DesiredSpeed -gt 0) {
            HwW ("  {0} : {1} RPM" -f $f.DeviceID, $f.DesiredSpeed); $fanInfo=$true
        }
    }
    if (-not $fanInfo) {
        HwW "  Windows n'expose pas les vitesses de ventilateurs." 'warn'
        HwW "  Les RPM proviennent du chipset de la carte mere (Super I/O) et"
        HwW "  necessitent un outil dedie (HWiNFO, ou l'utilitaire du fabricant)."
    }
    HwW ""
    # --- Carte graphique ---
    HwW "=== CARTE GRAPHIQUE ===" 'ttl'
    foreach ($gpu in (Get-CimInstance Win32_VideoController -EA SilentlyContinue)) {
        $vram = if ($gpu.AdapterRAM) { "{0:N0} Mo" -f ($gpu.AdapterRAM/1MB) } else { "n/a" }
        HwW ("  {0}" -f $gpu.Name)
        HwW ("  Memoire : {0}    Pilote : {1}    Resolution : {2}x{3}" -f $vram, $gpu.DriverVersion, $gpu.CurrentHorizontalResolution, $gpu.CurrentVerticalResolution)
    }
    HwW ""
    # --- Noyau / systeme ---
    HwW "=== NOYAU / SYSTEME ===" 'ttl'
    HwW ("  Windows : {0}" -f $os.Caption)
    HwW ("  Version : {0}  (build {1})" -f $os.Version, $os.BuildNumber)
    HwW ("  Architecture : {0}" -f $os.OSArchitecture)
    $bb = Get-CimInstance Win32_BIOS -EA SilentlyContinue
    HwW ("  BIOS/UEFI : {0}  {1}" -f $bb.Manufacturer, $bb.SMBIOSBIOSVersion)
    Write-Log "MATERIEL consulte"
}

$bHwRef.Add_Click({ Load-Hardware })
$bHwSave.Add_Click({
    $out = Join-Path ([Environment]::GetFolderPath('MyDocuments')) ("Materiel-" + $env:COMPUTERNAME + "-" + (Get-Date -Format 'yyyyMMdd-HHmm') + ".txt")
    [IO.File]::WriteAllText($out, $rtHw.Text, [Text.UTF8Encoding]::new($false))
    Dlg-OK "Exporte :`n$out"; Start-Process notepad $out
})
Load-Hardware


# ════════════════════════════════════════════════════════════════
#  ONGLET  ADRESSAGE IP
# ════════════════════════════════════════════════════════════════
$tIP = New-Tab "Adressage"
$TC.TabPages.Add($tIP)

$tIP.Controls.Add((New-Label "Interface :" 0 4 90 26))
$Script:allAd = @(Get-NetAdapter | Where-Object { $_.HardwareInterface } | Sort-Object ifIndex)
$cbo = [System.Windows.Forms.ComboBox]::new()
$cbo.BackColor=$TxtBg; $cbo.ForeColor=$TxtFg; $cbo.FlatStyle='Flat'
$cbo.Location=[Drawing.Point]::new(95,2); $cbo.Size=[Drawing.Size]::new(300,26)
$cbo.DropDownStyle='DropDownList'; $cbo.Font=$FN
$Script:allAd | ForEach-Object { $cbo.Items.Add($_.Name) | Out-Null }
if ($cbo.Items.Count -gt 0) { $cbo.SelectedIndex = 0 }
$tIP.Controls.Add($cbo)
$bLoadIP = New-Btn "Charger" 406 1 90 28; $tIP.Controls.Add($bLoadIP)
$tIP.Controls.Add((New-Sep 0 36 880))

# Gauche : etat actuel (readonly)
$tIP.Controls.Add((New-Label "Etat actuel" 0 48 300 22 $true))
$Script:roIP = @{}
$labRO = @("Adresse IP","Masque","Passerelle","DNS actuel","MAC","Mode")
$yRO = 74
foreach ($fld in $labRO) {
    $tIP.Controls.Add((New-Label "$fld :" 0 $yRO 95 24))
    $t = New-Txt 100 $yRO 295 "" $true; $Script:roIP[$fld] = $t; $tIP.Controls.Add($t); $yRO += 34
}

$tIP.Controls.Add((New-Sep 418 36 1 520))

# Droite : formulaire edition
$tIP.Controls.Add((New-Label "Modifier  (Entree = conserver)" 432 48 380 22 $true))
$Script:edIP = @{}
$labED = @("Adresse IP","Masque","Passerelle","DNS (virgule)")
$yED = 74
foreach ($fld in $labED) {
    $tIP.Controls.Add((New-Label "$fld :" 432 $yED 120 24))
    $t = New-Txt 558 $yED 290 ""; $Script:edIP[$fld] = $t; $tIP.Controls.Add($t); $yED += 34
}
$chkDHCP = [System.Windows.Forms.CheckBox]::new()
$chkDHCP.Text = "Activer DHCP"; $chkDHCP.Location = [Drawing.Point]::new(432,$yED)
$chkDHCP.Size = [Drawing.Size]::new(200,24); $chkDHCP.Font = $FN
$tIP.Controls.Add($chkDHCP)

$bApplyIP = New-Btn "Appliquer la configuration" 432 ($yED+36) 220 32; $tIP.Controls.Add($bApplyIP)

$Script:curAd = $null
$Script:loadAd = {
    $name = $cbo.SelectedItem; if (-not $name) { return }
    $ad = $Script:allAd | Where-Object { $_.Name -eq $name }
    $Script:curAd = $ad
    $conf = Get-NetIPConfiguration -InterfaceIndex $ad.ifIndex -EA SilentlyContinue
    $ipA  = $conf.IPv4Address | Where-Object { $_.PrefixOrigin -ne 'WellKnown' } | Select-Object -First 1
    $gwA  = $conf.IPv4DefaultGateway.NextHop
    $dnsA = ($conf.DNSServer | Where-Object { $_.AddressFamily -eq 2 } |
             Select-Object -ExpandProperty ServerAddresses) -join ', '
    $mode = (Get-NetIPInterface -InterfaceIndex $ad.ifIndex -AddressFamily IPv4 -EA SilentlyContinue).Dhcp
    $msk  = ""
    if ($ipA) {
        $m = [uint32]([math]::Pow(2,32) - [math]::Pow(2,(32 - $ipA.PrefixLength)))
        $b = [BitConverter]::GetBytes($m)
        if ([BitConverter]::IsLittleEndian) { [Array]::Reverse($b) }
        $msk = $b -join '.'
    }
    $Script:roIP["Adresse IP"].Text = if ($ipA) { $ipA.IPAddress } else { "" }
    $Script:roIP["Masque"].Text     = $msk
    $Script:roIP["Passerelle"].Text = if ($gwA) { $gwA } else { "" }
    $Script:roIP["DNS actuel"].Text = $dnsA
    $Script:roIP["MAC"].Text        = $ad.MacAddress
    $Script:roIP["Mode"].Text       = if ($mode -eq 'Disabled') { "Statique" } else { "DHCP" }
    $cfg = Read-Cfg
    $defDNS = if ($cfg.dns -and $cfg.dns.Count -gt 0) { $cfg.dns -join ', ' } else { $dnsA }
    $Script:edIP["Adresse IP"].Text    = if ($ipA) { $ipA.IPAddress } else { "" }
    $Script:edIP["Masque"].Text        = if ($msk) { $msk } else { "255.255.255.0" }
    $Script:edIP["Passerelle"].Text    = if ($gwA) { $gwA } else { "" }
    $Script:edIP["DNS (virgule)"].Text = $defDNS
    $chkDHCP.Checked = ($mode -ne 'Disabled')
}
$cbo.Add_SelectedIndexChanged($Script:loadAd)
$bLoadIP.Add_Click($Script:loadAd)
if ($cbo.Items.Count -gt 0) { & $Script:loadAd }

$bApplyIP.Add_Click({
    if (-not $Script:curAd) { return }
    $ad = $Script:curAd
    if ($chkDHCP.Checked) {
        if (Dlg-YN "Activer DHCP sur $($ad.Name) ?") {
            try {
                Set-NetIPInterface -InterfaceIndex $ad.ifIndex -Dhcp Enabled
                Set-DnsClientServerAddress -InterfaceIndex $ad.ifIndex -ResetServerAddresses
                Write-Log "DHCP [$($ad.Name)]"; Dlg-OK "DHCP active sur $($ad.Name)."
                & $Script:loadAd
            } catch { Dlg-Err $_.Exception.Message }
        }; return
    }
    $newIP  = $Script:edIP["Adresse IP"].Text.Trim()
    $newMsk = $Script:edIP["Masque"].Text.Trim()
    $newGW  = $Script:edIP["Passerelle"].Text.Trim()
    $newDNS = $Script:edIP["DNS (virgule)"].Text.Trim()
    if ([string]::IsNullOrEmpty($newIP)) { Dlg-Err "Adresse IP requise."; return }
    if (-not (Test-IPv4 $newIP)) { Dlg-Err "Adresse IP invalide : $newIP"; return }
    try {
        $b = ([Net.IPAddress]$newMsk).GetAddressBytes()
        $bin = ($b | ForEach-Object { [Convert]::ToString($_,2).PadLeft(8,'0') }) -join ''
        if ($bin -notmatch '^1+0*$') { Dlg-Err "Masque invalide (bits non contigus) : $newMsk"; return }
        $pre = ($bin.ToCharArray() | Where-Object { $_ -eq '1' }).Count
    } catch { Dlg-Err "Masque invalide."; return }
    if ($newGW -and -not (Test-IPv4 $newGW)) { Dlg-Err "Passerelle invalide : $newGW"; return }
    $dnsArr = ($newDNS -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $badDNS = @($dnsArr | Where-Object { -not (Test-IPv4 $_) })
    if ($badDNS.Count -gt 0) { Dlg-Err "DNS invalide(s) : $($badDNS -join ', ')"; return }
    $recap  = "Interface : $($ad.Name)`nIP : $newIP/$pre`nMasque : $newMsk`nGW : $(if($newGW){$newGW}else{'aucune'})`nDNS : $($dnsArr -join ', ')"
    if (Dlg-YN "Appliquer ?`n`n$recap") {
        try {
            Get-NetIPAddress -InterfaceIndex $ad.ifIndex -AddressFamily IPv4 -EA SilentlyContinue |
                Remove-NetIPAddress -Confirm:$false -EA SilentlyContinue
            Get-NetRoute -InterfaceIndex $ad.ifIndex -DestinationPrefix '0.0.0.0/0' -EA SilentlyContinue |
                Remove-NetRoute -Confirm:$false -EA SilentlyContinue
            Set-NetIPInterface -InterfaceIndex $ad.ifIndex -Dhcp Disabled -EA SilentlyContinue
            $p = @{ InterfaceIndex=$ad.ifIndex; IPAddress=$newIP; PrefixLength=$pre; ErrorAction='Stop' }
            if ($newGW) { $p.DefaultGateway = $newGW }
            New-NetIPAddress @p | Out-Null
            if ($dnsArr.Count -gt 0) { Set-DnsClientServerAddress -InterfaceIndex $ad.ifIndex -ServerAddresses $dnsArr -EA Stop }
            Write-Log "IP [$($ad.Name)] $newIP/$pre GW=$newGW DNS=$($dnsArr -join ';')"
            Dlg-OK "Configuration appliquee."; & $Script:loadAd
        } catch { Dlg-Err $_.Exception.Message }
    }
})

# ════════════════════════════════════════════════════════════════
#  ONGLET  DNS
# ════════════════════════════════════════════════════════════════
$tDNS = New-Tab "DNS"
$TC.TabPages.Add($tDNS)

$tDNS.Controls.Add((New-Label "Serveurs DNS du profil" 0 4 400 22 $true))
$tDNS.Controls.Add((New-Sep 0 28 880))

$lbDNS = [System.Windows.Forms.ListBox]::new()
$lbDNS.Location=[Drawing.Point]::new(0,40); $lbDNS.Size=[Drawing.Size]::new(390,285)
$lbDNS.Font=$FN; $lbDNS.BackColor=$CardBg; $lbDNS.ForeColor=$TxtFg; $lbDNS.BorderStyle='FixedSingle'; $tDNS.Controls.Add($lbDNS)

$Script:loadDNS = { $lbDNS.Items.Clear(); (Read-Cfg).dns | ForEach-Object { $lbDNS.Items.Add($_) | Out-Null } }
& $Script:loadDNS

$tDNS.Controls.Add((New-Label "Nouveau DNS :" 0 340 110 26))
$txDA = New-Txt 114 338 180 ""; $tDNS.Controls.Add($txDA)
$bDA = New-Btn "Ajouter" 300 337 90 28; $tDNS.Controls.Add($bDA)
$bDD = New-Btn "Supprimer" 0 378 120 28 $Red; $tDNS.Controls.Add($bDD)
$bDP = New-Btn "Appliquer sur toutes les cartes" 130 378 260 28 $Green; $tDNS.Controls.Add($bDP)

$tDNS.Controls.Add((New-Sep 405 28 1 366))
$tDNS.Controls.Add((New-Label "Etat des cartes" 420 4 400 22 $true))
$rtDNS = [System.Windows.Forms.RichTextBox]::new()
$rtDNS.Anchor = 'Top,Bottom,Left,Right'
$rtDNS.Location=[Drawing.Point]::new(420,40); $rtDNS.Size=[Drawing.Size]::new(470,366)
$rtDNS.Font=[Drawing.Font]::new("Courier New",8); $rtDNS.ReadOnly=$true
$rtDNS.BackColor=$CardBg; $rtDNS.ForeColor=$TxtFg; $rtDNS.BorderStyle='FixedSingle'; $tDNS.Controls.Add($rtDNS)

$Script:refreshDNS = {
    $cfg = Read-Cfg; $sb = [System.Text.StringBuilder]::new()
    foreach ($ad in (Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.HardwareInterface})) {
        $pres = @((Get-DnsClientServerAddress -InterfaceIndex $ad.ifIndex -AddressFamily IPv4 -EA SilentlyContinue).ServerAddresses)
        $ko   = @($cfg.dns | Where-Object { $_ -notin $pres })
        $st   = if ($ko.Count -eq 0 -or $cfg.dns.Count -eq 0) {"[OK]"} else {"[KO]"}
        [void]$sb.AppendLine("$st  $($ad.Name)")
        [void]$sb.AppendLine("     $($pres -join ' , ')")
        if ($ko.Count -gt 0) { [void]$sb.AppendLine("     Manque: $($ko -join ', ')") }
        [void]$sb.AppendLine()
    }
    $rtDNS.Text = $sb.ToString()
}
& $Script:refreshDNS

$bDR = New-Btn "Rafraichir l'etat" 0 416 150 28 $LGray; $tDNS.Controls.Add($bDR)
$bDF = New-Btn "Vider le cache DNS" 160 416 170 28 $LGray; $tDNS.Controls.Add($bDF)
$bDR.Add_Click({ & $Script:refreshDNS })
$bDF.Add_Click({ Clear-DnsClientCache -EA SilentlyContinue; Write-Log "FLUSHDNS"; Dlg-OK "Cache DNS vide." })

$bDA.Add_Click({
    $ip = $txDA.Text.Trim(); if ([string]::IsNullOrEmpty($ip)) { return }
    if (-not (Test-IPv4 $ip)) { Dlg-Err "Adresse DNS invalide : $ip"; return }
    $c = Read-Cfg
    if ($c.dns -notcontains $ip) { $c.dns = @($c.dns) + @($ip); Save-Cfg $c; Write-Log "DNS+ $ip"; & $Script:loadDNS; & $Script:refreshDNS }
    $txDA.Clear()
})
$bDD.Add_Click({
    if (-not $lbDNS.SelectedItem) { return }
    $sel = $lbDNS.SelectedItem; $c = Read-Cfg
    $c.dns = @($c.dns | Where-Object { $_ -ne $sel }); Save-Cfg $c; Write-Log "DNS- $sel"
    & $Script:loadDNS; & $Script:refreshDNS
})
$bDP.Add_Click({
    $c = Read-Cfg
    if ($c.dns.Count -eq 0) { Dlg-OK "Aucun DNS dans le profil."; return }
    foreach ($ad in (Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.HardwareInterface})) {
        $curr = @((Get-DnsClientServerAddress -InterfaceIndex $ad.ifIndex -AddressFamily IPv4 -EA SilentlyContinue).ServerAddresses)
        $fin  = @($c.dns) + @($curr | Where-Object { $_ -notin $c.dns })
        Set-DnsClientServerAddress -InterfaceIndex $ad.ifIndex -ServerAddresses $fin -EA SilentlyContinue
        Write-Log "DNS PUSH [$($ad.Name)]"
    }
    Clear-DnsClientCache; & $Script:refreshDNS; Dlg-OK "DNS appliques."
})

# ════════════════════════════════════════════════════════════════
#  ONGLET  LECTEURS RESEAU
# ════════════════════════════════════════════════════════════════
$tDr = New-Tab "Lecteurs"
$TC.TabPages.Add($tDr)

$tDr.Controls.Add((New-Label "Lecteurs configures" 0 4 400 22 $true))
$tDr.Controls.Add((New-Sep 0 28 880))

$lvDr = [System.Windows.Forms.ListView]::new()
$lvDr.Anchor = 'Top,Left,Right'
$lvDr.Location=[Drawing.Point]::new(0,40); $lvDr.Size=[Drawing.Size]::new(880,240)
$lvDr.View='Details'; $lvDr.FullRowSelect=$true; $lvDr.GridLines=$true; $lvDr.Font=$FN
$lvDr.BackColor=$CardBg; $lvDr.ForeColor=$TxtFg; $lvDr.BorderStyle='FixedSingle'
foreach ($h in @("Lettre","Etat","Chemin UNC","Libelle")) {
    $col = [System.Windows.Forms.ColumnHeader]::new(); $col.Text = $h
    $col.Width = switch ($h) { "Lettre"{60}; "Etat"{80}; "Chemin UNC"{500}; default{220} }
    $lvDr.Columns.Add($col) | Out-Null
}
$tDr.Controls.Add($lvDr)

$Script:loadDr = {
    $lvDr.Items.Clear(); $cfg = Read-Cfg
    $mon = Get-CimInstance Win32_MappedLogicalDisk -EA SilentlyContinue
    foreach ($l in $cfg.lecteurs) {
        $m  = [bool]($mon | Where-Object { $_.DeviceID -eq "$($l.lettre):" })
        $it = [System.Windows.Forms.ListViewItem]::new($l.lettre)
        $it.SubItems.Add($(if ($m) {"MONTE"} else {"DEMONTE"})) | Out-Null
        $it.SubItems.Add($l.chemin) | Out-Null
        $it.SubItems.Add($l.libelle) | Out-Null
        $it.ForeColor = if ($m) { $Green } else { $Mute }
        $it.Tag = $l; $lvDr.Items.Add($it) | Out-Null
    }
}
& $Script:loadDr

$yDrB = 292
$bDrA  = New-Btn "Ajouter"    0 $yDrB 100; $tDr.Controls.Add($bDrA)
$bDrE  = New-Btn "Modifier"  110 $yDrB 100; $tDr.Controls.Add($bDrE)
$bDrD  = New-Btn "Supprimer" 220 $yDrB 100 30 $Red; $tDr.Controls.Add($bDrD)
$bDrM  = New-Btn "Monter"    340 $yDrB 100 30 $Green; $tDr.Controls.Add($bDrM)
$bDrU  = New-Btn "Demonter"  450 $yDrB 100; $tDr.Controls.Add($bDrU)
$bDrR  = New-Btn "Actualiser" 570 $yDrB 110; $tDr.Controls.Add($bDrR)

function DriveForm { param($def = @{})
    $dlg = [System.Windows.Forms.Form]::new()
    $dlg.Text = if ($def.Count) {"Modifier le lecteur"} else {"Ajouter un lecteur reseau"}
    $dlg.Size = [Drawing.Size]::new(530,240)
    $dlg.StartPosition = 'CenterParent'; $dlg.BackColor = $BGray
    $dlg.FormBorderStyle = 'FixedDialog'; $dlg.MaximizeBox = $false
    $res = @{}
    $pairs = @(
        @("Lettre :",       "lettre",  $(if($def["lettre"]){$def["lettre"]}else{""})),
        @("Chemin UNC * :", "chemin",  $(if($def["chemin"]){$def["chemin"]}else{""})),
        @("Libelle :",      "libelle", $(if($def["libelle"]){$def["libelle"]}else{""}))
    )
    $y = 16
    foreach ($p in $pairs) {
        $dlg.Controls.Add((New-Label $p[0] 14 $y 110 26))
        $t = New-Txt 128 $y 360 $p[2]; $dlg.Controls.Add($t); $res[$p[1]] = $t; $y += 40
    }
    $bOK = New-Btn "OK" 320 ($y+4) 90; $bOK.DialogResult = 'OK'; $dlg.Controls.Add($bOK)
    $bCa = New-Btn "Annuler" 420 ($y+4) 90 30 ($Mute); $bCa.DialogResult = 'Cancel'; $dlg.Controls.Add($bCa)
    $dlg.AcceptButton = $bOK; $dlg.CancelButton = $bCa
    if ($dlg.ShowDialog($F) -eq 'OK') {
        return @{ lettre=$res["lettre"].Text.ToUpper().Replace(":","").Trim(); chemin=$res["chemin"].Text.Trim(); libelle=$res["libelle"].Text.Trim() }
    }
    return $null
}

function Test-DriveEntry { param($r)
    if ($r.lettre -notmatch '^[A-Z]$') { Dlg-Err "Lettre de lecteur invalide : '$($r.lettre)' (une lettre A-Z)."; return $false }
    if ($r.chemin -notmatch '^\\\\[^\\]+\\.+') { Dlg-Err "Chemin UNC attendu, ex : \\serveur\partage"; return $false }
    return $true
}

$bDrA.Add_Click({ $r = DriveForm; if (-not $r -or -not $r.lettre -or -not $r.chemin) { return }
    if (-not (Test-DriveEntry $r)) { return }
    $c = Read-Cfg
    if (@($c.lecteurs | Where-Object { $_.lettre -eq $r.lettre }).Count -gt 0) { Dlg-Err "La lettre $($r.lettre): est deja dans le profil."; return }
    $c.lecteurs = @($c.lecteurs) + @([PSCustomObject]$r)
    Save-Cfg $c; Write-Log "DRIVE+ $($r.lettre)"; & $Script:loadDr })

$bDrE.Add_Click({ if (-not $lvDr.SelectedItems.Count) { return }; $l = $lvDr.SelectedItems[0].Tag
    $r = DriveForm @{lettre=$l.lettre; chemin=$l.chemin; libelle=$l.libelle}; if (-not $r) { return }
    if (-not (Test-DriveEntry $r)) { return }
    $c = Read-Cfg
    $c.lecteurs = @($c.lecteurs | ForEach-Object { if ($_.lettre -eq $l.lettre) { [PSCustomObject]$r } else { $_ } })
    Save-Cfg $c; Write-Log "DRIVE~ $($r.lettre)"; & $Script:loadDr })

$bDrD.Add_Click({ if (-not $lvDr.SelectedItems.Count) { return }; $l = $lvDr.SelectedItems[0].Tag
    if (Dlg-YN "Supprimer le lecteur $($l.lettre): du profil ?") {
        $c = Read-Cfg; $c.lecteurs = @($c.lecteurs | Where-Object { $_.lettre -ne $l.lettre })
        Save-Cfg $c; Write-Log "DRIVE- $($l.lettre)"; & $Script:loadDr } })

$bDrM.Add_Click({ if (-not $lvDr.SelectedItems.Count) { return }; $l = $lvDr.SelectedItems[0].Tag
    net use "$($l.lettre):" $l.chemin /persistent:yes 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Log "MONTE $($l.lettre):"; & $Script:loadDr }
    else { Dlg-Err "Echec montage (code $LASTEXITCODE)" } })

$bDrU.Add_Click({ if (-not $lvDr.SelectedItems.Count) { return }; $l = $lvDr.SelectedItems[0].Tag
    net use "$($l.lettre):" /delete /y 2>&1 | Out-Null; Write-Log "DEMONTE $($l.lettre):"; & $Script:loadDr })

$bDrR.Add_Click({ & $Script:loadDr })

# ════════════════════════════════════════════════════════════════
#  ONGLET  COMPTES
# ════════════════════════════════════════════════════════════════
$tUs = New-Tab "Comptes"
$TC.TabPages.Add($tUs)

$tUs.Controls.Add((New-Label "Comptes locaux" 0 4 400 22 $true))
$tUs.Controls.Add((New-Sep 0 28 880))

$lvUs = [System.Windows.Forms.ListView]::new()
$lvUs.Anchor = 'Top,Left,Right'
$lvUs.Location=[Drawing.Point]::new(0,40); $lvUs.Size=[Drawing.Size]::new(880,240)
$lvUs.View='Details'; $lvUs.FullRowSelect=$true; $lvUs.GridLines=$true; $lvUs.Font=$FN
$lvUs.BackColor=$CardBg; $lvUs.ForeColor=$TxtFg; $lvUs.BorderStyle='FixedSingle'
foreach ($h in @("Compte","Nom complet","Etat","Groupes","Description")) {
    $col=[System.Windows.Forms.ColumnHeader]::new(); $col.Text=$h
    $col.Width = switch($h) {"Compte"{120};"Nom complet"{160};"Etat"{80};"Groupes"{220};default{270}}
    $lvUs.Columns.Add($col)|Out-Null
}
$tUs.Controls.Add($lvUs)

$Script:loadUs = {
    $lvUs.Items.Clear()
    # Carte membre -> groupes construite en une seule passe (au lieu de groupes x comptes)
    $grpMap = @{}
    foreach ($g in (Get-LocalGroup -EA SilentlyContinue)) {
        foreach ($mb in @(Get-LocalGroupMember $g.Name -EA SilentlyContinue)) {
            $k = ($mb.Name -split '\\')[-1]
            if (-not $grpMap.ContainsKey($k)) { $grpMap[$k] = @() }
            $grpMap[$k] += $g.Name
        }
    }
    foreach ($u in (Get-LocalUser | Sort-Object Name)) {
        $grps = if ($grpMap.ContainsKey($u.Name)) { $grpMap[$u.Name] -join ', ' } else { '' }
        $it = [System.Windows.Forms.ListViewItem]::new($u.Name)
        $it.SubItems.Add($u.FullName)  | Out-Null
        $it.SubItems.Add($(if ($u.Enabled) {"Actif"} else {"Inactif"})) | Out-Null
        $it.SubItems.Add($grps)        | Out-Null
        $it.SubItems.Add($u.Description) | Out-Null
        $it.ForeColor = if ($u.Enabled) { $Dark } else { $Mute }
        $it.Tag = $u; $lvUs.Items.Add($it) | Out-Null
    }
}
& $Script:loadUs

$yUb = 292
$bUA = New-Btn "Ajouter"          0 $yUb 120; $tUs.Controls.Add($bUA)
$bUE = New-Btn "Modifier"       130 $yUb 120; $tUs.Controls.Add($bUE)
$bUP = New-Btn "Mot de passe"   260 $yUb 140; $tUs.Controls.Add($bUP)
$bUT = New-Btn "Activer/Desact" 410 $yUb 160; $tUs.Controls.Add($bUT)
$bUD = New-Btn "Supprimer"      580 $yUb 110 30 $Red; $tUs.Controls.Add($bUD)

function UserForm { param($u = $null)
    $dlg = [System.Windows.Forms.Form]::new()
    $dlg.Text = if ($u) {"Modifier  -  $($u.Name)"} else {"Nouveau compte utilisateur"}
    $dlg.Size = [Drawing.Size]::new(540,330)
    $dlg.StartPosition = 'CenterParent'; $dlg.BackColor = $BGray
    $dlg.FormBorderStyle = 'FixedDialog'; $dlg.MaximizeBox = $false
    $pairs = @(
        @("Identifiant * :", "name", $u.Name,        [bool]$u),
        @("Nom complet :",   "full", $u.FullName,    $false),
        @("Description :",   "desc", $u.Description, $false),
        @("Groupe :",        "grp",  "",             $false)
    )
    $res = @{}; $y = 16
    foreach ($p in $pairs) {
        $dlg.Controls.Add((New-Label $p[0] 14 $y 120 26))
        $t = New-Txt 138 $y 360 $p[2] $p[3]; $dlg.Controls.Add($t); $res[$p[1]] = $t; $y += 40
    }
    if (-not $u) {
        $dlg.Controls.Add((New-Label "Mot de passe * :" 14 $y 120 26))
        $tp = [System.Windows.Forms.TextBox]::new()
        $tp.Location = [Drawing.Point]::new(138,$y); $tp.Size = [Drawing.Size]::new(360,26)
        $tp.PasswordChar = [char]9679; $tp.Font = $FN; $dlg.Controls.Add($tp); $res["pwd"] = $tp; $y += 40
    }
    $bOK = New-Btn "OK" 320 ($y+4) 90; $bOK.DialogResult='OK'; $dlg.Controls.Add($bOK)
    $bCa = New-Btn "Annuler" 420 ($y+4) 90 30 ($Mute); $bCa.DialogResult='Cancel'; $dlg.Controls.Add($bCa)
    $dlg.AcceptButton=$bOK; $dlg.CancelButton=$bCa
    if ($dlg.ShowDialog($F) -eq 'OK') { return $res }
    return $null
}

$bUA.Add_Click({ $r = UserForm; if (-not $r) { return }
    $nom = $r["name"].Text.Trim(); if ([string]::IsNullOrEmpty($nom)) { return }
    try {
        $p = @{Name=$nom; PasswordNeverExpires=$true; ErrorAction='Stop'
               Password=(ConvertTo-SecureString $r["pwd"].Text -AsPlainText -Force)}
        if ($r["full"].Text) { $p.FullName    = $r["full"].Text }
        if ($r["desc"].Text) { $p.Description = $r["desc"].Text }
        New-LocalUser @p | Out-Null
        if ($r["grp"].Text) { Add-LocalGroupMember -Group $r["grp"].Text -Member $nom -EA SilentlyContinue }
        Write-Log "COMPTE+ $nom"; & $Script:loadUs; Dlg-OK "Compte $nom cree."
    } catch { Dlg-Err $_.Exception.Message } })

$bUE.Add_Click({ if (-not $lvUs.SelectedItems.Count) { return }; $u = $lvUs.SelectedItems[0].Tag
    $r = UserForm $u; if (-not $r) { return }
    try {
        $p = @{}
        if ($r["full"].Text -ne $u.FullName)    { $p.FullName    = $r["full"].Text }
        if ($r["desc"].Text -ne $u.Description) { $p.Description = $r["desc"].Text }
        if ($p.Count -gt 0) { $u | Set-LocalUser @p }
        Write-Log "COMPTE~ $($u.Name)"; & $Script:loadUs
    } catch { Dlg-Err $_.Exception.Message } })

$bUP.Add_Click({ if (-not $lvUs.SelectedItems.Count) { return }; $u = $lvUs.SelectedItems[0].Tag
    $dlg = [System.Windows.Forms.Form]::new(); $dlg.Text="Mot de passe  -  $($u.Name)"
    $dlg.Size=[Drawing.Size]::new(430,180); $dlg.StartPosition='CenterParent'
    $dlg.FormBorderStyle='FixedDialog'; $dlg.MaximizeBox=$false; $dlg.BackColor=$BGray
    $dlg.Controls.Add((New-Label "Nouveau mot de passe :" 14 18 175 26))
    $t1=[System.Windows.Forms.TextBox]::new(); $t1.Location=[Drawing.Point]::new(193,19)
    $t1.Size=[Drawing.Size]::new(200,26); $t1.PasswordChar=[char]9679; $t1.Font=$FN; $dlg.Controls.Add($t1)
    $dlg.Controls.Add((New-Label "Confirmer :" 14 56 175 26))
    $t2=[System.Windows.Forms.TextBox]::new(); $t2.Location=[Drawing.Point]::new(193,57)
    $t2.Size=[Drawing.Size]::new(200,26); $t2.PasswordChar=[char]9679; $t2.Font=$FN; $dlg.Controls.Add($t2)
    $bOK=New-Btn "OK" 200 98 90; $bOK.DialogResult='OK'; $dlg.Controls.Add($bOK)
    $bCa=New-Btn "Annuler" 300 98 90 30 ($Mute); $bCa.DialogResult='Cancel'; $dlg.Controls.Add($bCa)
    $dlg.AcceptButton=$bOK; $dlg.CancelButton=$bCa
    if ($dlg.ShowDialog($F) -eq 'OK') {
        if ($t1.Text -ne $t2.Text) { Dlg-Err "Mots de passe differents."; return }
        try { $u | Set-LocalUser -Password (ConvertTo-SecureString $t1.Text -AsPlainText -Force)
              Write-Log "MDP $($u.Name)"; Dlg-OK "Mot de passe modifie." }
        catch { Dlg-Err $_.Exception.Message } } })

$bUT.Add_Click({ if (-not $lvUs.SelectedItems.Count) { return }; $u = $lvUs.SelectedItems[0].Tag
    try {
        if ($u.Enabled) { Disable-LocalUser -Name $u.Name; Write-Log "DESACTIVE $($u.Name)" }
        else            { Enable-LocalUser  -Name $u.Name; Write-Log "ACTIVE $($u.Name)" }
        & $Script:loadUs
    } catch { Dlg-Err $_.Exception.Message } })

$bUD.Add_Click({ if (-not $lvUs.SelectedItems.Count) { return }; $u = $lvUs.SelectedItems[0].Tag
    if ($u.Name -in 'Administrateur','Administrator') { Dlg-Err "Compte protege."; return }
    if (Dlg-YN "Supprimer definitivement '$($u.Name)' ?") {
        try { Remove-LocalUser -Name $u.Name; Write-Log "COMPTE- $($u.Name)"; & $Script:loadUs }
        catch { Dlg-Err $_.Exception.Message } } })


# ════════════════════════════════════════════════════════════════
#  ONGLET  DIAGNOSTIC
# ════════════════════════════════════════════════════════════════
$tDg = New-Tab "Diagnostic"
$TC.TabPages.Add($tDg)

$tDg.Controls.Add((New-Label "Tests reseau et systeme" 0 4 400 22 $true))
$tDg.Controls.Add((New-Sep 0 28 880))

# Colonne boutons a gauche
$yD = 42
$diagBtns = @(
    @("Etat des lecteurs reseau",  "drives"),
    @("Test passerelle + DNS",     "conn"),
    @("Resolution DNS (nslookup)", "resolve"),
    @("Etat du pare-feu",          "fw"),
    @("Tester un port (host:port)","port"),
    @("Versions systeme",          "ver"),
    @("Config SMB / partages",     "smb"),
    @("Services reseau critiques", "svc"),
    @("Diagnostic complet",        "full")
)
foreach ($db in $diagBtns) {
    $b = New-Btn $db[0] 0 $yD 250 30
    $b.Tag = $db[1]; $b.TextAlign = 'MiddleLeft'
    $b.Add_Click({
        param($sender,$e)
        $rtDg.Clear()
        $rtDg.AppendText("=== $($sender.Text) ===`r`n`r`n")
        Run-Diag $sender.Tag
    })
    $tDg.Controls.Add($b); $yD += 38
}

# Champ cible pour test de port
$tDg.Controls.Add((New-Label "Cible :" 0 $yD 60 24))
$txDgTarget = New-Txt 62 $yD 188 "10.0.0.1:445"
$tDg.Controls.Add($txDgTarget)

$bDgSave = New-Btn "Exporter le resultat" 0 ($yD+36) 250 30 $LGray
$bDgSave.Add_Click({
    if ([string]::IsNullOrWhiteSpace($rtDg.Text)) { Dlg-OK "Rien a exporter : lancez d'abord un test."; return }
    $out = Join-Path ([Environment]::GetFolderPath('MyDocuments')) ("Diagnostic-" + $env:COMPUTERNAME + "-" + (Get-Date -Format 'yyyyMMdd-HHmm') + ".txt")
    [IO.File]::WriteAllText($out, $rtDg.Text, [Text.UTF8Encoding]::new($false))
    Write-Log "DIAG export"; Dlg-OK "Exporte :`n$out"; Start-Process notepad $out
})
$tDg.Controls.Add($bDgSave)

# Zone de sortie a droite
$rtDg = [System.Windows.Forms.RichTextBox]::new()
$rtDg.Anchor = 'Top,Bottom,Left,Right'
$rtDg.Location = [Drawing.Point]::new(268,42)
$rtDg.Size = [Drawing.Size]::new(600,480)
$rtDg.Font = [Drawing.Font]::new("Consolas",9)
$rtDg.ReadOnly = $true; $rtDg.BackColor = [Drawing.Color]::FromArgb(20,20,24)
$rtDg.ForeColor = [Drawing.Color]::FromArgb(220,220,220)
$rtDg.BorderStyle = 'None'
$tDg.Controls.Add($rtDg)

function DgW { param($txt,$col='gray')
    $c = switch($col){ 'ok'{[Drawing.Color]::FromArgb(80,220,120)} 'ko'{[Drawing.Color]::FromArgb(255,90,90)} 'warn'{[Drawing.Color]::FromArgb(240,200,80)} 'hi'{[Drawing.Color]::FromArgb(120,200,255)} default{[Drawing.Color]::FromArgb(210,210,210)} }
    $rtDg.SelectionColor = $c
    $rtDg.AppendText("$txt`r`n")
    $rtDg.ScrollToCaret()
}

function Run-Diag { param([string]$mode)
    switch ($mode) {
        'drives' {
            DgW "Lecteurs reseau mappes :" 'hi'
            $mapped = Get-CimInstance Win32_MappedLogicalDisk -EA SilentlyContinue
            if (-not $mapped) { DgW "  Aucun lecteur mappe." 'warn' }
            foreach ($m in $mapped) {
                $ok = Test-Path "$($m.DeviceID)\" -EA SilentlyContinue
                DgW ("  {0}  ->  {1}" -f $m.DeviceID, $m.ProviderName) 'hi'
                if ($ok) { DgW "       Accessible : OUI" 'ok' }
                else     { DgW "       Accessible : NON (deconnecte / X rouge)" 'ko' }
            }
            DgW ""
            DgW "Connexions SMB actives (net use) :" 'hi'
            $nu = net use 2>&1 | Out-String
            DgW $nu
        }
        'conn' {
            $gw = (Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } |
                   Select-Object -First 1).IPv4DefaultGateway.NextHop
            $dns = (Get-DnsClientServerAddress -AddressFamily IPv4 |
                    Where-Object { $_.ServerAddresses } | Select-Object -First 1).ServerAddresses
            if ($gw) {
                DgW "Ping passerelle $gw ..." 'hi'
                $p = Test-Connection $gw -Count 2 -Quiet -EA SilentlyContinue
                if ($p) { DgW "  Passerelle joignable." 'ok' } else { DgW "  Passerelle INJOIGNABLE." 'ko' }
            } else { DgW "  Aucune passerelle configuree." 'warn' }
            foreach ($d in $dns) {
                DgW "Ping DNS $d ..." 'hi'
                $p = Test-Connection $d -Count 2 -Quiet -EA SilentlyContinue
                if ($p) { DgW "  DNS $d joignable." 'ok' } else { DgW "  DNS $d INJOIGNABLE." 'ko' }
            }
            DgW "Test acces Internet (1.1.1.1) ..." 'hi'
            $pi = Test-Connection 1.1.1.1 -Count 2 -Quiet -EA SilentlyContinue
            if ($pi) { DgW "  Internet accessible." 'ok' } else { DgW "  Pas d'acces Internet (normal si reseau isole)." 'warn' }
        }
        'resolve' {
            $host2 = [Microsoft.VisualBasic.Interaction]::InputBox("Nom a resoudre :","Resolution DNS","microsoft.com")
            if (-not $host2) { return }
            DgW "Resolution de $host2 ..." 'hi'
            try {
                $r = Resolve-DnsName $host2 -EA Stop
                foreach ($e in $r) {
                    if ($e.IPAddress) { DgW ("  {0}  ->  {1}" -f $e.Name, $e.IPAddress) 'ok' }
                }
            } catch { DgW "  Echec resolution : $($_.Exception.Message)" 'ko' }
        }
        'fw' {
            DgW "Etat du pare-feu Windows par profil :" 'hi'
            foreach ($pr in (Get-NetFirewallProfile -EA SilentlyContinue)) {
                $st = if ($pr.Enabled) { "ACTIF" } else { "INACTIF" }
                $col = if ($pr.Enabled) { 'ok' } else { 'warn' }
                DgW ("  {0,-10} : {1}  (Entrant bloque par defaut: {2})" -f $pr.Name, $st, $pr.DefaultInboundAction) $col
            }
            DgW ""
            DgW "Regles de BLOCAGE sortant actives (top 15) :" 'hi'
            $blk = Get-NetFirewallRule -Direction Outbound -Action Block -Enabled True -EA SilentlyContinue |
                   Select-Object -First 15
            if (-not $blk) { DgW "  Aucune regle de blocage sortant active." 'ok' }
            foreach ($r in $blk) { DgW ("  [BLOCK] {0}" -f $r.DisplayName) 'warn' }
        }
        'port' {
            $tgt = $txDgTarget.Text.Trim()
            if ($tgt -notmatch ':') { DgW "  Format attendu : host:port (ex 10.0.0.1:445)" 'ko'; return }
            $h,$pt = $tgt -split ':',2
            $ptNum = 0
            if (-not [int]::TryParse($pt, [ref]$ptNum) -or $ptNum -lt 1 -or $ptNum -gt 65535) {
                DgW "  Port invalide : '$pt' (attendu : 1 a 65535)" 'ko'; return }
            DgW "Test connexion $h port $ptNum ..." 'hi'
            try {
                $tc = Test-NetConnection -ComputerName $h -Port $ptNum -WarningAction SilentlyContinue
                if ($tc.TcpTestSucceeded) {
                    DgW "  Port OUVERT - connexion reussie." 'ok'
                    if ($tc.PingReplyDetails) { DgW ("  Latence ping : {0} ms" -f $tc.PingReplyDetails.RoundtripTime) }
                } else {
                    DgW "  Port FERME ou filtre (firewall ?)." 'ko'
                    if (-not $tc.PingSucceeded) { DgW "  L'hote ne repond meme pas au ping." 'warn' }
                }
            } catch { DgW "  Erreur : $($_.Exception.Message)" 'ko' }
        }
        'ver' {
            $os = Get-CimInstance Win32_OperatingSystem
            DgW ("OS          : {0}" -f $os.Caption) 'hi'
            DgW ("Version     : {0}  build {1}" -f $os.Version, $os.BuildNumber)
            DgW ("Architecture: {0}" -f $os.OSArchitecture)
            DgW ("PowerShell  : {0}" -f $PSVersionTable.PSVersion.ToString())
            $net = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full" -EA SilentlyContinue).Release
            if ($net) { DgW ("(.NET Fw)    : release {0}" -f $net) }
            $smb = Get-SmbConnection -EA SilentlyContinue | Select-Object -First 1
            if ($smb) { DgW ("Dialecte SMB: {0}" -f $smb.Dialect) }
            DgW ("Nom machine : {0}" -f $env:COMPUTERNAME)
            DgW ("Derniere maj: consulter Windows Update") 
        }
        'smb' {
            DgW "Connexions SMB etablies :" 'hi'
            $cons = Get-SmbConnection -EA SilentlyContinue
            if (-not $cons) { DgW "  Aucune connexion SMB active." 'warn' }
            foreach ($c in $cons) {
                DgW ("  \\{0}\{1}  (dialecte {2})" -f $c.ServerName, $c.ShareName, $c.Dialect) 'ok'
            }
            DgW ""
            DgW "Parametres client SMB (timeout inactivite) :" 'hi'
            $cfg = Get-SmbClientConfiguration -EA SilentlyContinue
            if ($cfg) {
                DgW ("  SessionTimeout        : {0} s" -f $cfg.SessionTimeout)
                DgW ("  KeepConn (garde vive) : {0} s" -f $cfg.KeepConn)
                DgW ("  Signature requise     : {0}" -f $cfg.RequireSecuritySignature)
            }
        }
        'svc' {
            DgW "Services reseau critiques :" 'hi'
            $svcs = 'LanmanWorkstation','LanmanServer','Dnscache','Dhcp','NlaSvc','nsi'
            foreach ($s in $svcs) {
                $sv = Get-Service $s -EA SilentlyContinue
                if ($sv) {
                    $col = if ($sv.Status -eq 'Running') { 'ok' } else { 'ko' }
                    DgW ("  {0,-20} : {1}" -f $sv.DisplayName, $sv.Status) $col
                }
            }
        }
        'full' {
            Run-Diag 'ver';    DgW ("-"*50)
            Run-Diag 'conn';   DgW ("-"*50)
            Run-Diag 'drives'; DgW ("-"*50)
            Run-Diag 'fw';     DgW ("-"*50)
            Run-Diag 'svc'
            DgW ""; DgW "=== Diagnostic complet termine ===" 'ok'
        }
    }
}


# ════════════════════════════════════════════════════════════════
#  ONGLET  NETTOYAGE DISQUE
# ════════════════════════════════════════════════════════════════
$tCl = New-Tab "Nettoyage"
$TC.TabPages.Add($tCl)

$tCl.Controls.Add((New-Label "Liberer de l'espace disque" 0 4 400 22 $true))
$tCl.Controls.Add((New-Sep 0 28 880))

# Jauge disque C:
$tCl.Controls.Add((New-Label "Disque C: :" 0 42 90 24))
$pbDisk = [System.Windows.Forms.ProgressBar]::new()
$pbDisk.Location = [Drawing.Point]::new(92,44); $pbDisk.Size = [Drawing.Size]::new(400,22)
$pbDisk.Style = 'Continuous'
$tCl.Controls.Add($pbDisk)
$lbDisk = New-Label "" 500 42 360 24
$tCl.Controls.Add($lbDisk)

function Refresh-Disk {
    $d = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" -EA SilentlyContinue
    if (-not $d -or -not $d.Size) { $lbDisk.Text = "Disque C: indisponible"; $lbDisk.ForeColor = $Mute; return }
    $usedPct = [int]((($d.Size - $d.FreeSpace) / $d.Size) * 100)
    $pbDisk.Value = [math]::Min(100,$usedPct)
    $lbDisk.Text = "{0:N1} Go libres / {1:N1} Go  ({2}% utilise)" -f ($d.FreeSpace/1GB),($d.Size/1GB),$usedPct
    $lbDisk.ForeColor = if ($usedPct -ge 90) { $Red } elseif ($usedPct -ge 75) { [Drawing.Color]::DarkOrange } else { $Green }
}
Refresh-Disk

# Boutons de nettoyage a gauche
$yCl = 82
$cleanBtns = @(
    @("Analyser ce qui prend de la place", "analyze"),
    @("Explorer l'espace d'un dossier...", "explore"),
    @("Vider les fichiers temporaires",    "temp"),
    @("Vider la corbeille",                "recycle"),
    @("Cache Windows Update",              "wu"),
    @("Anciens journaux et vidages",       "logs"),
    @("Nettoyage Windows (cleanmgr)",      "cleanmgr"),
    @("Tout nettoyer (sauf cleanmgr)",     "all")
)
foreach ($cb in $cleanBtns) {
    $b = New-Btn $cb[0] 0 $yCl 260 32
    $b.Tag = $cb[1]; $b.TextAlign = 'MiddleLeft'
    if ($cb[1] -eq 'all') { $b.BackColor = [Drawing.Color]::FromArgb(200,120,20) }
    $b.Add_Click({
        param($sender,$e)
        $rtCl.Clear()
        $rtCl.AppendText("=== $($sender.Text) ===`r`n`r`n")
        Run-Clean $sender.Tag
        Refresh-Disk
    })
    $tCl.Controls.Add($b); $yCl += 40
}

# Zone sortie a droite
$rtCl = [System.Windows.Forms.RichTextBox]::new()
$rtCl.Anchor = 'Top,Bottom,Left,Right'
$rtCl.Location = [Drawing.Point]::new(280,82); $rtCl.Size = [Drawing.Size]::new(588,440)
$rtCl.Font = [Drawing.Font]::new("Consolas",9); $rtCl.ReadOnly = $true
$rtCl.BackColor = [Drawing.Color]::FromArgb(20,20,24); $rtCl.ForeColor = [Drawing.Color]::FromArgb(220,220,220)
$rtCl.BorderStyle = 'None'
$tCl.Controls.Add($rtCl)

function ClW { param($txt,$col='gray')
    $c = switch($col){ 'ok'{[Drawing.Color]::FromArgb(80,220,120)} 'warn'{[Drawing.Color]::FromArgb(240,200,80)} 'hi'{[Drawing.Color]::FromArgb(120,200,255)} default{[Drawing.Color]::FromArgb(210,210,210)} }
    $rtCl.SelectionColor = $c; $rtCl.AppendText("$txt`r`n"); $rtCl.ScrollToCaret()
}

function Get-FolderSize { param($p)
    try {
        $sum = (Get-ChildItem $p -Recurse -Force -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum
        return [math]::Round($sum/1MB,1)
    } catch { return 0 }
}

function Clean-Path { param($p,$label)
    if (-not (Test-Path $p)) { ClW "  $label : introuvable" 'warn'; return 0 }
    $before = Get-FolderSize $p
    $freed = 0
    Get-ChildItem $p -Force -EA SilentlyContinue | ForEach-Object {
        try { Remove-Item $_.FullName -Recurse -Force -EA SilentlyContinue; $freed++ } catch {}
    }
    $after = Get-FolderSize $p
    $gain = [math]::Max(0, $before - $after)
    ClW ("  {0} : {1} Mo liberes" -f $label, $gain) 'ok'
    return $gain
}

function Run-Clean { param([string]$mode)
    switch ($mode) {
        'analyze' {
            ClW "Analyse des postes courants (peut prendre 1 min) ..." 'hi'; ClW ""
            $paths = @(
                @("$env:TEMP",                              "Temp utilisateur"),
                @("$env:SystemRoot\Temp",                   "Temp Windows"),
                @("$env:SystemRoot\SoftwareDistribution\Download","Cache Windows Update"),
                @("$env:LOCALAPPDATA\Microsoft\Windows\INetCache","Cache Internet"),
                @("$env:SystemRoot\Logs",                   "Journaux Windows"),
                @("$env:SystemRoot\Minidump",               "Vidages memoire")
            )
            $tot = 0
            foreach ($p in $paths) {
                $sz = Get-FolderSize $p[0]
                $tot += $sz
                ClW ("  {0,-24} : {1,8} Mo" -f $p[1], $sz)
            }
            ClW ""
            ClW ("  Potentiel recuperable : ~{0} Mo" -f [math]::Round($tot,0)) 'hi'
            ClW ""
            ClW "Top 8 dossiers volumineux dans le profil :" 'hi'
            Get-ChildItem $env:USERPROFILE -Directory -EA SilentlyContinue | ForEach-Object {
                [PSCustomObject]@{ N=$_.Name; S=(Get-FolderSize $_.FullName) }
            } | Sort-Object S -Descending | Select-Object -First 8 | ForEach-Object {
                ClW ("  {0,-30} : {1,8} Mo" -f $_.N, $_.S)
            }
        }
        'explore' {
            $fb = New-Object System.Windows.Forms.FolderBrowserDialog
            $fb.Description = "Choisir un dossier ou un disque a analyser"
            $fb.SelectedPath = "C:\\"
            if ($fb.ShowDialog() -ne 'OK') { ClW "Analyse annulee." 'warn'; return }
            $root = $fb.SelectedPath
            ClW "Analyse de $root ..." 'hi'
            ClW "(selon la taille, cela peut prendre plusieurs minutes)"; ClW ""
            # Plus gros sous-dossiers (taille recursive)
            ClW "15 plus gros sous-dossiers :" 'hi'
            $dirs = Get-ChildItem $root -Directory -Force -EA SilentlyContinue | ForEach-Object {
                [PSCustomObject]@{ N=$_.Name; S=(Get-FolderSize $_.FullName) }
            } | Sort-Object S -Descending | Select-Object -First 15
            foreach ($d in $dirs) {
                $disp = if ($d.S -ge 1024) { "{0,8:N1} Go" -f ($d.S/1024) } else { "{0,8} Mo" -f $d.S }
                ClW ("  {0,-40}{1}" -f $d.N, $disp)
            }
            ClW ""
            # Plus gros fichiers (recursif)
            ClW "15 plus gros fichiers :" 'hi'
            Get-ChildItem $root -File -Recurse -Force -EA SilentlyContinue |
                Sort-Object Length -Descending | Select-Object -First 15 | ForEach-Object {
                    $mb = [math]::Round($_.Length/1MB,0)
                    $disp = if ($mb -ge 1024) { "{0,8:N1} Go" -f ($mb/1024) } else { "{0,8} Mo" -f $mb }
                    ClW ("  {0}`r`n     {1,-46}{2}" -f $_.DirectoryName, $_.Name, $disp)
                }
            ClW ""; ClW "Analyse terminee." 'hi'
            Write-Log "EXPLORE $root"
        }
        'temp' {
            $g = 0
            $g += Clean-Path "$env:TEMP"            "Temp utilisateur"
            $g += Clean-Path "$env:SystemRoot\Temp" "Temp Windows"
            ClW ""; ClW ("Total libere : {0} Mo" -f [math]::Round($g,0)) 'hi'
        }
        'recycle' {
            ClW "Vidage de la corbeille ..." 'hi'
            try { Clear-RecycleBin -Force -EA Stop; ClW "  Corbeille videe." 'ok' }
            catch { ClW "  $($_.Exception.Message)" 'warn' }
        }
        'wu' {
            ClW "Arret du service Windows Update ..." 'hi'
            Stop-Service wuauserv -Force -EA SilentlyContinue
            $g = Clean-Path "$env:SystemRoot\SoftwareDistribution\Download" "Cache WU"
            Start-Service wuauserv -EA SilentlyContinue
            ClW "  Service Windows Update redemarre." 'ok'
        }
        'logs' {
            $g = 0
            $g += Clean-Path "$env:SystemRoot\Logs"     "Journaux"
            $g += Clean-Path "$env:SystemRoot\Minidump" "Vidages memoire"
            ClW ""; ClW ("Total libere : {0} Mo" -f [math]::Round($g,0)) 'hi'
        }
        'cleanmgr' {
            ClW "Lancement de l'outil Nettoyage de disque Windows ..." 'hi'
            ClW "  (fenetre Windows separee)"
            Start-Process cleanmgr -ArgumentList "/d C:" -EA SilentlyContinue
        }
        'all' {
            if (-not (Dlg-YN "Lancer le nettoyage complet (temp + corbeille + cache WU + journaux) ?")) { return }
            $g = 0
            $g += Clean-Path "$env:TEMP"            "Temp utilisateur"
            $g += Clean-Path "$env:SystemRoot\Temp" "Temp Windows"
            Stop-Service wuauserv -Force -EA SilentlyContinue
            $g += Clean-Path "$env:SystemRoot\SoftwareDistribution\Download" "Cache WU"
            Start-Service wuauserv -EA SilentlyContinue
            $g += Clean-Path "$env:SystemRoot\Logs"     "Journaux"
            $g += Clean-Path "$env:SystemRoot\Minidump" "Vidages memoire"
            try { Clear-RecycleBin -Force -EA SilentlyContinue; ClW "  Corbeille videe." 'ok' } catch {}
            ClW ""; ClW ("TOTAL LIBERE : {0} Mo" -f [math]::Round($g,0)) 'hi'
            Write-Log "NETTOYAGE COMPLET $([math]::Round($g,0))Mo"
        }
    }
}


# ════════════════════════════════════════════════════════════════
#  ONGLET  COPIE  (assistant Robocopy)
# ════════════════════════════════════════════════════════════════
$tCp = New-Tab "Copie"
$TC.TabPages.Add($tCp)

$tCp.Controls.Add((New-Label "Copie et synchronisation de dossiers (Robocopy)" 0 4 500 22 $true))
$tCp.Controls.Add((New-Sep 0 28 940))

$tCp.Controls.Add((New-Label "Source :" 0 44 80 26))
$txCpSrc = New-Txt 84 44 640 ""; $tCp.Controls.Add($txCpSrc)
$bCpBrS = New-Btn "Parcourir" 732 44 110 28 $LGray; $tCp.Controls.Add($bCpBrS)

$tCp.Controls.Add((New-Label "Destination :" 0 82 80 26))
$txCpDst = New-Txt 84 82 640 ""; $tCp.Controls.Add($txCpDst)
$bCpBrD = New-Btn "Parcourir" 732 82 110 28 $LGray; $tCp.Controls.Add($bCpBrD)

function Pick-Folder { param($current)
    $fb = New-Object System.Windows.Forms.FolderBrowserDialog
    if ($current -and (Test-Path $current)) { $fb.SelectedPath = $current }
    if ($fb.ShowDialog() -eq 'OK') { return $fb.SelectedPath } else { return $null }
}
$bCpBrS.Add_Click({ $p = Pick-Folder $txCpSrc.Text; if ($p) { $txCpSrc.Text = $p } })
$bCpBrD.Add_Click({ $p = Pick-Folder $txCpDst.Text; if ($p) { $txCpDst.Text = $p } })

# Options
$tCp.Controls.Add((New-Label "Options :" 0 122 80 24 $true))
function New-Chk { param($txt,$x,$y,$w,$checked=$false)
    $c = [System.Windows.Forms.CheckBox]::new()
    $c.Text=$txt; $c.Location=[Drawing.Point]::new($x,$y); $c.Size=[Drawing.Size]::new($w,26)
    $c.ForeColor=$TxtFg; $c.Font=$FN; $c.Checked=$checked; return $c
}
$cbCpSub = New-Chk "Inclure les sous-dossiers (/E)"        0   148 260 $true
$cbCpMir = New-Chk "Miroir exact - supprime en trop (/MIR)" 270 148 300 $false
$cbCpRes = New-Chk "Mode reprise gros fichiers (/Z)"        0   178 260 $false
$cbCpMt  = New-Chk "Copie rapide multi-thread (/MT:16)"     270 178 300 $true
$cbCpFat = New-Chk "Conserver dates/attributs (/COPY:DAT)"  0   208 260 $true
$cbCpLog = New-Chk "Journal dans un fichier (/LOG)"         270 208 300 $true
foreach ($c in @($cbCpSub,$cbCpMir,$cbCpRes,$cbCpMt,$cbCpFat,$cbCpLog)) { $tCp.Controls.Add($c) }

# Construction de la commande
function Build-Robocopy { param([switch]$Simulate)
    $src = $txCpSrc.Text.Trim(); $dst = $txCpDst.Text.Trim()
    if (-not $src -or -not $dst) { Dlg-Err "Renseignez la source et la destination."; return $null }
    if (-not (Test-Path $src)) { Dlg-Err "Source introuvable :`n$src"; return $null }
    $Script:cpLog = $null
    $o = @("`"$src`"","`"$dst`"")
    if ($cbCpMir.Checked) { $o += "/MIR" } elseif ($cbCpSub.Checked) { $o += "/E" }
    if ($cbCpRes.Checked) { $o += "/Z" }
    if ($cbCpMt.Checked)  { $o += "/MT:16" }
    if ($cbCpFat.Checked) { $o += "/COPY:DAT" }
    $o += "/R:1","/W:1","/NP"
    if ($Simulate) { $o += "/L" }
    if ($cbCpLog.Checked) {
        $Script:cpLog = Join-Path ([Environment]::GetFolderPath('MyDocuments')) ("Robocopy-" + (Get-Date -Format 'yyyyMMdd-HHmm') + ".log")
        $o += "/TEE","/LOG:`"$Script:cpLog`""
    }
    return ($o -join ' ')
}

# Boutons d'action
$bCpSim = New-Btn "Simuler (rien n'est copie)" 0 250 240 34 ([Drawing.Color]::FromArgb(55,90,140))
$bCpGo  = New-Btn "Lancer la copie"           250 250 200 34 $Green
$bCpLogOpen = New-Btn "Ouvrir le journal"     460 250 160 34 $LGray
foreach ($b in @($bCpSim,$bCpGo,$bCpLogOpen)) { $tCp.Controls.Add($b) }

$rtCp = [System.Windows.Forms.RichTextBox]::new()
$rtCp.Anchor = 'Top,Bottom,Left,Right'
$rtCp.Location=[Drawing.Point]::new(0,298); $rtCp.Size=[Drawing.Size]::new(940,270)
$rtCp.Font=[Drawing.Font]::new("Consolas",9); $rtCp.ReadOnly=$true
$rtCp.BackColor=[Drawing.Color]::FromArgb(24,26,31); $rtCp.ForeColor=$TxtFg; $rtCp.BorderStyle='FixedSingle'
$tCp.Controls.Add($rtCp)
$rtCp.Text = "Choisissez une source et une destination, puis Simuler pour verifier avant de lancer."

$bCpSim.Add_Click({
    $cmd = Build-Robocopy -Simulate; if (-not $cmd) { return }
    $rtCp.Clear(); $rtCp.AppendText("SIMULATION (aucun fichier copie) :`r`nrobocopy $cmd`r`n`r`n")
    try {
        $out = & cmd /c "robocopy $cmd" 2>&1 | Out-String
        $rtCp.AppendText($out)
        $rc = $LASTEXITCODE
        $verdict = if ($rc -lt 8) { "Simulation OK (code robocopy $rc)." }
                   else           { "ATTENTION : code robocopy $rc - erreurs detectees, verifiez chemins et droits." }
        $rtCp.AppendText("`r`n$verdict`r`n")
    } catch { $rtCp.AppendText("Erreur : $($_.Exception.Message)") }
    $rtCp.ScrollToCaret()
})
$bCpGo.Add_Click({
    $cmd = Build-Robocopy; if (-not $cmd) { return }
    $warn = if ($cbCpMir.Checked) { "`n`nATTENTION : le mode Miroir SUPPRIME dans la destination tout ce qui n'est pas dans la source." } else { "" }
    if (-not (Dlg-YN "Lancer la copie ?$warn")) { return }
    $rtCp.Clear(); $rtCp.AppendText("COPIE EN COURS dans une fenetre separee...`r`nrobocopy $cmd`r`n")
    if ($Script:cpLog) { $rtCp.AppendText("`r`nJournal : $Script:cpLog`r`n") }
    Write-Log "ROBOCOPY $($txCpSrc.Text) -> $($txCpDst.Text)"
    Start-Process cmd -ArgumentList "/k robocopy $cmd & echo. & echo === Termine. Fermez cette fenetre. ==="
})
$bCpLogOpen.Add_Click({
    if ($Script:cpLog -and (Test-Path $Script:cpLog)) { Start-Process notepad $Script:cpLog }
    else { Dlg-OK "Aucun journal pour l'instant. Cochez l'option Journal et lancez une copie." }
})

# ════════════════════════════════════════════════════════════════
#  ONGLET  BITLOCKER  (etat, cle de recuperation, suspension)
# ════════════════════════════════════════════════════════════════
$tBl = New-Tab "BitLocker"
$TC.TabPages.Add($tBl)

$tBl.Controls.Add((New-Label "Chiffrement BitLocker - etat et recuperation" 0 4 500 22 $true))
$tBl.Controls.Add((New-Sep 0 28 940))

$lvBl = [System.Windows.Forms.ListView]::new()
$lvBl.Anchor = 'Top,Left,Right'
$lvBl.Location=[Drawing.Point]::new(0,40); $lvBl.Size=[Drawing.Size]::new(940,180)
$lvBl.View='Details'; $lvBl.FullRowSelect=$true; $lvBl.GridLines=$true; $lvBl.Font=$FN
$lvBl.BackColor=$CardBg; $lvBl.ForeColor=$TxtFg; $lvBl.BorderStyle='FixedSingle'
foreach ($h in @(@("Lecteur",90),@("Protection",110),@("Chiffrement",180),@("Etat",160),@("Methode",180),@("Verrou",100))) {
    $col=[System.Windows.Forms.ColumnHeader]::new(); $col.Text=$h[0]; $col.Width=$h[1]; $lvBl.Columns.Add($col)|Out-Null
}
$tBl.Controls.Add($lvBl)

$Script:blAvailable = $true
function Load-BitLocker {
    $lvBl.Items.Clear()
    try {
        $vols = Get-BitLockerVolume -EA Stop
        foreach ($v in $vols) {
            $prot = if ($v.ProtectionStatus -eq 'On') {"Activee"} else {"Desactivee"}
            $enc  = "$($v.EncryptionPercentage)%  ($($v.VolumeStatus))"
            $it=[System.Windows.Forms.ListViewItem]::new($v.MountPoint)
            $it.SubItems.Add($prot)|Out-Null
            $it.SubItems.Add($enc)|Out-Null
            $it.SubItems.Add("$($v.VolumeStatus)")|Out-Null
            $it.SubItems.Add("$($v.EncryptionMethod)")|Out-Null
            $it.SubItems.Add("$($v.LockStatus)")|Out-Null
            $it.ForeColor = if ($v.ProtectionStatus -eq 'On') { $Green } else { $Mute }
            $it.Tag=$v; $lvBl.Items.Add($it)|Out-Null
        }
        if (-not $vols) { $rtBl.Text = "Aucun volume BitLocker detecte." }
    } catch {
        $Script:blAvailable = $false
        $rtBl.Text = "BitLocker n'est pas disponible via PowerShell sur cette edition de Windows.`r`n`r`nUtilisez le bouton 'Gestionnaire BitLocker' ou la commande 'manage-bde -status' dans la Console."
    }
}

$yBl = 232
$bBlRef  = New-Btn "Rafraichir"              0   $yBl 120; $tBl.Controls.Add($bBlRef)
$bBlKey  = New-Btn "Cle de recuperation"     130 $yBl 190; $tBl.Controls.Add($bBlKey)
$bBlSusp = New-Btn "Suspendre protection"    330 $yBl 190 30 ([Drawing.Color]::FromArgb(200,120,20)); $tBl.Controls.Add($bBlSusp)
$bBlRes  = New-Btn "Reprendre protection"    530 $yBl 190 30 $Green; $tBl.Controls.Add($bBlRes)
$bBlUnl  = New-Btn "Deverrouiller un lecteur" 0  ($yBl+40) 200 30 ([Drawing.Color]::FromArgb(55,90,140)); $tBl.Controls.Add($bBlUnl)
$bBlMgr  = New-Btn "Gestionnaire BitLocker"  210 ($yBl+40) 200 30 $LGray; $tBl.Controls.Add($bBlMgr)
$bBlCopy = New-Btn "Copier la cle"           420 ($yBl+40) 160 30 $LGray; $tBl.Controls.Add($bBlCopy)

$rtBl = [System.Windows.Forms.RichTextBox]::new()
$rtBl.Anchor = 'Top,Bottom,Left,Right'
$rtBl.Location=[Drawing.Point]::new(0,($yBl+82)); $rtBl.Size=[Drawing.Size]::new(940,($TC.Size.Height - $yBl - 160))
$rtBl.Font=[Drawing.Font]::new("Consolas",9); $rtBl.ReadOnly=$true
$rtBl.BackColor=[Drawing.Color]::FromArgb(24,26,31); $rtBl.ForeColor=$TxtFg; $rtBl.BorderStyle='FixedSingle'
$tBl.Controls.Add($rtBl)
Load-BitLocker

function Bl-Selected { if ($lvBl.SelectedItems.Count) { return $lvBl.SelectedItems[0].Tag } else { Dlg-OK "Selectionnez d'abord un lecteur dans la liste."; return $null } }

$bBlRef.Add_Click({ Load-BitLocker })
$bBlKey.Add_Click({
    $v = Bl-Selected; if (-not $v) { return }
    $rtBl.Clear(); $rtBl.AppendText("Cle(s) de recuperation pour $($v.MountPoint)`r`n`r`n")
    $found=$false
    foreach ($kp in $v.KeyProtector) {
        if ($kp.KeyProtectorType -eq 'RecoveryPassword' -and $kp.RecoveryPassword) {
            $found=$true
            $rtBl.AppendText("ID   : $($kp.KeyProtectorId)`r`n")
            $rtBl.AppendText("Cle  : $($kp.RecoveryPassword)`r`n`r`n")
        }
    }
    if (-not $found) { $rtBl.AppendText("Aucune cle de recuperation de type mot de passe sur ce volume.") }
    else { $rtBl.AppendText("Conservez cette cle en lieu sur (hors de ce PC).") ; Write-Log "BITLOCKER cle vue $($v.MountPoint)" }
})
$bBlSusp.Add_Click({
    $v = Bl-Selected; if (-not $v) { return }
    if (-not (Dlg-YN "Suspendre la protection BitLocker sur $($v.MountPoint) ?`n`nLe disque reste chiffre mais deverrouille automatiquement (utile avant une maj BIOS/materiel). A reprendre ensuite.")) { return }
    try { Suspend-BitLocker -MountPoint $v.MountPoint -RebootCount 0 -EA Stop
          Write-Log "BITLOCKER suspendu $($v.MountPoint)"; $rtBl.Text="Protection suspendue sur $($v.MountPoint). Pensez a la reprendre."; Load-BitLocker }
    catch { Dlg-Err $_.Exception.Message }
})
$bBlRes.Add_Click({
    $v = Bl-Selected; if (-not $v) { return }
    try { Resume-BitLocker -MountPoint $v.MountPoint -EA Stop
          Write-Log "BITLOCKER repris $($v.MountPoint)"; $rtBl.Text="Protection reprise sur $($v.MountPoint)."; Load-BitLocker }
    catch { Dlg-Err $_.Exception.Message }
})
$bBlUnl.Add_Click({
    $dlg=[System.Windows.Forms.Form]::new(); $dlg.Text="Deverrouiller un lecteur BitLocker"
    $dlg.Size=[Drawing.Size]::new(520,210); $dlg.StartPosition='CenterParent'; $dlg.BackColor=$BGray
    $dlg.FormBorderStyle='FixedDialog'; $dlg.MaximizeBox=$false
    $dlg.Controls.Add((New-Label "Lecteur (ex: D:) :" 14 18 140 26))
    $txLtr=New-Txt 160 18 120 ""; $dlg.Controls.Add($txLtr)
    $dlg.Controls.Add((New-Label "Mot de passe de`r`nrecuperation (48 chiffres) :" 14 54 140 40))
    $tK=New-Txt 160 54 320 ""; $dlg.Controls.Add($tK)
    $bOK=New-Btn "Deverrouiller" 290 110 110; $bOK.DialogResult='OK'; $dlg.Controls.Add($bOK)
    $bCa=New-Btn "Annuler" 410 110 90 30 $Mute; $bCa.DialogResult='Cancel'; $dlg.Controls.Add($bCa)
    $dlg.AcceptButton=$bOK
    if ($dlg.ShowDialog($F) -eq 'OK') {
        try { Unlock-BitLocker -MountPoint $txLtr.Text.Trim() -RecoveryPassword $tK.Text.Trim() -EA Stop
              Write-Log "BITLOCKER deverrouille $($txLtr.Text)"; Dlg-OK "Lecteur deverrouille."; Load-BitLocker }
        catch { Dlg-Err $_.Exception.Message }
    }
})
$bBlMgr.Add_Click({ try { Start-Process control -ArgumentList "/name Microsoft.BitLockerDriveEncryption" } catch { Start-Process manage-bde -ArgumentList "-status" } })
$bBlCopy.Add_Click({
    $v = Bl-Selected; if (-not $v) { return }
    $keys = @($v.KeyProtector | Where-Object { $_.KeyProtectorType -eq 'RecoveryPassword' -and $_.RecoveryPassword } |
              ForEach-Object { $_.RecoveryPassword })
    if ($keys.Count -eq 0) { Dlg-OK "Aucune cle de recuperation de type mot de passe sur ce volume."; return }
    try {
        [System.Windows.Forms.Clipboard]::SetText(($keys -join "`r`n"))
        Write-Log "BITLOCKER cle copiee $($v.MountPoint)"
        Dlg-OK "Cle copiee dans le presse-papiers.`nCollez-la en lieu sur, puis pensez a vider le presse-papiers."
    } catch { Dlg-Err $_.Exception.Message }
})

# ════════════════════════════════════════════════════════════════
#  ONGLET  SYSTEME  (reparation et outils N3)
# ════════════════════════════════════════════════════════════════
$tSy = New-Tab "Systeme"
$TC.TabPages.Add($tSy)

$tSy.Controls.Add((New-Label "Reparation et outils systeme (support N3)" 0 4 500 22 $true))
$tSy.Controls.Add((New-Sep 0 28 940))

$rtSy = [System.Windows.Forms.RichTextBox]::new()
$rtSy.Anchor = 'Top,Bottom,Left,Right'
$rtSy.Location=[Drawing.Point]::new(380,40); $rtSy.Size=[Drawing.Size]::new(560,528)
$rtSy.Font=[Drawing.Font]::new("Consolas",9); $rtSy.ReadOnly=$true
$rtSy.BackColor=[Drawing.Color]::FromArgb(24,26,31); $rtSy.ForeColor=$TxtFg; $rtSy.BorderStyle='FixedSingle'
$tSy.Controls.Add($rtSy)
$rtSy.Text = "Les resultats rapides s'affichent ici.`r`nLes operations longues (SFC, DISM) s'ouvrent dans une console dediee."

function SyOut { param($t) $rtSy.AppendText("$t`r`n"); $rtSy.ScrollToCaret() }
function Sy-Console { param($cmd,$titre)
    Start-Process cmd -ArgumentList "/k echo === $titre === & echo. & $cmd & echo. & echo === Termine. ==="
}

# Colonne de boutons a gauche
$sysBtns = @(
    @("Verifier les fichiers systeme (SFC)","sfc",       [Drawing.Color]::FromArgb(55,90,140)),
    @("Reparer l'image Windows (DISM)","dism",           [Drawing.Color]::FromArgb(55,90,140)),
    @("Reinitialiser la pile reseau","netreset",         [Drawing.Color]::FromArgb(200,120,20)),
    @("Processus les plus gourmands","proc",             ""),
    @("Services arretes (demarrage auto)","svc",         ""),
    @("Taches planifiees actives","tasks",               ""),
    @("Rapport batterie (portable)","battery",           ""),
    @("Programmes au demarrage","startup",               ""),
    @("Export infos systeme (fichier)","sysinfo",        ""),
    @("God Mode (tous les reglages)","godmode",          [Drawing.Color]::FromArgb(90,70,150)),
    @("Redemarrer en mode avance","advboot",             $Red),
    @("Arret complet (sans demarrage rapide)","fullshut",$Red)
)
$ySy=40
foreach ($sb in $sysBtns) {
    $b = New-Btn $sb[0] 0 $ySy 360 32 $sb[2]
    $b.Tag=$sb[1]; $b.TextAlign='MiddleLeft'
    $b.Add_Click({ param($sender,$e) Run-SysTool $sender.Tag })
    $tSy.Controls.Add($b); $ySy += 40
}

function Run-SysTool { param([string]$t)
    switch ($t) {
        'sfc'      { Sy-Console "sfc /scannow" "Verification des fichiers systeme"; SyOut "SFC lance dans une console dediee (5-15 min)." }
        'dism'     { Sy-Console "DISM /Online /Cleanup-Image /RestoreHealth" "Reparation de l'image Windows"; SyOut "DISM lance dans une console dediee (peut etre long)." }
        'netreset' { if (Dlg-YN "Reinitialiser la pile reseau (winsock + IP) ?`nUn redemarrage sera necessaire.") { Sy-Console "netsh winsock reset & netsh int ip reset" "Reinitialisation reseau"; Write-Log "NET RESET"; SyOut "Reinitialisation lancee. Redemarrez ensuite." } }
        'proc'     {
            $rtSy.Clear(); SyOut "PROCESSUS - top 12 par memoire :`r`n"
            SyOut ("{0,-32}{1,10}{2,8}" -f "Nom","Memoire","PID")
            Get-Process | Sort-Object WS -Descending | Select-Object -First 12 | ForEach-Object {
                SyOut ("{0,-32}{1,7} Mo{2,8}" -f $_.ProcessName, [int]($_.WS/1MB), $_.Id)
            }
        }
        'svc'      {
            $rtSy.Clear(); SyOut "SERVICES en demarrage automatique mais ARRETES :`r`n"
            $n=0
            Get-CimInstance Win32_Service -Filter "StartMode='Auto' AND State='Stopped'" | ForEach-Object {
                SyOut (" - {0}  ({1})" -f $_.DisplayName, $_.Name); $n++
            }
            if ($n -eq 0) { SyOut "Aucun. Tous les services automatiques tournent." } else { SyOut "`r`n$n service(s) a verifier." }
        }
        'tasks'    {
            $rtSy.Clear(); SyOut "TACHES PLANIFIEES actives (hors Microsoft) :`r`n"
            try { Get-ScheduledTask -EA Stop | Where-Object { $_.State -eq 'Ready' -and $_.TaskPath -notlike '\Microsoft\*' } |
                  Select-Object -First 30 | ForEach-Object { SyOut (" - {0}{1}" -f $_.TaskPath, $_.TaskName) } }
            catch { Sy-Console "schtasks /query /fo LIST /v" "Taches planifiees" }
        }
        'battery'  {
            $out = Join-Path ([Environment]::GetFolderPath('MyDocuments')) "Rapport-batterie.html"
            try { powercfg /batteryreport /output "$out" | Out-Null; SyOut "Rapport batterie genere :`r`n$out"; Start-Process $out }
            catch { SyOut "Pas de batterie ou commande indisponible." }
        }
        'startup'  {
            $rtSy.Clear(); SyOut "PROGRAMMES lances au demarrage :`r`n"
            Get-CimInstance Win32_StartupCommand | ForEach-Object { SyOut (" - {0}`r`n     {1}" -f $_.Name, $_.Command) }
        }
        'sysinfo'  {
            $out = Join-Path ([Environment]::GetFolderPath('MyDocuments')) ("Infos-systeme-" + (Get-Date -Format 'yyyyMMdd-HHmm') + ".txt")
            SyOut "Export en cours..."; systeminfo | Out-File $out -Encoding UTF8
            SyOut "Infos systeme exportees :`r`n$out"; Write-Log "SYSINFO export"; Start-Process notepad $out
        }
        'godmode'  { Start-Process explorer "shell:::{ED7BA470-8E54-465E-825C-99712043E01C}" }
        'advboot'  { if (Dlg-YN "Redemarrer maintenant en mode avance (options de recuperation) ?") { Write-Log "REBOOT avance"; Start-Process shutdown -ArgumentList "/r /o /t 3" } }
        'fullshut' { if (Dlg-YN "Arret complet (desactive le demarrage rapide pour ce cycle) ?") { Write-Log "ARRET complet"; Start-Process shutdown -ArgumentList "/s /full /t 3" } }
    }
}


# ════════════════════════════════════════════════════════════════
#  ONGLET  CONSOLE  (CLI admin integree)
# ════════════════════════════════════════════════════════════════
$tCo = New-Tab "Console"
$TC.TabPages.Add($tCo)

$tCo.Controls.Add((New-Label "Console admin integree" 0 4 400 22 $true))
$tCo.Controls.Add((New-Sep 0 28 880))

# Boutons ouvrir consoles externes
$bPS = New-Btn "Ouvrir PowerShell (admin)" 0 40 220 30
$bPS.Add_Click({ Start-Process powershell -Verb RunAs })
$tCo.Controls.Add($bPS)

$bCmd = New-Btn "Ouvrir Invite cmd (admin)" 230 40 220 30 ([Drawing.Color]::FromArgb(70,75,85))
$bCmd.Add_Click({ Start-Process cmd -Verb RunAs })
$tCo.Controls.Add($bCmd)

# Choix moteur
$tCo.Controls.Add((New-Label "Moteur :" 470 46 60 22))
$cboEng = [System.Windows.Forms.ComboBox]::new()
$cboEng.BackColor=$TxtBg; $cboEng.ForeColor=$TxtFg; $cboEng.FlatStyle='Flat'
$cboEng.Location = [Drawing.Point]::new(532,44); $cboEng.Size = [Drawing.Size]::new(140,26)
$cboEng.DropDownStyle = 'DropDownList'; $cboEng.Font = $FN
$cboEng.Items.AddRange(@("PowerShell","CMD")); $cboEng.SelectedIndex = 0
$tCo.Controls.Add($cboEng)

# Zone de sortie
$rtCo = [System.Windows.Forms.RichTextBox]::new()
$rtCo.Anchor = 'Top,Bottom,Left,Right'
$rtCo.Location = [Drawing.Point]::new(0,82); $rtCo.Size = [Drawing.Size]::new(868,400)
$rtCo.Font = [Drawing.Font]::new("Consolas",9.5); $rtCo.ReadOnly = $true
$rtCo.BackColor = [Drawing.Color]::FromArgb(12,12,16); $rtCo.ForeColor = [Drawing.Color]::FromArgb(210,210,210)
$rtCo.BorderStyle = 'FixedSingle'
$tCo.Controls.Add($rtCo)
$rtCo.AppendText("Console admin integree - tapez une commande ci-dessous puis Entree.`r`nAttention : execution en tant qu'administrateur.`r`n`r`n")

# Ligne de saisie
$txCo = [System.Windows.Forms.TextBox]::new()
$txCo.Location = [Drawing.Point]::new(0,490); $txCo.Size = [Drawing.Size]::new(760,28)
$txCo.Font = [Drawing.Font]::new("Consolas",10)
$tCo.Controls.Add($txCo)

$bRun = New-Btn "Executer" 770 489 98 30 $Green
$tCo.Controls.Add($bRun)

$Script:runCmd = {
    $cmd = $txCo.Text
    if ([string]::IsNullOrWhiteSpace($cmd)) { return }
    $prompt = if ($cboEng.SelectedItem -eq 'CMD') { 'CMD>' } else { 'PS>' }
    $rtCo.SelectionColor = [Drawing.Color]::FromArgb(120,200,255)
    $rtCo.AppendText("$prompt $cmd`r`n")
    $rtCo.SelectionColor = [Drawing.Color]::FromArgb(210,210,210)
    try {
        if ($cboEng.SelectedItem -eq 'CMD') {
            $out = cmd /c $cmd 2>&1 | Out-String
        } else {
            $out = Invoke-Expression $cmd 2>&1 | Out-String
        }
        if ([string]::IsNullOrWhiteSpace($out)) { $out = "(pas de sortie)`r`n" }
        $rtCo.AppendText($out + "`r`n")
    } catch {
        $rtCo.SelectionColor = [Drawing.Color]::FromArgb(255,90,90)
        $rtCo.AppendText("ERREUR : $($_.Exception.Message)`r`n`r`n")
    }
    $rtCo.ScrollToCaret()
    Write-Log "CONSOLE: $cmd"
    $txCo.Clear()
}
$bRun.Add_Click($Script:runCmd)
$txCo.Add_KeyDown({ if ($_.KeyCode -eq 'Enter') { $_.SuppressKeyPress = $true; & $Script:runCmd } })


# ════════════════════════════════════════════════════════════════
#  ONGLET  AIDE  (fiche memo + raccourcis Windows)
# ════════════════════════════════════════════════════════════════
$tAi = New-Tab "Aide"
$TC.TabPages.Add($tAi)

$tAi.Controls.Add((New-Label "Raccourcis Windows (clic = ouvre)" 0 4 400 22 $true))
$tAi.Controls.Add((New-Sep 0 28 880))

# Boutons raccourcis : ouvrent directement les consoles Windows
$shortcuts = @(
    @("Connexions reseau",      "ncpa.cpl"),
    @("Proprietes systeme",     "sysdm.cpl"),
    @("Programmes installes",   "appwiz.cpl"),
    @("Pare-feu",               "firewall.cpl"),
    @("Services",               "services.msc"),
    @("Gestion ordinateur",     "compmgmt.msc"),
    @("Gestion des disques",    "diskmgmt.msc"),
    @("Utilisateurs et groupes","lusrmgr.msc"),
    @("Peripheriques",          "devmgmt.msc"),
    @("Observateur evenements", "eventvwr.msc"),
    @("Nettoyage de disque",    "cleanmgr"),
    @("Config systeme",         "msconfig"),
    @("Moniteur ressources",    "resmon"),
    @("Version Windows",        "winver"),
    @("Registre",               "regedit"),
    @("Panneau config",         "control")
)
$sx = 0; $sy = 40; $col = 0
foreach ($s in $shortcuts) {
    $b = New-Btn $s[0] $sx $sy 205 30 ([Drawing.Color]::FromArgb(55,90,140))
    $b.Tag = $s[1]; $b.TextAlign = 'MiddleLeft'; $b.Font = $FN
    $b.Add_Click({ param($sender,$e)
        try { Start-Process $sender.Tag -EA Stop } catch { Dlg-Err "Impossible d'ouvrir : $($sender.Tag)" }
    })
    $tAi.Controls.Add($b)
    $col++
    if ($col -ge 4) { $col = 0; $sx = 0; $sy += 38 } else { $sx += 215 }
}

# Zone memo commandes
$memoY = $sy + 14
$tAi.Controls.Add((New-Label "Fiche memo - commandes utiles (selectionner = copier)" 0 $memoY 500 22 $true))
$rtAi = [System.Windows.Forms.RichTextBox]::new()
$rtAi.Anchor = 'Top,Bottom,Left,Right'
$rtAi.Location = [Drawing.Point]::new(0,($memoY+26)); $rtAi.Size = [Drawing.Size]::new(880,($TC.Size.Height - $memoY - 70))
$rtAi.Font = [Drawing.Font]::new("Consolas",9); $rtAi.ReadOnly = $true
$rtAi.BackColor = [Drawing.Color]::FromArgb(24,24,28); $rtAi.ForeColor = [Drawing.Color]::FromArgb(215,215,215)
$rtAi.BorderStyle = 'FixedSingle'
$tAi.Controls.Add($rtAi)

function AiTitle { param($t)
    $rtAi.SelectionColor = [Drawing.Color]::FromArgb(120,200,255)
    $rtAi.SelectionFont = [Drawing.Font]::new("Consolas",9,[Drawing.FontStyle]::Bold)
    $rtAi.AppendText("`r`n== $t ==`r`n")
    $rtAi.SelectionFont = [Drawing.Font]::new("Consolas",9)
    $rtAi.SelectionColor = [Drawing.Color]::FromArgb(215,215,215)
}
function AiCmd { param($cmd,$desc)
    $rtAi.SelectionColor = [Drawing.Color]::FromArgb(130,230,160)
    $rtAi.AppendText(("  {0,-46}" -f $cmd))
    $rtAi.SelectionColor = [Drawing.Color]::FromArgb(150,150,150)
    $rtAi.AppendText("$desc`r`n")
}

AiTitle "RESEAU - diagnostic"
AiCmd "ipconfig /all"                    "config complete des cartes"
AiCmd "ipconfig /flushdns"               "vide le cache DNS"
AiCmd "ipconfig /release + /renew"       "relache et renouvelle le bail DHCP"
AiCmd "ping <ip>"                        "test de joignabilite"
AiCmd "tracert <ip>"                     "route vers la cible"
AiCmd "pathping <ip>"                    "route + perte de paquets"
AiCmd "nslookup <nom>"                   "resolution DNS"
AiCmd "netstat -ano"                     "connexions + PID"
AiCmd "arp -a"                           "table ARP (MAC connues)"
AiCmd "route print"                      "table de routage"
AiCmd "Test-NetConnection <ip> -Port n"  "test d'un port TCP (PowerShell)"
AiCmd "Get-NetIPConfiguration"           "config IP (PowerShell)"

AiTitle "LECTEURS RESEAU / SMB"
AiCmd "net use"                          "liste des lecteurs mappes"
AiCmd "net use X: \\srv\partage"        "monte un lecteur"
AiCmd "net use X: /delete"               "demonte un lecteur"
AiCmd "net use * /delete /y"             "demonte tous les lecteurs"
AiCmd "Get-SmbConnection"                "connexions SMB actives + dialecte"
AiCmd "Get-SmbClientConfiguration"       "timeouts SMB (KeepConn, Session)"
AiCmd "gpupdate /force"                  "force la maj des GPO (relance scripts de mappage)"

AiTitle "DISQUE / ESPACE"
AiCmd "cleanmgr"                         "nettoyage de disque Windows"
AiCmd "dism /online /cleanup-image /startcomponentcleanup" "purge WinSxS"
AiCmd "sfc /scannow"                     "verifie et repare les fichiers systeme"
AiCmd "chkdsk C: /f"                     "verifie le disque (au reboot)"
AiCmd "Get-PSDrive"                      "espace par lecteur"

AiTitle "COMPTES LOCAUX"
AiCmd "net user"                         "liste des comptes"
AiCmd "net user <nom> *"                 "change le mot de passe"
AiCmd "net localgroup Administrateurs"   "membres du groupe admin"
AiCmd "lusrmgr.msc"                      "gestion graphique des comptes"

AiTitle "PARE-FEU"
AiCmd "netsh advfirewall show allprofiles" "etat des 3 profils"
AiCmd "Get-NetFirewallProfile"           "etat pare-feu (PowerShell)"
AiCmd "netsh advfirewall set allprofiles state off" "desactive (prudence !)"

AiTitle "SYSTEME / INFOS"
AiCmd "systeminfo"                       "infos completes du poste"
AiCmd "winver"                           "version de Windows"
AiCmd "hostname"                         "nom de la machine"
AiCmd "whoami /groups"                   "groupes de l'utilisateur courant"
AiCmd "gpresult /r"                      "GPO appliquees"

AiTitle "REPERES - lecteur passe-plat"
$rtAi.SelectionColor = [Drawing.Color]::FromArgb(200,200,200)
$rtAi.AppendText("  Lecteur de TRAVAIL : lecture/ecriture directe dans un dossier partage.`r`n")
$rtAi.AppendText("  Lecteur PASSE-PLAT (sas) : zone tampon entre deux reseaux de niveaux`r`n")
$rtAi.AppendText("  differents. On DEPOSE un fichier d'un cote, il est controle, puis`r`n")
$rtAi.AppendText("  recupere de l'autre. Pas de traversee directe - rupture de flux.`r`n")
$rtAi.AppendText("  Souvent unidirectionnel. A confirmer avec l'equipe reseau du site.`r`n")

$rtAi.SelectionStart = 0; $rtAi.ScrollToCaret()


# ════════════════════════════════════════════════════════════════
#  LANCEMENT
# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
#  PAGE D'ACCUEIL  (overlay avec tuiles a icones GDI+)
# ════════════════════════════════════════════════════════════════

# --- Fonction de dessin d'icone vectorielle sur un Panel ---
function Draw-Icon {
    param($g, [string]$type, $color, $x, $y, $sz)
    $pen  = [System.Drawing.Pen]::new($color, 2.4)
    $pen.StartCap = 'Round'; $pen.EndCap = 'Round'; $pen.LineJoin = 'Round'
    $br   = [System.Drawing.SolidBrush]::new($color)
    $g.SmoothingMode = 'AntiAlias'
    switch ($type) {
        'machine' {
            # ecran + pied
            $g.DrawRectangle($pen, $x, $y, $sz, $sz*0.66)
            $g.DrawLine($pen, $x+$sz*0.35, $y+$sz*0.66, $x+$sz*0.30, $y+$sz*0.82)
            $g.DrawLine($pen, $x+$sz*0.65, $y+$sz*0.66, $x+$sz*0.70, $y+$sz*0.82)
            $g.DrawLine($pen, $x+$sz*0.22, $y+$sz*0.82, $x+$sz*0.78, $y+$sz*0.82)
        }
        'ip' {
            # globe reseau
            $g.DrawEllipse($pen, $x, $y, $sz, $sz)
            $g.DrawEllipse($pen, $x+$sz*0.30, $y, $sz*0.40, $sz)
            $g.DrawLine($pen, $x, $y+$sz*0.5, $x+$sz, $y+$sz*0.5)
            $g.DrawLine($pen, $x+$sz*0.08, $y+$sz*0.28, $x+$sz*0.92, $y+$sz*0.28)
            $g.DrawLine($pen, $x+$sz*0.08, $y+$sz*0.72, $x+$sz*0.92, $y+$sz*0.72)
        }
        'dns' {
            # serveur empile
            $h = $sz*0.26
            for ($i=0; $i -lt 3; $i++) {
                $yy = $y + $i*($h+$sz*0.04)
                $g.DrawRectangle($pen, $x, $yy, $sz, $h)
                $g.FillEllipse($br, $x+$sz*0.12, $yy+$h*0.32, $sz*0.14, $sz*0.14)
            }
        }
        'drive' {
            # dossier reseau
            $g.DrawLine($pen, $x, $y+$sz*0.22, $x+$sz*0.40, $y+$sz*0.22)
            $g.DrawLine($pen, $x+$sz*0.40, $y+$sz*0.22, $x+$sz*0.50, $y+$sz*0.10)
            $g.DrawLine($pen, $x+$sz*0.50, $y+$sz*0.10, $x+$sz, $y+$sz*0.10)
            $g.DrawRectangle($pen, $x, $y+$sz*0.22, $sz, $sz*0.62)
            $g.FillEllipse($br, $x+$sz*0.42, $y+$sz*0.50, $sz*0.16, $sz*0.16)
        }
        'users' {
            # personnage
            $g.DrawEllipse($pen, $x+$sz*0.28, $y, $sz*0.44, $sz*0.44)
            $g.DrawArc($pen, $x+$sz*0.05, $y+$sz*0.48, $sz*0.90, $sz*0.90, 180, 180)
        }
        'diag' {
            # loupe + coche
            $g.DrawEllipse($pen, $x, $y, $sz*0.62, $sz*0.62)
            $g.DrawLine($pen, $x+$sz*0.55, $y+$sz*0.55, $x+$sz*0.95, $y+$sz*0.95)
            $g.DrawLine($pen, $x+$sz*0.16, $y+$sz*0.31, $x+$sz*0.27, $y+$sz*0.42)
            $g.DrawLine($pen, $x+$sz*0.27, $y+$sz*0.42, $x+$sz*0.46, $y+$sz*0.18)
        }
        'clean' {
            # balai / brosse
            $g.DrawLine($pen, $x+$sz*0.70, $y+$sz*0.05, $x+$sz*0.40, $y+$sz*0.55)
            $g.DrawLine($pen, $x+$sz*0.25, $y+$sz*0.55, $x+$sz*0.62, $y+$sz*0.55)
            $g.DrawLine($pen, $x+$sz*0.22, $y+$sz*0.60, $x+$sz*0.16, $y+$sz*0.95)
            $g.DrawLine($pen, $x+$sz*0.38, $y+$sz*0.60, $x+$sz*0.36, $y+$sz*0.95)
            $g.DrawLine($pen, $x+$sz*0.54, $y+$sz*0.60, $x+$sz*0.60, $y+$sz*0.95)
            $g.DrawLine($pen, $x+$sz*0.22, $y+$sz*0.60, $x+$sz*0.62, $y+$sz*0.60)
        }
        'console' {
            # fenetre terminal + chevron
            $g.DrawRectangle($pen, $x, $y+$sz*0.10, $sz, $sz*0.78)
            $g.DrawLine($pen, $x, $y+$sz*0.28, $x+$sz, $y+$sz*0.28)
            $g.DrawLine($pen, $x+$sz*0.14, $y+$sz*0.45, $x+$sz*0.30, $y+$sz*0.58)
            $g.DrawLine($pen, $x+$sz*0.30, $y+$sz*0.58, $x+$sz*0.14, $y+$sz*0.71)
            $g.DrawLine($pen, $x+$sz*0.40, $y+$sz*0.71, $x+$sz*0.64, $y+$sz*0.71)
        }
        'materiel' {
            # puce / processeur
            $g.DrawRectangle($pen, $x+$sz*0.2, $y+$sz*0.2, $sz*0.6, $sz*0.6)
            $g.DrawRectangle($pen, $x+$sz*0.35, $y+$sz*0.35, $sz*0.3, $sz*0.3)
            foreach ($o in 0.35,0.5,0.65) {
                $g.DrawLine($pen, $x+$sz*$o, $y+$sz*0.2, $x+$sz*$o, $y+$sz*0.08)
                $g.DrawLine($pen, $x+$sz*$o, $y+$sz*0.8, $x+$sz*$o, $y+$sz*0.92)
                $g.DrawLine($pen, $x+$sz*0.2, $y+$sz*$o, $x+$sz*0.08, $y+$sz*$o)
                $g.DrawLine($pen, $x+$sz*0.8, $y+$sz*$o, $x+$sz*0.92, $y+$sz*$o)
            }
        }
        'copie' {
            # deux feuilles
            $g.DrawRectangle($pen, $x+$sz*0.12, $y+$sz*0.12, $sz*0.5, $sz*0.62)
            $g.DrawRectangle($pen, $x+$sz*0.36, $y+$sz*0.28, $sz*0.5, $sz*0.62)
        }
        'bitlocker' {
            # cadenas
            $g.DrawRectangle($pen, $x+$sz*0.24, $y+$sz*0.42, $sz*0.52, $sz*0.44)
            $g.DrawArc($pen, $x+$sz*0.34, $y+$sz*0.12, $sz*0.32, $sz*0.5, 180, 180)
            $g.FillEllipse($br, $x+$sz*0.45, $y+$sz*0.56, $sz*0.1, $sz*0.1)
        }
        'systeme' {
            # engrenage simplifie
            $g.DrawEllipse($pen, $x+$sz*0.28, $y+$sz*0.28, $sz*0.44, $sz*0.44)
            foreach ($a in 0,45,90,135,180,225,270,315) {
                $rad=[math]::PI*$a/180
                $x1=$x+$sz*0.5+[math]::Cos($rad)*$sz*0.24; $y1=$y+$sz*0.5+[math]::Sin($rad)*$sz*0.24
                $x2=$x+$sz*0.5+[math]::Cos($rad)*$sz*0.36; $y2=$y+$sz*0.5+[math]::Sin($rad)*$sz*0.36
                $g.DrawLine($pen, $x1, $y1, $x2, $y2)
            }
        }
        'help' {
            # cercle + point d'interrogation
            $g.DrawEllipse($pen, $x, $y, $sz, $sz)
            $g.DrawArc($pen, $x+$sz*0.30, $y+$sz*0.20, $sz*0.40, $sz*0.34, 160, 250)
            $g.DrawLine($pen, $x+$sz*0.50, $y+$sz*0.52, $x+$sz*0.50, $y+$sz*0.64)
            $g.FillEllipse($br, $x+$sz*0.46, $y+$sz*0.74, $sz*0.09, $sz*0.09)
        }
    }
    $pen.Dispose(); $br.Dispose()
}

# --- Panel accueil (recouvre le TabControl) ---
$HomePanel = [System.Windows.Forms.Panel]::new()
$HomePanel.Location = [Drawing.Point]::new(0,50)
$HomePanel.Size = [Drawing.Size]::new(1040, 668); $HomePanel.Anchor = 'Top,Bottom,Left,Right'
$HomePanel.BackColor = $BGray
$F.Controls.Add($HomePanel)
$HomePanel.BringToFront()

# Titre de bienvenue
$wLbl = New-Label "Bienvenue" 40 26 500 34 $true
$wLbl.Font = [Drawing.Font]::new("Segoe UI Light", 20)
$wLbl.ForeColor = $TxtFg
$HomePanel.Controls.Add($wLbl)

$wSub = New-Label "Selectionnez un module pour commencer" 42 66 600 24
$wSub.ForeColor = $Mute
$HomePanel.Controls.Add($wSub)

# Definition des tuiles : titre, sous-titre, index onglet, couleur, icone
$tiles = @(
    @{ t="Machine";     s="Identite du poste, renommage";    tab=0;  c=([Drawing.Color]::FromArgb(0,120,212));   ic="machine"   },
    @{ t="Materiel";    s="RAM, CPU, temperatures, GPU";     tab=1;  c=([Drawing.Color]::FromArgb(0,168,180));   ic="materiel"  },
    @{ t="Adressage";   s="Configurer les cartes reseau";    tab=2;  c=([Drawing.Color]::FromArgb(0,158,170));   ic="ip"        },
    @{ t="DNS";         s="Serveurs DNS et application";     tab=3;  c=([Drawing.Color]::FromArgb(120,90,200));  ic="dns"       },
    @{ t="Lecteurs";    s="Monter et gerer les partages";    tab=4;  c=([Drawing.Color]::FromArgb(200,120,20));  ic="drive"     },
    @{ t="Comptes";     s="Utilisateurs locaux et droits";   tab=5;  c=([Drawing.Color]::FromArgb(16,140,90));   ic="users"     },
    @{ t="Diagnostic";  s="Tests reseau, firewall, versions"; tab=6; c=([Drawing.Color]::FromArgb(190,60,120));  ic="diag"      },
    @{ t="Nettoyage";   s="Liberer de l'espace disque";      tab=7;  c=([Drawing.Color]::FromArgb(210,140,20));  ic="clean"     },
    @{ t="Copie";       s="Copier / synchroniser (Robocopy)"; tab=8; c=([Drawing.Color]::FromArgb(70,130,190));  ic="copie"     },
    @{ t="BitLocker";   s="Chiffrement et recuperation";     tab=9;  c=([Drawing.Color]::FromArgb(120,90,200));  ic="bitlocker" },
    @{ t="Systeme";     s="Reparation et outils N3";         tab=10; c=([Drawing.Color]::FromArgb(150,100,40));  ic="systeme"   },
    @{ t="Console";     s="Ligne de commande admin";         tab=11; c=([Drawing.Color]::FromArgb(130,140,155)); ic="console"   },
    @{ t="Aide";        s="Commandes et raccourcis Windows"; tab=12; c=([Drawing.Color]::FromArgb(90,140,60));   ic="help"      }
)

# Grille de tuiles
$cols = 5; $tw = 162; $th = 148; $gap = 15; $ox = 40; $oy = 106
for ($i=0; $i -lt $tiles.Count; $i++) {
    $ti  = $tiles[$i]
    $col = $i % $cols; $row = [math]::Floor($i / $cols)
    $px  = $ox + $col*($tw+$gap)
    $py  = $oy + $row*($th+$gap)

    $card = [System.Windows.Forms.Panel]::new()
    $card.Location = [Drawing.Point]::new($px,$py)
    $card.Size = [Drawing.Size]::new($tw,$th)
    $card.BackColor = $CardBg
    $card.Cursor = 'Hand'
    $card.Tag = $ti

    # Barre de couleur a gauche
    $bar = [System.Windows.Forms.Panel]::new()
    $bar.Location = [Drawing.Point]::new(0,0)
    $bar.Size = [Drawing.Size]::new(6,$th)
    $bar.BackColor = $ti.c
    $card.Controls.Add($bar)

    # Zone icone (dessin GDI+)
    $iconP = [System.Windows.Forms.Panel]::new()
    $iconP.Location = [Drawing.Point]::new(24,22)
    $iconP.Size = [Drawing.Size]::new(52,52)
    $iconP.BackColor = $CardBg
    $iconP.Tag = @{ ic = $ti.ic; c = $ti.c }
    $iconP.Add_Paint({
        param($sndr,$e)
        Draw-Icon $e.Graphics $sndr.Tag.ic $sndr.Tag.c 6 4 44
    })
    $card.Controls.Add($iconP)

    # Titre
    $tl = New-Label $ti.t 20 80 150 22 $true
    $tl.Font = [Drawing.Font]::new("Segoe UI Semibold", 10)
    $tl.ForeColor = $TxtFg
    $card.Controls.Add($tl)

    # Sous-titre
    $sl = New-Label $ti.s 20 104 138 40
    $sl.ForeColor = $Mute
    $sl.Font = [Drawing.Font]::new("Segoe UI", 7.5)
    $card.Controls.Add($sl)

    # Fleche
    $ar = New-Label ">" 134 18 22 22 $true
    $ar.ForeColor = $ti.c
    $ar.Font = [Drawing.Font]::new("Segoe UI", 13, [Drawing.FontStyle]::Bold)
    $card.Controls.Add($ar)

    # Bordure basse coloree fine
    $under = [System.Windows.Forms.Panel]::new()
    $under.Location = [Drawing.Point]::new(6,$th-3)
    $under.Size = [Drawing.Size]::new($tw-6,3)
    $under.BackColor = [Drawing.Color]::FromArgb(60,64,72)
    $card.Controls.Add($under)

    # --- Interactions : hover + clic (propagees aux enfants) ---
    # Remonte jusqu'a la CARTE (son Tag est une hashtable contenant la cle 'tab')
    $findCard = {
        param($ctl)
        $x = $ctl
        while ($x -and -not ($x.Tag -is [hashtable] -and $x.Tag.ContainsKey('tab'))) { $x = $x.Parent }
        return $x
    }
    $enter = {
        param($sndr,$e)
        $c = & $findCard $sndr
        if ($c) {
            $c.BackColor = [Drawing.Color]::FromArgb(54, 59, 68)
            $u = $c.Controls[$c.Controls.Count-1]
            if ($u) { $u.BackColor = $c.Tag.c }
        }
    }
    $leave = {
        param($sndr,$e)
        $c = & $findCard $sndr
        if ($c) {
            $c.BackColor = $CardBg
            $u = $c.Controls[$c.Controls.Count-1]
            if ($u) { $u.BackColor = [Drawing.Color]::FromArgb(60,64,72) }
        }
    }
    $click = {
        param($sndr,$e)
        $c = & $findCard $sndr
        if ($c) { $HomePanel.Visible = $false; $TC.SelectedIndex = $c.Tag.tab; $TC.BringToFront() }
    }
    $card.Add_MouseEnter($enter); $card.Add_MouseLeave($leave); $card.Add_Click($click)
    foreach ($child in $card.Controls) {
        $child.Add_MouseEnter($enter); $child.Add_Click($click)
    }
    $HomePanel.Controls.Add($card)
}

# Pied de page accueil
$foot = New-Label "Intervenant IT/OT   -   v$AppVersion   -   mode $(if($runFromInstall){'installe'}else{'portable'})" 42 616 700 24
$foot.ForeColor = $Mute
$foot.Font = [Drawing.Font]::new("Segoe UI", 8.5)
$HomePanel.Controls.Add($foot)

# --- Bouton "Accueil" dans la barre de titre pour revenir ---
$btnHome = [System.Windows.Forms.Button]::new()
$btnHome.Text = "Accueil"
$btnHome.Location = [Drawing.Point]::new(830,10)
$btnHome.Size = [Drawing.Size]::new(96,30); $btnHome.Anchor = 'Top,Right'
$btnHome.BackColor = $Blue
$btnHome.ForeColor = $White
$btnHome.FlatStyle = 'Flat'; $btnHome.FlatAppearance.BorderSize = 0
$btnHome.Font = $FNB; $btnHome.Cursor = 'Hand'
$btnHome.Add_Click({ $HomePanel.Visible = $true; $HomePanel.BringToFront() })
$hdr.Controls.Add($btnHome)



# ════════════════════════════════════════════════════════════════
#  RAPPORT DE SESSION  (propose a la fermeture)
# ════════════════════════════════════════════════════════════════

function HEsc { param($s)
    if ($null -eq $s) { return "" }
    return ([string]$s).Replace('&','&amp;').Replace('<','&lt;').Replace('>','&gt;')
}

function Get-SessionLog {
    if (-not (Test-Path $Log)) { return @() }
    $lines = @(Get-Content $Log -EA SilentlyContinue)
    $idx = -1
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        if ($lines[$i] -match 'SESSION OUVERTE') { $idx = $i; break }
    }
    if ($idx -ge 0) { return @($lines[$idx..($lines.Count - 1)]) }
    return $lines
}

function Build-Report { param($intervenant, $objet, $observations)
    $now  = Get-Date -Format 'dd/MM/yyyy HH:mm'
    $sb   = [System.Text.StringBuilder]::new()

    # --- Collecte des donnees ---
    $cs   = Get-CimInstance Win32_ComputerSystem -EA SilentlyContinue
    $bios = Get-CimInstance Win32_BIOS -EA SilentlyContinue
    $os   = Get-CimInstance Win32_OperatingSystem -EA SilentlyContinue
    $lic  = Get-CimInstance SoftwareLicensingProduct -Filter "PartialProductKey IS NOT NULL AND ApplicationID='55c92734-d682-4d71-983e-d6ec3f16059f'" -EA SilentlyContinue | Select-Object -First 1
    $act  = switch ($lic.LicenseStatus) { 1 {"Active"} 0 {"Non active"} 2 {"Grace"} default {"Inconnu"} }

    # Reseau
    $netRows = ""
    foreach ($ad in (Get-NetAdapter -EA SilentlyContinue | Where-Object { $_.Status -eq 'Up' -and $_.HardwareInterface })) {
        $cfg2 = Get-NetIPConfiguration -InterfaceIndex $ad.ifIndex -EA SilentlyContinue
        $ip   = ($cfg2.IPv4Address.IPAddress -join ', ')
        $gw   = $cfg2.IPv4DefaultGateway.NextHop -join ', '
        $dns  = ($cfg2.DNSServer | Where-Object { $_.AddressFamily -eq 2 }).ServerAddresses -join ', '
        $pfx  = ($cfg2.IPv4Address.PrefixLength | Select-Object -First 1)
        $mode = (Get-NetIPInterface -InterfaceIndex $ad.ifIndex -AddressFamily IPv4 -EA SilentlyContinue).Dhcp
        $modeTxt = if ($mode -eq 'Disabled') { 'Statique' } else { 'DHCP' }
        $netRows += "<tr><td>$(HEsc $ad.Name)</td><td>$(HEsc $ip)/$(HEsc $pfx)</td><td>$(HEsc $gw)</td><td>$(HEsc $dns)</td><td>$(HEsc $ad.MacAddress)</td><td>$(HEsc $modeTxt)</td></tr>"
    }
    if (-not $netRows) { $netRows = "<tr><td colspan='6' class='muted'>Aucune carte active.</td></tr>" }

    # Lecteurs reseau
    $drvRows = ""
    foreach ($m in (Get-CimInstance Win32_MappedLogicalDisk -EA SilentlyContinue)) {
        $ok = Test-Path "$($m.DeviceID)\" -EA SilentlyContinue
        $etat = if ($ok) { "<span class='ok'>Accessible</span>" } else { "<span class='ko'>Deconnecte</span>" }
        $drvRows += "<tr><td>$(HEsc $m.DeviceID)</td><td>$(HEsc $m.ProviderName)</td><td>$etat</td></tr>"
    }
    if (-not $drvRows) { $drvRows = "<tr><td colspan='3' class='muted'>Aucun lecteur reseau monte.</td></tr>" }

    # Disque C:
    $d = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" -EA SilentlyContinue
    $diskTxt = if ($d) {
        $pct = [int]((($d.Size - $d.FreeSpace) / $d.Size) * 100)
        "{0:N1} Go libres sur {1:N1} Go  ({2}% utilise)" -f ($d.FreeSpace/1GB), ($d.Size/1GB), $pct
    } else { "Indisponible" }

    # Journal de session
    $logRows = ""
    foreach ($ln in (Get-SessionLog)) {
        $parts = $ln -split ' \| ', 3
        if ($parts.Count -eq 3) {
            $logRows += "<tr><td class='mono'>$(HEsc $parts[0])</td><td>$(HEsc $parts[2])</td></tr>"
        }
    }
    if (-not $logRows) { $logRows = "<tr><td colspan='2' class='muted'>Aucune action enregistree.</td></tr>" }

    $obsHtml = if ([string]::IsNullOrWhiteSpace($observations)) { "<span class='muted'>(aucune)</span>" } else { (HEsc $observations).Replace("`r`n","<br>").Replace("`n","<br>") }

    # --- Assemblage HTML ---
    [void]$sb.Append(@"
<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Rapport d'intervention - $(HEsc $cs.Name) - $now</title>
<style>
 * { box-sizing: border-box; }
 body { font-family: 'Segoe UI', Arial, sans-serif; color: #1f2530; margin: 0; padding: 32px 40px; background: #fff; font-size: 13px; }
 h1 { font-size: 22px; margin: 0 0 2px; color: #14202e; }
 h2 { font-size: 14px; text-transform: uppercase; letter-spacing: .5px; color: #2d6fb0; margin: 26px 0 8px; padding-bottom: 4px; border-bottom: 2px solid #e3e8ef; }
 .sub { color: #6b7280; font-size: 12px; margin-bottom: 18px; }
 table { width: 100%; border-collapse: collapse; margin: 4px 0; }
 th, td { text-align: left; padding: 6px 10px; border: 1px solid #dce1e8; vertical-align: top; }
 th { background: #f3f6fa; font-weight: 600; color: #33404f; width: 190px; }
 .grid th { width: auto; }
 .mono { font-family: Consolas, 'Courier New', monospace; font-size: 12px; white-space: nowrap; }
 .muted { color: #9aa0aa; font-style: italic; }
 .ok { color: #1a8a4b; font-weight: 600; }
 .ko { color: #c0392b; font-weight: 600; }
 .cartouche { border: 1px solid #cfd6df; border-radius: 6px; padding: 16px 20px; background: #f8fafc; margin-bottom: 6px; }
 .cartouche table { margin: 0; }
 .cartouche td { border: none; padding: 3px 8px 3px 0; }
 .cartouche td.k { color: #6b7280; width: 130px; }
 .cartouche td.v { font-weight: 600; }
 .sign { margin-top: 34px; display: flex; gap: 60px; }
 .sign div { flex: 1; }
 .sign .line { border-top: 1px solid #9aa0aa; margin-top: 42px; padding-top: 4px; color: #6b7280; font-size: 11px; }
 .foot { margin-top: 30px; padding-top: 10px; border-top: 1px solid #e3e8ef; color: #9aa0aa; font-size: 11px; }
 @media print { body { padding: 0; } h2 { break-after: avoid; } tr { break-inside: avoid; } }
</style></head><body>

<h1>Rapport d'intervention</h1>
<div class="sub">Poste $(HEsc $cs.Name) &nbsp;&bull;&nbsp; $now</div>

<div class="cartouche"><table>
 <tr><td class="k">Intervenant</td><td class="v">$(HEsc $intervenant)</td><td class="k">Date</td><td class="v">$now</td></tr>
 <tr><td class="k">Poste</td><td class="v">$(HEsc $cs.Name)</td><td class="k">Session ouverte par</td><td class="v">$(HEsc $env:USERNAME)</td></tr>
 <tr><td class="k">Objet</td><td class="v" colspan="3">$(HEsc $objet)</td></tr>
</table></div>

<h2>1. Identite du poste</h2>
<table>
 <tr><th>Nom machine</th><td>$(HEsc $cs.Name)</td></tr>
 <tr><th>Fabricant / Modele</th><td>$(HEsc $cs.Manufacturer) &nbsp; $(HEsc $cs.Model)</td></tr>
 <tr><th>Numero de serie</th><td>$(HEsc $bios.SerialNumber)</td></tr>
 <tr><th>Systeme</th><td>$(HEsc $os.Caption) &nbsp; (build $(HEsc $os.BuildNumber), $(HEsc $os.OSArchitecture))</td></tr>
 <tr><th>Activation Windows</th><td>$act</td></tr>
</table>

<h2>2. Configuration reseau</h2>
<table class="grid">
 <tr><th>Carte</th><th>IP / prefixe</th><th>Passerelle</th><th>DNS</th><th>MAC</th><th>Mode</th></tr>
 $netRows
</table>

<h2>3. Lecteurs reseau</h2>
<table class="grid">
 <tr><th>Lettre</th><th>Chemin</th><th>Etat</th></tr>
 $drvRows
</table>

<h2>4. Espace disque</h2>
<table><tr><th>Disque systeme (C:)</th><td>$diskTxt</td></tr></table>

<h2>5. Actions realisees pendant la session</h2>
<table class="grid">
 <tr><th style="width:170px">Horodatage</th><th>Action</th></tr>
 $logRows
</table>

<h2>6. Observations</h2>
<div style="padding:8px 2px;">$obsHtml</div>

<div class="sign">
 <div><div class="line">Intervenant &mdash; $(HEsc $intervenant)</div></div>
 <div><div class="line">Responsable site &mdash; nom et signature</div></div>
</div>

<div class="foot">Rapport genere le $now par Outils Reseau v$AppVersion &bull; document a valeur de compte-rendu d'intervention.</div>
</body></html>
"@)
    return $sb.ToString()
}

function Show-ReportDialog {
    $dlg = [System.Windows.Forms.Form]::new()
    $dlg.Text = "Rapport de session"
    $dlg.Size = [Drawing.Size]::new(520, 500)
    $dlg.StartPosition = 'CenterScreen'
    $dlg.FormBorderStyle = 'FixedDialog'; $dlg.MaximizeBox = $false; $dlg.MinimizeBox = $false
    $dlg.BackColor = $BGray; $dlg.Font = $FN
    if ($IcoPath -and (Test-Path $IcoPath)) { try { $dlg.Icon = [System.Drawing.Icon]::new($IcoPath) } catch {} }

    $dlg.Controls.Add((New-Label "Compte-rendu de l'intervention" 20 18 460 24 $true))
    $dlg.Controls.Add((New-Label "Renseignez les elements ci-dessous, puis enregistrez le rapport." 20 44 460 20))

    $dlg.Controls.Add((New-Label "Intervenant" 20 82 460 20))
    $txInt = New-Txt 20 104 470 $env:USERNAME
    $dlg.Controls.Add($txInt)

    $dlg.Controls.Add((New-Label "Objet de l'intervention" 20 140 460 20))
    $txObj = New-Txt 20 162 470 ""
    $dlg.Controls.Add($txObj)

    $dlg.Controls.Add((New-Label "Observations" 20 198 460 20))
    $txObs = [System.Windows.Forms.TextBox]::new()
    $txObs.Location = [Drawing.Point]::new(20,220); $txObs.Size = [Drawing.Size]::new(470,150)
    $txObs.Multiline = $true; $txObs.ScrollBars = 'Vertical'; $txObs.Font = $FN
    $txObs.BackColor = $TxtBg; $txObs.ForeColor = $TxtFg; $txObs.BorderStyle = 'FixedSingle'
    $dlg.Controls.Add($txObs)

    $bSave = New-Btn "Enregistrer le rapport" 20 388 300 34 $Green
    $bCancel = New-Btn "Annuler" 340 388 150 34 ([Drawing.Color]::FromArgb(70,75,85))
    $dlg.Controls.Add($bSave); $dlg.Controls.Add($bCancel)

    $bCancel.Add_Click({ $dlg.Close() })
    $bSave.Add_Click({
        $html = Build-Report $txInt.Text $txObj.Text $txObs.Text
        $sfd = New-Object System.Windows.Forms.SaveFileDialog
        $sfd.Filter = "Page HTML (*.html)|*.html"
        $sfd.FileName = "Rapport-$env:COMPUTERNAME-$(Get-Date -Format 'yyyyMMdd-HHmm').html"
        try { $sfd.InitialDirectory = [Environment]::GetFolderPath('MyDocuments') } catch {}
        if ($sfd.ShowDialog() -eq 'OK') {
            try {
                [IO.File]::WriteAllText($sfd.FileName, $html, [Text.UTF8Encoding]::new($false))
                Write-Log "RAPPORT genere : $($sfd.FileName)"
                $open = [System.Windows.Forms.MessageBox]::Show(
                    "Rapport enregistre :`n$($sfd.FileName)`n`nL'ouvrir maintenant ?",
                    "Rapport enregistre", 'YesNo', 'Information')
                if ($open -eq 'Yes') { Start-Process $sfd.FileName }
                $dlg.Close()
            } catch {
                [System.Windows.Forms.MessageBox]::Show("Echec de l'enregistrement :`n$($_.Exception.Message)","Erreur",'OK','Error') | Out-Null
            }
        }
    })
    $dlg.ShowDialog() | Out-Null
}


Write-Log "SESSION OUVERTE v$AppVersion"
$F.ShowDialog() | Out-Null
Write-Log "SESSION FERMEE"

# ── Proposition de rapport de session apres fermeture de la fenetre ──
try {
    $rep = [System.Windows.Forms.MessageBox]::Show(
        "Generer un rapport de cette session avant de quitter ?",
        "Rapport de session", 'YesNo', 'Question')
    if ($rep -eq 'Yes') { Show-ReportDialog }
} catch {}
