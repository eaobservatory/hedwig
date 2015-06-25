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

from ...type import CalculatorInfo, FigureType, TextRole
from ..util import require_admin, require_auth, send_file, templated


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
    @facility_template('proposal_new.html')
    @require_auth(require_institution=True)
    def proposal_new(call_id):
        return facility.view_proposal_new(
            db, call_id, request.form, request.method == 'POST')

    @bp.route('/proposal/<int:proposal_id>')
    @facility_template('proposal_view.html')
    @require_auth(require_person=True)
    def proposal_view(proposal_id):
        return facility.view_proposal_view(db, proposal_id)

    @bp.route('/proposal/<int:proposal_id>/submit', methods=['GET', 'POST'])
    @facility_template('proposal_submit.html')
    @require_auth(require_person=True)
    def proposal_submit(proposal_id):
        return facility.view_proposal_submit(
            db, proposal_id, request.form, request.method == 'POST')

    @bp.route('/proposal/<int:proposal_id>/withdraw', methods=['GET', 'POST'])
    @facility_template('proposal_withdraw.html')
    @require_auth(require_person=True)
    def proposal_withdraw(proposal_id):
        return facility.view_proposal_withdraw(
            db, proposal_id, request.form, request.method == 'POST')

    @bp.route('/proposal/<int:proposal_id>/title', methods=['GET', 'POST'])
    @facility_template('title_edit.html')
    @require_auth(require_person=True)
    def title_edit(proposal_id):
        return facility.view_title_edit(
            db, proposal_id, request.form, request.method == 'POST')

    @bp.route('/proposal/<int:proposal_id>/abstract', methods=['GET', 'POST'])
    @facility_template('text_edit.html')
    @require_auth(require_person=True)
    def abstract_edit(proposal_id):
        return facility.view_abstract_edit(
            db, proposal_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/member', methods=['GET', 'POST'])
    @facility_template('member_edit.html')
    @require_auth(require_person=True)
    def member_edit(proposal_id):
        return facility.view_member_edit(
            db, proposal_id, request.form, request.method == 'POST')

    @bp.route('/proposal/<int:proposal_id>/member/add',
              methods=['GET', 'POST'])
    @facility_template('member_add.html')
    @require_auth(require_person=True)
    def member_add(proposal_id):
        return facility.view_member_add(
            db, proposal_id, request.form, request.method == 'POST')

    @bp.route('/proposal/<int:proposal_id>/target', methods=['GET', 'POST'])
    @facility_template('target_edit.html')
    @require_auth(require_person=True)
    def target_edit(proposal_id):
        return facility.view_target_edit(
            db, proposal_id, request.form, request.method == 'POST')

    @bp.route('/proposal/<int:proposal_id>/request', methods=['GET', 'POST'])
    @facility_template('request_edit.html')
    @require_auth(require_person=True)
    def request_edit(proposal_id):
        return facility.view_request_edit(
            db, proposal_id, request.form, request.method == 'POST')

    @bp.route('/proposal/<int:proposal_id>/technical')
    @facility_template('case_edit.html')
    @require_auth(require_person=True)
    def tech_edit(proposal_id):
        return facility.view_case_edit(
            db, proposal_id, TextRole.TECHNICAL_CASE)

    @bp.route('/proposal/<int:proposal_id>/technical/text',
              methods=['GET', 'POST'])
    @facility_template('text_edit.html')
    @require_auth(require_person=True)
    def tech_edit_text(proposal_id):
        return facility.view_case_edit_text(
            db, proposal_id, TextRole.TECHNICAL_CASE,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/technical/figure/new',
              methods=['GET', 'POST'])
    @facility_template('figure_edit.html')
    @require_auth(require_person=True)
    def tech_new_figure(proposal_id):
        return facility.view_case_edit_figure(
            db, proposal_id, None, TextRole.TECHNICAL_CASE,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route(
        '/proposal/<int:proposal_id>/technical/figure/<int:fig_id>/edit',
        methods=['GET', 'POST'])
    @facility_template('figure_edit.html')
    @require_auth(require_person=True)
    def tech_edit_figure(proposal_id, fig_id):
        return facility.view_case_edit_figure(
            db, proposal_id, fig_id, TextRole.TECHNICAL_CASE,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/technical/figure/manage',
              methods=['GET', 'POST'])
    @facility_template('figure_manage.html')
    @require_auth(require_person=True)
    def tech_manage_figure(proposal_id):
        return facility.view_case_manage_figure(
            db, proposal_id, TextRole.TECHNICAL_CASE,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/technical/figure/<int:fig_id>')
    @send_file()
    @require_auth(require_person=True)
    def tech_view_figure(proposal_id, fig_id):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, TextRole.TECHNICAL_CASE)

    @bp.route(
        '/proposal/<int:proposal_id>/technical/figure/<int:fig_id>/thumbnail')
    @send_file(FigureType.PNG)
    @require_auth(require_person=True)
    def tech_view_figure_thumbnail(proposal_id, fig_id):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, TextRole.TECHNICAL_CASE, 'thumbnail')

    @bp.route(
        '/proposal/<int:proposal_id>/technical/figure/<int:fig_id>/preview')
    @send_file(FigureType.PNG)
    @require_auth(require_person=True)
    def tech_view_figure_preview(proposal_id, fig_id):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, TextRole.TECHNICAL_CASE, 'preview')

    @bp.route('/proposal/<int:proposal_id>/technical/pdf/edit',
              methods=['GET', 'POST'])
    @facility_template('pdf_upload.html')
    @require_auth(require_person=True)
    def tech_edit_pdf(proposal_id):
        return facility.view_case_edit_pdf(
            db, proposal_id, TextRole.TECHNICAL_CASE,
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/technical/pdf/view')
    @send_file(FigureType.PDF)
    @require_auth(require_person=True)
    def tech_view_pdf(proposal_id):
        return facility.view_case_view_pdf(
            db, proposal_id, TextRole.TECHNICAL_CASE)

    @bp.route('/proposal/<int:proposal_id>/technical/pdf/preview/<int:page>')
    @send_file(FigureType.PNG)
    @require_auth(require_person=True)
    def tech_view_pdf_preview(proposal_id, page):
        return facility.view_case_view_pdf_preview(
            db, proposal_id, page, TextRole.TECHNICAL_CASE)

    @bp.route('/proposal/<int:proposal_id>/scientific')
    @facility_template('case_edit.html')
    @require_auth(require_person=True)
    def sci_edit(proposal_id):
        return facility.view_case_edit(db, proposal_id, TextRole.SCIENCE_CASE)

    @bp.route('/proposal/<int:proposal_id>/scientific/text',
              methods=['GET', 'POST'])
    @facility_template('text_edit.html')
    @require_auth(require_person=True)
    def sci_edit_text(proposal_id):
        return facility.view_case_edit_text(
            db, proposal_id, TextRole.SCIENCE_CASE,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/scientific/figure/new',
              methods=['GET', 'POST'])
    @facility_template('figure_edit.html')
    @require_auth(require_person=True)
    def sci_new_figure(proposal_id):
        return facility.view_case_edit_figure(
            db, proposal_id, None, TextRole.SCIENCE_CASE,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route(
        '/proposal/<int:proposal_id>/scientific/figure/<int:fig_id>/edit',
        methods=['GET', 'POST'])
    @facility_template('figure_edit.html')
    @require_auth(require_person=True)
    def sci_edit_figure(proposal_id, fig_id):
        return facility.view_case_edit_figure(
            db, proposal_id, fig_id, TextRole.SCIENCE_CASE,
            (request.form if request.method == 'POST' else None),
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/scientific/figure/manage',
              methods=['GET', 'POST'])
    @facility_template('figure_manage.html')
    @require_auth(require_person=True)
    def sci_manage_figure(proposal_id):
        return facility.view_case_manage_figure(
            db, proposal_id, TextRole.SCIENCE_CASE,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/scientific/figure/<int:fig_id>')
    @send_file()
    @require_auth(require_person=True)
    def sci_view_figure(proposal_id, fig_id):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, TextRole.SCIENCE_CASE)

    @bp.route(
        '/proposal/<int:proposal_id>/scientific/figure/<int:fig_id>/thumbnail')
    @send_file(FigureType.PNG)
    @require_auth(require_person=True)
    def sci_view_figure_thumbnail(proposal_id, fig_id):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, TextRole.SCIENCE_CASE, 'thumbnail')

    @bp.route(
        '/proposal/<int:proposal_id>/scientific/figure/<int:fig_id>/preview')
    @send_file(FigureType.PNG)
    @require_auth(require_person=True)
    def sci_view_figure_preview(proposal_id, fig_id):
        return facility.view_case_view_figure(
            db, proposal_id, fig_id, TextRole.SCIENCE_CASE, 'preview')

    @bp.route('/proposal/<int:proposal_id>/scientific/pdf/edit',
              methods=['GET', 'POST'])
    @facility_template('pdf_upload.html')
    @require_auth(require_person=True)
    def sci_edit_pdf(proposal_id):
        return facility.view_case_edit_pdf(
            db, proposal_id, TextRole.SCIENCE_CASE,
            (request.files['file'] if request.method == 'POST' else None))

    @bp.route('/proposal/<int:proposal_id>/scientific/pdf/view')
    @send_file(FigureType.PDF)
    @require_auth(require_person=True)
    def sci_view_pdf(proposal_id):
        return facility.view_case_view_pdf(
            db, proposal_id, TextRole.SCIENCE_CASE)

    @bp.route('/proposal/<int:proposal_id>/scientific/pdf/preview/<int:page>')
    @send_file(FigureType.PNG)
    @require_auth(require_person=True)
    def sci_view_pdf_preview(proposal_id, page):
        return facility.view_case_view_pdf_preview(
            db, proposal_id, page, TextRole.SCIENCE_CASE)

    @bp.route('/proposal/<int:proposal_id>/calculation',
              methods=['GET', 'POST'])
    @facility_template('calculation_manage.html')
    @require_auth(require_person=True)
    def calculation_manage(proposal_id):
        return facility.view_calculation_manage(
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
        return facility.view_semester_edit(db, None, request.form,
                                           request.method == 'POST')

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
        return facility.view_semester_edit(db, semester_id, request.form,
                                           request.method == 'POST')

    @bp.route('/admin/queue/')
    @facility_template('queue_list.html')
    @require_admin
    def queue_list():
        return facility.view_queue_list(db)

    @bp.route('/admin/queue/new', methods=['GET', 'POST'])
    @facility_template('queue_edit.html')
    @require_admin
    def queue_new():
        return facility.view_queue_edit(db, None, request.form,
                                        request.method == 'POST')

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
        return facility.view_queue_edit(db, queue_id, request.form,
                                        request.method == 'POST')

    @bp.route('/admin/queue/<int:queue_id>/affiliation',
              methods=['GET', 'POST'])
    @facility_template('affiliation_edit.html')
    @require_admin
    def affiliation_edit(queue_id):
        return facility.view_affiliation_edit(db, queue_id, request.form,
                                              request.method == 'POST')

    @bp.route('/admin/call/')
    @facility_template('call_list.html')
    @require_admin
    def call_list():
        return facility.view_call_list(db)

    @bp.route('/admin/call/new', methods=['GET', 'POST'])
    @facility_template('call_edit.html')
    @require_admin
    def call_new():
        return facility.view_call_edit(db, None, request.form,
                                       request.method == 'POST')

    @bp.route('/admin/call/<int:call_id>')
    @facility_template('call_view.html')
    @require_admin
    def call_view(call_id):
        return facility.view_call_view(db, call_id)

    @bp.route('/admin/call/<int:call_id>/edit', methods=['GET', 'POST'])
    @facility_template('call_edit.html')
    @require_admin
    def call_edit(call_id):
        return facility.view_call_edit(db, call_id, request.form,
                                       request.method == 'POST')

    @bp.route('/admin/call/<int:call_id>/proposals')
    @facility_template('call_proposals.html')
    @require_admin
    def call_proposals(call_id):
        return facility.view_call_proposals(db, call_id)

    # Configure the facility's calculators.
    for calculator_class in facility.get_calculator_classes():
        calculator_code = calculator_class.get_code()
        calculator_id = db.ensure_calculator(facility.id_, calculator_code)
        calculator = calculator_class(facility, calculator_id)

        facility.calculators[calculator_id] = CalculatorInfo(
            calculator_id, calculator_code, calculator.get_name(),
            calculator, calculator.modes)

        for (calculator_mode_id, calculator_mode) in calculator.modes.items():
            route_opts = (calculator_code, calculator_mode.code)

            bp.add_url_rule('/calculator/{}/{}'.format(*route_opts),
                            'calc_{}_{}'.format(*route_opts),
                            make_calculator_view(
                                db, calculator, code, calculator_code,
                                calculator_mode_id),
                            methods=['GET', 'POST'])

    @bp.context_processor
    def add_to_context():
        return {
            'facility_name': name,
        }

    return bp


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
