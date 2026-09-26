"""Optional integration check: pip install playwright; uses installed Chrome."""
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app, SUBJECTS
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server


def main():
    output = Path('test-results')
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        app.config.update(DATABASE_URL=None, DATABASE=str(Path(directory)/'browser.sqlite3'), SESSION_COOKIE_SECURE=False)
        os.environ['TWILIO_ACCOUNT_SID']=''
        os.environ['TEACHER_PHONE']=''
        server=make_server('127.0.0.1',5055,app,threaded=True)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True)
            context=browser.new_context(viewport={'width':1440,'height':1100})
            page=context.new_page()
            errors=[]
            page.on('pageerror',lambda error: errors.append(str(error)))
            page.goto('http://127.0.0.1:5055',wait_until='networkidle')
            page.screenshot(path=str(output/'desktop.png'),full_page=True)
            assert page.locator('h1').first.inner_text()=='Bugün kaç soru?'
            page.locator('#profile-open').click()
            page.locator('[name=student_name]').fill('Test Öğrenci')
            page.locator('[name=father_phone]').fill('05321234567')
            page.locator('[name=teacher_phone]').fill('05331234567')
            page.locator('[name=consent]').check()
            page.locator('#profile-save').click()
            for key,_,_ in SUBJECTS:
                page.locator(f'[name={key}_correct]').fill('50')
                page.locator(f'[name={key}_wrong]').fill('3')
                page.locator(f'[name={key}_blank]').fill('2')
            assert page.locator('#total-questions').inner_text()=='330'
            page.locator('#save-button').click()
            page.locator('#result-dialog[open]').wait_for()
            assert '330 soru' in page.locator('#saved-summary').inner_text()
            assert 'Gönderilmedi' in page.locator('#notification-results').inner_text()
            page.locator('#result-close').click()
            page.locator('.history-card').wait_for()
            assert page.locator('.history-card').count()==1
            page.locator('[data-view=entry]').click()
            assert '330 soru' in page.locator('.day-heading').inner_text()
            page.locator('#note-open').click()
            page.locator('[name=notes]').fill('Çevrimdışı taslak')
            page.locator('#note-save').click()
            page.reload(wait_until='networkidle')
            assert page.locator('[name=notes]').input_value()=='Çevrimdışı taslak'
            page.evaluate('navigator.serviceWorker.ready')
            context.set_offline(True)
            page.reload(wait_until='load')
            assert page.locator('[name=notes]').input_value()=='Çevrimdışı taslak'
            context.set_offline(False)
            page.reload(wait_until='networkidle')
            for width,height in ((390,844),(320,568),(375,667),(768,844)):
                page.set_viewport_size({'width':width,'height':height})
                page.screenshot(path=str(output/f'check-{width}.png'),full_page=True)
                print(width, height, page.locator('#save-button').bounding_box(), page.evaluate('document.documentElement.scrollHeight'))
                if width < 650:
                    assert page.locator('#save-button').bounding_box()['y']+page.locator('#save-button').bounding_box()['height'] <= height-58, 'Save button below navigation'
                    assert page.evaluate('document.documentElement.scrollHeight <= window.innerHeight'), 'Entry needs vertical scroll'
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'Overflow at {width}'
                page.screenshot(path=str(output/f'mobile-{width}.png'),full_page=True)
            page.locator('[data-view=reports]').click()
            page.locator('.report-stats').wait_for()
            assert '330' in page.locator('.report-stats').inner_text()
            page.locator('[data-view=entry]').click()
            page.evaluate('''() => {
              const el=document.querySelector('#screens');
              const touch=(x)=>new Touch({identifier:1,target:el,clientX:x,clientY:170});
              el.dispatchEvent(new TouchEvent('touchstart',{touches:[touch(280)],bubbles:true}));
              el.dispatchEvent(new TouchEvent('touchend',{changedTouches:[touch(70)],bubbles:true}));
            }''')
            assert page.locator('#reports-view').is_visible()
            assert not errors, errors
            browser.close()
        server.shutdown()
    print('PASS: desktop, mobile 320/390/768, save, history, draft restore, offline shell, no JS errors')


if __name__=='__main__':
    main()
