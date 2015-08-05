# Copyright (C) 2015 East Asian Observatory
# All Rights Reserved.
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful,but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,51 Franklin
# Street, Fifth Floor, Boston, MA  02110-1301, USA

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import os.path
from threading import Thread

from flask import request, make_response
from PIL import Image
from selenium import webdriver
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException

from hedwig.config import get_config
from hedwig.web.app import create_web_app

from test.dummy_config import DummyConfigTestCase
from test.dummy_db import get_dummy_database


class DummyServer(Thread):
    def __init__(self, db):
        Thread.__init__(self)
        self.app = create_web_app(db=db)

        @self.app.route('/shutdown')
        def shutdown():
            request.environ['werkzeug.server.shutdown']()
            return make_response('')

    def run(self):
        self.app.run(host='127.0.0.1', port=11111,
                     debug=False, use_reloader=False)


class IntegrationTest(DummyConfigTestCase):
    def test_app(self):
        config = get_config()
        # Use the JCMT facility for our examples.
        config.set('application', 'facilities', 'JCMT')

        self.base_url = 'http://127.0.0.1:11111/'
        self.user_image_root = os.path.join('doc', 'user', 'image')
        self.admin_image_root = os.path.join('doc', 'user', 'image')

        self.db = get_dummy_database(allow_multi_threaded=True)
        server = DummyServer(self.db)

        self.browser = webdriver.Firefox(
            firefox_binary=FirefoxBinary(config.get('utilities', 'firefox')))
        self.browser.set_window_size(1200, 800)

        server.start()

        try:
            self.register_user(user_name='test', person_name='Example Admin')

            self.browser.find_element_by_link_text('log out').click()

            self.register_user(user_name='username',
                               person_name='Example Person',
                               person_email='example@somewhere.edu',
                               screenshot_path=self.user_image_root)

            self.browser.find_element_by_link_text('log out').click()

        finally:
            self.browser.get('http://127.0.0.1:11111/shutdown')
            self.browser.quit()

    def register_user(self, user_name, person_name, person_email='a@a',
                      institution_name='Test Institution',
                      institution_country='United States',
                      screenshot_path=None):
        self.browser.get(self.base_url)

        log_in = self.browser.find_element_by_link_text('Log in')

        self._save_screenshot(screenshot_path, 'home_page', highlight=[log_in])

        log_in.click()
        self.browser.find_element_by_link_text('register').click()

        self.browser.find_element_by_name('user_name').send_keys(user_name)
        self.browser.find_element_by_name('password').send_keys('pass')
        self.browser.find_element_by_name('password_check').send_keys('pass')

        self._save_screenshot(screenshot_path, 'user_new')

        self.browser.find_element_by_name('submit').click()

        self.assertIn('Your user account has been created.',
                      self.browser.page_source)

        self.browser.find_element_by_name('person_name').send_keys(person_name)
        self.browser.find_element_by_name('person_public').click()
        self.browser.find_element_by_name('single_email').send_keys(
            person_email)

        self._save_screenshot(screenshot_path, 'profile_new')

        self.browser.find_element_by_name('submit').click()

        self.assertIn('Your user profile has been saved.',
                      self.browser.page_source)

        try:
            Select(
                self.browser.find_element_by_name('institution_id')
            ).select_by_visible_text('{}, {}'.format(
                institution_name, institution_country))

            self._save_screenshot(screenshot_path, 'profile_institution')

            self.browser.find_element_by_name('submit_select').click()

            self.assertIn('Your institution has been selected.',
                          self.browser.page_source)

        except NoSuchElementException:
            self.browser.find_element_by_name('institution_name').send_keys(
                institution_name)
            Select(
                self.browser.find_element_by_name('country_code')
            ).select_by_visible_text(institution_country)

            self._save_screenshot(screenshot_path, 'profile_institution')

            self.browser.find_element_by_name('submit_add').click()

            self.assertIn('Your institution has been recorded.',
                          self.browser.page_source)

        profile_link = self.browser.find_element_by_link_text(person_name)
        self._save_screenshot(screenshot_path, 'profile_complete',
                              highlight=[profile_link, 'log_out_link'])

        profile_link.click()
        self._save_screenshot(screenshot_path, 'profile_view')

    def _save_screenshot(self, path, name, highlight=[]):
        if path is None:
            return

        for highlight_element in highlight:
            if not isinstance(highlight_element, basestring):
                highlight_element = highlight_element.get_attribute('id')
            self.browser.execute_script(
                'document.getElementById("' + highlight_element +
                '").classList.add("highlight_for_doc");')

        path_small = os.path.join(path, name + '_small.png')
        path_large = os.path.join(path, name + '_large.png')

        self.browser.save_screenshot(path_large)

        im = Image.open(path_large)

        size = tuple(int(x / 2) for x in im.size)

        im = im.resize(size, resample=Image.BICUBIC)

        im.save(path_small, format='PNG')
