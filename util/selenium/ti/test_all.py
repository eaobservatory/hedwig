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
        self.base_url = 'http://127.0.0.1:11111/'
        self.user_image_root = os.path.join('doc', 'user', 'image')
        self.admin_image_root = os.path.join('doc', 'user', 'image')

        self.db = get_dummy_database(allow_multi_threaded=True)
        server = DummyServer(self.db)

        self.browser = webdriver.Firefox(
            firefox_binary=FirefoxBinary(
                get_config().get('utilities', 'firefox')))
        self.browser.set_window_size(1200, 800)

        server.start()

        try:
            self.register_user(user_name='test', person_name='Test One',
                               screenshot_path=self.user_image_root)

            self.browser.find_element_by_link_text('log out').click()

            self.register_user(user_name='test2', person_name='Test Two')

            self.browser.find_element_by_link_text('log out').click()

        finally:
            self.browser.get('http://127.0.0.1:11111/shutdown')
            self.browser.quit()

    def register_user(self, user_name, person_name, person_email='a@a',
                      institution_name='Test Institution',
                      institution_country='United States',
                      screenshot_path=None):
        self.browser.get(self.base_url)
        self.browser.find_element_by_link_text('Log in').click()
        self.browser.find_element_by_link_text('register').click()

        if screenshot_path is not None:
            self.browser.save_screenshot(
                os.path.join(screenshot_path, 'user_new.png'))

        self.browser.find_element_by_name('user_name').send_keys(user_name)
        self.browser.find_element_by_name('password').send_keys('pass')
        self.browser.find_element_by_name('password_check').send_keys('pass')
        self.browser.find_element_by_name('submit').click()

        self.assertIn('Your user account has been created.',
                      self.browser.page_source)
        if screenshot_path is not None:
            self.browser.save_screenshot(
                os.path.join(screenshot_path, 'profile_new.png'))

        self.browser.find_element_by_name('person_name').send_keys(person_name)
        self.browser.find_element_by_name('single_email').send_keys('a@a')
        self.browser.find_element_by_name('submit').click()

        self.assertIn('Your user profile has been saved.',
                      self.browser.page_source)

        if screenshot_path is not None:
            self.browser.save_screenshot(os.path.join(
                screenshot_path, 'profile_institution.png'))
        try:
            Select(
                self.browser.find_element_by_name('institution_id')
            ).select_by_visible_text('{}, {}'.format(
                institution_name, institution_country))
            self.browser.find_element_by_name('submit_select').click()

            self.assertIn('Your institution has been selected.',
                          self.browser.page_source)

        except NoSuchElementException:
            self.browser.find_element_by_name('institution_name').send_keys(
                institution_name)
            Select(
                self.browser.find_element_by_name('country_code')
            ).select_by_visible_text(institution_country)

            self.browser.find_element_by_name('submit_add').click()

            self.assertIn('Your institution has been recorded.',
                          self.browser.page_source)
