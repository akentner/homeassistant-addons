import sys, threading, http.server, functools, json
from playwright.sync_api import sync_playwright
root = sys.argv[1]
h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
h.log_message = lambda *a, **k: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_port}/index.html"
out = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/brave", args=["--no-sandbox"])
    for kiosk in (False, True):
        for mode in ("topbar", "tabs"):
            for lang in ("en", "de"):
                for w in (320, 375, 414, 600):
                    ctx = b.new_context(viewport={"width": w, "height": 700})
                    pg = ctx.new_page()
                    pg.route("**/api/health", lambda r: r.fulfill(json={"status": "ok", "addon_version": "0.1.0-5", "lib_version": "0.4.0", "addon_slug": "local_admin_ui"}))
                    pg.add_init_script(f"localStorage.setItem('admin-ui:demo-nav','{mode}');localStorage.setItem('admin-ui:lang','{lang}');")
                    pg.goto(url.replace("index.html","host.html") if kiosk else url); fr = pg.frame_locator("#f") if kiosk else pg; fr.locator("header.topbar").wait_for(); pg.wait_for_timeout(400)
                    if kiosk:
                        # simulate the host menu button by posting a properties message is not possible without a parent: force the DOM check via class only
                        pass
                    tgt = pg.frames[1] if kiosk else pg
                    r = tgt.evaluate("""()=>({sw:document.documentElement.scrollWidth,iw:innerWidth,
                      bsw:document.body.scrollWidth,
                      bar:(()=>{const b=document.querySelector('.topbar');return b.scrollWidth<=b.clientWidth+1})(),
                      burger:!!document.querySelector('.nav-burger'), h:document.querySelector('.shell-head').getBoundingClientRect().height,menus:document.querySelectorAll('.menu-btn').length,info:document.querySelectorAll('.info-btn').length,infoMenu:!!document.querySelector('.info-link'),hscroll:document.documentElement.scrollWidth>innerWidth})""")
                    r.update(kiosk=kiosk, mode=mode, lang=lang, w=w, ok=r["sw"] <= r["iw"] and r["bar"])
                    out.append(r); ctx.close()
                if not kiosk: pass
            pass
    b.close()
bad = [r for r in out if not r["ok"]]
for r in out: print({k:r[k] for k in ("kiosk","mode","lang","w","sw","iw","bar","burger","h","menus","info","ok")})
print("FAILURES", len(bad))
