""" This file aims to demonstrate how to write custom commands in OpenWPM

Steps to have a custom command run as part of a CommandSequence

1. Create a class that derives from BaseCommand
2. Implement the execute method
3. Append it to the CommandSequence
4. Execute the CommandSequence

"""
import logging

from selenium.webdriver import Firefox
from selenium.webdriver.common.by import By

from openwpm.commands.types import BaseCommand
from openwpm.config import BrowserParams, ManagerParams
from openwpm.socket_interface import ClientSocket


class LinkCountingCommand(BaseCommand):
    """This command logs how many links it found on any given page"""

    def __init__(self) -> None:
        self.logger = logging.getLogger("openwpm")

    # While this is not strictly necessary, we use the repr of a command for logging
    # So not having a proper repr will make your logs a lot less useful
    def __repr__(self) -> str:
        return "LinkCountingCommand"

    # Have a look at openwpm.commands.types.BaseCommand.execute to see
    # an explanation of each parameter
    def execute(
        self,
        webdriver: Firefox,
        browser_params: BrowserParams,
        manager_params: ManagerParams,
        extension_socket: ClientSocket,
    ) -> None:
        current_url = webdriver.current_url
        link_count = len(webdriver.find_elements(By.TAG_NAME, "a"))
        self.logger.info("There are %d links on %s", link_count, current_url)
        
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.common.exceptions import TimeoutException
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError
from urllib.parse import urljoin
import random
import time
import timeit
import datetime

import domain_utils
from openwpm.commands.utils.webdriver_utils import wait_until_loaded
from openwpm.commands.browser_commands import GetCommand, bot_mitigation, SaveScreenshotCommand, DumpPageSourceCommand

# Link text ranking
_TYPE_TEXT = 'text'
_TYPE_HREF = 'href'
_FLAG_NONE = 0
_FLAG_STAY_ON_PAGE = 1
_FLAG_IN_NEW_URL_ONLY = 2
_LINK_TEXT_RANK = [
    # probably newsletters
    (_TYPE_TEXT, 'newsletter', 10, _FLAG_NONE),
    (_TYPE_TEXT, 'weekly ad',   9, _FLAG_NONE),
    (_TYPE_TEXT, 'subscribe',   9, _FLAG_NONE),
    (_TYPE_TEXT, 'inbox',       8, _FLAG_NONE),
    (_TYPE_TEXT, 'email',       7, _FLAG_NONE),
    (_TYPE_TEXT, 'sale alert',  6, _FLAG_NONE),

    # sign-up links (for something?)
    (_TYPE_TEXT, 'signup',     5, _FLAG_NONE),
    (_TYPE_TEXT, 'sign up',    5, _FLAG_NONE),
    (_TYPE_TEXT, 'sign me up', 5, _FLAG_NONE),
    (_TYPE_TEXT, 'register',   4, _FLAG_NONE),
    (_TYPE_TEXT, 'create',     4, _FLAG_NONE),
    (_TYPE_TEXT, 'join',       4, _FLAG_NONE),

    # articles (sometimes sign-up links are on these pages...)
    (_TYPE_HREF, '/article', 3, _FLAG_NONE),
    (_TYPE_HREF, 'news/',    3, _FLAG_IN_NEW_URL_ONLY),
    (_TYPE_HREF, '/' + str(datetime.datetime.now().year), 2, _FLAG_NONE),

    # country selectors (for country-selection landing pages)
    (_TYPE_HREF, '/us/',  1, _FLAG_STAY_ON_PAGE | _FLAG_IN_NEW_URL_ONLY),
    (_TYPE_HREF, '=us&',  1, _FLAG_STAY_ON_PAGE | _FLAG_IN_NEW_URL_ONLY),
    (_TYPE_HREF, 'en-us', 1, _FLAG_STAY_ON_PAGE | _FLAG_IN_NEW_URL_ONLY),
]
_LINK_RANK_SKIP = 6  # minimum rank to select immediately (skipping the rest of the links)
_LINK_MATCH_TIMEOUT = 20  # maximum time to match links, in seconds
_LINK_TEXT_BLACKLIST = ['unsubscribe', 'mobile', 'phone']

# Keywords
_KEYWORDS_EMAIL  = ['email', 'e-mail', 'subscribe', 'newsletter']
_KEYWORDS_SUBMIT = ['submit', 'sign up', 'sign-up', 'signup', 'sign me up', 'subscribe', 'register', 'join']
_KEYWORDS_SELECT = ['yes', 'ny', 'new york', 'united states', 'usa', '1990']

# Other constants
_PAGE_LOAD_TIME = 5  # time to wait for pages to load (in seconds)
_FORM_SUBMIT_SLEEP = 2  # time to wait after submitting a form (in seconds)
_FORM_CONTAINER_SEARCH_LIMIT = 4  # number of parents of input fields to search

# User information to supply to forms
def _get_user_info(email):
    """Returns a dictionary of user information."""
    return {
        'email': email,
        'first_name': 'Bob',
        'last_name': 'Smith',
        'full_name': 'Bob Smith',
        'user': 'bobsmith' + str(random.randrange(0,1000)),
        'password': 'p4S$w0rd123',
        'tel': '212' + '555' + '01' + str(random.randrange(0,10)) + str(random.randrange(0,10)),
        'company': 'Smith & Co.',
        'title': 'Mr.',
        'zip': '12345',
        'street1': '101 Main St.',
        'street2': 'Apt. 101',
        'city': 'Schenectady',
        'state': 'New York',
    }
def get_website(url, sleep, visit_id, webdriver, proxy_queue, browser_params, extension_socket):
    getcommand = GetCommand(url,sleep)
    getcommand.set_visit_browser_id(visit_id, browser_params.browser_id)
    getcommand.execute(webdriver,browser_params,None, extension_socket)
def dump_page_source(dump_name, webdriver, browser_params, manager_params):
    dump = DumpPageSourceCommand(dump_name)
    dump.set_visit_browser_id(0, browser_params.browser_id)
    dump.execute(webdriver,browser_params,manager_params, None)

def save_screenshot(screenshot_name, webdriver, browser_params, manager_params):
    screen = SaveScreenshotCommand(screenshot_name)
    screen.set_visit_browser_id(0, browser_params.browser_id)
    screen.execute(webdriver,browser_params,manager_params,None)

def fill_forms(url, email_producer, num_links, page_timeout, debug, visit_id,
               webdriver, proxy_queue, browser_params, manager_params, extension_socket,logger):
    """Finds a newsletter form on the page. If not found, visits <num_links>
    internal links and scans those pages for a form. Submits the form if found.
    """
    # load the site
    webdriver.set_page_load_timeout(page_timeout)
    get_website(url, 0, visit_id, webdriver, proxy_queue, browser_params, extension_socket)

    # connect to the logger

    # try to find a newsletter form on the landing page
    if _find_and_fill_form(webdriver, email_producer, visit_id, debug, browser_params, manager_params, logger):
        return

    # otherwise, scan more pages
    main_handle = webdriver.current_window_handle
    visited_links = set()
    for i in range(num_links):
        # get all links on the page
        links = webdriver.find_elements(By.TAG_NAME, 'a')
        random.shuffle(links)

        current_url = webdriver.current_url
        current_ps1 = domain_utils.get_ps_plus_1(current_url)

        # find links to click
        match_links = []
        start_time = timeit.default_timer()
        for link in links:
            try:
                if not link.is_displayed():
                    continue

                # check if link is valid and not already visited
                href = link.get_attribute('href')
                if href is None or href in visited_links:
                    continue

                # check if this is an internal link
                if not _is_internal_link(href, current_url, current_ps1):
                    continue

                link_text = link.text.lower()

                # skip links with blacklisted text
                blacklisted = False
                for bl_text in _LINK_TEXT_BLACKLIST:
                    if bl_text in link_text:
                        blacklisted = True
                        break
                if blacklisted:
                    continue

                # should we click this link?
                link_rank = 0
                for type, s, rank, flags in _LINK_TEXT_RANK:
                    if (type == _TYPE_TEXT and s in link_text) or (type == _TYPE_HREF and s in href):
                        if flags & _FLAG_IN_NEW_URL_ONLY:
                            # don't use this link if the current page URL already matches too
                            if type == _TYPE_HREF and s in current_url:
                                continue

                        # link matches!
                        link_rank = rank
                        match_links.append((link, rank, link_text, href, flags))
                        break
                if link_rank >= _LINK_RANK_SKIP:  # good enough, stop looking
                    break
            except:
                logger.error("error while looping through links...")

            # quit if too much time passed (for some reason, this is really slow...)
            if match_links and timeit.default_timer() - start_time > _LINK_MATCH_TIMEOUT:
                break

        # find the best link to click
        if not match_links:
            break  # no more links to click
        match_links.sort(key=lambda l: l[1])
        next_link = match_links[-1]
        visited_links.add(next_link[3])

        # click the link
        try:
            # load the page
            logger.info("clicking on link '%s' - %s" % (next_link[2], next_link[3]))
            logger.info("go")
            next_link[0].click()
            logger.info("post click")
            wait_until_loaded(webdriver, _PAGE_LOAD_TIME)
            logger.info("post load")
            logger.info("about to fill form pre")
            if browser_params.bot_mitigation:
                logger.info("botting")
                bot_mitigation(webdriver)
            logger.info("about to fill form3")
            logger.info("about to fill form")
            # find newsletter form
            if _find_and_fill_form(webdriver, email_producer, visit_id, debug, browser_params, manager_params, logger):
                return

            # should we stay on this page?
            if next_link[4] & _FLAG_STAY_ON_PAGE:
                continue

            # go back
            webdriver.back()
            wait_until_loaded(webdriver, _PAGE_LOAD_TIME)

            # check other windows (ex. pop-ups)
            windows = webdriver.window_handles
            if len(windows) > 1:
                form_found_in_popup = False
                for window in windows:
                    if window != main_handle:
                        webdriver.switch_to.window(window)
                        wait_until_loaded(webdriver, _PAGE_LOAD_TIME)

                        # find newsletter form
                        if _find_and_fill_form(webdriver, email_producer, visit_id, debug, browser_params, manager_params, logger):
                            form_found_in_popup = True

                        webdriver.close()
                webdriver.switch_to.window(main_handle)
                time.sleep(1)

                if form_found_in_popup:
                    return
        except:
            pass

def _is_internal_link(href, url, ps1=None):
    """Returns whether the given link is an internal link."""
    if ps1 is None:
        ps1 = domain_utils.get_ps_plus_1(url)
    return domain_utils.get_ps_plus_1(urljoin(url, href)) == ps1

def _find_and_fill_form(webdriver, email_producer, visit_id, debug, browser_params, manager_params, logger):
    """Finds and fills a form, and returns True if accomplished."""
    current_url = webdriver.current_url
    current_site_title = webdriver.title.encode('ascii', 'replace')
    main_handle = webdriver.current_window_handle
    in_iframe = False

    # debug: save before/after screenshots and page source
    debug_file_prefix = str(visit_id) + '_'
    debug_form_pre_initial = debug_file_prefix + 'form_initial_presubmit'
    debug_form_post_initial = debug_file_prefix + 'form_initial_result'
    debug_form_pre_followup = debug_file_prefix + 'form_followup_presubmit'
    debug_form_post_followup = debug_file_prefix + 'form_followup_result'
    debug_page_source_initial = debug_file_prefix + 'src_initial'
    debug_page_source_followup = debug_file_prefix + 'src_followup'

    # try to find newsletter form on landing page
    newsletter_form = _find_newsletter_form(webdriver)
    if newsletter_form is None:
        if debug:
            logger.info("no luck on default: " + current_url)
        # search for forms in iframes (if present)
        iframes = webdriver.find_elements(By.TAG_NAME, 'iframe')
        for iframe in iframes:
            # switch to the iframe
            webdriver.switch_to.frame(iframe)

            # is there a form?
            newsletter_form = _find_newsletter_form(webdriver)
            if newsletter_form is not None:
                if debug:
                    dump_page_source(debug_page_source_initial, webdriver, browser_params, manager_params)
                in_iframe = True
                break  # form found, stay on the iframe

            # switch back
            webdriver.switch_to.default_content()

        # still no form?
        if newsletter_form is None:
            return False
    elif debug:
        if debug:
            logger.info("luck on default: " + current_url)
        dump_page_source(debug_page_source_initial, webdriver, browser_params, manager_params)

    email = email_producer(current_url, current_site_title)
    user_info = _get_user_info(email)
    _form_fill_and_submit(newsletter_form, user_info, webdriver, False, browser_params, manager_params, debug_form_pre_initial if debug else None)
    logger.info('submitted form on [%s] with email [%s]', current_url, email)
    time.sleep(_FORM_SUBMIT_SLEEP)
    _dismiss_alert(webdriver)
    if debug: save_screenshot(debug_form_post_initial, webdriver, browser_params, manager_params)

    # fill any follow-up forms...
    wait_until_loaded(webdriver, _PAGE_LOAD_TIME)  # wait if we got redirected
    follow_up_form = None

    # first check other windows (ex. pop-ups)
    windows = webdriver.window_handles
    if len(windows) > 1:
        form_found_in_popup = False
        for window in windows:
            if window != main_handle:
                webdriver.switch_to.window(window)

                # find newsletter form
                if follow_up_form is None:
                    follow_up_form = _find_newsletter_form(webdriver)
                    if follow_up_form is not None:
                        if debug:
                            dump_page_source(debug_page_source_followup, webdriver, browser_params, manager_params)
                        _form_fill_and_submit(follow_up_form, user_info, webdriver, True, browser_params, manager_params, debug_form_pre_followup if debug else None)
                        time.sleep(_FORM_SUBMIT_SLEEP)
                        _dismiss_alert(webdriver)
                        if debug: save_screenshot(debug_form_post_followup, webdriver, browser_params, manager_params)

                webdriver.close()
        webdriver.switch_to.window(main_handle)
        time.sleep(1)

    # else check current page
    if follow_up_form is None:
        follow_up_form = _find_newsletter_form(webdriver)
        if follow_up_form is not None:
            if debug:
                dump_page_source(debug_page_source_followup, webdriver, browser_params, manager_params)
            _form_fill_and_submit(follow_up_form, user_info, webdriver, True, browser_params, manager_params, debug_form_pre_followup if debug else None)
            time.sleep(_FORM_SUBMIT_SLEEP)
            _dismiss_alert(webdriver)
            if debug: save_screenshot(debug_form_post_followup, webdriver, browser_params, manager_params)

	# switch back
    if in_iframe:
        webdriver.switch_to.default_content()

    # close other windows (ex. pop-ups)
    windows = webdriver.window_handles
    if len(windows) > 1:
        for window in windows:
            if window != main_handle:
                webdriver.switch_to.window(window)
                webdriver.close()
        webdriver.switch_to.window(main_handle)
        time.sleep(1)

    return True

def _find_newsletter_form(webdriver):
    """Tries to find a form element on the page for newsletter sign-up.
    Returns None if no form was found.
    """
    # find all forms that match
    newsletter_forms = []
    forms = webdriver.find_elements(By.TAG_NAME, 'form')
    for form in forms:
        if not form.is_displayed():
            continue

        # find email keywords in the form HTML (preliminary filtering)
        form_html = form.get_attribute('outerHTML').lower()
        match = False
        for s in _KEYWORDS_EMAIL:
            if s in form_html:
                match = True
                break
        if not match:
            continue

        # check if an input field contains an email element
        input_fields = form.find_elements(By.TAG_NAME, 'input')
        match = False
        for input_field in input_fields:
            if input_field.is_displayed() and _is_email_input(input_field):
                match = True
                break
        if not match:
            continue

        # form matched, get some other ranking criteria:
        # - rank modal/pop-up/dialogs higher, since these are likely to be sign-up forms
        z_index = _get_z_index(form, webdriver)
        has_modal_text = 'modal' in form_html or 'dialog' in form_html
        # - rank login dialogs lower, in case better forms exist
        #   (count occurrences of these keywords, since they might just be in a URL)
        login_text_count = -sum([form_html.count(s) for s in ['login', 'log in', 'sign in']])
        # - rank forms with more input elements higher
        input_field_count = len([x for x in input_fields if x.is_displayed()])
        newsletter_forms.append((form, (z_index, int(has_modal_text), login_text_count, input_field_count)))

    # return highest ranked form
    if newsletter_forms:
        newsletter_forms.sort(key=lambda x: x[1], reverse=True)
        return newsletter_forms[0][0]

    # try to find any container with email input fields and a submit button
    input_fields = webdriver.find_elements(By.TAG_NAME,'input')
    visited_containers = set()
    for input_field in input_fields:
        if not input_field.is_displayed() or not _is_email_input(input_field):
            continue

        # email input field found, check parents for container with a submit button
        try:
            e = input_field
            for i in range(_FORM_CONTAINER_SEARCH_LIMIT):
                e = e.find_element_by_xpath('..')  # get parent
                if e is None or e.id in visited_containers:
                    continue  # already visited

                # is this a container type? (<div> or <span>)
                tag_name = e.tag_name.lower()
                if tag_name == 'div' or tag_name == 'span':
                    # does this contain a submit button?
                    if _has_submit_button(e):
                        return e  # yes, we're done

                visited_containers.add(e.id)
        except:
            pass

    # still no matches?
    return None

def _is_email_input(input_field):
    """Returns whether the given input field is an email input field."""
    type = input_field.get_attribute('type').lower()
    if type == 'email':
        return True
    elif type == 'text':
        if _element_contains_text(input_field, _KEYWORDS_EMAIL):
            return True
    return False

def _has_submit_button(container):
    """Returns whether the given container has a submit button."""
    # check <input> tags
    input_fields = container.find_elements(By.TAG_NAME, 'input')
    for input_field in input_fields:
        if not input_field.is_displayed():
            continue

        type = input_field.get_attribute('type').lower()
        if type == 'submit' or type == 'button' or type == 'image':
            if _element_contains_text(input_field, _KEYWORDS_SUBMIT):
                return True

    # check <button> tags
    buttons = container.find_elements(By.TAG_NAME, 'button')
    for button in buttons:
        if not button.is_displayed():
            continue

        type = button.get_attribute('type').lower()
        if type is None or (type != 'reset' and type != 'menu'):
            if _element_contains_text(button, _KEYWORDS_SUBMIT):
                return True

    return False

def _get_z_index(element, webdriver):
    """Tries to find the actual z-index of an element, otherwise returns 0."""
    e = element
    while e is not None:
        try:
            # selenium is usually wrong, don't bother with this
            #z = element.value_of_css_property('z-index')

            # get z-index with javascript
            script = 'return window.document.defaultView.getComputedStyle(arguments[0], null).getPropertyValue("z-index")'
            z = webdriver.execute_script(script, e)
            if z != None and z != 'auto':
                try:
                    return int(z)
                except ValueError:
                    pass

            # try the parent...
            e = e.find_element_by_xpath('..')  # throws exception when parent is the <html> tag
        except:
            break
    return 0

def _dismiss_alert(webdriver):
    """Dismisses an alert, if present."""
    try:
        WebDriverWait(webdriver, 0.5).until(expected_conditions.alert_is_present())
        alert = webdriver.switch_to.alert
        alert.dismiss()
    except TimeoutException:
        pass

def _form_fill_and_submit(form, user_info, webdriver, clear, browser_params, manager_params, screenshot_filename):
    """Fills out a form and submits it, then waits for the response."""
    # try to fill all input fields in the form...
    input_fields = form.find_elements(By.TAG_NAME, 'input')
    submit_button = None
    text_field = None
    for input_field in input_fields:
        if not input_field.is_displayed():
            continue

        type = input_field.get_attribute('type').lower()
        if type == 'email':
            # using html5 "email" type, this is probably an email field
            _type_in_field(input_field, user_info['email'], clear)
            text_field = input_field
        elif type == 'text':
            # try to decipher this based on field attributes
            if _element_contains_text(input_field, 'company'):
                _type_in_field(input_field, user_info['company'], clear)
            elif _element_contains_text(input_field, 'title'):
                _type_in_field(input_field, user_info['title'], clear)
            elif _element_contains_text(input_field, 'name'):
                if _element_contains_text(input_field, ['first', 'forename', 'fname']):
                    _type_in_field(input_field, user_info['first_name'], clear)
                elif _element_contains_text(input_field, ['last', 'surname', 'lname']):
                    _type_in_field(input_field, user_info['last_name'], clear)
                elif _element_contains_text(input_field, ['user', 'account']):
                    _type_in_field(input_field, user_info['user'], clear)
                else:
                    _type_in_field(input_field, user_info['full_name'], clear)
            elif _element_contains_text(input_field, ['zip', 'postal']):
                _type_in_field(input_field, user_info['zip'], clear)
            elif _element_contains_text(input_field, 'city'):
                _type_in_field(input_field, user_info['city'], clear)
            elif _element_contains_text(input_field, 'state'):
                _type_in_field(input_field, user_info['state'], clear)
            elif _element_contains_text(input_field, _KEYWORDS_EMAIL):
                _type_in_field(input_field, user_info['email'], clear)
            elif _element_contains_text(input_field, ['street', 'address']):
                if _element_contains_text(input_field, ['2', 'number']):
                    _type_in_field(input_field, user_info['street2'], clear)
                elif _element_contains_text(input_field, '3'):
                    pass
                else:
                    _type_in_field(input_field, user_info['street1'], clear)
            elif _element_contains_text(input_field, ['phone', 'tel', 'mobile']):
                _type_in_field(input_field, user_info['tel'], clear)
            elif _element_contains_text(input_field, 'search'):
                pass
            else:
                # skip if visibly marked "optional"
                placeholder = input_field.get_attribute('placeholder')
                if placeholder is not None and 'optional' in placeholder.lower():
                    pass

                # default: assume email
                else:
                    _type_in_field(input_field, user_info['email'], clear)
            text_field = input_field
        elif type == 'number':
            if _element_contains_text(input_field, ['phone', 'tel', 'mobile']):
                _type_in_field(input_field, user_info['tel'], clear)
            elif _element_contains_text(input_field, ['zip', 'postal']):
                _type_in_field(input_field, user_info['zip'], clear)
            else:
                _type_in_field(input_field, user_info['zip'], clear)
        elif type == 'checkbox' or type == 'radio':
            # check anything/everything
            if not input_field.is_selected():
                input_field.click()
        elif type == 'password':
            _type_in_field(input_field, user_info['password'], clear)
        elif type == 'tel':
            _type_in_field(input_field, user_info['tel'], clear)
        elif type == 'submit' or type == 'button' or type == 'image':
            if _element_contains_text(input_field, _KEYWORDS_SUBMIT):
                submit_button = input_field
        elif type == 'reset' or type == 'hidden' or type == 'search':
            # common irrelevant input types
            pass
        else:
            # default: assume email
            _type_in_field(input_field, user_info['email'], clear)

    # find 'button' tags (if necessary)
    if submit_button is None:
        buttons = form.find_elements(By.TAG_NAME, 'button')
        for button in buttons:
            if not button.is_displayed():
                continue

            # filter out non-submit button types
            type = button.get_attribute('type').lower()
            if type is not None and (type == 'reset' or type == 'menu'):
                continue

            # pick first matching button
            if _element_contains_text(button, _KEYWORDS_SUBMIT):
                submit_button = button
                break

    # fill in 'select' fields
    select_fields = form.find_elements(By.TAG_NAME,'select')
    for select_field in select_fields:
        if not select_field.is_displayed():
            continue

        # select an appropriate element if possible,
        # otherwise second element (to skip blank fields),
        # falling back on the first
        select = Select(select_field)
        select_options = select.options
        selected_index = None
        for i, opt in enumerate(select_options):
            opt_text = opt.text.strip().lower()
            if opt_text in _KEYWORDS_SELECT:
                selected_index = i
                break
        if selected_index is None:
            selected_index = min(1, len(select_options) - 1)
        select.select_by_index(selected_index)

    # debug: save screenshot
    if screenshot_filename: save_screenshot(screenshot_filename, webdriver, browser_params, manager_params)

    # submit the form
    if submit_button is not None:
        try:
            submit_button.click()  # trigger javascript events if possible
            return
        except:
            pass
    if text_field is not None:
        try:
            text_field.send_keys(Keys.RETURN)  # press enter
        except:
            pass
    try:
        if form.tag_name.lower() == 'form':
            form.submit()  # submit() form
    except:
        pass

def _element_contains_text(element, text):
    """Scans various element attributes for the given text."""
    attributes = ['name', 'class', 'id', 'placeholder', 'value', 'for', 'title', 'innerHTML']
    text_list = text if type(text) is list else [text]
    for s in text_list:
        for attr in attributes:
            e = element.get_attribute(attr)
            if e is not None and s in e.lower():
                return True
    return False

def _type_in_field(input_field, text, clear):
    """Types text into an input field."""
    if clear:
        input_field.send_keys(Keys.CONTROL, 'a')
    input_field.send_keys(text)
    
class SignupCommand(BaseCommand):
    """This command logs how many links it found on any given page"""

    def __init__(self,email_producer,num_links,page_timeout,debug = False) -> None:
        self.logger = logging.getLogger("openwpm")
        self.num_links = num_links
        self.page_timeout = page_timeout
        self.debug = debug
        self.email_producer = email_producer

    # While this is not strictly necessary, we use the repr of a command for logging
    # So not having a proper repr will make your logs a lot less useful
    def __repr__(self) -> str:
        return "SignupCommand"

    # Have a look at openwpm.commands.types.BaseCommand.execute to see
    # an explanation of each parameter
    def execute(
        self,
        webdriver: Firefox,
        browser_params: BrowserParams,
        manager_params: ManagerParams,
        extension_socket: ClientSocket,
    ) -> None:
        current_url = webdriver.current_url
        fill_forms(current_url, self.email_producer, self.num_links, self.page_timeout, self.debug, 0,
               webdriver, None, browser_params, manager_params, extension_socket,self.logger)
        link_count = len(webdriver.find_elements(By.TAG_NAME, "a"))
        self.logger.info("There are %d links on %s", link_count, current_url)
