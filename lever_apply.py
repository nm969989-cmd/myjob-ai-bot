"""Narrow Lever form adapter. Unknown fields/challenges stop before submission."""
from urllib.parse import urljoin, urlsplit
from auto_apply_service import lever_url


def complete_form(page, job, policy, profile, resume):
    target = lever_url(job['url'])
    page.goto(target[2], wait_until='domcontentloaded', timeout=30000)
    # Recheck the live role/location; the employer is bound to the approved URL slug.
    title = page.locator('.posting-headline h2')
    location = page.locator('.posting-categories .location')
    if title.count() != 1 or location.count() != 1:
        return False
    if title.inner_text().strip().casefold() != job['title'].casefold() or location.inner_text().strip().casefold() != job['city'].casefold():
        return False
    if policy['minSalaryLpa'] > 0:
        # Ambiguous salary sections need manual review, not an inferred amount.
        import re
        salary = page.locator('.salary')
        if salary.count() != 1:
            return False
        match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(?:-\s*\d+(?:\.\d+)?)?\s*LPA\s*', salary.inner_text(), re.I)
        if not match or float(match[1]) < policy['minSalaryLpa']:
            return False
    page.goto(target[2] + '/apply', wait_until='domcontentloaded', timeout=30000)
    if lever_url(page.url) != target:
        return False
    # Includes hidden challenge widgets; no CAPTCHA/OTP bypass or guessed answers.
    if page.locator('iframe, [class*="captcha"], [id*="captcha"], input[autocomplete="one-time-code"]').count():
        return False
    form = page.locator('form').filter(has=page.locator('input[name="email"]'))
    if form.count() != 1:
        return False
    action = urljoin(page.url, form.get_attribute('action') or page.url)
    if lever_url(action) != target or (form.get_attribute('method') or '').lower() != 'post':
        return False
    known = {'name': profile['full_name'], 'email': profile['email'], 'phone': profile['phone']}
    optional = {'org': profile.get('current_company', ''), 'urls[LinkedIn]': profile.get('linkedin', ''), 'urls[GitHub]': profile.get('github', ''), 'urls[Portfolio]': profile.get('portfolio', '')}
    fields = form.locator('input,textarea,select')
    for field in fields.all():
        kind = (field.get_attribute('type') or '').lower()
        name = field.get_attribute('name') or ''
        if kind == 'hidden' or not field.is_visible() or kind in ('submit', 'button'):
            continue
        if name in known and kind not in ('checkbox', 'radio', 'file'):
            field.fill(known[name])
        elif name in optional and kind in ('', 'text', 'url'):
            if optional[name]:
                field.fill(optional[name])
            elif field.get_attribute('required') is not None:
                return False
        elif name == 'resume' and kind == 'file':
            field.set_input_files(str(resume))
        else:
            # Even optional custom questions may represent legal acknowledgments.
            return False
    if any(form.locator(f'input[name="{key}"]').count() != 1 for key in ('name', 'email', 'resume')):
        return False
    if not form.evaluate('(form) => form.checkValidity()'):
        return False
    submit = form.locator('button[type="submit"],input[type="submit"]')
    if submit.count() != 1:
        return False
    with page.expect_response(lambda response: response.request.method == 'POST' and lever_url(response.url) == target, timeout=15000) as received:
        submit.click(timeout=15000)
    if not 200 <= received.value.status < 300:
        return False
    confirmation = page.locator('.application-confirmation')
    try:
        confirmation.wait_for(state='visible', timeout=15000)
        return (urlsplit(page.url).netloc == target[0]
                and confirmation.inner_text().strip().lower() in
                ('application submitted!', 'thank you for applying!', 'your application has been submitted.'))
    except Exception:
        return False


def apply(job, policy, profile, resume):
    from playwright.sync_api import sync_playwright
    target = lever_url(job['url'])
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            # Keep submitted candidate data on the approved employer's Lever route.
            def restrict(route):
                request = route.request
                u = urlsplit(request.url)
                if request.method not in ('GET', 'HEAD', 'OPTIONS') and lever_url(request.url) != target:
                    return route.abort()
                if request.is_navigation_request() and (u.scheme != 'https' or u.netloc != target[0] or not u.path.startswith('/' + target[1] + '/')):
                    return route.abort()
                return route.continue_()
            context.route('**/*', restrict)
            return complete_form(context.new_page(), job, policy, profile, resume)
        finally:
            browser.close()
