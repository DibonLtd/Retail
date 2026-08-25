param([string]$Modules = "retail_base", [string]$Db = "tano_test", [string]$Tags = "")
$py = "C:\Users\orega\odoo18-dev\venv\Scripts\python.exe"
$bin = "C:\Users\orega\odoo18-dev\odoo18\odoo-bin"
$conf = "C:\Users\orega\Documents\GitHub\Retail\config\odoo.conf"
if (-not $Tags) { $Tags = "/" + ($Modules -split "," | Select-Object -First 1) }
& $py $bin -c $conf -d $Db -u $Modules --test-enable --stop-after-init --test-tags $Tags 2>&1 |
  Select-String -Pattern "FAIL:|ERROR:|AssertionError|ValueError|odoo.tests.stats|odoo.tests.result|CRITICAL|Modules loaded" |
  Select-Object -Last 40
"EXITCODE=$LASTEXITCODE"
