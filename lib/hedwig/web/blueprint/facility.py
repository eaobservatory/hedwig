# Copyright (C) 2015-2021 East Asian Observatory
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

from ...error import FormattedError
from ...type.enum import FigureType
from ..util import HTTPRedirect, \
    require_admin, require_auth, send_file, send_json, templated, url_for


def create_facility_blueprint(db, facility):
    """
    Create Flask blueprint for a facility.

    **Calculators**

    A list of possible HTML templates to use for the calculator
    is constructed as follows:

    * `<facility_code>/calculator_<calculator_code>.html`

      The template for this particular calculator in the current
      facility's template directory.

    * `<calculator_facility_code>/calculator_<calculator_code>.html`

      The template for this particular calculator in the template
      directory for the facility (code) returned by the calculator's
      :meth:`~hedwig.view.calculator.BaseCalculator.get_default_facility_code`
      method, if that method returns a value other than `None`.

    * `generic/calculator_base.html`

      The base calculator template.

    **Target Tools**

    A list of possible HTML templates to use for the target tool
    is constructed as follows:

    * `<facility code>/tool_<tool code>.html`

      The template for the specific tool and current facility.

    * `<tool facility code>/tool_<tool code>.html`

      The template for the specific tool and its default facility.

    * `generic/tool_base.html`

      The base target tool template.
    """

    code = facility.get_code()
    name = facility.get_name()

    bp = Blueprint(code, __name__)

    def facility_template(template):
        """
        Decorator which uses the template from the facility's directory if it
        exists, otherwise the generic template.

        It does this by providing a list of alternative templates,
        from which Flask's `render_template` method will pick the first which
        exists.  The list of possible templates is passed to the normal
        Hedwig :func:`~hedwg.web.util.templated` decorator.
        """

        def decorator(f):
            return templated((code + '/' + template, 'generic/' + template))(f)
        return decorator

    @bp.route('/')
    @facility_template('facility_home.html')
    def facility_home():
        return facility.view_facility_home(db)

    @bp.route('/semester/<int:semester_id>/'
              '<hedwig_call_type_{}:call_type>'.format(code))
    @facility_template('semester_calls.html')
    def semester_calls(semester_id, call_type):
        return facility.view_semester_calls(
            db, semester_id, call_type, None)

    @bp.route('/semester/<int:semester_id>/'
              '<hedwig_call_type_{}:call_type>/<int:queue_id>'.format(code))
    @facility_template('semester_calls.html')
    def semester_call_separate(semester_id, call_type, queue_id):
        return facility.view_semester_calls(
            db, semester_id, call_type, queue_id)

    @bp.route('/semester/closed')
    @facility_template('semester_closed.html')
    def semester_closed():
        return facility.view_semester_closed(db)

    @bp.route('/semester/other')
    @facility_template('semester_non_standard.html')
    def semester_non_standard():
        return facility.view_semester_non_standard(db)

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

    @bp.route('/call/<int:call_id>/review/allocation')
    @require_auth(require_person=True)
    @facility_template('call_review_allocation.html')
    def review_call_allocation(call_id):
        return facility.view_review_call_allocation(db, call_id)

    @bp.route('/call/<int:call_id>/review/allocation/query')
    @require_auth(require_person=True)
    @send_json()
    def review_call_allocation_query(call_id):
        return facility.view_review_call_allocation_query(db, call_id)

    @bp.route('/call/<int:call_id>/review/review_stats')
    @require_auth(require_person=True)
    @facility_template('call_review_statistics.html')
    def review_call_stats(call_id):
        return facility.view_review_call_stats(db, call_id)

    @bp.route('/call/<int:call_id>/review/review_stats/download')
    @require_auth(require_person=True)
    @send_file()
    def review_call_stats_download(call_id):
        return facility.view_review_call_stats_download(db, call_id)

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

    @bp.route('/call/<int:call_id>/deadline', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('call_review_deadline.html')
    def review_call_deadline(call_id):
        return facility.view_review_call_deadline(
            db, call_id, (request.form if request.method == 'POST' else None))

    @bp.route('/call/<int:call_id>/advance_final', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('call_advance_final_confirm.html')
    def review_call_advance_final(call_id):
        return facility.view_review_advance_final(
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

    @bp.route('/call/<int:call_id>/reviewers/'
              '<hedwig_review_{}:reviewer_role>'.format(code),
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('reviewer_grid.html')
    def review_call_grid(call_id, reviewer_role):
        return facility.view_reviewer_grid(
            db, call_id, reviewer_role,
            (request.form if request.method == 'POST' else None))

    @bp.route(
        '/call/<int:call_id>/reviewers/<hedwig_review_{}:reviewer_role>'
        '/notify'.format(code),
        methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('reviewer_notify.html')
    def review_call_notify(call_id, reviewer_role):
        return facility.view_reviewer_notify(
            db, call_id, reviewer_role,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>')
    @require_auth(require_person=True)
    @facility_template('proposal_view.html')
    def proposal_view(proposal_id):
        return facility.view_proposal_view(db, proposal_id, request.args)

    @bp.route('/proposal/<int:proposal_id>/alter_state',
              methods=['GET', 'POST'])
    @require_admin
    @facility_template('proposal_alter_state.html')
    def proposal_alter_state(proposal_id):
        return facility.view_proposal_alter_state(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

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

    @bp.route('/proposal/<int:proposal_id>/member_affiliation/<int:member_id>',
              methods=['GET', 'POST'])
    @require_admin
    @facility_template('member_affiliation_edit.html')
    def member_affiliation_edit(proposal_id, member_id):
        return facility.view_member_affiliation_edit(
            db, proposal_id, member_id,
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

    @bp.route('/proposal/<int:proposal_id>/target/download')
    @require_auth(require_person=True)
    @send_file()
    def target_download(proposal_id):
        return facility.view_target_download(db, proposal_id)

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

    @bp.route('/proposal/<int:proposal_id>/<hedwig_text_{}:role>'.format(code))
    @require_auth(require_person=True)
    @facility_template('case_edit.html')
    def case_edit(proposal_id, role):
        return facility.view_case_edit(db, proposal_id, role)

    @bp.route('/proposal/<int:proposal_id>/'
              '<hedwig_text_{}:role>/text'.format(code),
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('text_edit.html')
    def case_edit_text(proposal_id, role):
        return facility.view_case_edit_text(
            db, proposal_id, role,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/'
              '<hedwig_text_{}:role>/figure/new'.format(code),
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('figure_edit.html')
    def case_new_figure(proposal_id, role):
        return facility.view_case_edit_figure(
            db, proposal_id, None, role,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/<hedwig_text_{}:role>/'
              'figure/<int:fig_id>/edit'.format(code),
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('figure_edit.html')
    def case_edit_figure(proposal_id, role, fig_id):
        return facility.view_case_edit_figure(
            db, proposal_id, fig_id, role,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/'
              '<hedwig_text_{}:role>/figure/manage'.format(code),
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('figure_manage.html')
    def case_manage_figure(proposal_id, role):
        return facility.view_case_manage_figure(
            db, proposal_id, role,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/<hedwig_text_{}:role>/'
              'figure/<int:fig_id>/<md5sum>'.format(code))
    @require_auth(require_person=True)
    @send_file(allow_cache=True)
    def case_view_figure(proposal_id, role, fig_id, md5sum):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, role, md5sum)

    @bp.route('/proposal/<int:proposal_id>/<hedwig_text_{}:role>/'
              'figure/<int:fig_id>/thumbnail/<md5sum>'.format(code))
    @require_auth(require_person=True)
    @send_file(fixed_type=FigureType.PNG, allow_cache=True)
    def case_view_figure_thumbnail(proposal_id, role, fig_id, md5sum):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, role, md5sum,
            'thumbnail')

    @bp.route('/proposal/<int:proposal_id>/<hedwig_text_{}:role>/'
              'figure/<int:fig_id>/preview/<md5sum>'.format(code))
    @require_auth(require_person=True)
    @send_file(fixed_type=FigureType.PNG, allow_cache=True)
    def case_view_figure_preview(proposal_id, role, fig_id, md5sum):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, role, md5sum,
            'preview')

    @bp.route('/proposal/<int:proposal_id>/'
              '<hedwig_text_{}:role>/pdf/edit'.format(code),
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('pdf_upload.html')
    def case_edit_pdf(proposal_id, role):
        return facility.view_case_edit_pdf(
            db, proposal_id, role,
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/<hedwig_text_{}:role>/'
              'pdf/view/<md5sum>'.format(code))
    @require_auth(require_person=True)
    @send_file(allow_cache=True)
    def case_view_pdf(proposal_id, role, md5sum):
        return facility.view_case_view_pdf(
            db, proposal_id, role, md5sum)

    @bp.route('/proposal/<int:proposal_id>/<hedwig_text_{}:role>/'
              'pdf/preview/<int:page>/<md5sum>'.format(code))
    @require_auth(require_person=True)
    @send_file(fixed_type=FigureType.PNG, allow_cache=True)
    def case_view_pdf_preview(proposal_id, role, page, md5sum):
        return facility.view_case_view_pdf_preview(
            db, proposal_id, page, role, md5sum)

    @bp.route('/proposal/<int:proposal_id>/calculation',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('calculation_manage.html')
    def calculation_manage(proposal_id):
        return facility.view_calculation_manage(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/calculation/<int:calculation_id>')
    @require_auth(require_person=True)
    def calculation_view(proposal_id, calculation_id):
        return facility.view_calculation_view(
            db, proposal_id, calculation_id)

    @bp.route('/proposal/<int:proposal_id>/copy/<int:request_id>/')
    @require_auth(require_person=True)
    @facility_template('request_status.html')
    def proposal_copy_request_status(proposal_id, request_id):
        return facility.view_proposal_copy_request_status(
            db, proposal_id, request_id)

    @bp.route('/proposal/<int:proposal_id>/copy/<int:request_id>/query')
    @require_auth(require_person=True)
    @send_json()
    def proposal_copy_request_query(proposal_id, request_id):
        return facility.view_proposal_copy_request_query(
            db, proposal_id, request_id)

    @bp.route('/proposal/<int:proposal_id>/feedback')
    @require_auth(require_person=True)
    @facility_template('proposal_feedback.html')
    def proposal_feedback(proposal_id):
        return facility.view_proposal_feedback(db, proposal_id)

    @bp.route('/proposal/<int:proposal_id>/review/')
    @require_auth(require_person=True)
    @facility_template('proposal_reviews.html')
    def proposal_reviews(proposal_id):
        return facility.view_proposal_reviews(db, proposal_id)

    @bp.route('/proposal/<int:proposal_id>/review/'
              '<hedwig_review_{}:reviewer_role>/new'.format(code),
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('review_edit.html')
    def proposal_review_new(proposal_id, reviewer_role):
        return facility.view_review_new(
            db, proposal_id, reviewer_role, request.args,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/review/'
              '<hedwig_review_{}:reviewer_role>/add'.format(code),
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('reviewer_select.html')
    def proposal_reviewer_add(proposal_id, reviewer_role):
        return facility.view_reviewer_add(
            db, proposal_id, reviewer_role,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal_by_code')
    @facility_template('proposal_by_code.html')
    def proposal_by_code():
        return facility.view_proposal_by_code(db, request.args)

    @bp.route('/review/<int:reviewer_id>/remove',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @templated('confirm.html')
    def proposal_reviewer_remove(reviewer_id):
        return facility.view_reviewer_remove(
            db, reviewer_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/review/<int:reviewer_id>/reinvite',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('reviewer_reinvite_confirm.html')
    def proposal_reviewer_reinvite(reviewer_id):
        return facility.view_reviewer_reinvite(
            db, reviewer_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/review/<int:reviewer_id>/remind',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('reviewer_reinvite_confirm.html')
    def proposal_reviewer_remind(reviewer_id):
        return facility.view_reviewer_remind(
            db, reviewer_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/decision', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('proposal_decision.html')
    def proposal_decision(proposal_id):
        return facility.view_proposal_decision(
            db, proposal_id, request.args,
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

    @bp.route('/admin/semester/<int:semester_id>/preamble/'
              '<hedwig_call_type_{}:call_type>'.format(code),
              methods=['GET', 'POST'])
    @facility_template('call_preamble_edit.html')
    @require_admin
    def call_preamble_edit(semester_id, call_type):
        return facility.view_call_preamble_edit(
            db, semester_id, call_type,
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

    @bp.route('/admin/queue/<int:queue_id>/group/<hedwig_group:group_type>')
    @facility_template('group_view.html')
    @require_admin
    def group_view(queue_id, group_type):
        return facility.view_group_view(db, queue_id, group_type)

    @bp.route('/admin/queue/<int:queue_id>/group/<hedwig_group:group_type>/'
              'add',
              methods=['GET', 'POST'])
    @templated('person_select.html')
    @require_admin
    def group_member_add(queue_id, group_type):
        return facility.view_group_member_add(
            db, queue_id, group_type,
            (request.form if request.method == 'POST' else None))

    @bp.route('/admin/queue/<int:queue_id>/group/<hedwig_group:group_type>/'
              'edit',
              methods=['GET', 'POST'])
    @facility_template('group_member_edit.html')
    @require_admin
    def group_member_edit(queue_id, group_type):
        return facility.view_group_member_edit(
            db, queue_id, group_type,
            (request.form if request.method == 'POST' else None))

    @bp.route('/admin/queue/<int:queue_id>/group/<hedwig_group:group_type>/'
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

    @bp.route('/admin/call/new/<hedwig_call_type_{}:call_type>'.format(code),
              methods=['GET', 'POST'])
    @facility_template('call_edit.html')
    @require_admin
    def call_new(call_type):
        return facility.view_call_edit(
            db, None, call_type,
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
            db, call_id, None,
            (request.form if request.method == 'POST' else None))

    @bp.route(
        '/admin/call/<int:call_id>/intermediate_close',
        methods=['GET', 'POST'])
    @facility_template('call_mid_close.html')
    @require_admin
    def call_mid_close(call_id):
        return facility.view_call_mid_close(
            db, call_id, (request.form if request.method == 'POST' else None))

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

    @bp.route('/review/<int:reviewer_id>', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('review_edit.html')
    def review_edit(reviewer_id):
        return facility.view_review_edit(
            db, reviewer_id, request.args,
            (request.form if request.method == 'POST' else None))

    @bp.route('/review/<int:reviewer_id>/accept', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('review_accept.html')
    def review_accept(reviewer_id):
        return facility.view_review_accept(
            db, reviewer_id, request.args,
            (request.form if request.method == 'POST' else None))

    @bp.route('/review/<int:reviewer_id>/information')
    @require_auth(require_person=True)
    @facility_template('review_info.html')
    def review_info(reviewer_id):
        return facility.view_review_info(db, reviewer_id)

    @bp.route('/review/<int:reviewer_id>/calculation',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('calculation_manage.html')
    def review_calculation_manage(reviewer_id):
        return facility.view_review_calculation_manage(
            db, reviewer_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/review/<int:reviewer_id>/calculation/<int:review_calculation_id>')
    @require_auth(require_person=True)
    def review_calculation_view(reviewer_id, review_calculation_id):
        return facility.view_review_calculation_view(
            db, reviewer_id, review_calculation_id)

    @bp.route('/review/<int:reviewer_id>/figure/new', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('figure_edit.html')
    def review_new_figure(reviewer_id):
        return facility.view_review_edit_figure(
            db, reviewer_id, None,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route(
        '/review/<int:reviewer_id>/figure/<int:fig_id>/edit',
        methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('figure_edit.html')
    def review_edit_figure(reviewer_id, fig_id):
        return facility.view_review_edit_figure(
            db, reviewer_id, fig_id,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/review/<int:reviewer_id>/figure/<int:fig_id>/<md5sum>')
    @require_auth(require_person=True)
    @send_file(allow_cache=True)
    def review_view_figure(reviewer_id, fig_id, md5sum):
        return facility.view_review_view_figure(
            db, reviewer_id, fig_id, md5sum)

    @bp.route('/review/<int:reviewer_id>/figure/<int:fig_id>/thumbnail/'
              '<md5sum>')
    @require_auth(require_person=True)
    @send_file(fixed_type=FigureType.PNG, allow_cache=True)
    def review_view_figure_thumbnail(reviewer_id, fig_id, md5sum):
        return facility.view_review_view_figure(
            db, reviewer_id, fig_id, md5sum, 'thumbnail')

    @bp.route('/review/<int:reviewer_id>/figure/<int:fig_id>/preview/<md5sum>')
    @require_auth(require_person=True)
    @send_file(fixed_type=FigureType.PNG, allow_cache=True)
    def review_view_figure_preview(reviewer_id, fig_id, md5sum):
        return facility.view_review_view_figure(
            db, reviewer_id, fig_id, md5sum, 'preview')

    @bp.route('/review/<int:reviewer_id>/figure/manage',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @facility_template('figure_manage.html')
    def review_manage_figure(reviewer_id):
        return facility.view_review_manage_figure(
            db, reviewer_id,
            (request.form if request.method == 'POST' else None))

    # Register custom routes.
    for route in facility.get_custom_routes():
        options = {}
        if route.options.get('allow_post', False):
            options['methods'] = ['GET', 'POST']

        bp.add_url_rule(
            route.rule, route.endpoint,
            make_custom_route(
                db,
                (None if route.template is None
                 else ['{}/{}'.format(x, route.template)
                       for x in (code, 'generic')]),
                route.func,
                **route.options),
            **options)

    # Configure the facility's calculators.
    for calculator_info in facility.calculators.values():
        calculator = calculator_info.calculator

        # Prepare information to generate list of templates to use.
        template_params = [(code, calculator_info.code)]

        default_facility_code = calculator.get_default_facility_code()
        if ((default_facility_code is not None) and
                (default_facility_code != code)):
            template_params.append((
                default_facility_code, calculator_info.code))

        template_params.append(('generic', 'base'))

        extra_context = {
            'calculator_code': calculator_info.code,
            'calculator_name': calculator_info.name,
        }

        # Create redirect for calculator to its default (first) mode.
        bp.add_url_rule(
            '/calculator/{}/'.format(calculator_info.code),
            'calc_{}'.format(calculator_info.code),
            make_custom_redirect(
                '.calc_{}_{}'.format(
                    calculator_info.code,
                    list(calculator_info.modes.values())[0].code)))

        # Create routes for each calculator mode.
        for (calculator_mode_id, calculator_mode) in \
                calculator_info.modes.items():
            route_opts = (calculator_info.code, calculator_mode.code)

            calculator_info.view_functions[calculator_mode_id] = \
                view_func = make_custom_route(
                db,
                ['{}/calculator_{}.html'.format(*x) for x in template_params],
                calculator.view, include_args=True, allow_post=True,
                extra_params=[calculator_mode_id],
                extra_context=extra_context)

            bp.add_url_rule(
                '/calculator/{}/{}'.format(*route_opts),
                'calc_{}_{}'.format(*route_opts),
                view_func,
                methods=['GET', 'POST'])

        for route in calculator.get_custom_routes():
            options = {}
            if route.options.get('allow_post', False):
                options['methods'] = ['GET', 'POST']

            bp.add_url_rule(
                '/calculator/{}/{}'.format(calculator_info.code, route.rule),
                'calc_{}_{}'.format(calculator_info.code, route.endpoint),
                make_custom_route(
                    db,
                    (None if route.template is None else [
                        '{}/calculator_{}_{}'.format(*(x + (route.template,)))
                        for x in template_params]),
                    route.func,
                    extra_context=(None if route.template is None
                                   else extra_context),
                    **route.options),
                **options)

    # Configure the facility's target tools.
    for tool_info in facility.target_tools.values():
        tool = tool_info.tool

        # Prepare information to generate list of templates to use.
        template_params = [(code, tool_info.code)]

        default_facility_code = tool.get_default_facility_code()
        if ((default_facility_code is not None) and
                (default_facility_code != code)):
            template_params.append((default_facility_code, tool_info.code))

        template_params.append(('generic', 'base'))

        extra_context = {
            'target_tool_code': tool_info.code,
            'target_tool_name': tool_info.name,
        }

        bp.add_url_rule(
            '/tool/{}'.format(tool_info.code),
            'tool_{}'.format(tool_info.code),
            make_custom_route(
                db, ['{}/tool_{}.html'.format(*x) for x in template_params],
                tool.view_single, include_args=True, allow_post=True,
                extra_context=extra_context),
            methods=['GET', 'POST'])

        bp.add_url_rule(
            '/tool/{}/upload'.format(tool_info.code),
            'tool_{}_upload'.format(tool_info.code),
            make_custom_route(
                db, ['{}/tool_{}.html'.format(*x) for x in template_params],
                tool.view_upload, include_args=True,
                allow_post=True, post_files=['file'],
                extra_context=extra_context),
            methods=['GET', 'POST'])

        bp.add_url_rule(
            '/tool/{}/proposal/<int:proposal_id>'.format(tool_info.code),
            'tool_{}_proposal'.format(tool_info.code),
            make_custom_route(
                db, ['{}/tool_{}.html'.format(*x) for x in template_params],
                tool.view_proposal, include_args=True, auth_required=True,
                init_route_params=['proposal_id'],
                extra_context=extra_context))

        for route in tool.get_custom_routes():
            options = {}
            if route.options.get('allow_post', False):
                options['methods'] = ['GET', 'POST']

            bp.add_url_rule(
                '/tool/{}/{}'.format(tool_info.code, route.rule),
                'tool_{}_{}'.format(tool_info.code, route.endpoint),
                make_custom_route(
                    db,
                    (None if route.template is None else [
                        '{}/tool_{}_{}'.format(*(x + (route.template,)))
                        for x in template_params]),
                    route.func,
                    extra_context=(None if route.template is None
                                   else extra_context),
                    **route.options),
                **options)

    @bp.context_processor
    def add_to_context():
        return {
            'facility_name': name,
            'facility_role_class': facility.get_reviewer_roles(),
            'facility_call_type_class': facility.get_call_types(),
        }

    return bp


def make_custom_redirect(target, target_opts={}):
    """
    Create a view function for a redirect to the given target.

    The target and options (for use with `url_for`) must be passed
    rather than a direct URL so that `url_for` can be called in the
    context of handing a request.
    """

    def custom_redirect():
        raise HTTPRedirect(url_for(target, **target_opts))

    return custom_redirect


def make_custom_route(db, template, func, include_args=False,
                      allow_post=False, post_files=[],
                      send_file_opts={}, extra_params=[],
                      auth_required=False, admin_required=False,
                      init_route_params=[], extra_context=None):
    """
    Create a custom view function.

    Creates a route handler which calls the specified function `func` with
    the arguments:

    * Database control object.
    * Any route arguments listed in `init_route_params`.
    * Any specified `extra_params`.
    * If `include_args` was specified: the request arguments.
    * If `allow_post` was specified: the request form (if the request is a
      POST, or `None` otherwise).
    * If `allow_post` was specified: for each entry in `post_files`, the
      corresponding file (if the request is a POST, or `None` otherwise).
    * Any other route keyword arguments (not listed in `init_route_params`).

    If the `template` argument is specified then the view function
    is wrapped by the :func:`~hedwig.web.util.templated` decorator.
    Otherwise it is assumed that a file is being generated
    and the :func:`~hedwig.web.util.send_file` decorator is
    applied instead, with the given `send_file_opts`.

    If `extra_context` is specified, the context dictionary returned by the
    view function is updated using it (like a context processor).
    """

    def view_func(**kwargs):
        args = [db]
        for param in init_route_params:
            args.append(kwargs.pop(param))
        args.extend(extra_params)
        if include_args:
            args.append(request.args)
        if allow_post:
            args.append(request.form if request.method == 'POST' else None)
            for post_file in post_files:
                args.append(request.files[post_file]
                            if request.method == 'POST' else None)

        ctx = func(*args, **kwargs)

        if extra_context is not None:
            ctx.update(extra_context)

        return ctx

    if template is None:
        if extra_context is not None:
            raise FormattedError(
                'custom file route for {!r} has extra context', func)
        view_func = send_file(**send_file_opts)(view_func)

    else:
        view_func = templated(template)(view_func)

    if auth_required:
        view_func = require_auth(require_person=True)(view_func)

    if admin_required:
        view_func = require_admin(view_func)

    return view_func
