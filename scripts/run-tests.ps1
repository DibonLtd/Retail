# Test runner for the Tano Retail addons on a local Odoo 18 CE instance.
#
# Note: --log-handler odoo.tests.common:ERROR suppresses a broken RUNBOT-level
# log call in Odoo 18.0 (odoo/fields.py __str__ touches Field.name before it is
# set). Without it, a multi-module test run emits over a million lines of
# "--- Logging error ---" stacks. It is cosmetic, but it drowns real output.
param(
  [string]$Modules = "retail_base",
  [string]$Db = "tano_test",
  [string]$Tags = "",
  [switch]$Install
)
$base = "C:\Users\orega\odoo18-dev"
$py   = "$base\venv\Scripts\python.exe"
$bin  = "$base\odoo18\odoo-bin"
$conf = "C:\Users\orega\Documents\GitHub\Retail\config\odoo.conf"
$log  = "$base\test-$Db.log"
if (-not $Tags) { $Tags = "/" + ($Modules -split "," | Select-Object -First 1) }
$flag = if ($Install) { "-i" } else { "-u" }
& $py $bin -c $conf -d $Db $flag $Modules --test-enable --stop-after-init --test-tags $Tags --log-handler "odoo.tests.common:ERROR" *> $log
"EXITCODE=$LASTEXITCODE"
"LOG=$log"
Select-String -Path $log -Pattern "FAIL:|ERROR:|CRITICAL|odoo.tests.result|odoo.tests.stats" | Select-Object -Last 30 | ForEach-Object { $_.Line }
