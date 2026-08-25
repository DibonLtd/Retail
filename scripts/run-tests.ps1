param(
  [string]$Modules = "retail_base",
  [string]$Db = "tano_test",
  [string]$Tags = "",
  [switch]$Install
)
$py = "C:\Users\orega\odoo18-dev\venv\Scripts\python.exe"
$bin = "C:\Users\orega\odoo18-dev\odoo18\odoo-bin"
$conf = "C:\Users\orega\Documents\GitHub\Retail\config\odoo.conf"
if (-not $Tags) { $Tags = "/" + ($Modules -split "," | Select-Object -First 1) }
$flag = if ($Install) { "-i" } else { "-u" }
& $py $bin -c $conf -d $Db $flag $Modules --test-enable --stop-after-init --test-tags $Tags 2>&1 |
  Select-String -Pattern "FAIL:|ERROR:|AssertionError|ValueError|KeyError|AttributeError:|odoo.tests.stats|odoo.tests.result|CRITICAL" |
  Select-Object -Last 40
"EXITCODE=$LASTEXITCODE"
