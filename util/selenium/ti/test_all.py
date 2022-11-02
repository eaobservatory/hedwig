# Copyright (C) 2015-2022 East Asian Observatory
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
import logging
import os
from threading import Thread
from time import sleep

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
from hedwig.admin.proposal import close_call_proposals
from hedwig.compat import first_value, string_type
from hedwig.config import get_config
from hedwig.db.meta import invitation, reset_token, verify_token
from hedwig.admin.poll import send_proposal_feedback
from hedwig.file.poll import process_moc, \
    process_proposal_figure, process_proposal_pdf, \
    process_review_figure
from hedwig.request.poll import process_request_prop_copy
from hedwig.type.enum import BaseReviewerRole, MessageState, ProposalState
from hedwig.view.query import QueryView
from hedwig.web.app import create_web_app

from test.dummy_config import DummyConfigTestCase
from test.dummy_db import get_dummy_database


class DummyServer(Thread):
    def __init__(self, db):
        Thread.__init__(self)
        self.app = create_web_app(db=db)

        log_handler = logging.StreamHandler()
        log_handler.setLevel(logging.WARNING)
        self.app.logger.addHandler(log_handler)

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
        self.review_image_root = os.path.join('doc', 'review', 'image')
        self.admin_image_root = os.path.join('doc', 'admin', 'image')

        self.db = get_dummy_database(randomize_ids=False,
                                     allow_multi_threaded=True)
        self.server = DummyServer(self.db)

        self.browser = webdriver.Firefox(
            firefox_binary=FirefoxBinary(config.get('utilities', 'firefox')))
        self.browser.set_window_size(1200, 800)

        self.server.start()

        sleep(1)

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

            self.register_user(user_name='tech1',
                               person_name='Example Technical Assessor')

            self.log_out_user()

            self.register_user(user_name='group1',
                               person_name='Example Group Member')

            self.log_out_user()

            self.register_user(user_name='group2',
                               person_name='Another Group Member')

            self.log_out_user()

            self.register_user(user_name='noprofile', person_name=None)

            self.log_out_user()

            # Log in as administrative user and set up a semester.
            # (Process the MOC so that it can be searched later.)
            self.log_in_user(user_name='test')

            (semester_name, queue_name) = self.set_up_facility('jcmt')

            self.log_out_user()

            process_moc(self.db)

            # While we have the MOC set up (we delete it later), test the
            # target tools in stand-alone mode.
            self.try_jcmt_tools()

            # Log back in a normal use and create a proposal.
            self.log_in_user(user_name='username')

            self.create_proposal('jcmt', semester_name)

            self.view_person_proposals()

            self.log_out_user()

            # View user directory while there is an unregistered invitee.
            self.log_in_user(user_name='test')

            self.view_user_directory()

            self.log_out_user()

            # Try accepting an invitation.
            self.accept_invitation(screenshot_path=self.user_image_root)

            self.remove_self()

            self.log_out_user()

            # Try managing an account
            self.log_in_user(user_name='username')

            self.manage_account()

            self.log_out_user()

            self.reset_password()

            self.log_in_user(user_name='test')

            self.administer_facility('jcmt', semester_name, queue_name)

            # Set up review process.
            close_call_proposals(self.db, 1)

            self.set_up_review('jcmt')

            self.log_out_user()

            # Enter a technical assessment.
            self.log_in_user(user_name='tech1')

            self.enter_technical_assessment()

            self.log_out_user()

            # Enter an external review.
            self.accept_invitation(user_name='invitee2',
                                   screenshot_path=self.review_image_root)

            self.enter_review()

            self.view_person_reviews()

            self.log_out_user()

            # Enter committee reviews.
            self.log_in_user(user_name='group1')

            self.enter_cttee_review(
                'TAC Primary', '60', 'Expert',
                screenshot_path=self.review_image_root)

            self.log_out_user()

            self.log_in_user(user_name='group2')

            self.enter_cttee_review(
                'TAC Secondary', '40', 'Intermediate')

            self.log_out_user()

            # View the completed review.
            self.log_in_user(user_name='test')

            self.view_proposal_reviews('jcmt')

            self.administer_site()

            semester_name = self.open_new_call('jcmt')

            self.log_out_user()

            # Log back in as the proposal author to view the feedback page.
            # (Note changed user name and need to process feedback to put the
            # proposal into its final state.)
            send_proposal_feedback(self.db)

            self.log_in_user(user_name='newusername')

            self.view_proposal_feedback('jcmt', 1)

            # Also try copying the proposal into the rapid turnaround call.
            self.copy_proposal('jcmt', None, 'Rapid Turnaround',
                               screenshot_path=self.user_image_root)

            self.log_out_user()

            self.log_in_user(user_name='username2')

            self.copy_proposal('jcmt', None, 'Rapid Turnaround')

            self.log_out_user()

            # Set up peer review process.
            for proposal_id in (2, 3):
                self.db.update_proposal(
                    proposal_id, state=ProposalState.REVIEW)

            self.log_in_user(user_name='test')

            self.set_up_peer_review('jcmt')

            self.log_out_user()

            self.log_in_user(user_name='newusername')

            self.enter_peer_review()

            self.log_out_user()

            # Try the JCMT stand-alone ITCs
            self.try_jcmt_itcs()

        except:
            # In the event of an error, pause in case the cause of the
            # error is visible in the web browser.
            sleep(10)
            raise

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

        if person_name is None:
            return

        self.browser.find_element_by_name('person_name').send_keys(person_name)

        if public_profile:
            self.browser.find_element_by_name('person_public').click()

        self.browser.find_element_by_name('single_email').send_keys(
            person_email)

        self._save_screenshot(screenshot_path, 'profile_new')

        self.browser.find_element_by_name('submit').click()

        self.assertIn('Your user profile has been saved.',
                      self.browser.page_source)

        self._do_verify_email(person_email, screenshot_path=screenshot_path)

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

    def _do_verify_email(self, email_address, screenshot_path=None):
        self.assertIn(
            'You can verify your address by sending a verification',
            self.browser.page_source)

        self._save_screenshot(screenshot_path, 'email_verify_get')

        self.browser.find_element_by_name('submit_send').click()

        self.assertIn(
            'Your address verification code has been sent by email to',
            self.browser.page_source)

        self._save_screenshot(screenshot_path, 'email_verify_use')

        with self.db._transaction() as conn:
            token = conn.execute(select([verify_token.c.token])).scalar()

        self.browser.find_element_by_name('token').send_keys(token)

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'Your email address {} has been verified.'.format(email_address),
            self.browser.page_source)

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

        facility_home_url = self.browser.current_url

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
        semester_name = self._create_semester(
            'A', screenshot_path=self.admin_image_root)

        # Create a new queue.
        self.browser.get(admin_menu_url)
        self.browser.find_element_by_link_text('Queues').click()
        self.browser.find_element_by_link_text('New queue').click()

        queue_name = 'PI Science'
        self.browser.find_element_by_name('queue_name').send_keys(queue_name)
        self.browser.find_element_by_name('queue_code').send_keys('P')
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
        Select(
            self.browser.find_element_by_name('type_new_3')
        ).select_by_visible_text('Excluded')

        self._save_screenshot(self.admin_image_root, 'queue_affiliation',
                              [affiliation_add])

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The affiliations have been updated.',
            self.browser.page_source)

        # Create a call.
        self.browser.get(admin_menu_url)
        self._create_call(
            'Regular', semester_name, screenshot_path=self.admin_image_root)

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
        self.browser.get(facility_home_url)
        self.browser.find_element_by_link_text('Clash Tool').click()
        self.browser.find_element_by_link_text('View all defined areas of sky coverage').click()

        self.browser.find_element_by_link_text('New coverage map').click()

        self.browser.find_element_by_name('name').send_keys('Example')
        self.browser.find_element_by_name('description').send_keys(
            'This area is part of the "..." survey and ...')

        # Give path to MOC assuming we are in the top level directory.
        self.browser.find_element_by_name('file').send_keys(
            self._get_example_path('example_moc.fits'))

        self._save_screenshot(self.admin_image_root, 'moc')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The new coverage map has been stored.',
            self.browser.page_source)

        return (semester_name, queue_name)

    def _create_semester(self, suffix, screenshot_path=None):
        self.browser.find_element_by_link_text('Semesters').click()
        self.browser.find_element_by_link_text('New semester').click()

        # Make sure we are going to generate a semester which is open for
        # submissions: base it on the current date and use JCMT naming.
        current_date = datetime.utcnow()
        semester_year = str(current_date.year + 1)
        semester_name = semester_year[2:] + suffix
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
            'The instrumentation available is as follows ...')

        self._save_screenshot(screenshot_path, 'semester_new')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'New semester "{}" has been created.'.format(semester_name),
            self.browser.page_source)

        # Enter the call preamble.
        preamble_link = self.browser.find_element_by_id('preamble_edit_1')
        self._save_screenshot(
            screenshot_path, 'semester_view', [preamble_link])
        preamble_link.click()

        self.browser.find_element_by_name('description').send_keys(
            'We invite proposals ...')
        self._save_screenshot(screenshot_path, 'call_preamble')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The regular call preamble for semester {} '
            'has been saved.'.format(semester_name),
            self.browser.page_source)

        return semester_name

    def _create_call(self, type_name, semester_name, screenshot_path=None):
        self.browser.find_element_by_link_text('Calls').click()

        self._save_screenshot(screenshot_path, 'call_list_empty',
                              ['new_call_links'])

        self.browser.find_element_by_link_text(type_name).click()

        Select(
            self.browser.find_element_by_name('semester_id')
        ).select_by_visible_text(semester_name)

        current_date = datetime.utcnow()
        current_year = str(current_date.year)
        self.browser.find_element_by_name('open_date').send_keys(
            current_year + '-01-01')
        self.browser.find_element_by_name('open_time').send_keys(
            '00:00')
        self.browser.find_element_by_name('close_date').send_keys(
            current_year + '-12-31')
        self.browser.find_element_by_name('close_time').send_keys(
            '23:59')

        self._save_screenshot(screenshot_path, 'call_new')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The new call has been added.',
            self.browser.page_source)

    def create_proposal(self, facility_code, semester_name):
        self.browser.get(self.base_url + facility_code)

        semester_link = self.browser.find_element_by_link_text(semester_name)

        self._save_screenshot(self.user_image_root, 'facility_home',
                              [semester_link])

        semester_link.click()

        queue_link = self.browser.find_element_by_link_text(
            'Create a proposal for the PI Science Queue')

        self._save_screenshot(self.user_image_root, 'call_view', [queue_link])

        queue_link.click()

        Select(
            self.browser.find_element_by_name('affiliation_id')
        ).select_by_visible_text('China')

        self.browser.find_element_by_name('proposal_title').send_keys(
            'An Example Proposal')

        self._save_screenshot(self.user_image_root, 'proposal_new')

        self.browser.find_element_by_name('submit_new').click()

        self.assertIn(
            'Your new proposal has been created.',
            self.browser.page_source)

        self.browser.find_element_by_id('callout_dismiss').click()

        self._save_screenshot(
            self.user_image_root, 'proposal_view',
            ['submit_proposal_link', 'person_proposals_link',
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

        self.browser.find_element_by_name('submit_link').click()

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

        self.browser.find_element_by_name('submit_invite').click()

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

        # Try re-sending the invitation email.
        self.browser.find_element_by_link_text('Re-send invitation').click()

        self.assertIn(
            'Would you like to re-send an invitation',
            self.browser.page_source)

        self.browser.find_element_by_name('submit_confirm').click()

        self.assertIn(
            'has been re-invited to the proposal',
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

        # Edit the public summary.
        self.browser.find_element_by_partial_link_text(
            'Edit public summary').click()

        self.browser.find_element_by_name('text').send_keys(
            'We are observing ...')

        self._save_screenshot(self.user_image_root, 'jcmt_pr_summary_edit')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The public summary has been saved.',
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
        ).select_by_value('1')
        Select(
            self.browser.find_element_by_name('weather_new_2')
        ).select_by_value('5')

        self.browser.find_element_by_name('time_new_1').send_keys(4)

        self.browser.find_element_by_name('time_new_2').send_keys(12)

        self._save_screenshot(self.user_image_root, 'request_edit')

        self.browser.find_element_by_name('submit_save').click()

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

        # Place these targets in the name resolver proxy's fixed target list
        # so that we don't have to connect to CADC to resolve them.
        QueryView.add_fixed_name_response(
            'LDN 123', '{"target":"LDN 123","service":"Hedwig(fixed)",'
            '"coordsys":"ICRS","ra":271.9,"dec":-27.4167,"time":1}')
        QueryView.add_fixed_name_response(
            'LDN 456', '{"target":"LDN 456","service":"Hedwig(fixed)",'
            '"coordsys":"ICRS","ra":283.2,"dec":-10.9333,"time":0}')

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

        self.browser.find_element_by_link_text('Target Availability').click()

        self._save_screenshot(self.user_image_root, 'target_avail')

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
        self._add_itc_calculation(
            screenshot_path=self.user_image_root,
            highlight_extra=['main_result_table', 'perm_query_link'])

        # Edit technical justification.
        self.browser.find_element_by_link_text(
            'Edit technical justification').click()

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

        self.browser.find_element_by_name('file').send_keys(
            self._get_example_path('example_justification.pdf'))

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The technical justification has been uploaded.',
            self.browser.page_source)

        self.assertIn(
            'Not yet processed',
            self.browser.page_source)

        n_processed = process_proposal_pdf(db=self.db)

        self.assertEqual(n_processed, 1)

        self.browser.get(self.browser.current_url)

        self.assertIn(
            'Processed successfully',
            self.browser.page_source)

        self._save_screenshot(self.user_image_root, 'tech_case_pdf_uploaded')

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

        self._add_figure(
            screenshot_path=self.user_image_root,
            screenshot_prefix='sci_case')

        manage_figures = self.browser.find_element_by_link_text(
            'Manage figures')

        self._save_screenshot(self.user_image_root, 'sci_case_edit',
                              [manage_figures, 'edit_figure_1_link'])

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
        self._submit_proposal(screenshot_path=self.user_image_root)

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

        # Re-submit the proposal so that we can use it to test the review
        # system later.
        self._submit_proposal()

        # Test more source list upload.
        self.browser.find_element_by_link_text('Upload target list').click()

        self.browser.find_element_by_name('file').send_keys(
            self._get_example_path('example_list.txt'))

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The target object list has been updated.',
            self.browser.page_source)

        self.assertIn('LDN 123', self.browser.page_source)
        self.assertIn('LDN 456', self.browser.page_source)
        self.assertIn('NGC 1234', self.browser.page_source)

    def _submit_proposal(self, screenshot_path=None):
        self.browser.find_element_by_link_text('Submit proposal').click()

        self._save_screenshot(screenshot_path, 'submit_ok')

        self.browser.find_element_by_name('submit_confirm').click()

        self.assertIn(
            'The proposal has been submitted.',
            self.browser.page_source)

    def _add_figure(
            self,
            screenshot_path=None,
            screenshot_prefix='component',
            is_review=False):
        current_url = self.browser.current_url

        self.browser.find_element_by_link_text('Upload new figure').click()

        self.browser.find_element_by_name('text').send_keys(
            'An example figure showing ...')

        self._save_screenshot(
            screenshot_path, '{}_{}'.format(screenshot_prefix, 'fig'))

        self.browser.find_element_by_name('file').send_keys(
            self._get_example_path('example_figure.png'))

        self.browser.find_element_by_name('submit').click()

        # Process the uploaded figure and reload.
        if is_review:
            n_processed = process_review_figure(db=self.db)

        else:
            n_processed = process_proposal_figure(db=self.db)

        self.assertEqual(n_processed, 1)

        self.browser.get(current_url)

        manage_figures = self.browser.find_element_by_link_text(
            'Manage figures')

        manage_figures.click()

        self._save_screenshot(
            screenshot_path, '{}_{}'.format(screenshot_prefix, 'fig_manage'))

        self.browser.find_element_by_name('submit').click()

    def _add_itc_calculation(
            self, screenshot_path=None,
            sensitivity='1.343', title='SCUBA-2 observation of LDN 456',
            save_prefix='', highlight_extra=[]):
        self.browser.find_element_by_link_text('SCUBA-2 ITC').click()

        position = self.browser.find_element_by_name('pos')
        position.clear()
        position.send_keys('-10')

        rms = self.browser.find_element_by_name('rms')
        rms.clear()
        rms.send_keys(sensitivity)

        self.browser.find_element_by_name('submit_calc').click()

        self.assertIn(
            'Results',
            self.browser.page_source)

        self.browser.find_element_by_name(
            '{}calculation_title'.format(save_prefix)).send_keys(title)

        submit_save_redir = self.browser.find_element_by_name(
            '{}submit_save_redir'.format(save_prefix))

        self._save_screenshot(
            screenshot_path, 'calc_scuba2',
            [submit_save_redir] + highlight_extra)

        submit_save_redir.click()

        self.assertIn(
            'The calculation has been saved',
            self.browser.page_source)

        self.browser.find_element_by_link_text('Manage calculations').click()

        self.assertIn(
            'Calculator: SCUBA-2 ITC',
            self.browser.page_source)

        self._save_screenshot(screenshot_path, 'calc_manage')

        self.browser.find_element_by_name('submit').click()

    def view_person_proposals(self):
        # Test the personal proposal list.
        self.browser.get(self.base_url + 'proposals')

        self.assertIn(
            '<h1>Your Proposals</h1>',
            self.browser.page_source)

        self.assertIn(
            'An Example Proposal',
            self.browser.page_source)

        self._save_screenshot(self.user_image_root, 'proposal_list')

    def accept_invitation(self, user_name='invitee', screenshot_path=None):
        # Determine the invitation token to use.
        with self.db._transaction() as conn:
            token = conn.execute(select([invitation.c.token])).scalar()

        self.browser.get(self.base_url)

        self.browser.find_element_by_link_text(
            'Enter an invitation code').click()

        self.browser.find_element_by_name('token').send_keys(token)

        self._save_screenshot(screenshot_path, 'invitation_enter')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'Please log in or register for an account to proceed.',
            self.browser.page_source)

        register_link = self.browser.find_element_by_link_text('register')

        self._save_screenshot(screenshot_path, 'log_in_register',
                              [register_link])

        register_link.click()

        self._do_register_user(user_name, 'password')

        self._save_screenshot(screenshot_path, 'invitation_accept')

        self.browser.find_element_by_name('submit_accept').click()

        self.assertIn(
            'The invitation has been accepted successfully.',
            self.browser.page_source)

    def remove_self(self):
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
        # Go to the home page to loose any flashed message box.
        self.browser.get(self.base_url)

        profile_link = self.browser.find_element_by_id('user_profile_link')

        self._save_screenshot(self.user_image_root, 'profile_link',
                              [profile_link])

        profile_link.click()

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

        self._save_screenshot(self.user_image_root, 'email_edit',
                              ['delete_2', 'add_email'])

        email_new = 'example@somewhere.else.edu'

        self.browser.find_element_by_id('add_email').click()

        self.browser.find_element_by_name('email_new_1').send_keys(email_new)
        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'Your email addresses have been updated.',
            self.browser.page_source)

        self.browser.refresh()
        self._save_screenshot(
            self.user_image_root, 'profile_edit_links',
            ['account_manage_links', 'profile_manage_links',
             self.browser.find_element_by_link_text('verify')])

        # Verify email address.
        self.browser.find_element_by_link_text('verify').click()

        self._do_verify_email(email_new)

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
            'View this institution').click()

        edit_institution = self.browser.find_element_by_link_text(
            'Edit this institution')

        self._save_screenshot(self.user_image_root, 'institution_view',
                              [edit_institution])

        edit_institution.click()

        self.assertIn(
            'Are you sure you want to edit this institution?',
            self.browser.page_source)

        self.browser.find_element_by_name('submit_confirm').click()

        self._save_screenshot(self.user_image_root, 'institution_edit')

        self.browser.find_element_by_name('submit_edit').click()

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

    def administer_facility(self, facility_code, semester_name, queue_name):
        """
        This test performs some administrative tasks on a facility.

        It takes a screenshot of the call proposals list and so is intended
        to run after a user has created a proposal.

        It also alters the closing date of the call so that it is no longer
        open.
        """

        self.browser.get(self.base_url + facility_code)

        facility_home_url = self.browser.current_url

        self.browser.find_element_by_link_text('take admin').click()
        self.browser.find_element_by_link_text('Administrative menu').click()

        admin_menu_url = self.browser.current_url

        # Go to the call list and get screenshots of the list and the
        # list of proposals.
        self.browser.find_element_by_link_text('Calls').click()

        self._save_screenshot(self.admin_image_root, 'call_list')

        self.browser.find_element_by_link_text(queue_name).click()

        self.assertIn('<h1>Call:',
                      self.browser.page_source)

        self.browser.find_element_by_link_text('Edit call').click()

        # Set the closing date back to the start of the year.
        current_date = datetime.utcnow()
        current_year = str(current_date.year)

        close_date = self.browser.find_element_by_name('close_date')
        close_date.clear()
        close_date.send_keys(current_year + '-01-01')

        close_time = self.browser.find_element_by_name('close_time')
        close_time.clear()
        close_time.send_keys('00:01')

        self.browser.find_element_by_name('submit').click()

        self.assertIn('The call has been updated.',
                      self.browser.page_source)

        self.browser.find_element_by_link_text('View proposals').click()

        self.assertIn('<h1>Proposals:',
                      self.browser.page_source)

        self._save_screenshot(self.admin_image_root, 'call_proposals')

        # Go to a proposal to correct the affiliation information.
        self.browser.find_element_by_id('proposal_view_1').click()

        edit_link = self.browser.find_element_by_id('member_aff_ed_2')
        self._save_screenshot(self.admin_image_root, 'proposal_mem_aff_link',
                              [edit_link, 'alter_state_link'])

        edit_link.click()

        Select(
            self.browser.find_element_by_name('affiliation_id')
        ).select_by_visible_text('Japan')

        self._save_screenshot(self.admin_image_root, 'proposal_mem_aff_edit')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The affiliation has been updated.',
            self.browser.page_source)

        edit_link = self.browser.find_element_by_id('alter_state_link').click()

        self._save_screenshot(self.admin_image_root, 'proposal_alter_state')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The proposal state has been updated.',
            self.browser.page_source)

        # Try deleting the MOC.
        self.browser.get(facility_home_url)
        self.browser.find_element_by_link_text('Clash Tool').click()
        self.browser.find_element_by_link_text('View all defined areas of sky coverage').click()
        self.browser.find_element_by_link_text('Delete').click()
        self.browser.find_element_by_name('submit_confirm').click()

        self.assertIn('The coverage map has been deleted.',
                      self.browser.page_source)

        # Also test the semester and queue edit pages.
        self.browser.get(admin_menu_url)
        self.browser.find_element_by_link_text('Semesters').click()
        self.browser.find_element_by_link_text(semester_name).click()
        self.browser.find_element_by_link_text('Edit semester').click()
        self.browser.find_element_by_name('submit').click()

        self.assertIn('Semester "{}" has been updated.'.format(semester_name),
                      self.browser.page_source)

        self.browser.find_element_by_link_text('Administrative menu').click()
        self.browser.find_element_by_link_text('Queues').click()
        self.browser.find_element_by_link_text('PI Science').click()
        self.browser.find_element_by_link_text('Edit queue').click()
        self.browser.find_element_by_name('submit').click()

        self.assertIn('Queue "PI Science" has been updated.',
                      self.browser.page_source)

        # Set up the review groups.
        admin_queue_url = self.browser.current_url

        for (group_name, group_abbr, group_members) in (
                ('Committee members', 'cttee', (
                    'Example Group Member', 'Another Group Member')),
                ('Technical assessors', 'tech', (
                    'Example Technical Assessor',))):
            self.browser.get(admin_queue_url)
            self.browser.find_element_by_link_text(group_name).click()

            first_person = True
            for person_name in group_members:
                self.browser.find_element_by_link_text('Add member').click()
                Select(
                    self.browser.find_element_by_name('person_id')
                ).select_by_visible_text(
                    '{}, Test Institution, United States'.format(person_name))

                if first_person:
                    self._save_screenshot(self.admin_image_root,
                                          'group_{}_add'.format(group_abbr))

                self.browser.find_element_by_name('submit_link').click()

                self.assertIn(
                    '{} has been added to the group.'.format(person_name),
                    self.browser.page_source)

                first_person = False

            # Reload page to remove the yellow flash box for the screenshot.
            self.browser.get(self.browser.current_url)

            self._save_screenshot(self.admin_image_root,
                                  'group_{}'.format(group_abbr))

            self.browser.find_element_by_link_text('Edit members').click()

            self._save_screenshot(self.admin_image_root,
                                  'group_{}_edit'.format(group_abbr))

            self.browser.find_element_by_name('submit').click()

            self.assertIn('The group membership has been saved.',
                          self.browser.page_source)

        # Go back to the main page and test the "drop admin" link.
        self.browser.get(self.base_url)
        self.browser.find_element_by_link_text('drop admin').click()

        self.assertIn('You have dropped administrative privileges.',
                      self.browser.page_source)

    def set_up_review(self, facility_code):
        """
        This test sets up a review process.
        """

        self.browser.get(self.base_url + facility_code)
        self.browser.find_element_by_link_text('take admin').click()
        self.browser.find_element_by_link_text('Administrative menu').click()
        self.browser.find_element_by_link_text('Calls').click()
        self.browser.find_element_by_link_text('Review process').click()

        self._save_screenshot(self.admin_image_root, 'review_process')

        # Set review deadlines.
        self.browser.find_element_by_link_text(
            'Edit review deadlines').click()

        self.browser.find_element_by_name('date_date_2').send_keys('2020-01-01')
        self.browser.find_element_by_name('date_time_2').send_keys('00:00')

        self._save_screenshot(self.admin_image_root, 'review_deadline')

        self.browser.find_element_by_name('submit').click()
        self.assertIn('The review deadlines have been saved.',
                      self.browser.page_source)

        # Add an external reviewer.
        self.browser.find_element_by_link_text('Assign reviewers').click()
        self._save_screenshot(
            self.admin_image_root, 'reviewer_assign',
            ['assign_reviewer_links'])

        self.browser.find_element_by_link_text('Add external reviewer').click()

        self.browser.find_element_by_name('name').send_keys('Invited Reviewer')
        self.browser.find_element_by_name('email').send_keys(
            'reviewer@somewhere.edu')

        self._save_screenshot(self.admin_image_root, 'reviewer_external', [
            'review_deadline_cell'])

        self.browser.find_element_by_name('submit_invite').click()

        self.assertIn(
            'Invited Reviewer has been invited to register.',
            self.browser.page_source)

        Select(
            self.browser.find_element_by_name('institution_id')
        ).select_by_visible_text(
            'Test Institution, United States')

        self.browser.find_element_by_name('submit_select').click()

        self.assertIn(
            'The institution has been selected.',
            self.browser.page_source)

        # Technical reviewers page.
        self.browser.find_element_by_link_text(
            'Assign technical assessors').click()

        self.browser.find_elements_by_name('rev_{}_1'.format(
            BaseReviewerRole.TECH))[0].click()

        self._save_screenshot(self.admin_image_root, 'reviewer_tech')

        self.browser.find_element_by_name('submit').click()

        self.assertIn('assignments have been updated.',
                      self.browser.page_source)

        # Committee reviewers page.
        self.browser.find_element_by_link_text(
            'Assign committee members').click()

        self.browser.find_elements_by_name('rev_{}_1'.format(
            BaseReviewerRole.CTTEE_PRIMARY))[1].click()
        self.browser.find_elements_by_name('rev_{}_1'.format(
            BaseReviewerRole.CTTEE_SECONDARY))[0].click()

        self._save_screenshot(self.admin_image_root, 'reviewer_cttee')

        self.browser.find_element_by_name('submit').click()

        self.assertIn('assignments have been updated.',
                      self.browser.page_source)

        # Sending notifications.
        self.browser.refresh()
        self._save_screenshot(
            self.admin_image_root, 'reviewer_assign_filled',
            ['notify_reviewer_links'])

        self.browser.find_element_by_link_text(
            'Notify technical assessors').click()

        self._save_screenshot(self.admin_image_root, 'reviewer_tech_notify')

        self.browser.find_element_by_name('submit_confirm').click()

        self.assertIn('Notifications have been sent',
                      self.browser.page_source)

    def set_up_peer_review(self, facility_code):
        self.browser.get(self.base_url + facility_code)
        self.browser.find_element_by_link_text('take admin').click()
        self.browser.find_element_by_link_text('rapid turnaround').click()

        # Set review deadlines.
        self.browser.find_element_by_link_text(
            'Edit review deadlines').click()

        self.browser.find_element_by_name('date_date_7').send_keys('2020-01-01')
        self.browser.find_element_by_name('date_time_7').send_keys('00:00')

        self.browser.find_element_by_name('submit').click()
        self.assertIn('The review deadlines have been saved.',
                      self.browser.page_source)

        # Assign peer reviewers.
        self.browser.find_element_by_link_text('Assign reviewers').click()
        self.browser.find_element_by_link_text('Assign peer reviewers').click()

        for checkbox in self.browser.find_elements_by_css_selector(
                'input[type="checkbox"]'):
            checkbox.click()

        self.browser.find_element_by_name('submit').click()

        self.assertIn('assignments have been updated.',
                      self.browser.page_source)

    def enter_technical_assessment(self):
        """
        Tests entering a technical assessment.
        """

        # Navigate to the technical assessment.
        self.browser.find_element_by_link_text('Your reviews').click()

        self.browser.find_element_by_link_text('Technical').click()

        # Add a calculation.
        self._add_itc_calculation(
            screenshot_path=self.review_image_root,
            sensitivity='1.434', title='Adjusted sensitivity',
            save_prefix='review_')

        # Add a figure.
        self._add_figure(
            screenshot_path=self.review_image_root,
            screenshot_prefix='tech_assess',
            is_review=True)

        # Fill in the review.
        self.browser.find_element_by_name('text').send_keys(
            'My assessment of the feasibility of this proposal is...')

        Select(
            self.browser.find_element_by_name('assessment')
        ).select_by_visible_text('Feasible')

        self.browser.find_element_by_name('done').click()

        self._save_screenshot(self.review_image_root, 'tech_assess_edit',
                              ['add_calc_links', 'upload_fig_link'])

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The review has been saved and marked as done.',
            self.browser.page_source)

    def enter_review(self):
        """
        Tests entering a review.

        Assumes that the person starts on their review information page
        after accepting an invitation.
        """

        self.accept_review()

        self._save_screenshot(self.review_image_root, 'review_info',
                              ['person_reviews_link', 'review_action_links'])

        self.browser.find_element_by_link_text('Write your review').click()

        self.browser.find_element_by_name('jcmt_review_aims').send_keys(
            'The aims of this proposal ...')

        self.browser.find_element_by_name('jcmt_review_analysis').send_keys(
            'The proposed analysis ...')

        self.browser.find_element_by_name(
            'jcmt_review_difficulties').send_keys(
            'Difficulties with this proposal are ...')

        Select(
            self.browser.find_element_by_name('jcmt_rating_justification')
        ).select_by_visible_text('Convincing and well described')

        self.browser.find_element_by_name('jcmt_review_details').send_keys(
            'The technical details in this program ...')

        self.browser.find_element_by_name('jcmt_review_obj_inst').send_keys(
            'The target objects and instrumentation ...')

        self.browser.find_element_by_name('jcmt_review_telescope').send_keys(
            'The choice of telescope for this proposal is ...')

        Select(
            self.browser.find_element_by_name('jcmt_rating_technical')
        ).select_by_visible_text('Correct and well described')

        Select(
            self.browser.find_element_by_name('jcmt_rating_urgency')
        ).select_by_visible_text('Timely and competitive: must be done now')

        self.browser.find_element_by_name('text').send_keys(
            'My opinion of this proposal is...')
        self.browser.find_element_by_name('rating').send_keys('50')

        self.browser.find_element_by_name('done').click()

        self._save_screenshot(self.review_image_root, 'review_edit')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The review has been saved and marked as done.',
            self.browser.page_source)

    def enter_cttee_review(
            self, role_name, rating, expertise, screenshot_path=None):
        """
        Tests entering a committee member's.
        """

        # Navigate to the review.
        self.browser.find_element_by_link_text('Your reviews').click()

        self.browser.find_element_by_link_text(role_name).click()

        # Fill in the review.
        self.browser.find_element_by_name('text').send_keys(
            'My {} review is as follows...'.format(role_name))

        self.browser.find_element_by_name('rating').send_keys(rating)

        Select(
            self.browser.find_element_by_name('jcmt_expertise')
        ).select_by_visible_text(expertise)

        self.browser.find_element_by_name('done').click()

        self._save_screenshot(screenshot_path, 'cttee_review_edit')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The review has been saved and marked as done.',
            self.browser.page_source)

    def enter_peer_review(self):
        self.browser.find_element_by_link_text('Your reviews').click()

        self.browser.find_element_by_link_text('Peer').click()

        self.accept_review(screenshot_prefix='peer_review')

        self._save_screenshot(self.review_image_root, 'peer_review_edit')

    def accept_review(self, screenshot_prefix=None):
        Select(
            self.browser.find_element_by_name('accepted')
        ).select_by_value('1')

        if screenshot_prefix is not None:
            self._save_screenshot(
                self.review_image_root, '{}_accept'.format(screenshot_prefix))

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The review has been accepted.',
            self.browser.page_source)

        # Reload page to remove the yellow flash box for the screenshot.
        self.browser.get(self.browser.current_url)

    def view_person_reviews(self):
        # Now acquire a screenshot of the "Your reviews" page.
        self.browser.find_element_by_link_text('Your reviews').click()

        self.assertIn('<h1>Your Reviews</h1>', self.browser.page_source)
        self.assertIn('An Example Proposal', self.browser.page_source)
        self.assertIn('External', self.browser.page_source)

        self._save_screenshot(self.review_image_root, 'review_list')

    def view_proposal_reviews(self, facility_code):
        self.browser.find_element_by_link_text('take admin').click()
        self.browser.get(self.base_url + facility_code)
        self.browser.find_element_by_link_text('Administrative menu').click()
        self.browser.find_element_by_link_text('Calls').click()
        self.browser.find_element_by_link_text('Review process').click()

        review_process_url = self.browser.current_url

        # Enter affiliation weights.
        self.browser.find_element_by_link_text(
            'Edit affiliation weights').click()

        self.browser.find_element_by_name('weight_1').send_keys('40')
        self.browser.find_element_by_name('weight_2').send_keys('40')

        self._save_screenshot(self.admin_image_root, 'affiliation_weights')

        self.browser.find_element_by_name('submit').click()
        self.assertIn('The affiliation weights have been updated.',
                      self.browser.page_source)

        # Enter times by weather band.
        self.browser.find_element_by_link_text(
            'Edit time available').click()

        self.browser.find_element_by_name('available_1').send_keys('150')
        self.browser.find_element_by_name('available_2').send_keys('250')
        self.browser.find_element_by_name('available_3').send_keys('250')
        self.browser.find_element_by_name('available_4').send_keys('200')
        self.browser.find_element_by_name('available_5').send_keys('150')

        self._save_screenshot(self.admin_image_root, 'time_available')

        self.browser.find_element_by_name('submit').click()
        self.assertIn('The time available has been saved.',
                      self.browser.page_source)

        # Advance to the final review phase.
        self.browser.find_element_by_link_text(
            'Advance to final review phase').click()

        self._save_screenshot(
            self.admin_image_root, 'review_final', ['roles_closing_list'])

        self.browser.find_element_by_name('submit_confirm').click()

        self.assertIn('1 proposal advanced to the final review state',
                      self.browser.page_source)

        # Look at the tabulation page and enter a decision.
        self.browser.find_element_by_link_text(
            'View detailed tabulation').click()

        decision_link = self.browser.find_element_by_id('decision_1_link')
        self._save_screenshot(self.admin_image_root, 'review_tabulation',
                              [decision_link])

        decision_link.click()

        Select(
            self.browser.find_element_by_name('decision_accept')
        ).select_by_visible_text('Accept proposal')

        time_field = self.browser.find_element_by_name('time_new_1')
        time_field.clear()
        time_field.send_keys('2')
        time_field = self.browser.find_element_by_name('time_new_2')
        time_field.clear()
        time_field.send_keys('6')

        self._save_screenshot(self.admin_image_root, 'decision_edit')

        self.browser.find_element_by_name('submit').click()

        self.assertRegex(
            self.browser.page_source,
            'The decision for proposal [A-Z0-9]+ has been saved\.')

        self._save_screenshot(self.admin_image_root,
                              'review_tabulation_updated')

        # Look at the reviewer statistics page
        self.browser.get(review_process_url)
        self.browser.find_element_by_link_text(
            'View review statistics').click()

        self._save_screenshot(self.admin_image_root,
                              'review_statistics')

        # Look at the allocation details page
        self.browser.get(review_process_url)
        self.browser.find_element_by_link_text(
            'View allocation details').click()

        self._save_screenshot(self.admin_image_root,
                              'allocation_details')

        # View reviews page.
        self.browser.get(review_process_url)
        self.browser.find_element_by_link_text('Reviews').click()

        self._save_screenshot(self.admin_image_root, 'proposal_reviews',
                              ['extra_review_links'])

        # Enter feedback text.
        self.browser.find_element_by_link_text('Add feedback').click()

        self.browser.find_element_by_name('text').send_keys(
            'This is an example feedback comment.')

        self.browser.find_element_by_name('done').click()

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The review has been saved and marked as done.',
            self.browser.page_source)

        # Check that the feedback approval page works.
        self.browser.get(review_process_url)
        self.browser.find_element_by_link_text(
            'Approve feedback reports').click()
        self.browser.find_element_by_xpath('//input[@type="checkbox"]').click()

        self._save_screenshot(self.admin_image_root, 'approve_feedback')

        self.browser.find_element_by_name('submit').click()
        self.assertIn('The feedback approval status has been updated.',
                      self.browser.page_source)

    def administer_site(self):
        self.browser.get(self.base_url)
        self.browser.find_element_by_link_text('Site administration').click()
        admin_menu_url = self.browser.current_url

        self._save_screenshot(self.admin_image_root, 'site_admin_menu')

        self.browser.find_element_by_link_text('Email messages').click()
        self._save_screenshot(self.admin_image_root, 'message_list')

        self.browser.find_element_by_partial_link_text('submitted').click()

        thread_link = self.browser.find_element_by_id('message_thread_link')

        self._save_screenshot(self.admin_image_root, 'message_view',
                              [thread_link])
        thread_link.click()

        self.assertIn('<h1>Message thread:', self.browser.page_source)

        self._save_screenshot(self.admin_image_root, 'message_thread')

        # Move a message into the "error" state so that we can test the
        # reset control.
        messages = self.db.search_message(
            state=MessageState.UNSENT, oldest_first=True)
        self.assertTrue(messages)
        self.db.update_message(
            message_id=first_value(messages).id,
            state_prev=MessageState.UNSENT, state=MessageState.ERROR,
            state_is_system=True)

        self.browser.find_element_by_link_text('Messages').click()

        self.browser.find_element_by_xpath('//input[@type="checkbox"]').click()

        self._save_screenshot(self.admin_image_root, 'message_reset',
                              ['message_state_control'])

        self.browser.find_element_by_name('submit').click()

        self.assertIn('The status for 1 message has been set to unsent.',
                      self.browser.page_source)

        self.browser.get(admin_menu_url)
        self.browser.find_element_by_link_text(
            'Approve institution edits').click()
        self._save_screenshot(self.admin_image_root, 'approve_inst_edit')

        self.browser.get(admin_menu_url)
        self.browser.find_element_by_link_text(
            'View processing status').click()
        self._save_screenshot(self.admin_image_root, 'processing_status')

        self.browser.get(admin_menu_url)
        self.browser.find_element_by_link_text('Unregistered users').click()
        self._save_screenshot(self.admin_image_root, 'user_unregistered')

        # View administrative links on a profile and institution pages.
        self.browser.find_element_by_id('user_profile_link').click()

        self._save_screenshot(self.admin_image_root, 'person_admin',
                              ['account_admin_links'])

        self.browser.find_element_by_link_text('User account log').click()

        self._save_screenshot(self.admin_image_root, 'user_log')

        self.browser.back()

        self.browser.find_element_by_link_text(
            'Subsume duplicate profile').click()

        Select(
            self.browser.find_element_by_name('duplicate_id')
        ).select_by_visible_text(
            'Another Person, Test Institution, United States')

        self._save_screenshot(self.admin_image_root, 'person_subsume')

        self.browser.find_element_by_name('submit').click()

        self._save_screenshot(self.admin_image_root, 'person_subsume_confirm')

        self.browser.find_element_by_name('submit_cancel').click()

        self.browser.find_element_by_partial_link_text(
            'View this institution').click()

        self._save_screenshot(self.admin_image_root, 'institution_links',
                              ['institution_admin_links'])

        self.browser.find_element_by_link_text('View edit log').click()
        self._save_screenshot(self.admin_image_root, 'institution_log')

        self.browser.back()

        self.browser.find_element_by_link_text(
            'Subsume duplicate record').click()

        Select(
            self.browser.find_element_by_name('duplicate_id')
        ).select_by_visible_text('Another Institution, United States')

        self._save_screenshot(self.admin_image_root, 'institution_subsume')

        self.browser.find_element_by_name('submit').click()

        self._save_screenshot(self.admin_image_root,
                              'institution_subsume_confirm')

        self.browser.find_element_by_name('submit_cancel').click()

        # Test the site group system.
        self.browser.get(admin_menu_url)
        self.browser.find_element_by_link_text('Profile viewers').click()

        self.browser.find_element_by_link_text('Add member').click()

        self._save_screenshot(
            self.admin_image_root, 'site_group_view_prof_add')

        self.browser.find_element_by_name('name').send_keys(
            'Site Group Member')
        self.browser.find_element_by_name('email').send_keys(
            'member@somewhere.edu')

        self.browser.find_element_by_name('submit_invite').click()

        self.assertIn(
            'Site Group Member has been added to the site group.',
            self.browser.page_source)

        Select(
            self.browser.find_element_by_name('institution_id')
        ).select_by_visible_text(
            'Test Institution, United States')

        self.browser.find_element_by_name('submit_select').click()

        self.assertIn(
            'The institution has been selected.',
            self.browser.page_source)

        self.browser.get(self.browser.current_url)

        self._save_screenshot(self.admin_image_root, 'site_group_view_prof')

        self.browser.find_element_by_link_text('Edit members').click()

        self._save_screenshot(
            self.admin_image_root, 'site_group_view_prof_edit')

        self.browser.find_element_by_name('submit').click()

        self.assertIn(
            'The site group membership has been saved.',
            self.browser.page_source)

    def view_user_directory(self):
        self.browser.get(self.base_url + 'person')

        self.browser.find_element_by_link_text('take admin').click()

        Select(
            self.browser.find_element_by_name('registered')
        ).select_by_visible_text('Any status')

        self.browser.find_element_by_id('submit_filter').click()

        self._save_screenshot(self.admin_image_root, 'person_list')

        self.browser.find_element_by_link_text(
            'Invited Member').click()

        self._save_screenshot(
            self.admin_image_root, 'person_unregistered',
            ['account_admin_links'])

        self.browser.find_element_by_link_text(
            'Invite to register').click()

        self._save_screenshot(self.admin_image_root, 'person_invite')

        self.browser.find_element_by_name('submit_cancel').click()

    def open_new_call(self, facility_code):
        self.browser.get(self.base_url + facility_code)

        self.browser.find_element_by_link_text('Administrative menu').click()

        admin_menu_url = self.browser.current_url

        # Create a new semester.
        semester_name = self._create_semester('B')

        # Create a call.
        self.browser.get(admin_menu_url)
        self._create_call('Rapid Turnaround', semester_name)

        return semester_name

    def view_proposal_feedback(self, facility_code, proposal_id):
        self.browser.get(self.base_url +
                         '{}/proposal/{}'.format(facility_code, proposal_id))

        feedback_link = self.browser.find_element_by_link_text('View feedback')

        self._save_screenshot(self.user_image_root, 'proposal_reviewed',
                              [feedback_link])

        feedback_link.click()

        self.assertIn('<h2>Comments</h2>', self.browser.page_source)

        self._save_screenshot(self.user_image_root, 'proposal_feedback')

    def copy_proposal(
            self, facility_code, semester_name, call_type_name=None,
            screenshot_path=None):
        self.browser.get(self.base_url + facility_code)

        if call_type_name is None:
            self.browser.find_element_by_link_text(semester_name).click()

        else:
            self.browser.find_element_by_link_text('Other calls for proposals').click()

            self.browser.find_element_by_link_text(call_type_name).click()

        queue_link = self.browser.find_element_by_partial_link_text(
            'Create a proposal for the PI Science Queue')

        queue_link.click()

        Select(
            self.browser.find_element_by_name('affiliation_id')
        ).select_by_visible_text('China')

        self._save_screenshot(screenshot_path, 'proposal_copy')

        self.browser.find_element_by_name('submit_copy').click()

        self.assertIn(
            'Please wait while your proposal is copied.',
            self.browser.page_source)

        # Process the request and refresh now -- should be redirected to copy.
        process_request_prop_copy(self.db, self.server.app)

        self.browser.refresh()

        self.assertIn(
            'Proposal Copy Report',
            self.browser.page_source)

        self.assertNotIn(
            'Error',
            self.browser.page_source)

        self.browser.find_element_by_id('callout_dismiss').click()

        self._save_screenshot(
            screenshot_path, 'proposal_copied')

        self._submit_proposal()

    def try_jcmt_itcs(self):
        self.browser.get(self.base_url + 'jcmt/calculator/scuba2/time')

        self._save_screenshot(self.user_image_root, 'calc_scuba2_input')

        self.browser.get(self.base_url + 'jcmt/calculator/heterodyne/time')

        self._save_screenshot(self.user_image_root, 'calc_jcmt_het_input')

    def try_jcmt_tools(self):
        self.browser.get(self.base_url + 'jcmt/tool/clash')

        self.browser.find_element_by_name('x').send_keys('12:34:56')
        self.browser.find_element_by_name('y').send_keys('7:08:09')
        self.browser.find_element_by_name('submit_calc').click()

        self.assertIn(
            'No match was found for the following targets:',
            self.browser.page_source)

        self._save_screenshot(
            self.user_image_root, 'target_clash_single',
            ['perm_query_link', 'tool_upload_link'])

        self.browser.get(self.base_url + 'jcmt/tool/avail')

        self.browser.find_element_by_name('x').send_keys('12:34:56')
        self.browser.find_element_by_name('y').send_keys('7:08:09')
        self.browser.find_element_by_name('submit_calc').click()

        self.assertIn(
            '<h3>Availability by Date</h3>',
            self.browser.page_source)

        self._save_screenshot(
            self.user_image_root, 'target_avail_single',
            ['perm_query_link', 'tool_upload_link'])

    def _save_screenshot(self, path, name, highlight=[]):
        if path is None:
            return

        for highlight_element in highlight:
            if not isinstance(highlight_element, string_type):
                highlight_element = highlight_element.get_attribute('id')
            self.browser.execute_script(
                'document.getElementById("' + highlight_element +
                '").classList.add("highlight_for_doc");')

        path_small = os.path.join(path, name + '.png')
        path_large = os.path.join(path, name + '_large.png')

        self.browser.save_screenshot(path_large)

        im = Image.open(path_large)

        size = tuple(int(x / 2) for x in im.size)

        im = im.resize(size, resample=Image.BICUBIC)

        im.save(path_small, format='PNG')

    def _get_example_path(self, file_name):
        return os.path.join(
            os.getcwd(), 'util', 'selenium', 'data', file_name)
