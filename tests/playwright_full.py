import asyncio, json, time, sys
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8131/pelleto"
RES = []

def ok(l,d=""): print(f"  \033[32m\u2705 {l}\033[0m {d}"); RES.append((l,True,d))
def fail(l,d=""): print(f"  \033[31m\u274c {l}\033[0m {d}"); RES.append((l,False,d))
def check(l,c,d=""): ok(l,d) if c else fail(l,d)

async def t1_landing(page, js_errors):
    print("\n\033[1m-- 1. ЛЕНДИНГ\033[0m")
    t0=time.time()
    r=await page.goto(BASE+"/",wait_until="networkidle",timeout=20000)
    ms=int((time.time()-t0)*1000)
    check("HTTP 200",r.status==200,f"{r.status}")
    check("Загрузка<3s",ms<3000,f"{ms}ms")
    check("Title",bool(await page.title()),repr(await page.title()))
    check(".hero",await page.locator(".hero").count()>0)
    check("Логотип",bool((await page.locator(".nav__logo").inner_text()).strip()))
    check("Телефон",bool((await page.locator(".nav__phone a").inner_text()).strip()))
    pc=await page.locator(".product-card").count()
    check("Карточки товаров",pc>0,f"{pc} шт")
    bc=await page.locator(".btn--sm[href*='order']").count()
    check("Кнопка Заказать→/order",bc>0,f"{bc} кнопок")
    imgs=page.locator(".product-card__img")
    ic=await imgs.count(); br=0
    for i in range(ic):
        s=await imgs.nth(i).get_attribute("src") or ""
        if not s or "None" in s: br+=1
    check("Фото товаров",ic>0 and br==0,f"img={ic} broken={br}")
    check(".delivery",await page.locator(".delivery").count()>0)
    check(".contacts",await page.locator(".contacts").count()>0)
    check(".footer__version",await page.locator(".footer__version").count()>0)
    check("JS ошибок нет",len(js_errors)==0,str(js_errors[:2]) if js_errors else "")
    js_errors.clear()

async def t2_agent(page, js_errors):
    print("\n\033[1m-- 2. ВИДЖЕТ АГЕНТА\033[0m")
    await page.goto(BASE+"/",wait_until="networkidle")
    tg=page.locator(".agent-toggle")
    check(".agent-toggle",await tg.count()>0)
    if await tg.count()>0:
        await tg.click(); await page.wait_for_timeout(600)
        chat=page.locator(".agent-chat")
        vis=await chat.is_visible() if await chat.count()>0 else False
        check("Чат открылся",vis)
        inp=page.locator(".agent-chat__input input, .agent-chat__input textarea")
        check("Поле ввода",await inp.count()>0)
        if await inp.count()>0:
            await inp.first.fill("Сколько стоит тонна пеллет?")
            send=page.locator(".agent-chat__input button")
            if await send.count()>0:
                t0=time.time()
                await send.first.click()
                bot=page.locator(".agent-msg--bot").nth(1)
                try:
                    await bot.wait_for(state="visible",timeout=20000)
                    lat=int((time.time()-t0)*1000)
                    txt=(await bot.inner_text()).strip()
                    check("Ответ получен",bool(txt),repr(txt[:80]))
                    check("Латентность≤8s",lat<=8000,f"{lat}ms")
                    fb="недоступен" in txt.lower() or "unavailable" in txt.lower()
                    check("Не fallback",not fb,txt[:60] if fb else "")
                except Exception as e:
                    fail("Ответ агента",f"timeout: {e}")
    check("JS ошибок нет",len(js_errors)==0,str(js_errors[:2]) if js_errors else "")
    js_errors.clear()

async def t3_order(page, js_errors):
    print("\n\033[1m-- 3. ФОРМА ЗАКАЗА\033[0m")
    r=await page.goto(BASE+"/order",wait_until="networkidle")
    check("HTTP 200",r.status==200,f"{r.status}")
    check("#f-name",await page.locator("#f-name").count()>0)
    check("#f-phone",await page.locator("#f-phone").count()>0)
    check("#order-submit",await page.locator("#order-submit").count()>0)
    await page.locator("#order-submit").click()
    await page.wait_for_timeout(400)
    check("Валидация пустой формы",await page.locator("#form-error").is_visible())
    await page.locator("#f-name").fill("Playwright Test")
    await page.locator("#f-phone").fill("+7 999 000-00-00")
    await page.locator("#order-submit").click()
    await page.wait_for_timeout(3000)
    check("Успешная отправка",await page.locator("#form-ok").is_visible())
    check("JS ошибок нет",len(js_errors)==0,str(js_errors[:2]) if js_errors else "")
    js_errors.clear()

async def t4_admin(page, js_errors):
    print("\n\033[1m-- 4. АДМИНКА\033[0m")
    r=await page.goto(BASE+"/admin/login",wait_until="networkidle")
    check("/admin/login 200",r.status==200,f"{r.status}")
    await page.goto(BASE+"/admin",wait_until="networkidle")
    check("/admin без auth→login","login" in page.url,page.url)
    await page.goto(BASE+"/admin/login",wait_until="networkidle")
    ki=page.locator("input[type='password'],input[name='master_key']").first
    lb=page.locator("button[type='submit']").first
    check("Поле ключа",await ki.count()>0)
    check("Кнопка входа",await lb.count()>0)
    if await ki.count()>0:
        await ki.fill("wrong_pw_playwright"); await lb.click()
        await page.wait_for_timeout(1000)
        err=page.locator("[class*='error'],[class*='alert'],#login-error")
        check("Неверный ключ→ошибка",await err.count()>0)
    check("JS ошибок нет",len(js_errors)==0,str(js_errors[:2]) if js_errors else "")
    js_errors.clear()

async def t5_api(page):
    print("\n\033[1m-- 5. API\033[0m")
    await page.goto(BASE+"/")
    ag=await page.evaluate("""async()=>{
        try{const r=await fetch('/pelleto/api/agent/chat',{method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({question:'\u0422\u0438\u043f\u044b \u043f\u0435\u043b\u043b\u0435\u0442',session_id:'pw-api',history:[]})});
          const d=await r.json();
          return {s:r.status,ans:(d.answer||'').slice(0,100),phase:d.phase};
        }catch(e){return {error:String(e)};}
    }""")
    check("POST /api/agent/chat",ag.get("s")==200 and bool(ag.get("ans")),str(ag))
    o=await page.evaluate("""async()=>{
        try{const r=await fetch('/pelleto/api/order',{method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({name:'API Test',phone:'+7000'})});
          return {s:r.status};
        }catch(e){return {error:String(e)};}
    }""")
    check("POST /api/order",o.get("s")==200,str(o))

async def t6_mobile(browser):
    print("\n\033[1m-- 6. \u041c\u041e\u0411\u0418\u041b\u042c 375px\033[0m")
    m=await browser.new_context(viewport={"width":375,"height":812})
    p=await m.new_page()
    await p.goto(BASE+"/",wait_until="networkidle")
    sw=await p.evaluate("()=>document.documentElement.scrollWidth")
    check("Нет гориз. скролла",sw<=390,f"{sw}px")
    check("Заказать на мобиле",await p.locator(".btn--sm[href*='order']").count()>0)
    check(".agent-toggle на мобиле",await p.locator(".agent-toggle").count()>0)
    check(".hero__title видна",await p.locator(".hero__title").is_visible())
    await m.close()

async def run():
    async with async_playwright() as pw:
        b=await pw.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
        ctx=await b.new_context(viewport={"width":1280,"height":900})
        page=await ctx.new_page()
        js_errors=[]
        page.on("pageerror",lambda e:js_errors.append(str(e)))
        await t1_landing(page,js_errors)
        await t2_agent(page,js_errors)
        await t3_order(page,js_errors)
        await t4_admin(page,js_errors)
        await t5_api(page)
        await t6_mobile(b)
        await b.close()
        passed=sum(1 for _,s,_ in RES if s)
        failed=sum(1 for _,s,_ in RES if not s)
        print(f"\n{'='*52}")
        print(f"  \033[1m\u0418\u0422\u041e\u0413: \033[32m{passed} \u043f\u0440\u043e\u0448\u043b\u043e\033[0m / \033[31m{failed} \u0443\u043f\u0430\u043b\u043e\033[0m / {len(RES)} \u0432\u0441\u0435\u0433\u043e\033[0m")
        if failed:
            print("\n  \u041f\u0440\u043e\u0431\u043b\u0435\u043c\u044b:")
            for l,s,d in RES:
                if not s: print(f"    \u274c {l}: {d}")
        print(f"{'='*52}")
        return failed

if __name__=="__main__":
    sys.exit(1 if asyncio.run(run()) else 0)
