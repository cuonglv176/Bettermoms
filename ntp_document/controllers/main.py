# __author__ = 'BinhTT'
from odoo import http, _
from odoo.http import content_disposition, request
from odoo.addons.mail.controllers.discuss import DiscussController
from odoo.exceptions import AccessError, UserError
import base64
import json
from datetime import date

class VASFinancialReportController(DiscussController):

    @http.route('/mail/attachment/upload', methods=['POST'], type='http', auth='public')
    def mail_attachment_upload(self, ufile, thread_id, thread_model, is_pending=False, **kwargs):
        if thread_model in ('sale.order', 'purchase.order'):
            channel_partner = request.env['mail.channel.partner']
            if thread_model == 'mail.channel':
                channel_partner = request.env['mail.channel.partner']._get_as_sudo_from_request_or_raise(
                    request=request, channel_id=int(thread_id))
            thread_obj = request.env[thread_model].browse(int(thread_id))
            model_id = request.env['ir.model']._get(thread_model).id
            folder_name = request.env['documents.folder'].search([('ir_model', '=', model_id)])

            if thread_obj and folder_name:
                try:
                    vals_list = []
                    mimetype = ufile.content_type
                    datas = ufile.read()
                    today = date.today()
                    quarter = 'Q' + str(today.month//4 + 1)
                    # ('facet_id', 'in', folder_name.facet_ids.ids),
                    tag_obj = request.env['documents.tag'].search([('name', 'in', (str(today.year), str(today.month), quarter))])
                    tag_ids = [(6, 0, tag_obj.ids)]
                    vals = {
                        'name': ufile.filename,
                        'mimetype': mimetype,
                        'datas': datas,
                        'folder_id': folder_name.id or False,
                        'tag_ids': tag_ids,
                        'partner_id': thread_obj.partner_id.id,
                        'raw': datas,
                        'res_id': int(thread_id),
                        'res_model': thread_model,
                    }
                    if is_pending and is_pending != 'false':
                        # Add this point, the message related to the uploaded file does
                        # not exist yet, so we use those placeholder values instead.
                        vals.update({
                            'res_id': 0,
                            'res_model': 'mail.compose.message',
                        })
                    if channel_partner.env.user.share:
                        # Only generate the access token if absolutely necessary (= not for internal user).
                        vals['access_token'] = channel_partner.env['ir.attachment']._generate_access_token()

                    vals_list.append(vals)

                    cids = request.httprequest.cookies.get('cids', str(request.env.user.company_id.id))
                    allowed_company_ids = [int(cid) for cid in cids.split(',')]
                    document = request.env['documents.document'].with_context(
                        allowed_company_ids=allowed_company_ids).create(
                        vals_list)

                    attachment = document.attachment_id
                    # attachment._post_add_create()
                    attachmentData = {
                        'filename': ufile.filename,
                        'id': attachment.id,
                        'mimetype': attachment.mimetype,
                        'name': attachment.name,
                        'size': attachment.file_size
                    }
                    if attachment.access_token:
                        attachmentData['accessToken'] = attachment.access_token


                except AccessError:
                    attachmentData = {'error': _("You are not allowed to upload an attachment here.")}
                return request.make_response(
                    data=json.dumps(attachmentData),
                    headers=[('Content-Type', 'application/json')]
                )

        return super(VASFinancialReportController, self).mail_attachment_upload(ufile, thread_id, thread_model, is_pending, **kwargs)
