from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import serialize_exception, content_disposition

import base64


class Binary(http.Controller):
    @http.route(
        "/web/ntp_payment_support/download_bulk_transfer", type="http", auth="user"
    )
    @serialize_exception
    def download_bulk_transfer(self, model, field, id, filename=None, **kw):
        """Download link for files stored as binary fields.
        :param str model: name of the model to fetch the binary from
        :param str field: binary field
        :param str id: id of the record from which to fetch the binary
        :param str filename: field holding the file's name, if any
        :returns: :class:`werkzeug.wrappers.Response`
        """
        Model = request.env[model].sudo()
        res = Model.browse(int(id))
        res.action_generate_report()

        filecontent = base64.b64decode(res[field].datas or "")
        if not filecontent:
            return request.not_found()
        else:
            if not filename:
                filename = "%s_%s" % (model.replace(".", "_"), id)
            return request.make_response(
                filecontent,
                [
                    ("Content-Type", "application/octet-stream"),
                    ("Content-Disposition", content_disposition(filename)),
                ],
            )
