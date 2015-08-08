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
import os
from threading import Thread

from flask import request, make_response
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.common.exceptions import NoSuchElementException
from sqlalchemy.sql import select

from hedwig import auth
from hedwig.config import get_config
from hedwig.db.meta import invitation, reset_token, verify_token
from hedwig.file.poll import process_proposal_figure
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
                               public_profile=True,
                               screenshot_path=self.user_image_root)

            self.log_out_user()

            self.register_user(user_name='username2',
                               person_name='Another Person',
                               public_profile=True)

            self.log_out_user()

            # Log in as administrative user and set up a semester.
            self.log_in_user(user_name='test')

            semester_name = self.set_up_facility('jcmt')

            self.log_out_user()

            # Log back in a normal use and create a proposal.
            self.log_in_user(user_name='username')

            self.create_proposal('jcmt', semester_name)

            self.view_dashboard()

            self.log_out_user()

            # Try accepting an invitation.
            self.accept_invitation()

            self.log_out_user()

            # Try managing an account
            self.log_in_user(user_name='username')

            self.manage_account()

            self.log_out_user()

            self.reset_password()

        finally:
            self.browser.get(self.base_url + 'shutdown')
            self.browser.quit()

    def register_user(self, user_name, person_name, person_email='a@a',
                      password='password',
                      institution_name='Test Institution',
                      institution_country='United States',
                      public_profile=False,
                      screenshot_path=None):
        self.browser.get(self.base_url)

        log_in = self.browser.find_element_by_link_text('Log in')

        self._save_screenshot(screenshot_path, 'home_page', highlight=[log_in])

        log_in.click()
        self.browser.find_element_by_link_text('register').click()

        self._do_register_user(user_name, password, screenshot_path)

        self.browser.find_element_by_name('person_name').send_keys(person_name)

        if public_profile:
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

    def _do_register_user(self, user_name, password, screenshot_path=None):
        self.browser.find_element_by_name('user_name').send_keys(user_name)
        self.browser.find_element_by_name('password').send_keys(password)
        self.browser.find_element_by_name('password_check').send_keys(password)

        self._save_screenshot(screenshot_path, 'user_new')

        self.browser.find_element_by_name('submit').click()

        self.assertIn('Your user account has been created.',
                      self.browser.page_source)

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

        # Upload a MOC.
        self.browser.get(admin_menu_url)
        self.browser.find_element_by_link_text('Clash tool coverage').click()

        self.browser.find_element_by_link_text('New coverage map').click()

        self.browser.find_element_by_name('name').send_keys('Example')
        self.browser.find_element_by_name('description').send_keys(
            'This area is part of the "..." survey and ...')

        # Give path to MOC assuming we are in the top level directory.
        self.browser.find_element_by_name('file').send_keys(
            os.path.join(os.getcwd(), 'util', 'selenium',
                         'data', 'example_moc.fits'))

        self._save_screenshot(self.admin_image_root, 'moc')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The new coverage map has been stored.',
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

        proposal_url = self.browser.current_url

        # Add other members to the proposal.
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

        self.browser.find_element_by_link_text('Add member').click()

        for affiliation_selection in self.browser.find_elements_by_name(
                'affiliation_id'):
            Select(affiliation_selection).select_by_visible_text('Other')

        self.browser.find_element_by_name('name').send_keys('Invited Member')
        self.browser.find_element_by_name('email').send_keys(
            'invitee@somewhere.edu')

        self.browser.find_element_by_name('submit-invite').click()

        self.assertIn(
            'has been added to the proposal.',
            self.browser.page_source)

        self.browser.find_element_by_name('institution_name').send_keys(
            'Your Institution')
        Select(
            self.browser.find_element_by_name('country_code')
        ).select_by_visible_text('United States')

        self.browser.find_element_by_name('submit_add').click()
        self.assertIn(
            'The institution has been recorded.',
            self.browser.page_source)

        # Try submitting the proposal now -- this will generate errors,
        # and should not allow use to submit.
        self.browser.find_element_by_link_text('Submit proposal').click()

        self.assertIn(
            'Please correct the errors identified above before submitting',
            self.browser.page_source)

        with self.assertRaises(NoSuchElementException):
            self.browser.find_element_by_name('submit_confirm')

        self._save_screenshot(self.user_image_root, 'submit_error')

        self.browser.get(proposal_url)

        # Edit the title and abstract.
        self.browser.find_element_by_link_text('Edit title').click()

        self._save_screenshot(self.user_image_root, 'title_edit')

        self.browser.find_element_by_name('submit').click()

        # (Hedwig currently shows this flash message even if the title
        # didn't change.)
        self.assertIn(
            'The proposal title has been changed.',
            self.browser.page_source)

        self.browser.find_element_by_partial_link_text('Edit abstract').click()

        self.browser.find_element_by_name('category_1').click()
        self.browser.find_element_by_name('text').send_keys(
            'This is an example proposal.')

        self._save_screenshot(self.user_image_root, 'abstract_edit')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The abstract has been saved.',
            self.browser.page_source)

        # Create an observing request.
        self.browser.find_element_by_link_text(
            'Edit observing request').click()

        self.browser.find_element_by_id('add_request').click()

        Select(
            self.browser.find_element_by_name('instrument_new_1')
        ).select_by_visible_text('SCUBA-2')
        Select(
            self.browser.find_element_by_name('instrument_new_2')
        ).select_by_visible_text('HARP')

        Select(
            self.browser.find_element_by_name('weather_new_1')
        ).select_by_visible_text('Band 1')
        Select(
            self.browser.find_element_by_name('weather_new_2')
        ).select_by_visible_text('Band 5')

        self.browser.find_element_by_name('time_new_1').send_keys(4)

        self.browser.find_element_by_name('time_new_2').send_keys(12)

        self._save_screenshot(self.user_image_root, 'request_edit')

        self.browser.find_element_by_name('submit-save').click()

        self.assertIn(
            'The observing request has been saved.',
            self.browser.page_source)

        # Add a previous proposal.
        self.browser.find_element_by_partial_link_text(
            'Edit previous proposals').click()

        self.browser.find_element_by_name('code_new_1').send_keys('M00AI000')

        Select(
            self.browser.find_element_by_name('pub_type_0_new_1')
        ).select_by_visible_text('ADS bibcode')
        self.browser.find_element_by_name('publication_0_new_1').send_keys(
            '2013MNRAS.430.2513H')

        Select(
            self.browser.find_element_by_name('pub_type_1_new_1')
        ).select_by_visible_text('ADS bibcode')
        self.browser.find_element_by_name('publication_1_new_1').send_keys(
            '2013MNRAS.430.2534D')

        self._save_screenshot(self.user_image_root, 'prev_proposal')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The previous proposals list has been saved.',
            self.browser.page_source)

        # Add target objects.
        self.browser.find_element_by_link_text('Edit targets').click()

        self.browser.find_element_by_id('add_target').click()

        self.browser.find_element_by_name('name_new_1').send_keys('LDN 123')
        self.browser.find_element_by_name('name_new_2').send_keys('LDN 456')
        self.browser.find_element_by_id('resolve_new_1').click()
        self.browser.find_element_by_id('resolve_new_2').click()
        self.browser.find_element_by_name('time_new_1').send_keys('8')
        self.browser.find_element_by_name('time_new_2').send_keys('8')
        self.browser.find_element_by_name('priority_new_1').send_keys('1')
        self.browser.find_element_by_name('priority_new_2').send_keys('2')

        # Wait for the resolver to finish.
        wait = WebDriverWait(self.browser, 10)
        wait.until(expected_conditions.text_to_be_present_in_element_value((
            By.NAME, 'x_new_1'), ':'))
        wait.until(expected_conditions.text_to_be_present_in_element_value((
            By.NAME, 'x_new_2'), ':'))

        self.assertTrue(self.browser.find_element_by_name(
            'x_new_1').get_attribute('value').startswith('18:07:'))
        self.assertTrue(self.browser.find_element_by_name(
            'y_new_1').get_attribute('value').startswith('-27:25:'))
        self.assertTrue(self.browser.find_element_by_name(
            'x_new_2').get_attribute('value').startswith('18:52:'))
        self.assertTrue(self.browser.find_element_by_name(
            'y_new_2').get_attribute('value').startswith('-10:55:'))

        self._save_screenshot(self.user_image_root, 'target_edit')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The target object list has been saved.',
            self.browser.page_source)

        self.browser.find_element_by_link_text('Upload target list').click()

        self.assertIn(
            'A target list can be uploaded as a plain text file',
            self.browser.page_source)

        self._save_screenshot(self.user_image_root, 'target_upload')

        self.browser.get(proposal_url)

        self.browser.find_element_by_link_text('Clash Tool').click()

        self._save_screenshot(self.user_image_root, 'target_clash')

        self.browser.find_element_by_link_text('Back to proposal').click()

        self.browser.find_element_by_link_text('Edit note').click()

        self.browser.find_element_by_name('text').send_keys(
            'I used the clash tool and I found ...')

        self._save_screenshot(self.user_image_root, 'target_note')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The note on tool results has been saved.',
            self.browser.page_source)

        # Add an integration time calculation.
        self.browser.find_element_by_link_text('SCUBA-2 ITC').click()

        position = self.browser.find_element_by_name('pos')
        position.clear()
        position.send_keys('-10')

        rms = self.browser.find_element_by_name('rms')
        rms.clear()
        rms.send_keys('1.343')

        self.browser.find_element_by_name('submit_calc').click()

        self.assertIn(
            'Results',
            self.browser.page_source)

        self.browser.find_element_by_name('calculation_title').send_keys(
            'SCUBA-2 observation of LDN 456')

        submit_save_redir = self.browser.find_element_by_name(
            'submit_save_redir')

        self._save_screenshot(self.user_image_root, 'calc_scuba2',
                              [submit_save_redir, 'main_result_table'])

        submit_save_redir.click()

        self.assertIn(
            'The calculation has been saved',
            self.browser.page_source)

        # Edit technical justification.
        self.browser.find_element_by_link_text(
            'Edit technical justification').click()

        tech_case_url = self.browser.current_url

        edit_text_link = self.browser.find_element_by_link_text('Edit text')
        upload_pdf_link = self.browser.find_element_by_link_text(
            'Upload new PDF file')

        self._save_screenshot(self.user_image_root, 'tech_case_edit',
                              [edit_text_link, upload_pdf_link])

        upload_pdf_link.click()

        self.assertIn(
            'Upload Technical Justification PDF',
            self.browser.page_source)

        self._save_screenshot(self.user_image_root, 'tech_case_pdf')

        self.browser.get(tech_case_url)

        self.browser.find_element_by_link_text('Edit text').click()

        self.browser.find_element_by_name('text').send_keys(
            'We plan to observe ...')

        self._save_screenshot(self.user_image_root, 'tech_case_text',
                              ['text_words'])

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The technical justification has been saved.',
            self.browser.page_source)

        self.browser.find_element_by_link_text('Back to proposal').click()

        # Edit scientific justification.
        self.browser.find_element_by_link_text(
            'Edit scientific justification').click()

        sci_case_url = self.browser.current_url

        self.browser.find_element_by_link_text('Upload new figure').click()

        self.browser.find_element_by_name('text').send_keys(
            'An example figure showing ...')

        self._save_screenshot(self.user_image_root, 'sci_case_fig')

        self.browser.find_element_by_name('file').send_keys(
            os.path.join(os.getcwd(), 'util', 'selenium',
                         'data', 'example_figure.png'))

        self.browser.find_element_by_name('submit').click()

        # Process the uploaded figure and reload.
        n_processed = process_proposal_figure(db=self.db)

        self.assertEqual(n_processed, 1)

        self.browser.get(sci_case_url)

        manage_figures = self.browser.find_element_by_link_text(
            'Manage figures')

        self._save_screenshot(self.user_image_root, 'sci_case_edit',
                              [manage_figures, 'edit_figure_1_link'])

        manage_figures.click()

        self._save_screenshot(self.user_image_root, 'sci_case_fig_manage')

        self.browser.find_element_by_name('submit').click()

        self.browser.find_element_by_link_text('Edit text').click()

        self.browser.find_element_by_name('text').send_keys(
            'The scientific rationale for this project is ...')

        self._save_screenshot(self.user_image_root, 'sci_case_text',
                              ['text_words'])

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The scientific justification has been saved.',
            self.browser.page_source)

        self.browser.find_element_by_link_text('Back to proposal').click()

        # Submit the proposal (should stay at the end to minimize warnings
        # on the submission page).
        self.browser.find_element_by_link_text('Submit proposal').click()

        self._save_screenshot(self.user_image_root, 'submit_ok')

        self.browser.find_element_by_name('submit_confirm').click()

        self.assertIn(
            'The proposal has been submitted.',
            self.browser.page_source)

        self.browser.find_element_by_link_text('Validate proposal').click()

        self._save_screenshot(self.user_image_root, 'validate')

        self.browser.find_element_by_link_text('Back to proposal').click()

        # Grab a screenshot of the complete proposal now.
        self._save_screenshot(self.user_image_root, 'proposal_complete',
                              ['proposal_status_cell'])

        self.browser.find_element_by_link_text('Withdraw proposal').click()

        self._save_screenshot(self.user_image_root, 'withdraw')

        self.browser.find_element_by_name('submit_confirm').click()

        self.assertIn(
            'The proposal has been withdrawn.',
            self.browser.page_source)

    def view_dashboard(self):
        # Test the personal dashboard.
        self.browser.get(self.base_url + 'dashboard')

        self.assertIn(
            'Personal Dashboard',
            self.browser.page_source)

        self.assertIn(
            'An Example Proposal',
            self.browser.page_source)

        self._save_screenshot(self.user_image_root, 'dashboard')

    def accept_invitation(self):
        # Determine the invitation token to use.
        with self.db._transaction() as conn:
            token = conn.execute(select([invitation.c.token])).scalar()

        self.browser.get(self.base_url)

        self.browser.find_element_by_link_text(
            'Enter an invitation code').click()

        self.browser.find_element_by_name('token').send_keys(token)

        self._save_screenshot(self.user_image_root, 'invitation_enter')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'Please log in or register for an account to proceed.',
            self.browser.page_source)

        self.browser.find_element_by_link_text('register').click()

        self._do_register_user('invitee', 'password')

        self._save_screenshot(self.user_image_root, 'invitation_accept')

        self.browser.find_element_by_name('submit-accept').click()

        self.assertIn(
            'The invitation has been accepted successfully.',
            self.browser.page_source)

        # Now remove self from the proposal.
        self.browser.find_element_by_link_text(
            'Remove yourself from this proposal').click()

        self.assertIn(
            'Are you sure you wish to remove yourself',
            self.browser.page_source)

        self.browser.find_element_by_name('submit_confirm').click()

        self.assertIn(
            'You have been removed from proposal',
            self.browser.page_source)

    def manage_account(self):
        self.browser.find_element_by_id('user_profile_link').click()

        self._save_screenshot(
            self.user_image_root, 'profile_edit_links',
            ['account_manage_links', 'profile_manage_links',
             self.browser.find_element_by_link_text('verify')])

        # Change password.
        self.browser.find_element_by_link_text('Change password').click()

        self.browser.find_element_by_name('password').send_keys('password')
        self.browser.find_element_by_name('password_new').send_keys(
            'new-pass')
        self.browser.find_element_by_name('password_check').send_keys(
            'new-pass')

        self._save_screenshot(self.user_image_root, 'password_change')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'Your password has been changed.',
            self.browser.page_source)

        # Change user name.
        self.browser.find_element_by_link_text('Change user name').click()

        user_name_box = self.browser.find_element_by_name('user_name')
        user_name_box.clear()
        user_name_box.send_keys('newusername')
        self.browser.find_element_by_name('password').send_keys('new-pass')

        self._save_screenshot(self.user_image_root, 'user_name_change')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'Your user name has been changed.',
            self.browser.page_source)

        # Edit profile.
        self.browser.find_element_by_link_text('Edit profile').click()

        self.assertIn(
            'Show in directory',
            self.browser.page_source)

        self._save_screenshot(self.user_image_root, 'profile_edit')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'Your user profile has been saved.',
            self.browser.page_source)

        # Edit email addresses.
        self.browser.find_element_by_link_text('Edit email addresses').click()

        self.assertIn(
            'not verified',
            self.browser.page_source)

        self._save_screenshot(self.user_image_root, 'email_edit',
                              ['delete_2', 'add_email'])

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'Your email addresses have been updated.',
            self.browser.page_source)

        # Verify email address.
        self.browser.find_element_by_link_text('verify').click()

        self.assertIn(
            'You can verify your address by sending a verification',
            self.browser.page_source)

        self.browser.find_element_by_name('submit_sent').click()

        self.assertIn(
            'Your address verification code has been sent by email to',
            self.browser.page_source)

        with self.db._transaction() as conn:
            token = conn.execute(select([verify_token.c.token])).scalar()

        self.browser.find_element_by_name('token').send_keys(token)

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'Your email address example@somewhere.edu has been verified.',
            self.browser.page_source)

        # Change institution.
        self.browser.find_element_by_link_text('Change institution').click()

        self.assertIn(
            'If you would like to make minor corrections',
            self.browser.page_source)

        self.browser.find_element_by_name('institution_name').send_keys(
            'Another Institution')

        Select(
            self.browser.find_element_by_name('country_code')
        ).select_by_visible_text('United States')

        self._save_screenshot(self.user_image_root, 'institution_change')

        self.browser.find_element_by_name('submit_add').click()

        self.assertIn(
            'Your institution has been recorded.',
            self.browser.page_source)

        self.browser.find_element_by_link_text('Change institution').click()

        Select(
            self.browser.find_element_by_name('institution_id')
        ).select_by_visible_text(
            'Test Institution, United States')

        self.browser.find_element_by_name('submit_select').click()

        self.assertIn(
            'Your institution has been selected.',
            self.browser.page_source)

        # View institution.
        self.browser.find_element_by_partial_link_text(
            'Test Institution').click()

        edit_institution = self.browser.find_element_by_link_text(
            'Edit this institution')

        self._save_screenshot(self.user_image_root, 'institution_view',
                              [edit_institution])

        edit_institution.click()

        self.assertIn(
            'Are you sure you want to edit this institution?',
            self.browser.page_source)

        self.browser.find_element_by_name('submit-confirm').click()

        self._save_screenshot(self.user_image_root, 'institution_edit')

        self.browser.find_element_by_name('submit-edit').click()

        self.assertIn(
            'The institution\'s record has been updated.',
            self.browser.page_source)

        # Institution list.
        self.browser.find_element_by_link_text('Institutions').click()

        self.assertIn(
            '<h1>Institutions</h1>',
            self.browser.page_source)

        # User directory.
        self.browser.find_element_by_id('user_profile_link').click()

        self.browser.find_element_by_link_text('User Directory').click()

        self.assertIn(
            '<h1>Directory of Users</h1>',
            self.browser.page_source)

    def reset_password(self):
        self.browser.find_element_by_link_text('Log in').click()

        reset_password = self.browser.find_element_by_link_text(
            'reset your password')

        self._save_screenshot(self.user_image_root, 'pass_reset_link',
                              [reset_password])

        reset_password.click()

        self.browser.find_element_by_name('email').send_keys(
            'example@somewhere.edu')

        self._save_screenshot(self.user_image_root, 'pass_reset_get')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'Your password reset code has been sent',
            self.browser.page_source)

        with self.db._transaction() as conn:
            token = conn.execute(select([reset_token.c.token])).scalar()

        self.browser.find_element_by_name('token').send_keys(token)
        self.browser.find_element_by_name('password').send_keys(
            'password')
        self.browser.find_element_by_name('password_check').send_keys(
            'password')

        self._save_screenshot(self.user_image_root, 'pass_reset_use')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'Your password has been changed.',
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
