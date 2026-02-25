# -*- coding: utf-8 -*-
"""
Model: bizzi.api.connector
Xử lý tích hợp với Bizzi API - upload hóa đơn PDF/XML.
"""
import base64
import json
import logging
import time

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Timeout settings
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


class BizziApiConnector(models.AbstractModel):
    """
    Abstract model cung cấp các phương thức tích hợp Bizzi API.
    Không có bảng trong database, chỉ là service layer.
    """
    _name = "bizzi.api.connector"
    _description = "Bizzi API Connector Service"

    # ====================================================================
    # Configuration Helpers
    # ====================================================================
    @api.model
    def _get_bizzi_config(self):
        """Lấy cấu hình Bizzi từ system parameters."""
        ICP = self.env["ir.config_parameter"].sudo()
        config = {
            "api_url": ICP.get_param(
                "ntp_einvoice_bizzi.bizzi_api_url",
                default="https://api.bizzi.vn/v1"
            ),
            "api_key": ICP.get_param("ntp_einvoice_bizzi.bizzi_api_key", default=""),
            "company_code": ICP.get_param(
                "ntp_einvoice_bizzi.bizzi_company_code", default=""
            ),
            "timeout": int(ICP.get_param(
                "ntp_einvoice_bizzi.bizzi_timeout", default=str(REQUEST_TIMEOUT)
            )),
            "max_retries": int(ICP.get_param(
                "ntp_einvoice_bizzi.bizzi_max_retries", default=str(MAX_RETRIES)
            )),
        }
        return config

    @api.model
    def _get_headers(self, config):
        """Tạo headers cho Bizzi API request."""
        return {
            "Authorization": "Bearer %s" % config.get("api_key", ""),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Company-Code": config.get("company_code", ""),
        }

    # ====================================================================
    # Core Push Method
    # ====================================================================
    @api.model
    def push_invoice_to_bizzi(self, staging_record):
        """
        Đẩy một hóa đơn từ staging sang Bizzi API.

        Args:
            staging_record: Bản ghi invoice.staging.queue

        Returns:
            bool: True nếu thành công
        """
        config = self._get_bizzi_config()

        if not config.get("api_key"):
            _logger.warning(
                "Bizzi API Key chưa được cấu hình. Bỏ qua hóa đơn %s",
                staging_record.invoice_number
            )
            staging_record.write({
                "bizzi_status": "failed",
                "error_message": "Bizzi API Key chưa được cấu hình. "
                                 "Vui lòng vào Cài đặt > NTP E-Invoice để cấu hình.",
            })
            return False

        payload = self._build_payload(staging_record, config)
        api_url = "%s/documents/upload" % config["api_url"].rstrip("/")

        _logger.info(
            "Đẩy hóa đơn %s sang Bizzi: %s",
            staging_record.invoice_number, api_url
        )

        last_error = None
        for attempt in range(1, config["max_retries"] + 1):
            try:
                response = requests.post(
                    api_url,
                    json=payload,
                    headers=self._get_headers(config),
                    timeout=config["timeout"],
                )
                return self._handle_response(staging_record, response, attempt)

            except requests.Timeout:
                last_error = "Timeout sau %ds (lần %d/%d)" % (
                    config["timeout"], attempt, config["max_retries"]
                )
                _logger.warning(
                    "Bizzi API Timeout cho hóa đơn %s (lần %d/%d)",
                    staging_record.invoice_number, attempt, config["max_retries"]
                )
            except requests.ConnectionError as e:
                last_error = "Lỗi kết nối: %s" % str(e)
                _logger.warning(
                    "Bizzi API Connection Error cho hóa đơn %s: %s",
                    staging_record.invoice_number, str(e)
                )
            except Exception as e:
                last_error = "Lỗi không xác định: %s" % str(e)
                _logger.error(
                    "Lỗi không xác định khi đẩy hóa đơn %s: %s",
                    staging_record.invoice_number, str(e),
                    exc_info=True
                )

            if attempt < config["max_retries"]:
                time.sleep(RETRY_DELAY * attempt)

        # Tất cả lần thử đều thất bại
        staging_record.write({
            "bizzi_status": "failed",
            "error_message": last_error,
            "retry_count": staging_record.retry_count + config["max_retries"],
            "bizzi_response_log": json.dumps({
                "error": last_error,
                "attempts": config["max_retries"],
                "timestamp": fields.Datetime.now().isoformat(),
            }, ensure_ascii=False),
        })
        return False

    # ====================================================================
    # Payload Builder
    # ====================================================================
    @api.model
    def _build_payload(self, staging_record, config):
        """
        Xây dựng payload gửi đến Bizzi API.
        Cấu trúc payload theo chuẩn Bizzi API Documents.
        """
        payload = {
            "companyCode": config.get("company_code", ""),
            "invoiceNumber": staging_record.invoice_number or "",
            "invoiceCode": staging_record.invoice_code or "",
            "invoiceSymbol": staging_record.invoice_symbol or "",
            "invoiceDate": staging_record.invoice_date.isoformat()
            if staging_record.invoice_date else None,
            "sellerTaxCode": staging_record.seller_tax_code or "",
            "sellerName": staging_record.seller_name or "",
            "amountUntaxed": staging_record.amount_untaxed or 0,
            "amountTax": staging_record.amount_tax or 0,
            "amountTotal": staging_record.amount_total or 0,
            "source": staging_record.source or "manual",
            "externalId": "odoo_staging_%d" % staging_record.id,
            "files": [],
        }

        # Đính kèm file PDF
        if staging_record.pdf_file:
            payload["files"].append({
                "type": "pdf",
                "filename": staging_record.pdf_filename or (
                    "invoice_%s.pdf" % staging_record.invoice_number
                ),
                "content": staging_record.pdf_file.decode("utf-8")
                if isinstance(staging_record.pdf_file, bytes)
                else staging_record.pdf_file,
            })

        # Đính kèm file XML nếu có
        if staging_record.xml_file:
            payload["files"].append({
                "type": "xml",
                "filename": staging_record.xml_filename or (
                    "invoice_%s.xml" % staging_record.invoice_number
                ),
                "content": staging_record.xml_file.decode("utf-8")
                if isinstance(staging_record.xml_file, bytes)
                else staging_record.xml_file,
            })

        return payload

    # ====================================================================
    # Response Handler
    # ====================================================================
    @api.model
    def _handle_response(self, staging_record, response, attempt):
        """Xử lý phản hồi từ Bizzi API."""
        response_data = {}
        try:
            response_data = response.json()
        except Exception:
            response_data = {"raw": response.text[:2000]}

        log_entry = {
            "status_code": response.status_code,
            "attempt": attempt,
            "timestamp": fields.Datetime.now().isoformat(),
            "response": response_data,
        }

        if response.status_code in (200, 201):
            # Thành công
            bizzi_doc_id = (
                response_data.get("documentId")
                or response_data.get("id")
                or response_data.get("data", {}).get("id", "")
            )
            staging_record.write({
                "bizzi_status": "pushed",
                "bizzi_document_id": str(bizzi_doc_id) if bizzi_doc_id else "",
                "bizzi_push_date": fields.Datetime.now(),
                "bizzi_response_log": json.dumps(log_entry, ensure_ascii=False),
                "error_message": False,
            })
            _logger.info(
                "Đẩy thành công hóa đơn %s sang Bizzi. Document ID: %s",
                staging_record.invoice_number, bizzi_doc_id
            )
            return True

        elif response.status_code == 409:
            # Trùng lặp trên Bizzi
            staging_record.write({
                "bizzi_status": "pushed",
                "bizzi_response_log": json.dumps(log_entry, ensure_ascii=False),
                "error_message": "Hóa đơn đã tồn tại trên Bizzi (HTTP 409)",
            })
            _logger.warning(
                "Hóa đơn %s đã tồn tại trên Bizzi",
                staging_record.invoice_number
            )
            return True

        else:
            # Lỗi
            error_msg = (
                response_data.get("message")
                or response_data.get("error")
                or "HTTP %d" % response.status_code
            )
            staging_record.write({
                "bizzi_status": "failed",
                "error_message": "Bizzi API Error: %s" % error_msg,
                "bizzi_response_log": json.dumps(log_entry, ensure_ascii=False),
                "retry_count": staging_record.retry_count + 1,
            })
            _logger.error(
                "Lỗi đẩy hóa đơn %s sang Bizzi: HTTP %d - %s",
                staging_record.invoice_number, response.status_code, error_msg
            )
            return False

    # ====================================================================
    # Batch Push
    # ====================================================================
    @api.model
    def push_batch_to_bizzi(self, staging_records):
        """Đẩy nhiều hóa đơn sang Bizzi theo batch."""
        results = {"success": 0, "failed": 0, "errors": []}
        for record in staging_records:
            try:
                success = self.push_invoice_to_bizzi(record)
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "id": record.id,
                        "invoice_number": record.invoice_number,
                        "error": record.error_message,
                    })
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "id": record.id,
                    "invoice_number": record.invoice_number,
                    "error": str(e),
                })
        return results

    # ====================================================================
    # Status Polling (Optional - for async Bizzi processing)
    # ====================================================================
    @api.model
    def poll_bizzi_status(self, staging_record):
        """
        Kiểm tra trạng thái xử lý của Bizzi cho một hóa đơn.
        Gọi khi cần cập nhật trạng thái từ 'pushed' → 'processed'.
        """
        if not staging_record.bizzi_document_id:
            return False

        config = self._get_bizzi_config()
        if not config.get("api_key"):
            return False

        api_url = "%s/documents/%s/status" % (
            config["api_url"].rstrip("/"),
            staging_record.bizzi_document_id
        )

        try:
            response = requests.get(
                api_url,
                headers=self._get_headers(config),
                timeout=config["timeout"],
            )
            if response.status_code == 200:
                data = response.json()
                bizzi_state = data.get("status", "").lower()
                if bizzi_state in ("processed", "completed", "done"):
                    staging_record.write({"bizzi_status": "processed"})
                    return True
        except Exception as e:
            _logger.error(
                "Lỗi poll Bizzi status cho hóa đơn %s: %s",
                staging_record.invoice_number, str(e)
            )
        return False
