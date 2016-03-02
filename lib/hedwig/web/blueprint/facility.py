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

from flask import Blueprint, request

from ...type import CalculatorInfo, FigureType, ReviewerRole, \
    TargetToolInfo, TextRole
from ..util import HTTPRedirect, \
    require_admin, require_auth, send_file, templated, url_for


def create_facility_blueprint(db, facility):
    """
    Create Flask blueprint for a facility.
    """

    code = facility.get_code()
    name = facility.get_name()

    bp = Blueprint(code, __name__)

    def facility_template(template):
        """
        Decorator which uses the template from the facility's directory if it
        exists, otherwise the generic template.  It does this by providing a
        list of alternative templates, from which Flask's "render_template"
        method will pick the first which exists.
        """

        def decorator(f):
            return templated((code + '/' + template, 'generic/' + template))(f)
        return decorator

    @bp.route('/')
    @facility_template('facility_home.html')
    def facility_home():
        return facility.view_facility_home(db)

    @bp.route('/semester/<int:semester_id>')
    @facility_template('semester_calls.html')
    def semester_calls(semester_id):
        return facility.view_semester_calls(db, semester_id)

    @bp.route('/call/<int:call_id>/new_proposal',
              methods=['GET', 'POST'])
    @require_auth(require_institution=True)
    @facility_template('proposal_new.html')
    def proposal_new(call_id):
        return facility.view_proposal_new(
            db, call_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/call/<int:call_id>/review')
    @require_auth(require_person=True)
    @facility_template('call_review.html')
    def review_call(call_id):
        return facility.view_review_call(db, call_id)

    @bp.route('/call/<int:call_id>/review/tabulation')
    @require_auth(require_person=True)
    @facility_template('call_review_tabulation.html')
    def review_call_tabulation(call_id):
        return facility.view_review_call_tabulation(db, call_id)

    @bp.route('/call/<int:call_id>/review/tabulation/download')
    @require_auth(require_person=True)
    @send_file()
    def review_call_tabulation_download(call_id):
        return facility.view_review_call_tabulation_download(db, call_id)

    @bp.route('/call/<int:call_id>/affiliation', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('call_affiliation_weight.html')
    def review_affiliation_weight(call_id):
        return facility.view_review_affiliation_weight(
            db, call_id, (request.form if request.method == 'POST' else None))

    @bp.route('/call/<int:call_id>/available', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('call_available.html')
    def review_call_available(call_id):
        return facility.view_review_call_available(
            db, call_id, (request.form if request.method == 'POST' else None))

    @bp.route('/call/<int:call_id>/feedback', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('call_feedback.html')
    def review_confirm_feedback(call_id):
        return facility.view_review_confirm_feedback(
            db, call_id, (request.form if request.method == 'POST' else None))

    @bp.route('/call/<int:call_id>/reviewers')
    @require_auth(require_person=True)
    @facility_template('call_reviewers.html')
    def review_call_reviewers(call_id):
        return facility.view_review_call_reviewers(db, call_id, request.args)

    @bp.route('/call/<int:call_id>/reviewers/technical',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('reviewer_grid.html')
    def review_call_technical(call_id):
        return facility.view_reviewer_grid(
            db, call_id, ReviewerRole.TECH,
            (request.form if request.method == 'POST' else None))

    @bp.route('/call/<int:call_id>/reviewers/committee',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('reviewer_grid.html')
    def review_call_committee(call_id):
        return facility.view_reviewer_grid(
            db, call_id, ReviewerRole.CTTEE_PRIMARY,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>')
    @require_auth(require_person=True)
    @facility_template('proposal_view.html')
    def proposal_view(proposal_id):
        return facility.view_proposal_view(db, proposal_id, request.args)

    @bp.route('/proposal/<int:proposal_id>/submit', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('proposal_submit.html')
    def proposal_submit(proposal_id):
        return facility.view_proposal_submit(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/validate')
    @require_auth(require_person=True)
    @facility_template('proposal_submit.html')
    def proposal_validate(proposal_id):
        return facility.view_proposal_validate(
            db, proposal_id)

    @bp.route('/proposal/<int:proposal_id>/withdraw', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('proposal_withdraw.html')
    def proposal_withdraw(proposal_id):
        return facility.view_proposal_withdraw(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/title', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('title_edit.html')
    def title_edit(proposal_id):
        return facility.view_title_edit(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/abstract', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('abstract_edit.html')
    def abstract_edit(proposal_id):
        return facility.view_abstract_edit(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/member', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('member_edit.html')
    def member_edit(proposal_id):
        return facility.view_member_edit(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/member/add',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('member_add.html')
    def member_add(proposal_id):
        return facility.view_member_add(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/member/reinvite/<int:member_id>',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @templated('confirm.html')
    def member_reinvite(proposal_id, member_id):
        return facility.view_member_reinvite(
            db, proposal_id, member_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/member/remove',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @templated('confirm.html')
    def remove_self(proposal_id):
        return facility.view_member_remove_self(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/student', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('student_edit.html')
    def student_edit(proposal_id):
        return facility.view_student_edit(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/previous',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('previous_edit.html')
    def previous_edit(proposal_id):
        return facility.view_previous_edit(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/target', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('target_edit.html')
    def target_edit(proposal_id):
        return facility.view_target_edit(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/target/upload',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('target_upload.html')
    def target_upload(proposal_id):
        return facility.view_target_upload(
            db, proposal_id,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/target/note',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('tool_note_edit.html')
    def tool_note_edit(proposal_id):
        return facility.view_tool_note_edit(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/request', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('request_edit.html')
    def request_edit(proposal_id):
        return facility.view_request_edit(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/technical')
    @require_auth(require_person=True)
    @facility_template('case_edit.html')
    def tech_edit(proposal_id):
        return facility.view_case_edit(
            db, proposal_id, TextRole.TECHNICAL_CASE)

    @bp.route('/proposal/<int:proposal_id>/technical/text',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('text_edit.html')
    def tech_edit_text(proposal_id):
        return facility.view_case_edit_text(
            db, proposal_id, TextRole.TECHNICAL_CASE,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/technical/figure/new',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('figure_edit.html')
    def tech_new_figure(proposal_id):
        return facility.view_case_edit_figure(
            db, proposal_id, None, TextRole.TECHNICAL_CASE,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route(
        '/proposal/<int:proposal_id>/technical/figure/<int:fig_id>/edit',
        methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('figure_edit.html')
    def tech_edit_figure(proposal_id, fig_id):
        return facility.view_case_edit_figure(
            db, proposal_id, fig_id, TextRole.TECHNICAL_CASE,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/technical/figure/manage',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('figure_manage.html')
    def tech_manage_figure(proposal_id):
        return facility.view_case_manage_figure(
            db, proposal_id, TextRole.TECHNICAL_CASE,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/technical/figure/'
              '<int:fig_id>/<md5sum>')
    @require_auth(require_person=True)
    @send_file(allow_cache=True)
    def tech_view_figure(proposal_id, fig_id, md5sum):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, TextRole.TECHNICAL_CASE, md5sum)

    @bp.route('/proposal/<int:proposal_id>/technical/figure/'
              '<int:fig_id>/thumbnail/<md5sum>')
    @require_auth(require_person=True)
    @send_file(fixed_type=FigureType.PNG, allow_cache=True)
    def tech_view_figure_thumbnail(proposal_id, fig_id, md5sum):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, TextRole.TECHNICAL_CASE, md5sum,
            'thumbnail')

    @bp.route('/proposal/<int:proposal_id>/technical/figure/'
              '<int:fig_id>/preview/<md5sum>')
    @require_auth(require_person=True)
    @send_file(fixed_type=FigureType.PNG, allow_cache=True)
    def tech_view_figure_preview(proposal_id, fig_id, md5sum):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, TextRole.TECHNICAL_CASE, md5sum,
            'preview')

    @bp.route('/proposal/<int:proposal_id>/technical/pdf/edit',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('pdf_upload.html')
    def tech_edit_pdf(proposal_id):
        return facility.view_case_edit_pdf(
            db, proposal_id, TextRole.TECHNICAL_CASE,
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/technical/pdf/view/<md5sum>')
    @require_auth(require_person=True)
    @send_file(allow_cache=True)
    def tech_view_pdf(proposal_id, md5sum):
        return facility.view_case_view_pdf(
            db, proposal_id, TextRole.TECHNICAL_CASE, md5sum)

    @bp.route('/proposal/<int:proposal_id>/technical/pdf/'
              'preview/<int:page>/<md5sum>')
    @require_auth(require_person=True)
    @send_file(fixed_type=FigureType.PNG, allow_cache=True)
    def tech_view_pdf_preview(proposal_id, page, md5sum):
        return facility.view_case_view_pdf_preview(
            db, proposal_id, page, TextRole.TECHNICAL_CASE, md5sum)

    @bp.route('/proposal/<int:proposal_id>/scientific')
    @require_auth(require_person=True)
    @facility_template('case_edit.html')
    def sci_edit(proposal_id):
        return facility.view_case_edit(db, proposal_id, TextRole.SCIENCE_CASE)

    @bp.route('/proposal/<int:proposal_id>/scientific/text',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('text_edit.html')
    def sci_edit_text(proposal_id):
        return facility.view_case_edit_text(
            db, proposal_id, TextRole.SCIENCE_CASE,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/scientific/figure/new',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('figure_edit.html')
    def sci_new_figure(proposal_id):
        return facility.view_case_edit_figure(
            db, proposal_id, None, TextRole.SCIENCE_CASE,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route(
        '/proposal/<int:proposal_id>/scientific/figure/<int:fig_id>/edit',
        methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('figure_edit.html')
    def sci_edit_figure(proposal_id, fig_id):
        return facility.view_case_edit_figure(
            db, proposal_id, fig_id, TextRole.SCIENCE_CASE,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/scientific/figure/manage',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('figure_manage.html')
    def sci_manage_figure(proposal_id):
        return facility.view_case_manage_figure(
            db, proposal_id, TextRole.SCIENCE_CASE,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/scientific/figure/'
              '<int:fig_id>/<md5sum>')
    @require_auth(require_person=True)
    @send_file(allow_cache=True)
    def sci_view_figure(proposal_id, fig_id, md5sum):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, TextRole.SCIENCE_CASE, md5sum)

    @bp.route('/proposal/<int:proposal_id>/scientific/figure/'
              '<int:fig_id>/thumbnail/<md5sum>')
    @require_auth(require_person=True)
    @send_file(fixed_type=FigureType.PNG, allow_cache=True)
    def sci_view_figure_thumbnail(proposal_id, fig_id, md5sum):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, TextRole.SCIENCE_CASE, md5sum,
            'thumbnail')

    @bp.route('/proposal/<int:proposal_id>/scientific/figure/'
              '<int:fig_id>/preview/<md5sum>')
    @require_auth(require_person=True)
    @send_file(fixed_type=FigureType.PNG, allow_cache=True)
    def sci_view_figure_preview(proposal_id, fig_id, md5sum):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, TextRole.SCIENCE_CASE, md5sum,
            'preview')

    @bp.route('/proposal/<int:proposal_id>/scientific/pdf/edit',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('pdf_upload.html')
    def sci_edit_pdf(proposal_id):
        return facility.view_case_edit_pdf(
            db, proposal_id, TextRole.SCIENCE_CASE,
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/scientific/pdf/view/<md5sum>')
    @require_auth(require_person=True)
    @send_file(allow_cache=True)
    def sci_view_pdf(proposal_id, md5sum):
        return facility.view_case_view_pdf(
            db, proposal_id, TextRole.SCIENCE_CASE, md5sum)

    @bp.route('/proposal/<int:proposal_id>/scientific/pdf/'
              'preview/<int:page>/<md5sum>')
    @require_auth(require_person=True)
    @send_file(fixed_type=FigureType.PNG, allow_cache=True)
    def sci_view_pdf_preview(proposal_id, page, md5sum):
        return facility.view_case_view_pdf_preview(
            db, proposal_id, page, TextRole.SCIENCE_CASE, md5sum)

    @bp.route('/proposal/<int:proposal_id>/calculation',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('calculation_manage.html')
    def calculation_manage(proposal_id):
        return facility.view_calculation_manage(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/feedback')
    @require_auth(require_person=True)
    @facility_template('proposal_feedback.html')
    def proposal_feedback(proposal_id):
        return facility.view_proposal_feedback(db, proposal_id)

    @bp.route('/proposal/<int:proposal_id>/reviews')
    @require_auth(require_person=True)
    @facility_template('proposal_reviews.html')
    def proposal_reviews(proposal_id):
        return facility.view_proposal_reviews(db, proposal_id)

    @bp.route('/proposal/<int:proposal_id>/review/new/<int:reviewer_role>',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('review_edit.html')
    def proposal_review_new(proposal_id, reviewer_role):
        return facility.view_review_new(
            db, proposal_id, reviewer_role,
            (request.form if request.method == 'POST' else None),
            request.referrer)

    @bp.route('/proposal/<int:proposal_id>/reviewers/external/add',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('reviewer_select.html')
    def review_external_add(proposal_id):
        return facility.view_reviewer_add(
            db, proposal_id, ReviewerRole.EXTERNAL,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/reviewers/external/remove/'
              '<int:reviewer_id>',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @templated('confirm.html')
    def review_external_remove(proposal_id, reviewer_id):
        return facility.view_reviewer_remove(
            db, proposal_id, ReviewerRole.EXTERNAL, reviewer_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/reviewers/external/reinvite/'
              '<int:reviewer_id>',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @templated('confirm.html')
    def review_external_reinvite(proposal_id, reviewer_id):
        return facility.view_reviewer_reinvite(
            db, proposal_id, ReviewerRole.EXTERNAL, reviewer_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/decision', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('proposal_decision.html')
    def proposal_decision(proposal_id):
        return facility.view_proposal_decision(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/admin')
    @facility_template('facility_admin.html')
    @require_admin
    def facility_admin():
        return facility.view_facility_admin(db)

    @bp.route('/admin/semester/')
    @facility_template('semester_list.html')
    @require_admin
    def semester_list():
        return facility.view_semester_list(db)

    @bp.route('/admin/semester/new', methods=['GET', 'POST'])
    @facility_template('semester_edit.html')
    @require_admin
    def semester_new():
        return facility.view_semester_edit(
            db, None,
            (request.form if request.method == 'POST' else None))

    @bp.route('/admin/semester/<int:semester_id>')
    @facility_template('semester_view.html')
    @require_admin
    def semester_view(semester_id):
        return facility.view_semester_view(db, semester_id)

    @bp.route('/admin/semester/<int:semester_id>/edit',
              methods=['GET', 'POST'])
    @facility_template('semester_edit.html')
    @require_admin
    def semester_edit(semester_id):
        return facility.view_semester_edit(
            db, semester_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/admin/queue/')
    @facility_template('queue_list.html')
    @require_admin
    def queue_list():
        return facility.view_queue_list(db)

    @bp.route('/admin/queue/new', methods=['GET', 'POST'])
    @facility_template('queue_edit.html')
    @require_admin
    def queue_new():
        return facility.view_queue_edit(
            db, None,
            (request.form if request.method == 'POST' else None))

    @bp.route('/admin/queue/<int:queue_id>')
    @facility_template('queue_view.html')
    @require_admin
    def queue_view(queue_id):
        return facility.view_queue_view(db, queue_id)

    @bp.route('/admin/queue/<int:queue_id>/edit',
              methods=['GET', 'POST'])
    @facility_template('queue_edit.html')
    @require_admin
    def queue_edit(queue_id):
        return facility.view_queue_edit(
            db, queue_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/admin/queue/<int:queue_id>/affiliation',
              methods=['GET', 'POST'])
    @facility_template('affiliation_edit.html')
    @require_admin
    def affiliation_edit(queue_id):
        return facility.view_affiliation_edit(
            db, queue_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/admin/queue/<int:queue_id>/group/<int:group_type>')
    @facility_template('group_view.html')
    @require_admin
    def group_view(queue_id, group_type):
        return facility.view_group_view(db, queue_id, group_type)

    @bp.route('/admin/queue/<int:queue_id>/group/<int:group_type>/add',
              methods=['GET', 'POST'])
    @facility_template('person_select.html')
    @require_admin
    def group_member_add(queue_id, group_type):
        return facility.view_group_member_add(
            db, queue_id, group_type,
            (request.form if request.method == 'POST' else None))

    @bp.route('/admin/queue/<int:queue_id>/group/<int:group_type>/edit',
              methods=['GET', 'POST'])
    @facility_template('group_member_edit.html')
    @require_admin
    def group_member_edit(queue_id, group_type):
        return facility.view_group_member_edit(
            db, queue_id, group_type,
            (request.form if request.method == 'POST' else None))

    @bp.route('/admin/queue/<int:queue_id>/group/<int:group_type>/'
              'reinvite/<int:member_id>',
              methods=['GET', 'POST'])
    @templated('confirm.html')
    @require_admin
    def group_member_reinvite(queue_id, group_type, member_id):
        return facility.view_group_member_reinvite(
            db,  queue_id, group_type, member_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/admin/call/')
    @facility_template('call_list.html')
    @require_admin
    def call_list():
        return facility.view_call_list(db)

    @bp.route('/admin/call/new', methods=['GET', 'POST'])
    @facility_template('call_edit.html')
    @require_admin
    def call_new():
        return facility.view_call_edit(
            db, None,
            (request.form if request.method == 'POST' else None))

    @bp.route('/admin/call/<int:call_id>')
    @facility_template('call_view.html')
    @require_admin
    def call_view(call_id):
        return facility.view_call_view(db, call_id)

    @bp.route('/admin/call/<int:call_id>/edit', methods=['GET', 'POST'])
    @facility_template('call_edit.html')
    @require_admin
    def call_edit(call_id):
        return facility.view_call_edit(
            db, call_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/admin/call/<int:call_id>/proposals')
    @facility_template('call_proposals.html')
    @require_admin
    def call_proposals(call_id):
        return facility.view_call_proposals(db, call_id)

    @bp.route('/admin/categories', methods=['GET', 'POST'])
    @facility_template('category_edit.html')
    @require_admin
    def category_edit():
        return facility.view_category_edit(
            db, (request.form if request.method == 'POST' else None))

    @bp.route('/admin/coverage/')
    @facility_template('moc_list.html')
    @require_admin
    def moc_list():
        return facility.view_moc_list(db)

    @bp.route('/admin/coverage/new', methods=['GET', 'POST'])
    @facility_template('moc_edit.html')
    @require_admin
    def moc_new():
        return facility.view_moc_edit(
            db, None, (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/admin/coverage/<int:moc_id>', methods=['GET', 'POST'])
    @facility_template('moc_edit.html')
    @require_admin
    def moc_edit(moc_id):
        return facility.view_moc_edit(
            db, moc_id, (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/admin/coverage/<int:moc_id>/delete', methods=['GET', 'POST'])
    @require_admin
    @templated('confirm.html')
    def moc_delete(moc_id):
        return facility.view_moc_delete(
            db, moc_id, (request.form if request.method == 'POST' else None))

    @bp.route('/review/<int:reviewer_id>', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('review_edit.html')
    def review_edit(reviewer_id):
        return facility.view_review_edit(
            db, reviewer_id,
            (request.form if request.method == 'POST' else None),
            request.referrer)

    @bp.route('/review/<int:reviewer_id>/information')
    @require_auth(require_person=True)
    @facility_template('review_info.html')
    def review_info(reviewer_id):
        return facility.view_review_info(db, reviewer_id)

    # Configure the facility's calculators.
    for calculator_class in facility.get_calculator_classes():
        calculator_code = calculator_class.get_code()
        calculator_id = db.ensure_calculator(facility.id_, calculator_code)
        calculator = calculator_class(facility, calculator_id)

        facility.calculators[calculator_id] = CalculatorInfo(
            calculator_id, calculator_code, calculator.get_name(),
            calculator, calculator.modes)

        # Create redirect for calculator to its default (first) mode.
        bp.add_url_rule('/calculator/{}/'.format(calculator_code),
                        'calc_{}'.format(calculator_code),
                        make_calculator_redirect(
                            calculator_code,
                            list(calculator.modes.values())[0].code))

        # Create routes for each calculator mode.
        for (calculator_mode_id, calculator_mode) in calculator.modes.items():
            route_opts = (calculator_code, calculator_mode.code)

            bp.add_url_rule('/calculator/{}/{}'.format(*route_opts),
                            'calc_{}_{}'.format(*route_opts),
                            make_calculator_view(
                                db, calculator, code, calculator_code,
                                calculator_mode_id),
                            methods=['GET', 'POST'])

    # Configure the facility's target tools.
    for tool_class in facility.get_target_tool_classes():
        tool_code = tool_class.get_code()
        tool_id = 0  # TODO: db.ensure_target_tool(facility.id, tool_code)
        tool = tool_class(facility, tool_id)

        facility.target_tools[tool_id] = TargetToolInfo(
            tool_id, tool_code, tool.get_name(), tool)

        (single_view, upload_view, proposal_view) = make_target_tool_views(
            db, tool, code, tool_code)

        bp.add_url_rule(
            '/tool/{}'.format(tool_code),
            'tool_{}'.format(tool_code),
            single_view, methods=['GET', 'POST'])

        bp.add_url_rule(
            '/tool/{}/upload'.format(tool_code),
            'tool_upload_{}'.format(tool_code),
            upload_view, methods=['GET', 'POST'])

        bp.add_url_rule(
            '/tool/{}/proposal/<int:proposal_id>'.format(tool_code),
            'tool_proposal_{}'.format(tool_code),
            proposal_view)

        for (template, rule, endpoint, func,
                options) in tool.get_custom_routes():
            bp.add_url_rule(rule, endpoint,
                            make_custom_route(db, template, func), **options)

    @bp.context_processor
    def add_to_context():
        return {
            'facility_name': name,
        }

    return bp


def make_calculator_redirect(calculator_code, calculator_mode):
    """
    Create a view function for a function without specifying a
    mode which should redirect to the given (default mode) for the
    calculator.
    """

    def default_calc_redirect():
        raise HTTPRedirect(url_for('.calc_{}_{}'.format(
            calculator_code, calculator_mode)))

    return default_calc_redirect


def make_calculator_view(db, calculator, facility_code, calculator_code,
                         calculator_mode_id):
    """
    Create a view function for a calculator.

    This is done in a separate function in order to create the proper
    scope for a closure.
    """

    @templated(('{}/calculator_{}.html'.format(facility_code, calculator_code),
                'generic/calculator_base.html'))
    def view_func():
        return calculator.view(
            db, calculator_mode_id, request.args,
            (request.form if request.method == 'POST' else None))

    return view_func


def make_target_tool_views(db, tool, facility_code, tool_code):
    """
    Create view functions for a target tool.
    """

    @templated(('generic/tool_{}.html'.format(tool_code),
                'generic/tool_base.html'))
    def single_view_func():
        return tool.view_single(
            db, request.args,
            (request.form if request.method == 'POST' else None))

    @templated(('generic/tool_{}.html'.format(tool_code),
                'generic/tool_base.html'))
    def upload_view_func():
        return tool.view_upload(
            db, request.args,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @templated(('generic/tool_{}.html'.format(tool_code),
                'generic/tool_base.html'))
    def proposal_view_func(proposal_id):
        return tool.view_proposal(
            db, proposal_id, request.args)

    return (single_view_func, upload_view_func, proposal_view_func)


def make_custom_route(db, template, func):
    """
    Create a custom view function.
    """

    def view_func(**kwargs):
        return func(
            db, request.args,
            (request.form if request.method == 'POST' else None),
            **kwargs)

    if template is None:
        return send_file()(view_func)

    else:
        return templated(template)(view_func)
