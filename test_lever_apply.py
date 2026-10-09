"""Run with installed Playwright Chromium; all pages intercepted, zero network."""
import tempfile
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
from lever_apply import complete_form
from test_auto_apply import URL


class LeverFormTests(unittest.TestCase):
    def test_confirmed_and_blocked_forms(self):
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as runtime:
            resume=Path(tmp)/'resume.pdf';resume.write_bytes(b'%PDF-1.4 fixture')
            browser=runtime.chromium.launch(headless=True,args=['--no-sandbox'])
            try:
                for case in ('confirmed','captcha','unknown','wrong-role','wrong-location','no-confirmation','external-action','rejected'):
                    with self.subTest(case=case):
                        context=browser.new_context(); sent=[]
                        def route(request_route):
                            request=request_route.request
                            if request.method=='POST':
                                sent.append(request.url)
                                body='<div class="application-confirmation">Application submitted!</div>' if case in ('confirmed','rejected') else '<h1>Something went wrong</h1>'
                            elif request.url.endswith('/apply'):
                                action='https://evil.invalid/collect' if case=='external-action' else URL+'/apply'
                                body=f'<form method="post" action="{action}" enctype="multipart/form-data"><input name="name" required><input name="email" type="email" required><input name="phone"><input name="resume" type="file" required><button type="submit">Submit application</button></form>'
                                if case=='captcha':body+='<div id="captcha">Challenge</div>'
                                if case=='unknown':body=body.replace('</form>','<input name="visa" required></form>')
                            else:
                                title='Other role' if case=='wrong-role' else 'Python Developer'
                                city='Other city' if case=='wrong-location' else 'Chennai'
                                body=f'<div class="posting-headline"><h2>{title}</h2></div><div class="posting-categories"><div class="location">{city}</div></div><div class="salary">6-8 LPA</div>'
                            request_route.fulfill(status=500 if case=='rejected' and request.method=='POST' else 200,content_type='text/html',body=body)
                        context.route('**/*',route)
                        ok=complete_form(context.new_page(),dict(url=URL,title='Python Developer',city='Chennai'),dict(minSalaryLpa=5),dict(full_name='Synthetic',email='test@candidate.invalid',phone='123'),resume)
                        self.assertEqual(ok,case=='confirmed')
                        self.assertEqual(len(sent),1 if case in ('confirmed','no-confirmation','rejected') else 0)
                        context.close()
            finally:browser.close()


if __name__=='__main__':unittest.main()
