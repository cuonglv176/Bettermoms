# __author__ = 'BinhTT'
from odoo import fields, models
from datetime import date
class DocumentExistUpdate(models.Model):
    _name = 'document.exist.update'
    ir_model = fields.Many2many('ir.model', 'document_exist_model_rel', string='Model')

    def button_create_document_from_attachment_exist(self):
        for attachment in self.env['ir.attachment'].search([('res_model', 'not in', (False, 'documents.document')),  ('description', '=', False),
                                                            ('type', '=', 'binary'), ('res_id', 'not in', (0, False))]):
            if self.env['documents.document'].search([('attachment_id', '=', attachment.id)]):
                continue
            model = self.env['ir.model']._get(attachment.res_model)
            folder_name = self.env['documents.folder'].search([('ir_model', '=', model.id)])
            # if not folder_name:
            #     folder_name = self.env['documents.folder'].create({'ir_model': model.id,
            #                                                        'name': model.name})
            if folder_name:
                obj_id = self.env[model.model].browse(attachment.res_id)
                today = date.today()
                quarter = 'Q' + str(attachment.create_date.month // 4 + 1)
                # ('facet_id', 'in', folder_name.facet_ids.ids),
                tag_obj = self.env['documents.tag'].search(
                    [('name', 'in', (str(attachment.create_date.year), str(attachment.create_date.month), quarter))])
                tag_ids = [(6, 0, tag_obj.ids)]
                vals = {
                    'attachment_id': attachment.id,
                    'folder_id': folder_name.id or False,
                    'tag_ids': tag_ids,
                    'partner_id': 'partner_id' in obj_id and obj_id.partner_id.id or False,
                    'res_id': int(obj_id.id),
                    'res_model': model.model,
                }

                document = self.env['documents.document'].with_context().create(vals)

        return