# -*- coding: utf-8 -*-
"""
Mở rộng Cài đặt hệ thống để thêm cấu hình Bizzi API.
"""
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ====================================================================
    # Bizzi API Configuration
    # ====================================================================
    bizzi_api_url = fields.Char(
        string="Bizzi API URL",
        config_parameter="ntp_einvoice_bizzi.bizzi_api_url",
        default="https://api.bizzi.vn/v1",
        help="URL endpoint của Bizzi API",
    )
    bizzi_api_key = fields.Char(
        string="Bizzi API Key",
        config_parameter="ntp_einvoice_bizzi.bizzi_api_key",
        help="API Key để xác thực với Bizzi",
    )
    bizzi_company_code = fields.Char(
        string="Bizzi Company Code",
        config_parameter="ntp_einvoice_bizzi.bizzi_company_code",
        help="Mã công ty trên hệ thống Bizzi",
    )
    bizzi_timeout = fields.Integer(
        string="Timeout (giây)",
        config_parameter="ntp_einvoice_bizzi.bizzi_timeout",
        default=30,
        help="Thời gian chờ tối đa cho mỗi request đến Bizzi API",
    )
    bizzi_max_retries = fields.Integer(
        string="Số lần thử lại tối đa",
        config_parameter="ntp_einvoice_bizzi.bizzi_max_retries",
        default=3,
        help="Số lần thử lại khi gặp lỗi kết nối Bizzi",
    )

    # ====================================================================
    # Extension API Configuration
    # ====================================================================
    extension_api_token = fields.Char(
        string="Extension API Token",
        config_parameter="ntp_einvoice_bizzi.extension_api_token",
        help="Token xác thực cho Chrome/Edge Extension. "
             "Extension sẽ dùng token này để gọi API Odoo.",
    )
    extension_allowed_origins = fields.Char(
        string="Allowed Origins",
        config_parameter="ntp_einvoice_bizzi.extension_allowed_origins",
        default="chrome-extension://",
        help="Danh sách origins được phép gọi API (ngăn cách bằng dấu phẩy)",
    )
    extension_batch_size = fields.Integer(
        string="Batch Size",
        config_parameter="ntp_einvoice_bizzi.extension_batch_size",
        default=10,
        help="Số lượng hóa đơn tối đa trong mỗi batch khi đồng bộ từ Extension",
    )

    def action_generate_extension_token(self):
        """Tạo token ngẫu nhiên cho Extension."""
        import secrets
        token = secrets.token_urlsafe(32)
        self.env["ir.config_parameter"].sudo().set_param(
            "ntp_einvoice_bizzi.extension_api_token", token
        )
        self.extension_api_token = token
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Token đã được tạo",
                "message": "Extension API Token mới đã được tạo thành công. "
                           "Hãy cập nhật token này vào Extension.",
                "type": "success",
                "sticky": True,
            },
        }

    def action_test_bizzi_connection(self):
        """Kiểm tra kết nối đến Bizzi API."""
        import requests
        api_url = self.bizzi_api_url or "https://api.bizzi.vn/v1"
        api_key = self.bizzi_api_key or ""

        if not api_key:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Thiếu API Key",
                    "message": "Vui lòng nhập Bizzi API Key trước khi kiểm tra kết nối.",
                    "type": "warning",
                    "sticky": False,
                },
            }

        try:
            response = requests.get(
                "%s/health" % api_url.rstrip("/"),
                headers={
                    "Authorization": "Bearer %s" % api_key,
                    "Accept": "application/json",
                },
                timeout=10,
            )
            if response.status_code in (200, 401, 403):
                msg = "Kết nối thành công đến Bizzi API (HTTP %d)" % response.status_code
                msg_type = "success"
            else:
                msg = "Kết nối được nhưng nhận HTTP %d" % response.status_code
                msg_type = "warning"
        except requests.ConnectionError:
            msg = "Không thể kết nối đến Bizzi API. Kiểm tra URL và kết nối mạng."
            msg_type = "danger"
        except requests.Timeout:
            msg = "Timeout khi kết nối đến Bizzi API."
            msg_type = "warning"
        except Exception as e:
            msg = "Lỗi: %s" % str(e)
            msg_type = "danger"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Kiểm tra kết nối Bizzi",
                "message": msg,
                "type": msg_type,
                "sticky": False,
            },
        }
