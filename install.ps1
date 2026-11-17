# Installe ou met a jour QCM Live sous Windows (INS-01, INS-02), sans droits d'administrateur :
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/GolemCode/qcm-live/main/install.ps1 | iex"
#
# Memes etapes que install.sh : donnees dans %LOCALAPPDATA%\qcm-live (ou QCM_DATA_DIR), uv
# installe s'il manque, code remplace a chaque mise a jour, donnees gardees. La suite
# (reglages, base, compte, demonstration, commande qcm-live.cmd) est faite par
# `python -m config.install`, commun a Linux et Windows. Ce script ajoute le raccourci du menu
# Demarrer et met %USERPROFILE%\.local\bin dans le PATH de l'utilisateur.
#
# Texte en ASCII seulement : Windows PowerShell 5.1 lit un fichier sans BOM comme de l'ANSI.

& {
    $ErrorActionPreference = "Stop"
    $ArchiveUrl = "https://github.com/GolemCode/qcm-live/archive/refs/heads/main.zip"

    $Data = if ($env:QCM_DATA_DIR) { $env:QCM_DATA_DIR } else { Join-Path $env:LOCALAPPDATA "qcm-live" }
    if (Test-Path (Join-Path $Data "app")) {
        Write-Host "QCM Live : nouvelle version dans $Data"
    } else {
        Write-Host "QCM Live : installation dans $Data"
    }
    New-Item -ItemType Directory -Force -Path $Data | Out-Null

    $Bin = Join-Path $env:USERPROFILE ".local\bin"
    $Found = Get-Command uv -ErrorAction SilentlyContinue
    if ($Found) {
        $Uv = $Found.Source
    } else {
        Write-Host "Installation de uv (gestionnaire Python, dans $Bin)..."
        $env:UV_NO_MODIFY_PATH = "1"
        powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
        $Uv = Join-Path $Bin "uv.exe"
        if (-not (Test-Path $Uv)) { throw "uv introuvable apres son installation." }
    }

    $Work = Join-Path ([IO.Path]::GetTempPath()) ("qcm-live-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $Work | Out-Null
    try {
        $Zip = Join-Path $Work "app.zip"
        if ($env:QCM_LIVE_ARCHIVE) {
            Copy-Item $env:QCM_LIVE_ARCHIVE $Zip
        } else {
            Write-Host "Telechargement de la derniere version..."
            Invoke-WebRequest -UseBasicParsing -Uri $ArchiveUrl -OutFile $Zip
        }
        $Unpacked = Join-Path $Work "x"
        Expand-Archive -Path $Zip -DestinationPath $Unpacked
        $Root = Get-ChildItem $Unpacked -Directory | Select-Object -First 1

        # Nouvelle version a cote de l'ancienne, environnement Python mis a jour, puis echange.
        # L'environnement est mis a jour sur place : relancer l'installation le remet d'aplomb.
        $App = Join-Path $Data "app"
        $New = Join-Path $Data "app.new"
        if (Test-Path $New) { Remove-Item -Recurse -Force $New }
        Move-Item $Root.FullName $New
        $env:UV_PROJECT_ENVIRONMENT = Join-Path $Data "venv"
        Write-Host "Preparation de l'environnement Python..."
        & $Uv sync --quiet --locked --no-dev --project $New
        if ($LASTEXITCODE -ne 0) { throw "Echec de l'installation des dependances : relancez l'installation." }
        if (Test-Path $App) { Remove-Item -Recurse -Force $App }
        Move-Item $New $App

        $env:QCM_DATA_DIR = $Data
        $env:PYTHONPATH = $App
        & (Join-Path $Data "venv\Scripts\python.exe") -m config.install
        if ($LASTEXITCODE -ne 0) { throw "Echec de la fin de l'installation." }
    } finally {
        Remove-Item -Recurse -Force $Work -ErrorAction SilentlyContinue
        Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
        Remove-Item Env:\UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
    }

    # Raccourci du menu Demarrer : il ouvre une console, qui donne l'adresse des telephones.
    $Shell = New-Object -ComObject WScript.Shell
    $Link = $Shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Programs")) "QCM Live.lnk"))
    $Link.TargetPath = Join-Path $Bin "qcm-live.cmd"
    $Link.WorkingDirectory = $env:USERPROFILE
    $Link.Description = "QCM Live : lancer le mode classe"
    $Link.Save()

    # La commande qcm-live dans les nouveaux terminaux.
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not (($UserPath -split ";") -contains $Bin)) {
        $NewPath = if ($UserPath) { "$UserPath;$Bin" } else { $Bin }
        [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
        Write-Host "$Bin ajoute au PATH : la commande qcm-live marchera dans un nouveau terminal."
    }
}
