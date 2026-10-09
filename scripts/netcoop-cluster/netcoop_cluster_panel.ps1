param([string]$Runtime = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
. (Join-Path $PSScriptRoot 'netcoop_cluster_controls.ps1')
$Runtime = [IO.Path]::GetFullPath($Runtime)
$planPath = Join-Path $Runtime 'appdata\server\netcoop_cluster.ltx'
if (-not (Test-Path -LiteralPath $planPath)) { throw "Cluster plan missing: $planPath" }
$wakeDir = Join-Path $Runtime 'appdata\server\netcoop_cluster'
$mapNames = @{
    k00_marsh='Болота'; l01_escape='Кордон'; l02_garbage='Свалка'; l03_agroprom='Агропром';
    l03u_agr_underground='Подземелья Агропрома'; l04_darkvalley='Тёмная долина'; l04u_labx18='Лаборатория X18';
    l05_bar='Бар'; l06_rostok='Дикая территория'; l07_military='Армейские склады'; l08_yantar='Янтарь';
    l08u_brainlab='Лаборатория X16'; l09_deadcity='Мёртвый город'; l10_limansk='Лиманск';
    l10_radar='Радар'; l10_red_forest='Рыжий лес'; l10u_bunker='Лаборатория X19'; l11_hospital='Госпиталь';
    l11_pripyat='Припять'; l12_stancia='ЧАЭС'; l12_stancia_2='ЧАЭС — север'; l12u_control_monolith='Управление Монолитом';
    l12u_sarcofag='Саркофаг'; l13_generators='Генераторы'; l13u_warlab='Лаборатория X7'; labx8='Лаборатория X8';
    jupiter='Юпитер'; jupiter_underground='Путепровод'; pripyat='Восточная Припять';
    zaton='Затон'; k01_darkscape='Тёмная лощина'; k02_trucks_cemetery='Кладбище техники'; y04_pole='Луга'
}
$locations = [ordered]@{}; $section = ''
foreach ($line in Get-Content -LiteralPath $planPath -Encoding Default) {
    $text = ($line -split ';',2)[0].Trim()
    if ($text -match '^\[(.+)\]$') { $section = $Matches[1]; continue }
    if ($section -eq 'locations' -and $text -match '^(\w+)\s*=\s*(\S+)$') { $locations[$Matches[1]] = $Matches[2] }
}
if (-not $locations.Count) { throw 'Cluster plan has no locations' }
$form = [Windows.Forms.Form]::new()
$form.Text = 'Lost Zone — управление локациями'
$form.Size = [Drawing.Size]::new(1080,740); $form.MinimumSize = [Drawing.Size]::new(850,520)
$form.StartPosition = 'CenterScreen'; $form.BackColor = [Drawing.Color]::FromArgb(28,32,38)
$form.ForeColor = [Drawing.Color]::Gainsboro; $form.Font = [Drawing.Font]::new('Segoe UI',11)
$layout = [Windows.Forms.TableLayoutPanel]::new(); $layout.Dock = 'Fill'; $layout.RowCount = 3; $layout.ColumnCount = 1
$layout.Padding = [Windows.Forms.Padding]::new(16)
$layout.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::Absolute,48))
$layout.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::Percent,100))
$layout.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::Absolute,90))
$header = [Windows.Forms.Label]::new(); $header.Dock = 'Fill'; $header.Text = "Все локации кластера · $($locations.Count) карт"
$grid = [Windows.Forms.DataGridView]::new(); $grid.Dock = 'Fill'; $grid.ReadOnly = $true
$grid.AllowUserToAddRows = $false; $grid.AllowUserToDeleteRows = $false; $grid.MultiSelect = $false
$grid.SelectionMode = 'FullRowSelect'; $grid.RowHeadersVisible = $false
$grid.AutoSizeColumnsMode = 'Fill'; $grid.BackgroundColor = $form.BackColor
$grid.DefaultCellStyle.BackColor = [Drawing.Color]::FromArgb(36,42,50)
$grid.DefaultCellStyle.ForeColor = $form.ForeColor; $grid.DefaultCellStyle.SelectionBackColor = [Drawing.Color]::FromArgb(57,79,102)
$grid.EnableHeadersVisualStyles = $false; $grid.ColumnHeadersDefaultCellStyle.BackColor = [Drawing.Color]::FromArgb(45,52,62)
$grid.ColumnHeadersDefaultCellStyle.ForeColor = $form.ForeColor; $grid.RowTemplate.Height = 30
foreach ($column in @('Локация','Адрес сервера','Состояние','Игроки','Режим')) { [void]$grid.Columns.Add($column,$column) }
$grid.Columns[0].FillWeight=160; $grid.Columns[3].FillWeight=50
$rowByMap = @{}
foreach ($map in $locations.Keys) {
    $name = if ($mapNames[$map]) { $mapNames[$map] } else { $map }
    $index = $grid.Rows.Add($name,$locations[$map],'Нет данных','—','—')
    $grid.Rows[$index].Tag = $map; $rowByMap[$map] = $grid.Rows[$index]
}
$footer = [Windows.Forms.FlowLayoutPanel]::new(); $footer.Dock = 'Fill'; $footer.WrapContents = $true
$buttons = @{}
foreach ($entry in @(@('start','Запустить'),@('stop','Остановить'),@('restart','Перезапустить'),@('auto','Автоматически'))) {
    $button = [Windows.Forms.Button]::new(); $button.Text=$entry[1]; $button.Tag=$entry[0]
    $button.AutoSize=$true; $button.Height=36; $button.Padding=[Windows.Forms.Padding]::new(8,0,8,0)
    $button.FlatStyle='Flat'; $buttons[$entry[0]]=$button; [void]$footer.Controls.Add($button)
    $button.Add_Click({
        try {
            if (-not $grid.SelectedRows.Count) { return }
            $map = [string]$grid.SelectedRows[0].Tag
            if (-not $script:localMaps.ContainsKey($map)) { return }
            Send-ClusterHostCommand $wakeDir $map ([string]$this.Tag)
            $hint.Text = 'Команда отправлена. Остановка и перезапуск сначала сохраняют мир и персонажей.'
        } catch { $hint.Text = $_.Exception.Message }
    })
}
$manage = [Windows.Forms.Button]::new(); $manage.Text='Подключить управление'; $manage.AutoSize=$true; $manage.Height=36; $manage.FlatStyle='Flat'
$manage.Add_Click({
    try {
        $watchdog = Join-Path $PSScriptRoot 'netcoop_cluster_watchdog.ps1'
        Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$watchdog`"",'-Runtime',"`"$Runtime`"",'-NoAutoStart') -WindowStyle Hidden
        $hint.Text='Подключение управления. Локации включаются выбранными кнопками.'
    } catch { $hint.Text=$_.Exception.Message }
})
[void]$footer.Controls.Add($manage)
$hint = [Windows.Forms.Label]::new(); $hint.Width=970; $hint.Height=40
$hint.Text='Выберите локацию. «Автоматически» возвращает запуск по переходам и гибернацию пустой карты.'
[void]$footer.Controls.Add($hint)
$layout.Controls.Add($header,0,0); $layout.Controls.Add($grid,0,1); $layout.Controls.Add($footer,0,2); $form.Controls.Add($layout)
$script:localMaps = @{}
$states=@{running='Работает';loading='Загружается';stopped='Выключена';saving='Сохраняется';memory='Ожидает память';loading_timeout='Загрузка затянулась'}
$modes=@{on='Включена хостером';off='Выключена хостером';auto='Автоматически'}
$refresh = {
    try {
        $viewPath = Join-Path $wakeDir 'host_view.json'
        $view = if (Test-Path -LiteralPath $viewPath) { [IO.File]::ReadAllText($viewPath) | ConvertFrom-Json } else { $null }
        $fresh = $view -and ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()-[long]$view.updated -lt 30)
        $script:localMaps = @{}
        if ($fresh) {
            foreach ($item in $view.maps) {
                $script:localMaps[$item.map]=$true
                $row=$rowByMap[$item.map]; if (-not $row) { continue }
                $row.Cells[2].Value = if ($states[$item.state]) { $states[$item.state] } else { $item.state }
                $row.Cells[3].Value = if ($item.processId) { [string]$item.players } else { '0' }
                $row.Cells[4].Value = $modes[$item.mode]
            }
            foreach ($map in $locations.Keys) { if (-not $script:localMaps.ContainsKey($map)) { $rowByMap[$map].Cells[2].Value='Другой хост' } }
        } else { foreach ($row in $rowByMap.Values) { $row.Cells[2].Value='Управление не подключено' } }
        $enabled = $fresh -and $grid.SelectedRows.Count -and $script:localMaps.ContainsKey([string]$grid.SelectedRows[0].Tag)
        foreach ($button in $buttons.Values) { $button.Enabled = $enabled }
        $manage.Enabled = -not $fresh
    } catch { $hint.Text=$_.Exception.Message }
}
$timer=[Windows.Forms.Timer]::new(); $timer.Interval=1500; $timer.Add_Tick($refresh); $timer.Start()
$grid.Add_SelectionChanged($refresh)
try { & $refresh; [void]$form.ShowDialog() } finally { $timer.Stop(); $timer.Dispose(); $form.Dispose() }
