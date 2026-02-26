# -*- coding: utf-8 -*-
"""
API Endpoints cho Chrome/Edge Extension.
Nhận dữ liệu hóa đơn và tạo bản ghi staging.

Lưu ý về type='json' trong Odoo:
- Extension gửi JSON-RPC: {"jsonrpc":"2.0","method":"call","id":xxx,"params":{...}}
- Odoo tự động unwrap "params" và truyền vào **kwargs
- request.jsonrequest chứa TOÀN BỘ JSON-RPC body (bao gồm jsonrpc, method, id, params)
- Do đó, PHẢI dùng kwargs (đã unwrap) hoặc request.jsonrequest.get("params", {})
"""
import json
import logging
import traceback

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

MAX_PAYLOAD_SIZE = 50 * 1024 * 1024
MAX_BATCH_SIZE = 50


def _validate_token():
    """
    Xác thực token từ Extension.
    Returns: (is_valid, error_dict_or_None)
    """
    token = request.httprequest.headers.get("X-Extension-Token") or \
            request.httprequest.headers.get("Authorization", "").replace("Bearer ", "")

    if not token:
        _logger.warning(
            "Extension API: Thiếu token từ IP %s",
            request.httprequest.remote_addr
        )
        return False, {"success": False, "error": "Thiếu token xác thực. Vui lòng cấu hình API Token trong Extension."}

    try:
        ICP = request.env["ir.config_parameter"].sudo()
        valid_token = ICP.get_param("ntp_einvoice_bizzi.extension_api_token", "")

        if not valid_token:
            _logger.warning("Extension API: Chưa cấu hình token trên Odoo")
            return False, {"success": False, "error": "Chưa cấu hình API Token trên Odoo. Vào Cài đặt → NTP E-Invoice Bizzi → Tạo Token."}

        if token != valid_token:
            _logger.warning(
                "Extension API: Token không khớp từ IP %s",
                request.httprequest.remote_addr,
            )
            return False, {"success": False, "error": "Token không hợp lệ. Kiểm tra lại API Token trong Extension."}

        return True, None

    except Exception as e:
        _logger.error("Extension API: Lỗi xác thực token: %s", str(e), exc_info=True)
        return False, {"success": False, "error": "Lỗi xác thực: %s" % str(e)}


def _get_json_data(**kwargs):
    """
    Lấy dữ liệu JSON từ request.
    Odoo type='json' tự unwrap params → kwargs.
    Fallback: lấy từ request.jsonrequest['params'] nếu kwargs rỗng.
    """
    # kwargs đã được Odoo unwrap từ params
    if kwargs and any(k not in ('context',) for k in kwargs):
        _logger.info("Extension API: Dữ liệu từ kwargs, keys=%s", list(kwargs.keys()))
        return kwargs

    # Fallback: lấy từ request.jsonrequest
    if hasattr(request, 'jsonrequest') and request.jsonrequest:
        jr = request.jsonrequest
        # Nếu là JSON-RPC format, lấy params
        if 'params' in jr:
            _logger.info("Extension API: Dữ liệu từ jsonrequest.params, keys=%s", list(jr['params'].keys()))
            return jr['params']
        # Nếu là plain JSON (không phải JSON-RPC)
        _logger.info("Extension API: Dữ liệu từ jsonrequest trực tiếp, keys=%s", list(jr.keys()))
        return jr

    _logger.warning("Extension API: Không tìm thấy dữ liệu trong request")
    return {}


class EInvoiceBizziController(http.Controller):
    """Controller xử lý API requests từ Chrome/Edge Extension."""

    # ====================================================================
    # Health Check (type='http', không cần token)
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
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Extension-Token",
            "Content-Type": "application/json",
        }

        if request.httprequest.method == "OPTIONS":
            return http.Response("{}", headers=headers)

        _logger.info("Health check from IP: %s", request.httprequest.remote_addr)

        token = request.httprequest.headers.get("X-Extension-Token", "")
        token_valid = False
        if token:
            try:
                ICP = request.env["ir.config_parameter"].sudo()
                valid_token = ICP.get_param("ntp_einvoice_bizzi.extension_api_token", "")
                token_valid = (token == valid_token) if valid_token else False
            except Exception:
                pass

        data = {
            "success": True,
            "message": "NTP E-Invoice Bizzi API is running",
            "version": "1.3.0",
            "token_valid": token_valid if token else None,
        }
        return http.Response(
            json.dumps(data, ensure_ascii=False),
            headers=headers,
        )

    # ====================================================================
    # CORS Preflight (type='http')
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
        return http.Response(
            "{}",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Extension-Token",
                "Content-Type": "application/json",
            },
        )

    # ====================================================================
    # Sync Single Invoice (type='json')
    # ====================================================================
    @http.route(
        "/api/einvoice/staging/create",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def create_staging(self, **kwargs):
        """
        Nhận một hóa đơn từ Extension và tạo bản ghi staging.

        Extension gửi JSON-RPC:
        {
            "jsonrpc": "2.0",
            "method": "call",
            "id": xxx,
            "params": {
                "invoice_number": "62952",
                "source": "shinhan",
                ...
            }
        }

        Odoo unwrap "params" → kwargs chứa invoice_number, source, ...
        """
        try:
            # Xác thực token
            is_valid, error_dict = _validate_token()
            if not is_valid:
                return error_dict

            # Lấy dữ liệu - ưu tiên kwargs (Odoo đã unwrap params)
            invoice_data = _get_json_data(**kwargs)

            _logger.info(
                "Extension API create_staging: data_keys=%s, invoice_number=%s, source=%s, from IP=%s",
                list(invoice_data.keys()),
                invoice_data.get("invoice_number", "N/A"),
                invoice_data.get("source", "N/A"),
                request.httprequest.remote_addr,
            )

            if not invoice_data:
                return {"success": False, "error": "Request body trống"}

            session_id = invoice_data.get("session_id")

            # Tạo bản ghi staging
            StagingModel = request.env["invoice.staging.queue"].sudo()
            result = StagingModel.create_from_extension(invoice_data, session_id)

            _logger.info(
                "Extension API create_staging result: success=%s, invoice=%s, error=%s",
                result.get("success"),
                invoice_data.get("invoice_number", "N/A"),
                result.get("error", "none"),
            )

            return result

        except Exception as e:
            _logger.error(
                "Extension API create_staging exception: %s\n%s",
                str(e), traceback.format_exc()
            )
            return {"success": False, "error": "Lỗi server: %s" % str(e)}

    # ====================================================================
    # Batch Sync (type='json')
    # ====================================================================
    @http.route(
        "/api/einvoice/staging/batch",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def create_staging_batch(self, **kwargs):
        """Nhận nhiều hóa đơn cùng lúc từ Extension (batch upload)."""
        try:
            # Xác thực token
            is_valid, error_dict = _validate_token()
            if not is_valid:
                return error_dict

            data = _get_json_data(**kwargs)
            invoices = data.get("invoices", [])
            session_id = data.get("session_id")

            _logger.info(
                "Extension API batch: Received %d invoices from IP %s",
                len(invoices), request.httprequest.remote_addr,
            )

            if not invoices:
                return {"success": False, "error": "Danh sách hóa đơn trống"}

            if len(invoices) > MAX_BATCH_SIZE:
                return {
                    "success": False,
                    "error": "Batch quá lớn. Tối đa %d hóa đơn/batch" % MAX_BATCH_SIZE
                }

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

            return {
                "success": True,
                "total": len(invoices),
                "created": created_count,
                "duplicates": duplicate_count,
                "errors": error_count,
                "results": results,
            }

        except Exception as e:
            _logger.error("Extension API batch exception: %s\n%s", str(e), traceback.format_exc())
            return {"success": False, "error": "Lỗi server: %s" % str(e)}

    # ====================================================================
    # Get Staging List (type='http' - GET request)
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
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json",
        }

        try:
            is_valid, error_dict = _validate_token()
            if not is_valid:
                return http.Response(
                    json.dumps(error_dict, ensure_ascii=False),
                    status=403,
                    headers=headers,
                )

            params = request.httprequest.args
            limit = min(int(params.get("limit", 50)), 200)
            offset = int(params.get("offset", 0))
            status_filter = params.get("status")

            domain = []
            if status_filter:
                domain.append(("bizzi_status", "=", status_filter))

            StagingModel = request.env["invoice.staging.queue"].sudo()
            total = StagingModel.search_count(domain)
            records = StagingModel.search(domain, limit=limit, offset=offset, order="create_date desc")

            data = {
                "success": True,
                "total": total,
                "limit": limit,
                "offset": offset,
                "records": [
                    {
                        "id": rec.id,
                        "invoice_number": rec.invoice_number,
                        "invoice_code": rec.invoice_code,
                        "invoice_symbol": rec.invoice_symbol,
                        "invoice_date": str(rec.invoice_date) if rec.invoice_date else None,
                        "source": rec.source,
                        "seller_tax_code": rec.seller_tax_code,
                        "seller_name": rec.seller_name,
                        "amount_total": rec.amount_total,
                        "bizzi_status": rec.bizzi_status,
                        "has_pdf": rec.has_pdf,
                        "has_xml": rec.has_xml,
                        "create_date": str(rec.create_date),
                    }
                    for rec in records
                ],
            }

            return http.Response(
                json.dumps(data, ensure_ascii=False, default=str),
                headers=headers,
            )

        except Exception as e:
            _logger.error("Extension API list exception: %s\n%s", str(e), traceback.format_exc())
            return http.Response(
                json.dumps({"success": False, "error": str(e)}, ensure_ascii=False),
                status=500,
                headers=headers,
            )
