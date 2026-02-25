# -*- coding: utf-8 -*-
{
    "name": "NTP E-Invoice Bizzi Staging",
    "category": "Accounting",
    "summary": "Nhận hóa đơn từ Chrome Extension, lưu trữ staging và đẩy sang Bizzi",
    "description": """
        Module tiếp nhận dữ liệu hóa đơn điện tử từ Chrome/Edge Extension,
        lưu trữ vào bảng staging trung gian, và tự động đẩy sang hệ thống
        Bizzi để xử lý OCR và xác minh hóa đơn.

        Tính năng:
        - API endpoint nhận dữ liệu từ Extension (JSON + PDF Base64)
        - Bảng staging (invoice.staging.queue) với deduplication
        - Tích hợp Bizzi API (upload PDF/XML)
        - Cron job tự động đẩy staging sang Bizzi
        - Giao diện quản lý staging với filter, search, action buttons
        - Phân quyền theo nhóm người dùng
    """,
    "version": "15.0.1.0.0",
    "author": "NTP",
    "website": "",
    "depends": ["account", "mail", "base_setup"],
    "data": [
        "security/ir.model.access.csv",
        "security/security_groups.xml",
        "data/ir_cron.xml",
        "views/invoice_staging_views.xml",
        "views/res_config_settings_views.xml",
        "views/menu_views.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "OPL-1",
    "images": ["static/src/img/module_icon.png"],
}
