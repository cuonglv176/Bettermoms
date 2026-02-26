# -*- coding: utf-8 -*-
"""
API Endpoints cho Chrome/Edge Extension.
Nhận dữ liệu hóa đơn và tạo bản ghi staging.
"""
import json
import logging
import traceback

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

# Giới hạn kích thước payload (50MB)
MAX_PAYLOAD_SIZE = 50 * 1024 * 1024
# Số lượng hóa đơn tối đa trong một batch
MAX_BATCH_SIZE = 50

# CORS Headers
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Extension-Token, Accept",
    "Access-Control-Max-Age": "3600",
}


def _get_json_response(data, status=200):
    """Tạo JSON response chuẩn với CORS headers."""
    return Response(
        json.dumps(data, ensure_ascii=False, default=str),
        status=status,
        mimetype="application/json",
        headers=CORS_HEADERS,
    )


def _validate_token():
    """
    Xác thực token từ Extension.
    Returns: (is_valid, error_response)
    """
    # Lấy token từ header
    token = request.httprequest.headers.get("X-Extension-Token") or \
            request.httprequest.headers.get("Authorization", "").replace("Bearer ", "")

    if not token:
        _logger.warning(
            "Extension API: Thiếu token từ IP %s",
            request.httprequest.remote_addr
        )
        return False, _get_json_response(
            {"success": False, "error": "Thiếu token xác thực. Vui lòng cấu hình API Token trong Extension."},
            status=401
        )

    # Kiểm tra token trong database
    try:
        ICP = request.env["ir.config_parameter"].sudo()
        valid_token = ICP.get_param("ntp_einvoice_bizzi.extension_api_token", "")

        if not valid_token:
            _logger.warning("Extension API: Chưa cấu hình token trên Odoo")
            return False, _get_json_response(
                {"success": False, "error": "Chưa cấu hình API Token trên Odoo. Vào Cài đặt → NTP E-Invoice Bizzi → Tạo Token."},
                status=403
            )

        if token != valid_token:
            _logger.warning(
                "Extension API: Token không khớp từ IP %s (received: %s..., expected: %s...)",
                request.httprequest.remote_addr,
                token[:8] if len(token) > 8 else token,
                valid_token[:8] if len(valid_token) > 8 else valid_token,
            )
            return False, _get_json_response(
                {"success": False, "error": "Token không hợp lệ. Kiểm tra lại API Token trong Extension."},
                status=403
            )

        return True, None

    except Exception as e:
        _logger.error("Extension API: Lỗi xác thực token: %s", str(e), exc_info=True)
        return False, _get_json_response(
            {"success": False, "error": "Lỗi xác thực: %s" % str(e)},
            status=500
        )


class EInvoiceBizziController(http.Controller):
    """Controller xử lý API requests từ Chrome/Edge Extension."""

    # ====================================================================
    # Health Check (không cần token)
    # ====================================================================
    @http.route(
        "/api/einvoice/health",
        type="http",
        auth="public",
        methods=["GET", "OPTIONS"],
        csrf=False,
        cors="*",
    )
    def health_check(self, **kwargs):
        """Kiểm tra kết nối đến Odoo API."""
        if request.httprequest.method == "OPTIONS":
            return _get_json_response({})

        _logger.info("Health check from IP: %s", request.httprequest.remote_addr)

        # Nếu có token, kiểm tra luôn
        token = request.httprequest.headers.get("X-Extension-Token", "")
        token_valid = False
        if token:
            try:
                ICP = request.env["ir.config_parameter"].sudo()
                valid_token = ICP.get_param("ntp_einvoice_bizzi.extension_api_token", "")
                token_valid = (token == valid_token) if valid_token else False
            except Exception:
                pass

        return _get_json_response({
            "success": True,
            "message": "NTP E-Invoice Bizzi API is running",
            "version": "1.1.0",
            "token_valid": token_valid if token else None,
            "database": request.env.cr.dbname if request.env.cr else None,
        })

    # ====================================================================
    # CORS Preflight Handler
    # ====================================================================
    @http.route(
        [
            "/api/einvoice/staging/create",
            "/api/einvoice/staging/batch",
            "/api/einvoice/staging/list",
        ],
        type="http",
        auth="public",
        methods=["OPTIONS"],
        csrf=False,
        cors="*",
    )
    def handle_options(self, **kwargs):
        """Handle CORS preflight requests."""
        return _get_json_response({})

    # ====================================================================
    # Sync Single Invoice
    # ====================================================================
    @http.route(
        "/api/einvoice/staging/create",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def create_staging(self, **kwargs):
        """
        Nhận một hóa đơn từ Extension và tạo bản ghi staging.
        """
        try:
            # Xác thực token
            is_valid, error_response = _validate_token()
            if not is_valid:
                return error_response

            # Parse request body
            body = request.httprequest.get_data(as_text=True)
            _logger.info(
                "Extension API create_staging: Received %d bytes from IP %s",
                len(body) if body else 0,
                request.httprequest.remote_addr,
            )

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

            # Log dữ liệu nhận được (bỏ pdf/xml base64 để tránh log quá dài)
            log_data = {k: v for k, v in invoice_data.items()
                        if k not in ("pdf_base64", "xml_base64")}
            log_data["has_pdf_base64"] = bool(invoice_data.get("pdf_base64"))
            log_data["has_xml_base64"] = bool(invoice_data.get("xml_base64"))
            _logger.info("Extension API create_staging data: %s", json.dumps(log_data, ensure_ascii=False))

            # Tạo bản ghi staging
            StagingModel = request.env["invoice.staging.queue"].sudo()
            result = StagingModel.create_from_extension(invoice_data, session_id)

            _logger.info("Extension API create_staging result: %s", json.dumps(result, ensure_ascii=False, default=str))

            if result.get("success"):
                return _get_json_response(result, status=201)
            elif result.get("duplicate"):
                return _get_json_response(result, status=409)
            else:
                return _get_json_response(result, status=422)

        except json.JSONDecodeError as e:
            _logger.error("Extension API: JSON parse error: %s", str(e))
            return _get_json_response(
                {"success": False, "error": "JSON không hợp lệ: %s" % str(e)},
                status=400
            )
        except Exception as e:
            _logger.error(
                "Extension API create_staging exception: %s\n%s",
                str(e), traceback.format_exc()
            )
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
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def create_staging_batch(self, **kwargs):
        """Nhận nhiều hóa đơn cùng lúc từ Extension (batch upload)."""
        try:
            # Xác thực token
            is_valid, error_response = _validate_token()
            if not is_valid:
                return error_response

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

            _logger.info(
                "Extension API batch: Received %d invoices from IP %s",
                len(invoices), request.httprequest.remote_addr,
            )

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

            _logger.info(
                "Extension API batch result: created=%d, duplicates=%d, errors=%d",
                created_count, duplicate_count, error_count,
            )

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
            _logger.error("Extension API batch exception: %s\n%s", str(e), traceback.format_exc())
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
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def list_staging(self, **kwargs):
        """Lấy danh sách staging records."""
        try:
            # Xác thực token
            is_valid, error_response = _validate_token()
            if not is_valid:
                return error_response

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
            _logger.error("Extension API list exception: %s\n%s", str(e), traceback.format_exc())
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
        auth="public",
        methods=["POST", "OPTIONS"],
        csrf=False,
        cors="*",
    )
    def push_to_bizzi(self, staging_id, **kwargs):
        """Đẩy một hóa đơn cụ thể sang Bizzi."""
        if request.httprequest.method == "OPTIONS":
            return _get_json_response({})

        try:
            # Xác thực token
            is_valid, error_response = _validate_token()
            if not is_valid:
                return error_response

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
            _logger.error("Extension API push_to_bizzi exception (ID %d): %s\n%s",
                          staging_id, str(e), traceback.format_exc())
            return _get_json_response(
                {"success": False, "error": str(e)},
                status=500
            )
