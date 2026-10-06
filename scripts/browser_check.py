"""Exercise desktop/mobile interactions and exports against a running local server.

Uses installed Edge by default; override --browser with any Chromium executable.
Requires the optional playwright package.
"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def wait_map(page):
    page.wait_for_function("document.querySelector('#map').dataset.renderState==='ready'")


def set_year(page, year):
    page.locator("#year-input").fill(str(year))
    page.locator("#year-form button").click()
    wait_map(page)
    assert int(page.locator("#year-input").input_value()) == year


def choose_theme(page, theme):
    page.locator('#theme-toggle').click()
    page.locator(f'[data-theme-option="{theme}"]').click()
    assert page.locator('#theme-menu').is_hidden()
    assert page.locator('html').get_attribute('data-theme')==theme


def choose_layer(page, layer):
    page.locator('#layer-toggle').click()
    page.locator(f'[data-layer="{layer}"]').click()
    wait_map(page)
    assert page.locator('#layer-menu').is_hidden()


def check_layout(page):
    page.wait_for_function("Math.abs(document.querySelector('#dynasty-nav svg').viewBox.baseVal.width-document.querySelector('#dynasty-nav').clientWidth)<1")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight"), "Page overflow"
    assert page.locator('#dynasty-nav').evaluate("el => el.scrollWidth <= el.clientWidth && el.scrollHeight <= el.clientHeight"), "Dynasty overflow"
    assert page.locator('#polities-panel').evaluate("el => getComputedStyle(el).scrollbarWidth === 'none'")
    viewport=page.viewport_size
    labels=[]
    nav=page.locator('#dynasty-nav').bounding_box()
    for button in page.locator('#dynasty-nav button').all():
        bounds=button.bounding_box()
        assert 0<=bounds['x'] and bounds['x']+bounds['width']<=viewport['width']+1
        assert 0<=bounds['y'] and bounds['y']+bounds['height']<=viewport['height']+1
        year=int(button.get_attribute('data-year'))
        anchor=float(button.get_attribute('data-anchor'))
        assert abs(anchor-(year+2000)/4017*nav['width'])<1, "Landmark not proportional to year"
        for other in labels:
            assert bounds['x']+bounds['width']<=other['x']+1 or other['x']+other['width']<=bounds['x']+1 or bounds['y']+bounds['height']<=other['y']+1 or other['y']+other['height']<=bounds['y']+1, "Landmark label overlap"
        labels.append(bounds)
    assert len({round(box['y'],1) for box in labels})==1, "Dynasty labels must share one row"
    player=page.locator('.top-player').bounding_box()
    assert abs(player['x']+player['width']/2-viewport['width']/2)<2, "Top player must be centered"
    assert player['y']+player['height']<=page.locator('main').bounding_box()['y']+1
    assert page.locator('.top-player #play').count()==1
    assert page.locator('.top-player #playback-speed').count()==1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    edge=Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    parser.add_argument("--browser",default=str(edge) if edge.is_file() else None)
    parser.add_argument("--url",default="http://127.0.0.1:8000")
    args=parser.parse_args()
    errors,failures,external=[],[],[]
    checks=[]
    (ROOT/'artifacts').mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=args.browser,headless=True)
        context=browser.new_context(viewport={"width":1440,"height":1000},accept_downloads=True)
        # Block external access: a passing browser run proves offline data independence.
        def route_request(route):
            if route.request.url.startswith(args.url):
                route.continue_()
            else:
                external.append(route.request.url)
                route.abort()
        context.route("**/*",route_request)
        page=context.new_page()
        page.on("pageerror",lambda error:errors.append(str(error)))
        page.on("response",lambda response:failures.append(f"{response.status} {response.url}") if response.status>=400 else None)
        page.goto(args.url,wait_until="networkidle")
        wait_map(page)
        assert page.locator("#year-input").input_value()=="-2000"
        assert page.locator("#year-slider").get_attribute("min")=="-2000"
        assert page.locator("#dynasty-nav button").count()==14
        assert page.locator(".polity-card").count()>0
        assert page.locator("#map-status").is_hidden()
        check_layout(page)
        assert page.locator('.leaflet-control-attribution').count()==0
        assert '长按加速' not in page.locator('body').inner_text()
        assert 'Natural Earth' not in page.locator('body').inner_text()
        for button in page.locator('.icon-button').all():
            assert button.get_attribute('aria-label'), "Icon control has no accessible name"
            assert button.locator('svg').count()==1
        set_year(page,618)
        page.screenshot(path=str(ROOT/"artifacts/atlas-desktop.png"),full_page=True)
        checks.append("desktop initial map and labels")
        for year in [-2000,-221,-1,1,220,618,1279,1644,1912,2017]:
            set_year(page,year)
        checks.append("BCE/CE endpoints and representative historical years")
        for button in page.locator("#dynasty-nav button").all():
            year=int(button.get_attribute("data-year"))
            button.click()
            wait_map(page)
            assert page.locator("#year-input").input_value()==str(year)
        checks.append("14 proportional dynasty landmarks in one row, horizontally displaced without overlaps or scrolling")
        set_year(page,618)
        original_width=page.locator('#map').bounding_box()['width']
        page.locator('#toggle-records').click()
        assert not page.locator('#records').is_visible()
        page.wait_for_function("document.querySelector('#map').clientWidth>1200")
        assert page.locator('#map').bounding_box()['width']>original_width+300
        assert page.locator('#year-input').input_value()=='618'
        page.reload(wait_until='networkidle')
        wait_map(page)
        assert not page.locator('#records').is_visible()
        page.locator('.polity-label[title="唐"]').click()
        assert page.locator('#records').is_visible()
        page.locator('#detail .close').click()
        page.locator('#close-records').click()
        assert not page.locator('#records').is_visible()
        page.locator('#toggle-records').click()
        assert page.locator('#records').is_visible()
        check_layout(page)
        checks.append("desktop panel collapse, map resize, saved visibility, and polity-click reopening")
        for exit_via_api in (False,True):
            page.locator('#toggle-fullscreen').click()
            page.wait_for_function('document.fullscreenElement===document.documentElement')
            assert page.locator('#toggle-fullscreen').get_attribute('data-icon')=='minimize'
            check_layout(page)
            if exit_via_api:
                page.evaluate('document.exitFullscreen()')
            else:
                page.locator('#toggle-fullscreen').click()
            page.wait_for_function("!document.fullscreenElement && document.querySelector('#toggle-fullscreen').getAttribute('aria-pressed')==='false'")
            assert page.locator('#toggle-fullscreen').get_attribute('data-icon')=='fullscreen'
        checks.append("native fullscreen entry, button exit, and browser fullscreen-change synchronization")
        page.locator('#theme-toggle').click()
        assert page.locator('#theme-menu').is_visible()
        page.keyboard.press('Escape')
        assert page.locator('#theme-menu').is_hidden()
        assert page.locator('#theme-toggle').evaluate('el => el===document.activeElement')
        page.locator('#layer-toggle').click()
        page.locator('#map').click(position={'x':10,'y':100})
        assert page.locator('#layer-menu').is_hidden()
        checks.append("named SVG controls, icon-menu focus and dismissal, and removed on-map credit/instructions")
        backgrounds=[]
        for theme in ('light','dark','paper','vivid','vermilion','neon'):
            choose_theme(page,theme)
            assert page.locator('html').get_attribute('data-theme')==theme
            backgrounds.append(page.locator('#map').evaluate('el => getComputedStyle(el).backgroundColor'))
            page.wait_for_timeout(200)  # Let toolbar color transitions settle before capturing.
            page.screenshot(path=str(ROOT/f'artifacts/atlas-{theme}.png'),full_page=True)
        assert len(set(backgrounds))==6
        choose_theme(page,'paper')
        page.locator('#playback-speed').select_option('2')
        page.reload(wait_until='networkidle')
        wait_map(page)
        assert page.locator('[data-theme-option="paper"]').get_attribute('aria-pressed')=='true'
        assert page.locator('#playback-speed').input_value()=='2'
        assert page.locator('#year-input').input_value()=='618'
        choose_theme(page,'light')
        page.locator('#playback-speed').select_option('1')
        checks.append("six synchronized map themes including vivid/vermilion/neon and saved theme/speed preferences")
        set_year(page,618)
        page.locator("#search").fill("唐")
        page.locator(".polity-card").filter(has=page.locator("h3",has_text="唐")).first.click()
        assert "唐" in page.locator("#detail").inner_text()
        assert "原图" not in page.locator("#detail").inner_text()
        page.locator("#search").fill("")
        page.locator("#detail .close").click()
        label=page.locator('.polity-label[title="唐"]')
        label.hover()
        tooltip=page.locator('.leaflet-tooltip')
        assert "唐" in tooltip.inner_text()
        assert not any(word in tooltip.inner_text() for word in ("色块","原图","核定"))
        checks.append("polity search and ruler detail")
        page.locator('[data-tab="events"]').click()
        page.locator("#event-filter").select_option("ruler")
        assert page.locator(".event-card").count()>0
        event_year=int(page.locator(".event-card").first.get_attribute("data-year"))
        page.locator(".event-card").first.click()
        wait_map(page)
        assert int(page.locator("#year-input").input_value())==event_year
        page.locator("#event-filter").select_option("era")
        page.locator("#search").fill("贞观")
        assert page.locator(".event-card").count()>0
        page.locator("#search").fill("")
        checks.append("event type filters, era search, and year navigation")
        choose_layer(page,'raster')
        wait_map(page)
        assert page.locator('#map').get_attribute('data-mode')=='raster'
        assert page.locator(".leaflet-image-layer").count()==6
        choose_layer(page,'none')
        wait_map(page)
        assert page.locator('#map').get_attribute('data-mode')=='none'
        choose_layer(page,'vector')
        wait_map(page)
        page.locator("#show-labels").click()
        assert page.locator(".polity-label").count()==0
        page.locator("#show-labels").click()
        checks.append("raster/vector/basemap layers and label visibility")
        set_year(page,618)
        page.locator('#map').focus()
        page.keyboard.press('ArrowRight')
        wait_map(page)
        assert page.locator('#year-input').input_value()=='619'
        page.keyboard.press('ArrowLeft')
        wait_map(page)
        assert page.locator('#year-input').input_value()=='618'
        page.locator('#search').fill('唐')
        page.keyboard.press('ArrowLeft')
        assert page.locator('#year-input').input_value()=='618'
        page.locator('#search').fill('')
        set_year(page,-1)
        page.locator('#map').focus()
        page.keyboard.press('ArrowRight')
        assert page.locator('#year-input').input_value()=='1'
        page.keyboard.press('ArrowLeft')
        assert page.locator('#year-input').input_value()=='-1'
        set_year(page,618)
        page.locator('#map').focus()
        page.keyboard.down('ArrowRight')
        page.wait_for_timeout(2400)
        held_year=int(page.locator('#year-input').input_value())
        assert held_year>=630
        page.keyboard.up('ArrowRight')
        page.wait_for_timeout(200)
        assert int(page.locator('#year-input').input_value())==held_year
        page.locator('#previous').hover()
        page.mouse.down()
        page.wait_for_timeout(1100)
        page.mouse.up()
        assert int(page.locator('#year-input').input_value())<=held_year-5
        stopped_year=page.locator('#year-input').input_value()
        page.wait_for_timeout(200)
        assert page.locator('#year-input').input_value()==stopped_year
        page.locator('#map').focus()
        page.keyboard.down('ArrowRight')
        page.evaluate("window.dispatchEvent(new Event('blur'))")
        cancelled_year=page.locator('#year-input').input_value()
        page.wait_for_timeout(500)
        page.keyboard.up('ArrowRight')
        assert page.locator('#year-input').input_value()==cancelled_year
        checks.append("arrow keys, input editing, BCE crossing, held key/pointer acceleration, and release/blur cancellation")
        page.locator("#previous").click()
        wait_map(page)
        old_year=int(page.locator("#year-input").input_value())
        page.locator("#next").click()
        wait_map(page)
        assert int(page.locator("#year-input").input_value())>old_year
        set_year(page,618)
        page.locator('#playback-speed').select_option('0.5')
        page.locator("#play").click()
        page.wait_for_timeout(600)
        assert page.locator('#year-input').input_value()=='618'
        page.locator('#playback-speed').select_option('8')
        page.wait_for_function("Number(document.querySelector('#year-input').value)>=622")
        page.locator("#play").click()
        paused_year=page.locator('#year-input').input_value()
        page.wait_for_timeout(250)
        assert page.locator('#year-input').input_value()==paused_year
        assert page.locator('#play').get_attribute('aria-pressed')=='false'
        set_year(page,2017)
        page.locator('#play').click()
        page.wait_for_function("document.querySelector('#play').getAttribute('aria-pressed')==='false'")
        assert page.locator('#year-input').input_value()=='2017'
        page.locator('#playback-speed').select_option('1')
        checks.append("single-year buttons, live playback speed changes, pause and end-of-range stop")
        set_year(page,618)
        page.locator('[data-tab="data"]').click()
        for selector, expected_type in [("#download-snapshot","MultiPolygon"),("#download-labels","Point")]:
            with page.expect_download() as downloaded:
                page.locator(selector).click()
            download=downloaded.value
            contents=json.loads(Path(download.path()).read_text(encoding="utf-8"))
            assert contents["year"]==618 and contents["features"]
            assert expected_type in {f["geometry"]["type"] for f in contents["features"]}
        checks.append("standalone territory and label GeoJSON downloads")
        page.goto(args.url+"/#year=-221",wait_until="networkidle")
        wait_map(page)
        assert "221" in page.locator("#map-year").inner_text()
        checks.append("shareable year URL")
        page.goto(args.url+"/#year=-4000",wait_until="networkidle")
        wait_map(page)
        assert page.locator("#year-input").input_value()=="-2000"
        page.locator("#previous").click()
        assert page.locator("#year-input").input_value()=="-2000"
        checks.append("navigation cannot move before BCE 2000")
        mobile=browser.new_context(viewport={"width":390,"height":844},device_scale_factor=1,is_mobile=True,has_touch=True)
        mobile.route("**/*",route_request)
        phone=mobile.new_page()
        phone.on("pageerror",lambda error:errors.append(str(error)))
        phone.goto(args.url,wait_until="networkidle")
        wait_map(phone)
        check_layout(phone)
        assert not phone.locator('#records').is_visible()
        phone.locator('#dynasty-nav [data-year="1271"]').click()
        wait_map(phone)
        assert "1271" in phone.locator("#map-year").inner_text()
        phone.screenshot(path=str(ROOT/"artifacts/atlas-mobile.png"),full_page=True)
        for year in (-2000,-1600,1912):
            phone.locator(f'#dynasty-nav [data-year="{year}"]').click()
            wait_map(phone)
            assert phone.locator("#year-input").input_value()==str(year)
        choose_theme(phone,'dark')
        assert phone.locator('html').get_attribute('data-theme')=='dark'
        phone.locator('#toggle-records').click()
        assert phone.locator('#records').is_visible()
        phone.locator('#search').fill('日本')
        assert phone.locator('.polity-card').count()>0
        phone.locator('#close-records').click()
        assert not phone.locator('#records').is_visible()
        check_layout(phone)
        phone.set_viewport_size({'width':320,'height':680})
        check_layout(phone)
        checks.append("fixed mobile app layout at 390/320px, full dynasty navigation, theme switch, and records drawer")
        browser.close()
    assert not errors,errors
    assert not failures,failures
    assert not external,external
    report={"status":"passed","checks":checks,"page_errors":errors,"http_errors":failures,"external_requests":external}
    (ROOT/"artifacts/browser-check.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
