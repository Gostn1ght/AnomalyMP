param([string]$Runtime = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
. (Join-Path $PSScriptRoot 'netcoop_cluster_controls.ps1')
$Runtime = [IO.Path]::GetFullPath($Runtime)
$planPath = Join-Path $Runtime 'appdata\server\netcoop_cluster.ltx'
if (-not (Test-Path -LiteralPath $planPath)) { throw "Cluster plan missing: $planPath" }
$wakeDir = Join-Path $Runtime 'appdata\server\netcoop_cluster'
$logDir = Join-Path $Runtime 'appdata\server\logs'
# The watchdog publishes this machine's maps as host_view_<computer>.json
# (several hosts may share one plan); the panel used to read host_view.json,
# never saw a fresh view and kept every map button disabled.
$viewName = "host_view_$($env:COMPUTERNAME.ToLowerInvariant()).json"
$watchdogErr = Join-Path $wakeDir 'watchdog_error.log'
$watchdogOut = Join-Path $wakeDir 'watchdog.log'
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

# Palette: near-black surfaces, one warm accent, status colours only where they mean something.
function Rgb([int]$r,[int]$g,[int]$b) { [Drawing.Color]::FromArgb($r,$g,$b) }
$C = @{
    bg=(Rgb 10 10 11); surface=(Rgb 16 16 18); raised=(Rgb 24 24 27); hover=(Rgb 32 32 36); line=(Rgb 38 38 42)
    text=(Rgb 232 230 225); muted=(Rgb 140 140 145); dim=(Rgb 90 90 95); accent=(Rgb 217 164 65)
    green=(Rgb 76 195 138); amber=(Rgb 224 168 74); red=(Rgb 229 83 75)
}
$fontUi = [Drawing.Font]::new('Segoe UI', 10)
$fontSmall = [Drawing.Font]::new('Segoe UI', 9)
$fontHead = [Drawing.Font]::new('Segoe UI Semibold', 9)
$fontTitle = [Drawing.Font]::new('Bahnschrift SemiBold', 17)

# Dark window frame on Windows 10 1809+/11 (ignored where unsupported).
try {
    Add-Type -Namespace LostZone -Name Dwm -MemberDefinition '[System.Runtime.InteropServices.DllImport("dwmapi.dll")] public static extern int DwmSetWindowAttribute(System.IntPtr hwnd, int attribute, ref int value, int size);'
} catch {}

$form = [Windows.Forms.Form]::new()
$form.Text = 'Lost Zone — локации сервера'
$form.Size = [Drawing.Size]::new(1100,720); $form.MinimumSize = [Drawing.Size]::new(860,520)
$form.StartPosition = 'CenterScreen'; $form.BackColor = $C.bg; $form.ForeColor = $C.text; $form.Font = $fontUi
$form.Add_HandleCreated({ try { $on = 1; [void][LostZone.Dwm]::DwmSetWindowAttribute($form.Handle, 20, [ref]$on, 4) } catch {} })

$layout = [Windows.Forms.TableLayoutPanel]::new(); $layout.Dock = 'Fill'; $layout.ColumnCount = 1; $layout.RowCount = 4
$layout.Padding = [Windows.Forms.Padding]::new(24,18,24,10); $layout.BackColor = $C.bg
foreach ($height in @(64, -1, 60, 28)) {
    if ($height -lt 0) { [void]$layout.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::Percent,100)) }
    else { [void]$layout.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::Absolute,$height)) }
}

# Header: title on the left, live summary on the right.
$header = [Windows.Forms.TableLayoutPanel]::new(); $header.Dock = 'Fill'; $header.ColumnCount = 2; $header.RowCount = 2
[void]$header.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::Percent,55))
[void]$header.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::Percent,45))
function New-Label([string]$Text, $Font, $Color, [string]$Align = 'MiddleLeft') {
    $label = [Windows.Forms.Label]::new(); $label.Dock = 'Fill'; $label.Text = $Text; $label.Font = $Font
    $label.ForeColor = $Color; $label.TextAlign = $Align; $label.AutoEllipsis = $true; return $label
}
$title = New-Label 'LOST ZONE' $fontTitle $C.text 'BottomLeft'
$subtitle = New-Label "Локации сервера · $($locations.Count) карт" $fontSmall $C.muted 'TopLeft'
$summary = New-Label '' ([Drawing.Font]::new('Segoe UI Semibold',11)) $C.text 'BottomRight'
$connection = New-Label '' $fontSmall $C.muted 'TopRight'
$header.Controls.Add($title,0,0); $header.Controls.Add($summary,1,0); $header.Controls.Add($subtitle,0,1); $header.Controls.Add($connection,1,1)

# Location list: flat rows, a coloured dot carries the state at a glance.
$grid = [Windows.Forms.DataGridView]::new(); $grid.Dock = 'Fill'; $grid.ReadOnly = $true
$grid.AllowUserToAddRows = $false; $grid.AllowUserToDeleteRows = $false; $grid.AllowUserToResizeRows = $false
$grid.MultiSelect = $false; $grid.SelectionMode = 'FullRowSelect'; $grid.RowHeadersVisible = $false
$grid.AutoSizeColumnsMode = 'Fill'; $grid.BorderStyle = 'None'; $grid.BackgroundColor = $C.bg
$grid.CellBorderStyle = 'None'; $grid.GridColor = $C.line
$grid.EnableHeadersVisualStyles = $false; $grid.ColumnHeadersBorderStyle = 'None'
$grid.ColumnHeadersHeightSizeMode = 'DisableResizing'; $grid.ColumnHeadersHeight = 34
$grid.ColumnHeadersDefaultCellStyle.BackColor = $C.bg; $grid.ColumnHeadersDefaultCellStyle.ForeColor = $C.dim
$grid.ColumnHeadersDefaultCellStyle.SelectionBackColor = $C.bg; $grid.ColumnHeadersDefaultCellStyle.Font = $fontHead
$grid.DefaultCellStyle.BackColor = $C.surface; $grid.DefaultCellStyle.ForeColor = $C.text
$grid.DefaultCellStyle.SelectionBackColor = $C.hover; $grid.DefaultCellStyle.SelectionForeColor = $C.text
$grid.RowTemplate.Height = 38
foreach ($column in @(' ','ЛОКАЦИЯ','СОСТОЯНИЕ','ИГРОКИ','РЕЖИМ','АДРЕС')) { [void]$grid.Columns.Add($column,$column) }
$grid.Columns[0].FillWeight=14; $grid.Columns[1].FillWeight=150; $grid.Columns[2].FillWeight=110
$grid.Columns[3].FillWeight=50; $grid.Columns[4].FillWeight=100; $grid.Columns[5].FillWeight=110
$grid.Columns[5].DefaultCellStyle.ForeColor = $C.muted; $grid.Columns[4].DefaultCellStyle.ForeColor = $C.muted
foreach ($column in $grid.Columns) { $column.SortMode = 'NotSortable' }
$rowByMap = @{}; $stateByMap = @{}
foreach ($map in $locations.Keys) {
    $name = if ($mapNames[$map]) { $mapNames[$map] } else { $map }
    $index = $grid.Rows.Add('',$name,'Нет данных','—','—',$locations[$map])
    $grid.Rows[$index].Tag = $map; $rowByMap[$map] = $grid.Rows[$index]; $stateByMap[$map] = 'none'
}
# Only horizontal separators, drawn under each row (cell borders leave seams between columns).
$separator = [Drawing.Pen]::new($C.line)
$grid.Add_RowPostPaint({
    param($sender, $e)
    $y = $e.RowBounds.Bottom - 1
    $e.Graphics.DrawLine($separator, $e.RowBounds.Left, $y, $e.RowBounds.Right, $y)
})
$stateColor = @{ running=$C.green; loading=$C.amber; saving=$C.amber; memory=$C.red; loading_timeout=$C.red; stopped=$C.dim; none=$C.dim; remote=$C.dim }
$grid.Add_CellPainting({
    param($sender, $e)
    if ($e.RowIndex -lt 0 -or $e.ColumnIndex -ne 0) { return }
    $e.PaintBackground($e.ClipBounds, $true)
    $state = $stateByMap[[string]$grid.Rows[$e.RowIndex].Tag]
    $color = if ($stateColor[$state]) { $stateColor[$state] } else { $C.dim }
    $size = 9; $x = $e.CellBounds.X + 12; $y = $e.CellBounds.Y + [int](($e.CellBounds.Height - $size) / 2)
    $e.Graphics.SmoothingMode = 'AntiAlias'
    $brush = [Drawing.SolidBrush]::new($color); $e.Graphics.FillEllipse($brush, $x, $y, $size, $size); $brush.Dispose()
    $e.Handled = $true
})

# Actions: one primary button, quiet secondary ones, utilities on the right.
function New-Button([string]$Text, [bool]$Primary = $false) {
    $button = [Windows.Forms.Button]::new(); $button.Text = $Text; $button.AutoSize = $true
    $button.MinimumSize = [Drawing.Size]::new(118,38); $button.Padding = [Windows.Forms.Padding]::new(12,0,12,0)
    $button.Margin = [Windows.Forms.Padding]::new(0,10,8,0); $button.FlatStyle = 'Flat'; $button.Cursor = [Windows.Forms.Cursors]::Hand
    $button.FlatAppearance.BorderSize = 1; $button.Font = [Drawing.Font]::new('Segoe UI Semibold',10)
    if ($Primary) {
        $button.BackColor = $C.accent; $button.ForeColor = (Rgb 20 14 4); $button.FlatAppearance.BorderColor = $C.accent
        $button.FlatAppearance.MouseOverBackColor = (Rgb 233 184 88); $button.FlatAppearance.MouseDownBackColor = (Rgb 196 146 52)
    } else {
        $button.BackColor = $C.raised; $button.ForeColor = $C.text; $button.FlatAppearance.BorderColor = $C.line
        $button.FlatAppearance.MouseOverBackColor = $C.hover; $button.FlatAppearance.MouseDownBackColor = $C.line
    }
    # A disabled flat button keeps its colour by default: make it visibly inactive.
    $button | Add-Member -NotePropertyName Primary -NotePropertyValue $Primary
    $button.Add_EnabledChanged({
        if (-not $this.Enabled) { $this.BackColor = $C.surface; $this.FlatAppearance.BorderColor = $C.line }
        elseif ($this.Primary) { $this.BackColor = $C.accent; $this.FlatAppearance.BorderColor = $C.accent }
        else { $this.BackColor = $C.raised; $this.FlatAppearance.BorderColor = $C.line }
    })
    return $button
}
$actions = [Windows.Forms.TableLayoutPanel]::new(); $actions.Dock = 'Fill'; $actions.ColumnCount = 2; $actions.RowCount = 1
[void]$actions.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::Percent,100))
[void]$actions.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new([Windows.Forms.SizeType]::AutoSize))
$left = [Windows.Forms.FlowLayoutPanel]::new(); $left.Dock = 'Fill'; $left.WrapContents = $false
$right = [Windows.Forms.FlowLayoutPanel]::new(); $right.AutoSize = $true; $right.WrapContents = $false; $right.Dock = 'Fill'
$buttons = [ordered]@{}
$labels = [ordered]@{ start='Запустить'; stop='Остановить'; restart='Перезапустить'; auto='Автоматически' }
$hints = @{
    start='Запуск отправлен. Карта загружается 1–2 минуты.'
    stop='Остановка отправлена: мир и персонажи сохраняются перед выключением.'
    restart='Перезапуск отправлен: сначала сохранение, потом запуск.'
    auto='Автоматический режим: карта запускается по переходам игроков и засыпает пустой.'
}
function Invoke-MapAction([string]$Action) {
    try {
        if (-not $grid.SelectedRows.Count) { return }
        $map = [string]$grid.SelectedRows[0].Tag
        if (-not $script:localMaps.ContainsKey($map)) { return }
        Send-ClusterHostCommand $wakeDir $map $Action
        $status.ForeColor = $C.muted; $status.Text = "$($grid.SelectedRows[0].Cells[1].Value): $($hints[$Action])"
    } catch { $status.ForeColor = $C.red; $status.Text = $_.Exception.Message }
}
foreach ($action in $labels.Keys) {
    $button = New-Button $labels[$action] ($action -eq 'start'); $button.Tag = $action
    $button.Add_Click({ Invoke-MapAction ([string]$this.Tag) })
    $buttons[$action] = $button; [void]$left.Controls.Add($button)
}
$logs = New-Button 'Логи'
$logs.Add_Click({
    try { [IO.Directory]::CreateDirectory($logDir) | Out-Null; Start-Process -FilePath 'explorer.exe' -ArgumentList "`"$logDir`"" }
    catch { $status.ForeColor = $C.red; $status.Text = $_.Exception.Message }
})
$manage = New-Button 'Подключить управление' $true
$manage.Add_Click({
    try {
        $watchdog = Join-Path $PSScriptRoot 'netcoop_cluster_watchdog.ps1'
        [IO.Directory]::CreateDirectory($wakeDir) | Out-Null
        if (Test-Path -LiteralPath $watchdogErr) { Remove-Item -LiteralPath $watchdogErr -Force }
        # The hidden watchdog's errors go to a file the panel shows instead of vanishing.
        Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$watchdog`"",'-Runtime',"`"$Runtime`"",'-NoAutoStart') -WindowStyle Hidden -RedirectStandardError $watchdogErr -RedirectStandardOutput $watchdogOut
        $script:watchdogStarted = Get-Date
        $status.ForeColor = $C.muted; $status.Text = 'Управление подключается. Затем выберите карту и нажмите «Запустить».'
    } catch { $status.ForeColor = $C.red; $status.Text = $_.Exception.Message }
})
[void]$right.Controls.Add($logs); [void]$right.Controls.Add($manage)
$actions.Controls.Add($left,0,0); $actions.Controls.Add($right,1,0)

# Right click on a row: the same actions.
$menu = [Windows.Forms.ContextMenuStrip]::new(); $menu.ShowImageMargin = $false
$menu.BackColor = $C.raised; $menu.ForeColor = $C.text; $menu.Font = $fontUi
foreach ($action in $labels.Keys) {
    $item = $menu.Items.Add($labels[$action]); $item.Tag = $action; $item.ForeColor = $C.text
    $item.Add_Click({ Invoke-MapAction ([string]$this.Tag) })
}
$grid.Add_CellMouseDown({
    param($sender, $e)
    if ($e.Button -eq 'Right' -and $e.RowIndex -ge 0) { $grid.ClearSelection(); $grid.Rows[$e.RowIndex].Selected = $true }
})
$menu.Add_Opening({
    param($sender, $e)
    $ok = $grid.SelectedRows.Count -and $script:localMaps.ContainsKey([string]$grid.SelectedRows[0].Tag)
    if (-not $ok) { $e.Cancel = $true }
})
$grid.ContextMenuStrip = $menu

$status = New-Label 'Выберите карту в списке. Правая кнопка мыши — те же действия.' $fontSmall $C.muted
$layout.Controls.Add($header,0,0); $layout.Controls.Add($grid,0,1); $layout.Controls.Add($actions,0,2); $layout.Controls.Add($status,0,3)
$form.Controls.Add($layout)

$script:localMaps = @{}
$states=@{running='Работает';loading='Загружается';stopped='Выключена';saving='Сохраняется';memory='Ждёт память';loading_timeout='Загрузка затянулась'}
$modes=@{on='Включена вручную';off='Выключена вручную';auto='Автоматически'}
$refresh = {
    try {
        $viewPath = Join-Path $wakeDir $viewName
        $view = if (Test-Path -LiteralPath $viewPath) { [IO.File]::ReadAllText($viewPath) | ConvertFrom-Json } else { $null }
        $fresh = $view -and ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()-[long]$view.updated -lt 30)
        $script:localMaps = @{}
        $running = 0; $players = 0
        if ($fresh) {
            foreach ($item in $view.maps) {
                $script:localMaps[$item.map]=$true
                $row=$rowByMap[$item.map]; if (-not $row) { continue }
                $stateByMap[$item.map] = [string]$item.state
                $row.Cells[2].Value = if ($states[$item.state]) { $states[$item.state] } else { $item.state }
                $row.Cells[2].Style.ForeColor = if ($stateColor[[string]$item.state]) { $stateColor[[string]$item.state] } else { $C.text }
                $row.Cells[2].Style.SelectionForeColor = $row.Cells[2].Style.ForeColor
                $count = if ($item.processId) { [int]$item.players } else { 0 }
                $row.Cells[3].Value = [string]$count; $players += $count
                $row.Cells[4].Value = $modes[$item.mode]
                if ($item.state -eq 'running') { $running++ }
            }
            foreach ($map in $locations.Keys) {
                if (-not $script:localMaps.ContainsKey($map)) {
                    $stateByMap[$map]='remote'; $rowByMap[$map].Cells[2].Value='Другой хост'; $rowByMap[$map].Cells[2].Style.ForeColor=$C.dim; $rowByMap[$map].Cells[2].Style.SelectionForeColor=$C.dim
                }
            }
            $connection.Text = '● управление подключено'; $connection.ForeColor = $C.green
            if ($script:watchdogStarted) { $script:watchdogStarted = $null; $status.ForeColor = $C.muted; $status.Text = 'Управление подключено. Выберите карту и действие.' }
        } else {
            foreach ($map in $locations.Keys) {
                $stateByMap[$map]='none'; $rowByMap[$map].Cells[2].Value='Нет связи'; $rowByMap[$map].Cells[2].Style.ForeColor=$C.dim; $rowByMap[$map].Cells[2].Style.SelectionForeColor=$C.dim
                $rowByMap[$map].Cells[3].Value='—'; $rowByMap[$map].Cells[4].Value='—'
            }
            $connection.Text = '● управление не подключено — нажмите «Подключить управление»'; $connection.ForeColor = $C.amber
            if ((Test-Path -LiteralPath $watchdogErr) -and (Get-Item -LiteralPath $watchdogErr).Length -gt 0) {
                $reason = @(Get-Content -LiteralPath $watchdogErr -Encoding Default | Where-Object { $_.Trim() -and $_ -notmatch '^\s*(\+|CategoryInfo|FullyQualifiedErrorId|At |строка|At line)' }) | Select-Object -First 1
                $status.ForeColor = $C.red; $status.Text = "Управление не запустилось: $reason"
            } elseif ($script:watchdogStarted -and ((Get-Date) - $script:watchdogStarted).TotalSeconds -gt 20) {
                $status.ForeColor = $C.amber; $status.Text = 'Управление не отвечает. Подробности: appdata\server\netcoop_cluster\watchdog.log'
            }
        }
        $summary.Text = "Работает $running из $($locations.Count)   ·   игроков $players"
        $enabled = $fresh -and $grid.SelectedRows.Count -and $script:localMaps.ContainsKey([string]$grid.SelectedRows[0].Tag)
        foreach ($button in $buttons.Values) { $button.Enabled = [bool]$enabled }
        $manage.Visible = -not $fresh
        $grid.Invalidate()
    } catch { $status.ForeColor = $C.red; $status.Text = $_.Exception.Message }
}
$timer=[Windows.Forms.Timer]::new(); $timer.Interval=1500; $timer.Add_Tick($refresh); $timer.Start()
$grid.Add_SelectionChanged($refresh)
try { & $refresh; [void]$form.ShowDialog() } finally { $timer.Stop(); $timer.Dispose(); $form.Dispose() }
