import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python, wait_for
from tw_common import login, wait_home, new_page
from playwright.sync_api import sync_playwright
guard_driver_python()
URL = sys.argv[1]
run = Run("probe", "/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/upgrades_b/run/probe")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    ctx, page = new_page(b, run, "x", dialogs=[])
    login(page, URL, "bob", "pw-bob"); wait_home(page)
    page.locator("input[placeholder='Search users']").fill("ali")
    page.wait_for_timeout(2000)
    print(page.evaluate("""() => { const i=document.querySelector('input[placeholder="Search users"]'); let e=i; for (let k=0;k<3;k++) e=e.parentElement; return e.outerHTML.slice(0,3000); }"""))
    b.close()
