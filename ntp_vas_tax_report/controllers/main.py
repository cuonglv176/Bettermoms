# __author__ = 'BinhTT'
from odoo import http
from odoo.http import content_disposition, request
from odoo.addons.account_reports.controllers.main import FinancialReportController
from odoo.tools import html_escape

import json


class VASFinancialReportController(FinancialReportController):
    @http.route('/account_reports', type='http', auth='user', methods=['POST'], csrf=False)
    def get_report(self, model, options, output_format, financial_id=None, **kw):
        if output_format != 'vas_xlsx':
            return super(VASFinancialReportController, self).get_report(model, options, output_format, financial_id)
        uid = request.session.uid
        account_report_model = request.env['account.report']
        options = json.loads(options)
        cids = kw.get('allowed_company_ids')
        if not cids or cids == 'null':
            cids = request.httprequest.cookies.get('cids', str(request.env.user.company_id.id))
        allowed_company_ids = [int(cid) for cid in cids.split(',')]
        report_obj = request.env[model].with_user(uid).with_context(allowed_company_ids=allowed_company_ids)
        if financial_id and financial_id != 'null':
            report_obj = report_obj.browse(int(financial_id))
        report_name = report_obj.get_report_filename(options)
        if output_format == 'vas_xlsx':
                response = request.make_response(
                    None,
                    headers=[
                        ('Content-Type', account_report_model.get_export_mime_type('xlsx')),
                        ('Content-Disposition', content_disposition(report_name + '.xlsx'))
                    ]
                )
                if options.get('report_name', '') == 'detail_report':
                    response.stream.write(report_obj.get_vas_detail_xlsx(options))
                else:
                    response.stream.write(report_obj.get_vas_xlsx(options))

                return response

