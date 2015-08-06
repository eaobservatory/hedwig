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

from datetime import datetime
import os.path
from threading import Thread

from flask import request, make_response
from PIL import Image
from selenium import webdriver
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException

from hedwig import auth
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
        # Speed up password hashing for the test.
        auth._rounds = 10

        config = get_config()
        # Use the JCMT facility for our examples.
        config.set('application', 'facilities', 'JCMT')

        self.base_url = 'http://127.0.0.1:11111/'
        self.user_image_root = os.path.join('doc', 'user', 'image')
        self.admin_image_root = os.path.join('doc', 'admin', 'image')

        self.db = get_dummy_database(randomize_ids=False,
                                     allow_multi_threaded=True)
        server = DummyServer(self.db)

        self.browser = webdriver.Firefox(
            firefox_binary=FirefoxBinary(config.get('utilities', 'firefox')))
        self.browser.set_window_size(1200, 800)

        server.start()

        try:
            # Register some people.
            self.register_user(user_name='test', person_name='Example Admin')

            self.log_out_user()

            # Make this user an administrator.
            person_id = self.db.search_person().get_single().id
            self.db.update_person(person_id, admin=True)

            self.register_user(user_name='username',
                               person_name='Example Person',
                               person_email='example@somewhere.edu',
                               screenshot_path=self.user_image_root)

            self.log_out_user()

            self.register_user(user_name='username2',
                               person_name='Another Person')

            self.log_out_user()

            # Log in as administrative user and set up a semester.
            self.log_in_user(user_name='test')

            semester_name = self.set_up_facility('jcmt')

            self.log_out_user()

            # Log back in a normal use and create a proposal.
            self.log_in_user(user_name='username')

            self.create_proposal('jcmt', semester_name)

        finally:
            self.browser.get(self.base_url + 'shutdown')
            self.browser.quit()

    def register_user(self, user_name, person_name, person_email='a@a',
                      password='password',
                      institution_name='Test Institution',
                      institution_country='United States',
                      screenshot_path=None):
        self.browser.get(self.base_url)

        log_in = self.browser.find_element_by_link_text('Log in')

        self._save_screenshot(screenshot_path, 'home_page', highlight=[log_in])

        log_in.click()
        self.browser.find_element_by_link_text('register').click()

        self.browser.find_element_by_name('user_name').send_keys(user_name)
        self.browser.find_element_by_name('password').send_keys(password)
        self.browser.find_element_by_name('password_check').send_keys(password)

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

    def log_out_user(self):
        self.browser.find_element_by_link_text('log out').click()

    def log_in_user(self, user_name, password='password'):
        self.browser.get(self.base_url)

        log_in = self.browser.find_element_by_link_text('Log in')

        log_in.click()

        self.browser.find_element_by_name('user_name').send_keys(user_name)
        self.browser.find_element_by_name('password').send_keys(password)

        self.browser.find_element_by_name('submit').click()

        self.assertIn('You have been logged in.',
                      self.browser.page_source)

    def set_up_facility(self, facility_code):
        self.browser.get(self.base_url + facility_code)

        take_admin = self.browser.find_element_by_link_text('take admin')

        self._save_screenshot(self.admin_image_root, 'facility_home',
                              [take_admin])

        take_admin.click()

        self.assertIn('You have taken administrative privileges.',
                      self.browser.page_source)

        drop_admin = self.browser.find_element_by_link_text('drop admin')
        admin_menu = self.browser.find_element_by_link_text(
            'Administrative menu')

        self._save_screenshot(self.admin_image_root, 'facility_home_admin',
                              [drop_admin, admin_menu])

        admin_menu.click()

        self._save_screenshot(self.admin_image_root, 'facility_admin_menu')

        admin_menu_url = self.browser.current_url

        # Create a new semester.
        self.browser.find_element_by_link_text('Semesters').click()
        self.browser.find_element_by_link_text('New semester').click()

        # Make sure we are going to generate a semester which is open for
        # submissions: base it on the current date and use JCMT naming.
        current_date = datetime.utcnow()
        semester_year = str(current_date.year + 1)
        semester_name = semester_year[2:] + 'A'
        self.browser.find_element_by_name('semester_name').send_keys(
            semester_name)
        self.browser.find_element_by_name('semester_code').send_keys(
            semester_name)
        self.browser.find_element_by_name('start_date').send_keys(
            semester_year + '-01-01')
        self.browser.find_element_by_name('start_time').send_keys(
            '00:00')
        self.browser.find_element_by_name('end_date').send_keys(
            semester_year + '-07-01')
        self.browser.find_element_by_name('end_time').send_keys(
            '00:00')
        self.browser.find_element_by_name('description').send_keys(
            'This is the semester description.')

        self._save_screenshot(self.admin_image_root, 'semester_new')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'New semester "{}" has been created.'.format(semester_name),
            self.browser.page_source)

        # Create a new queue.
        self.browser.get(admin_menu_url)
        self.browser.find_element_by_link_text('Queues').click()
        self.browser.find_element_by_link_text('New queue').click()

        queue_name = 'International'
        self.browser.find_element_by_name('queue_name').send_keys(queue_name)
        self.browser.find_element_by_name('queue_code').send_keys('I')
        self.browser.find_element_by_name('description').send_keys(
            'This is the queue description.')

        self._save_screenshot(self.admin_image_root, 'queue_new')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'New queue "{}" has been added.'.format(queue_name),
            self.browser.page_source)

        affiliation_edit = self.browser.find_element_by_link_text(
            'Edit affiliations')

        self._save_screenshot(self.admin_image_root, 'queue_view',
                              [affiliation_edit])

        affiliation_edit.click()

        affiliation_add = self.browser.find_element_by_id('add_affiliation')
        affiliation_add.click()
        affiliation_add.click()
        affiliation_add.click()

        self.browser.find_element_by_name('name_new_1').send_keys('China')
        self.browser.find_element_by_name('name_new_2').send_keys('Japan')
        self.browser.find_element_by_name('name_new_3').send_keys('Other')

        self._save_screenshot(self.admin_image_root, 'queue_affiliation',
                              [affiliation_add])

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The affiliations have been updated.',
            self.browser.page_source)

        # Create a call.
        self.browser.get(admin_menu_url)
        self.browser.find_element_by_link_text('Calls').click()
        self.browser.find_element_by_link_text('New call').click()

        current_year = str(current_date.year)
        self.browser.find_element_by_name('open_date').send_keys(
            current_year + '-01-01')
        self.browser.find_element_by_name('open_time').send_keys(
            '00:00')
        self.browser.find_element_by_name('close_date').send_keys(
            current_year + '-12-31')
        self.browser.find_element_by_name('close_time').send_keys(
            '23:59')

        self._save_screenshot(self.admin_image_root, 'call_new')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The new call has been added.',
            self.browser.page_source)

        # Add categories.
        self.browser.get(admin_menu_url)
        self.browser.find_element_by_link_text('Categories').click()

        category_add = self.browser.find_element_by_id('add_category')
        category_add.click()
        category_add.click()

        self.browser.find_element_by_name('name_new_1').send_keys(
            'Star formation')
        self.browser.find_element_by_name('name_new_2').send_keys(
            'Cosmology')

        self._save_screenshot(self.admin_image_root, 'category',
                              [category_add])

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The categories have been updated.',
            self.browser.page_source)

        return semester_name

    def create_proposal(self, facility_code, semester_name):
        self.browser.get(self.base_url + facility_code)

        semester_link = self.browser.find_element_by_link_text(semester_name)

        self._save_screenshot(self.user_image_root, 'facility_home',
                              [semester_link])

        semester_link.click()

        queue_link = self.browser.find_element_by_link_text(
            'Create a proposal for the International Queue')

        self._save_screenshot(self.user_image_root, 'call_view', [queue_link])

        queue_link.click()

        Select(
            self.browser.find_element_by_name('affiliation_id')
        ).select_by_visible_text('Other')

        self.browser.find_element_by_name('proposal_title').send_keys(
            'An Example Proposal')

        self._save_screenshot(self.user_image_root, 'proposal_new')

        self.browser.find_element_by_name('submit-new').click()

        self.assertIn(
            'Your new proposal has been created.',
            self.browser.page_source)

        self._save_screenshot(
            self.user_image_root, 'proposal_view',
            ['submit_proposal_link', 'personal_dashboard_link',
             'proposal_identifier_cell'])

        # Add another member to the proposal.
        self.browser.find_element_by_link_text('Add member').click()

        Select(
            self.browser.find_element_by_name('person_id')
        ).select_by_visible_text(
            'Another Person, Test Institution, United States')

        for affiliation_selection in self.browser.find_elements_by_name(
                'affiliation_id'):
            Select(affiliation_selection).select_by_visible_text('Other')

        self._save_screenshot(self.user_image_root, 'member_add')

        self.browser.find_element_by_name('submit-link').click()

        self.assertIn(
            'has been added to the proposal.',
            self.browser.page_source)

        self.browser.find_element_by_link_text('Edit members').click()

        self.browser.find_element_by_name('observer_1').click()

        self._save_screenshot(self.user_image_root, 'member_edit')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The proposal member list has been updated.',
            self.browser.page_source)

        self.browser.find_element_by_link_text('Edit student list').click()

        self.browser.find_element_by_name('student_2').click()

        self._save_screenshot(self.user_image_root, 'member_student')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The list of students has been updated.',
            self.browser.page_source)

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
