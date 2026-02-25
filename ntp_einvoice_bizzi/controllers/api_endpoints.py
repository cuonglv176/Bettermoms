# -*- coding: utf-8 -*-
"""
API Endpoints cho Chrome/Edge Extension.
Nhận dữ liệu hóa đơn và tạo bản ghi staging.
"""
import json
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

# Giới hạn kích thước payload (50MB)
MAX_PAYLOAD_SIZE = 50 * 1024 * 1024
# Số lượng hóa đơn tối đa trong một batch
MAX_BATCH_SIZE = 50


def _get_json_response(data, status=200):
    """Tạo JSON response chuẩn."""
    return Response(
        json.dumps(data, ensure_ascii=False, default=str),
        status=status,
        mimetype="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Extension-Token",
        },
    )


def _authenticate_extension(func):
    """Decorator xác thực token từ Extension."""
    def wrapper(self, *args, **kwargs):
        # Lấy token từ header
        token = request.httprequest.headers.get("X-Extension-Token") or \
                request.httprequest.headers.get("Authorization", "").replace("Bearer ", "")

        if not token:
            return _get_json_response(
                {"success": False, "error": "Thiếu token xác thực"},
                status=401
            )

        # Kiểm tra token
        ICP = request.env["ir.config_parameter"].sudo()
        valid_token = ICP.get_param("ntp_einvoice_bizzi.extension_api_token", "")

        if not valid_token or token != valid_token:
            _logger.warning(
                "Extension API: Token không hợp lệ từ IP %s",
                request.httprequest.remote_addr
            )
            return _get_json_response(
                {"success": False, "error": "Token không hợp lệ"},
                status=403
            )

        return func(self, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


class EInvoiceBizziController(http.Controller):
    """Controller xử lý API requests từ Chrome/Edge Extension."""

    # ====================================================================
    # Health Check
    # ====================================================================
    @http.route(
        "/api/einvoice/health",
        type="http",
        auth="none",
        methods=["GET", "OPTIONS"],
        csrf=False,
        cors="*",
    )
    def health_check(self, **kwargs):
        """Kiểm tra kết nối đến Odoo API."""
        if request.httprequest.method == "OPTIONS":
            return _get_json_response({})

        return _get_json_response({
            "success": True,
            "message": "NTP E-Invoice Bizzi API is running",
            "version": "1.0.0",
        })

    # ====================================================================
    # Sync Single Invoice
    # ====================================================================
    @http.route(
        "/api/einvoice/staging/create",
        type="http",
        auth="none",
        methods=["POST", "OPTIONS"],
        csrf=False,
        cors="*",
    )
    @_authenticate_extension
    def create_staging(self, **kwargs):
        """
        Nhận một hóa đơn từ Extension và tạo bản ghi staging.

        Request Body (JSON):
        {
            "invoice_number": "...",
            "invoice_code": "...",
            "invoice_symbol": "...",
            "invoice_date": "YYYY-MM-DD",
            "source": "grab|tracuu|shinhan",
            "seller_tax_code": "...",
            "seller_name": "...",
            "amount_untaxed": 0,
            "amount_tax": 0,
            "amount_total": 0,
            "pdf_base64": "...",
            "pdf_filename": "...",
            "xml_base64": "...",
            "xml_filename": "...",
            "session_id": "..."
        }
        """
        if request.httprequest.method == "OPTIONS":
            return _get_json_response({})

        try:
            # Parse request body
            body = request.httprequest.get_data(as_text=True)
            if not body:
                return _get_json_response(
                    {"success": False, "error": "Request body trống"},
                    status=400
                )

            # Kiểm tra kích thước
            if len(body.encode("utf-8")) > MAX_PAYLOAD_SIZE:
                return _get_json_response(
                    {"success": False, "error": "Payload quá lớn (tối đa 50MB)"},
                    status=413
                )

            invoice_data = json.loads(body)
            session_id = invoice_data.get("session_id")

            # Tạo bản ghi staging
            StagingModel = request.env["invoice.staging.queue"].sudo()
            result = StagingModel.create_from_extension(invoice_data, session_id)

            if result.get("success"):
                return _get_json_response(result, status=201)
            elif result.get("duplicate"):
                return _get_json_response(result, status=409)
            else:
                return _get_json_response(result, status=422)

        except json.JSONDecodeError as e:
            return _get_json_response(
                {"success": False, "error": "JSON không hợp lệ: %s" % str(e)},
                status=400
            )
        except Exception as e:
            _logger.error("Lỗi tạo staging: %s", str(e), exc_info=True)
            return _get_json_response(
                {"success": False, "error": "Lỗi server: %s" % str(e)},
                status=500
            )

    # ====================================================================
    # Batch Sync
    # ====================================================================
    @http.route(
        "/api/einvoice/staging/batch",
        type="http",
        auth="none",
        methods=["POST", "OPTIONS"],
        csrf=False,
        cors="*",
    )
    @_authenticate_extension
    def create_staging_batch(self, **kwargs):
        """
        Nhận nhiều hóa đơn cùng lúc từ Extension (batch upload).

        Request Body (JSON):
        {
            "session_id": "...",
            "invoices": [
                { ...invoice_data... },
                ...
            ]
        }

        Response:
        {
            "success": true,
            "total": 10,
            "created": 8,
            "duplicates": 1,
            "errors": 1,
            "results": [...]
        }
        """
        if request.httprequest.method == "OPTIONS":
            return _get_json_response({})

        try:
            body = request.httprequest.get_data(as_text=True)
            if not body:
                return _get_json_response(
                    {"success": False, "error": "Request body trống"},
                    status=400
                )

            if len(body.encode("utf-8")) > MAX_PAYLOAD_SIZE:
                return _get_json_response(
                    {"success": False, "error": "Payload quá lớn (tối đa 50MB)"},
                    status=413
                )

            data = json.loads(body)
            invoices = data.get("invoices", [])
            session_id = data.get("session_id")

            if not invoices:
                return _get_json_response(
                    {"success": False, "error": "Danh sách hóa đơn trống"},
                    status=400
                )

            if len(invoices) > MAX_BATCH_SIZE:
                return _get_json_response(
                    {
                        "success": False,
                        "error": "Batch quá lớn. Tối đa %d hóa đơn/batch" % MAX_BATCH_SIZE
                    },
                    status=400
                )

            StagingModel = request.env["invoice.staging.queue"].sudo()
            results = []
            created_count = 0
            duplicate_count = 0
            error_count = 0

            for invoice_data in invoices:
                result = StagingModel.create_from_extension(invoice_data, session_id)
                results.append(result)

                if result.get("success"):
                    created_count += 1
                elif result.get("duplicate"):
                    duplicate_count += 1
                else:
                    error_count += 1

            return _get_json_response({
                "success": True,
                "total": len(invoices),
                "created": created_count,
                "duplicates": duplicate_count,
                "errors": error_count,
                "results": results,
            }, status=200 if error_count == 0 else 207)

        except json.JSONDecodeError as e:
            return _get_json_response(
                {"success": False, "error": "JSON không hợp lệ: %s" % str(e)},
                status=400
            )
        except Exception as e:
            _logger.error("Lỗi batch staging: %s", str(e), exc_info=True)
            return _get_json_response(
                {"success": False, "error": "Lỗi server: %s" % str(e)},
                status=500
            )

    # ====================================================================
    # Get Staging List
    # ====================================================================
    @http.route(
        "/api/einvoice/staging/list",
        type="http",
        auth="none",
        methods=["GET", "OPTIONS"],
        csrf=False,
        cors="*",
    )
    @_authenticate_extension
    def list_staging(self, **kwargs):
        """Lấy danh sách staging records."""
        if request.httprequest.method == "OPTIONS":
            return _get_json_response({})

        try:
            params = request.httprequest.args
            limit = min(int(params.get("limit", 50)), 200)
            offset = int(params.get("offset", 0))
            status_filter = params.get("status")

            domain = []
            if status_filter:
                domain.append(("bizzi_status", "=", status_filter))

            StagingModel = request.env["invoice.staging.queue"].sudo()
            records = StagingModel.search(domain, limit=limit, offset=offset, order="id desc")
            total = StagingModel.search_count(domain)

            data = []
            for rec in records:
                data.append({
                    "id": rec.id,
                    "invoice_number": rec.invoice_number,
                    "invoice_date": rec.invoice_date.isoformat() if rec.invoice_date else None,
                    "source": rec.source,
                    "seller_name": rec.seller_name,
                    "seller_tax_code": rec.seller_tax_code,
                    "amount_total": rec.amount_total,
                    "bizzi_status": rec.bizzi_status,
                    "has_pdf": rec.has_pdf,
                    "has_xml": rec.has_xml,
                    "create_date": rec.create_date.isoformat() if rec.create_date else None,
                })

            return _get_json_response({
                "success": True,
                "total": total,
                "limit": limit,
                "offset": offset,
                "data": data,
            })

        except Exception as e:
            _logger.error("Lỗi lấy danh sách staging: %s", str(e), exc_info=True)
            return _get_json_response(
                {"success": False, "error": str(e)},
                status=500
            )

    # ====================================================================
    # Manual Push to Bizzi
    # ====================================================================
    @http.route(
        "/api/einvoice/staging/<int:staging_id>/push-bizzi",
        type="http",
        auth="none",
        methods=["POST", "OPTIONS"],
        csrf=False,
        cors="*",
    )
    @_authenticate_extension
    def push_to_bizzi(self, staging_id, **kwargs):
        """Đẩy một hóa đơn cụ thể sang Bizzi."""
        if request.httprequest.method == "OPTIONS":
            return _get_json_response({})

        try:
            StagingModel = request.env["invoice.staging.queue"].sudo()
            record = StagingModel.browse(staging_id)

            if not record.exists():
                return _get_json_response(
                    {"success": False, "error": "Không tìm thấy bản ghi ID %d" % staging_id},
                    status=404
                )

            connector = request.env["bizzi.api.connector"].sudo()
            success = connector.push_invoice_to_bizzi(record)

            return _get_json_response({
                "success": success,
                "staging_id": staging_id,
                "bizzi_status": record.bizzi_status,
                "bizzi_document_id": record.bizzi_document_id,
                "error": record.error_message if not success else None,
            })

        except Exception as e:
            _logger.error("Lỗi push to Bizzi (ID %d): %s", staging_id, str(e), exc_info=True)
            return _get_json_response(
                {"success": False, "error": str(e)},
                status=500
            )
