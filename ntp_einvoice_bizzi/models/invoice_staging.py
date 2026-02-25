# -*- coding: utf-8 -*-
"""
Model: invoice.staging.queue
Bảng trung gian lưu trữ hóa đơn nhận từ Chrome Extension
trước khi đẩy sang Bizzi.
"""
import base64
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class InvoiceStagingQueue(models.Model):
    _name = "invoice.staging.queue"
    _description = "Invoice Staging Queue"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "invoice_number"

    # ====================================================================
    # Basic Info Fields
    # ====================================================================
    invoice_number = fields.Char(
        string="Số hóa đơn",
        required=True,
        index=True,
        tracking=True,
        help="Số hóa đơn điện tử",
    )
    invoice_code = fields.Char(
        string="Mã tra cứu",
        index=True,
        help="Mã tra cứu hóa đơn",
    )
    invoice_symbol = fields.Char(
        string="Ký hiệu",
        help="Ký hiệu hóa đơn (VD: 1C25TAA)",
    )
    invoice_date = fields.Date(
        string="Ngày lập",
        tracking=True,
    )
    source = fields.Selection(
        selection=[
            ("grab", "Grab"),
            ("tracuu", "SPV Tracuuhoadon"),
            ("shinhan", "Shinhan Bank"),
            ("manual", "Thủ công"),
        ],
        string="Nguồn",
        required=True,
        default="grab",
        tracking=True,
    )

    # ====================================================================
    # Seller Info
    # ====================================================================
    seller_tax_code = fields.Char(
        string="Mã số thuế NCC",
        index=True,
        tracking=True,
        help="Mã số thuế nhà cung cấp",
    )
    seller_name = fields.Char(
        string="Tên người bán",
        tracking=True,
    )

    # ====================================================================
    # Amount Fields
    # ====================================================================
    amount_untaxed = fields.Float(
        string="Tiền trước thuế",
        digits=(16, 2),
    )
    amount_tax = fields.Float(
        string="Tiền thuế",
        digits=(16, 2),
    )
    amount_total = fields.Float(
        string="Tổng tiền sau thuế",
        digits=(16, 2),
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        default=lambda self: self.env.company.currency_id.id,
    )

    # ====================================================================
    # File Attachments
    # ====================================================================
    pdf_file = fields.Binary(
        string="File PDF",
        attachment=True,
        help="File PDF hóa đơn điện tử",
    )
    pdf_filename = fields.Char(
        string="Tên file PDF",
    )
    xml_file = fields.Binary(
        string="File XML",
        attachment=True,
        help="File XML hóa đơn điện tử",
    )
    xml_filename = fields.Char(
        string="Tên file XML",
    )
    has_pdf = fields.Boolean(
        string="Có file PDF",
        compute="_compute_has_files",
        store=True,
    )
    has_xml = fields.Boolean(
        string="Có file XML",
        compute="_compute_has_files",
        store=True,
    )

    # ====================================================================
    # Bizzi Integration Fields
    # ====================================================================
    bizzi_status = fields.Selection(
        selection=[
            ("draft", "Nháp"),
            ("pushed", "Đã đẩy sang Bizzi"),
            ("processed", "Bizzi xử lý xong"),
            ("failed", "Lỗi"),
        ],
        string="Trạng thái Bizzi",
        default="draft",
        tracking=True,
        index=True,
    )
    bizzi_document_id = fields.Char(
        string="Bizzi Document ID",
        readonly=True,
        help="ID tài liệu trên hệ thống Bizzi",
    )
    bizzi_response_log = fields.Text(
        string="Log phản hồi Bizzi",
        readonly=True,
        help="Chi tiết mã lỗi hoặc message trả về từ Bizzi API",
    )
    bizzi_push_date = fields.Datetime(
        string="Ngày đẩy sang Bizzi",
        readonly=True,
    )
    retry_count = fields.Integer(
        string="Số lần thử lại",
        default=0,
        readonly=True,
    )

    # ====================================================================
    # Extension Sync Info
    # ====================================================================
    extension_sync_date = fields.Datetime(
        string="Ngày đồng bộ từ Extension",
        readonly=True,
    )
    extension_session_id = fields.Char(
        string="Extension Session ID",
        readonly=True,
        help="ID phiên đồng bộ từ Extension",
    )
    raw_data = fields.Text(
        string="Dữ liệu thô",
        readonly=True,
        help="Dữ liệu JSON gốc nhận từ Extension",
    )

    # ====================================================================
    # Notes
    # ====================================================================
    notes = fields.Text(string="Ghi chú")
    error_message = fields.Text(
        string="Chi tiết lỗi",
        readonly=True,
    )

    # ====================================================================
    # SQL Constraints - Deduplication
    # ====================================================================
    _sql_constraints = [
        (
            "unique_invoice_seller",
            "UNIQUE(invoice_number, seller_tax_code)",
            "Hóa đơn này (Số hóa đơn + MST nhà cung cấp) đã tồn tại trong hệ thống!",
        ),
    ]

    # ====================================================================
    # Computed Fields
    # ====================================================================
    @api.depends("pdf_file", "xml_file")
    def _compute_has_files(self):
        for rec in self:
            rec.has_pdf = bool(rec.pdf_file)
            rec.has_xml = bool(rec.xml_file)

    # ====================================================================
    # Constraints
    # ====================================================================
    @api.constrains("invoice_number", "seller_tax_code")
    def _check_duplicate(self):
        for rec in self:
            if rec.invoice_number and rec.seller_tax_code:
                domain = [
                    ("invoice_number", "=", rec.invoice_number),
                    ("seller_tax_code", "=", rec.seller_tax_code),
                    ("id", "!=", rec.id),
                ]
                duplicate = self.search(domain, limit=1)
                if duplicate:
                    raise ValidationError(
                        _(
                            "Hóa đơn số '%s' của nhà cung cấp MST '%s' đã tồn tại "
                            "trong hệ thống (ID: %d)."
                        )
                        % (rec.invoice_number, rec.seller_tax_code, duplicate.id)
                    )

    # ====================================================================
    # Business Logic Methods
    # ====================================================================
    def action_push_to_bizzi(self):
        """Đẩy hóa đơn sang Bizzi (thủ công)."""
        self.ensure_one()
        if self.bizzi_status not in ("draft", "failed"):
            raise ValidationError(
                _("Chỉ có thể đẩy hóa đơn ở trạng thái Nháp hoặc Lỗi.")
            )
        connector = self.env["bizzi.api.connector"]
        return connector.push_invoice_to_bizzi(self)

    def action_push_selected_to_bizzi(self):
        """Đẩy các hóa đơn được chọn sang Bizzi."""
        records = self.filtered(lambda r: r.bizzi_status in ("draft", "failed"))
        if not records:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Không có hóa đơn"),
                    "message": _("Không có hóa đơn nào ở trạng thái Nháp hoặc Lỗi để đẩy."),
                    "type": "warning",
                    "sticky": False,
                },
            }
        connector = self.env["bizzi.api.connector"]
        success_count = 0
        fail_count = 0
        for record in records:
            try:
                connector.push_invoice_to_bizzi(record)
                success_count += 1
            except Exception as e:
                _logger.error("Failed to push invoice %s to Bizzi: %s", record.invoice_number, e)
                fail_count += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Kết quả đẩy sang Bizzi"),
                "message": _(
                    "Thành công: %d hóa đơn. Lỗi: %d hóa đơn."
                ) % (success_count, fail_count),
                "type": "success" if fail_count == 0 else "warning",
                "sticky": False,
            },
        }

    def action_reset_to_draft(self):
        """Reset trạng thái về Nháp để thử lại."""
        self.filtered(lambda r: r.bizzi_status == "failed").write({
            "bizzi_status": "draft",
            "error_message": False,
            "retry_count": 0,
        })

    def action_view_pdf(self):
        """Xem file PDF hóa đơn."""
        self.ensure_one()
        if not self.pdf_file:
            raise ValidationError(_("Không có file PDF cho hóa đơn này."))
        attachments = self.env["ir.attachment"].search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("mimetype", "=", "application/pdf"),
        ], limit=1)
        if attachments:
            return {
                "type": "ir.actions.act_url",
                "url": "/web/content/%d?download=false" % attachments[0].id,
                "target": "new",
            }

    # ====================================================================
    # Cron Methods
    # ====================================================================
    @api.model
    def cron_push_draft_to_bizzi(self):
        """Cron job: Tự động đẩy tất cả bản ghi Draft sang Bizzi."""
        _logger.info("Cron: Bắt đầu đẩy staging Draft sang Bizzi")
        draft_records = self.search([("bizzi_status", "=", "draft")], limit=100)
        if not draft_records:
            _logger.info("Cron: Không có bản ghi Draft nào để đẩy")
            return

        connector = self.env["bizzi.api.connector"]
        success_count = 0
        fail_count = 0

        for record in draft_records:
            try:
                connector.push_invoice_to_bizzi(record)
                success_count += 1
            except Exception as e:
                _logger.error(
                    "Cron: Lỗi đẩy hóa đơn %s: %s",
                    record.invoice_number, str(e)
                )
                fail_count += 1

        _logger.info(
            "Cron: Hoàn thành. Thành công: %d, Lỗi: %d",
            success_count, fail_count
        )

    # ====================================================================
    # Helper Methods
    # ====================================================================
    @api.model
    def create_from_extension(self, invoice_data, session_id=None):
        """
        Tạo bản ghi staging từ dữ liệu Extension gửi về.

        Args:
            invoice_data (dict): Dữ liệu hóa đơn từ Extension
            session_id (str): ID phiên đồng bộ

        Returns:
            dict: Kết quả tạo bản ghi (success/error)
        """
        import json

        invoice_number = invoice_data.get("invoice_number", "").strip()
        seller_tax_code = invoice_data.get("seller_tax_code", "").strip()

        if not invoice_number:
            return {"success": False, "error": "Thiếu số hóa đơn"}

        # Kiểm tra trùng lặp
        existing = self.search([
            ("invoice_number", "=", invoice_number),
            ("seller_tax_code", "=", seller_tax_code),
        ], limit=1)

        if existing:
            return {
                "success": False,
                "duplicate": True,
                "existing_id": existing.id,
                "error": "Hóa đơn đã tồn tại (ID: %d)" % existing.id,
            }

        # Xử lý file PDF Base64
        pdf_file = None
        pdf_filename = None
        pdf_data = invoice_data.get("pdf_base64")
        if pdf_data:
            try:
                # Validate Base64
                base64.b64decode(pdf_data)
                pdf_file = pdf_data
                pdf_filename = invoice_data.get("pdf_filename") or (
                    "invoice_%s.pdf" % invoice_number
                )
            except Exception as e:
                _logger.warning("Lỗi decode PDF Base64 cho hóa đơn %s: %s", invoice_number, e)

        # Xử lý file XML Base64
        xml_file = None
        xml_filename = None
        xml_data = invoice_data.get("xml_base64")
        if xml_data:
            try:
                base64.b64decode(xml_data)
                xml_file = xml_data
                xml_filename = invoice_data.get("xml_filename") or (
                    "invoice_%s.xml" % invoice_number
                )
            except Exception as e:
                _logger.warning("Lỗi decode XML Base64 cho hóa đơn %s: %s", invoice_number, e)

        # Parse ngày lập
        invoice_date = None
        date_str = invoice_data.get("invoice_date")
        if date_str:
            try:
                from datetime import datetime
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                    try:
                        invoice_date = datetime.strptime(date_str, fmt).date()
                        break
                    except ValueError:
                        continue
            except Exception:
                pass

        vals = {
            "invoice_number": invoice_number,
            "invoice_code": invoice_data.get("invoice_code", ""),
            "invoice_symbol": invoice_data.get("invoice_symbol", ""),
            "invoice_date": invoice_date,
            "source": invoice_data.get("source", "grab"),
            "seller_tax_code": seller_tax_code,
            "seller_name": invoice_data.get("seller_name", ""),
            "amount_untaxed": float(invoice_data.get("amount_untaxed") or 0),
            "amount_tax": float(invoice_data.get("amount_tax") or 0),
            "amount_total": float(invoice_data.get("amount_total") or 0),
            "pdf_file": pdf_file,
            "pdf_filename": pdf_filename,
            "xml_file": xml_file,
            "xml_filename": xml_filename,
            "bizzi_status": "draft",
            "extension_sync_date": fields.Datetime.now(),
            "extension_session_id": session_id,
            "raw_data": json.dumps(invoice_data, ensure_ascii=False, default=str),
        }

        try:
            record = self.create(vals)
            _logger.info(
                "Tạo staging thành công: ID=%d, Số HĐ=%s",
                record.id, invoice_number
            )
            return {
                "success": True,
                "staging_id": record.id,
                "invoice_number": invoice_number,
            }
        except Exception as e:
            _logger.error("Lỗi tạo staging cho hóa đơn %s: %s", invoice_number, str(e))
            return {"success": False, "error": str(e)}
