### Bettermoms — Odoo 15 Codebase Review and Improvement Plan

This document summarizes an initial, high‑level review of the Bettermoms Odoo 15 addon set and proposes prioritized improvements. It is intended as a starting point for deeper, module‑level audits.

Scope reviewed
- Monorepo path: D:\Jeisys\Bettermoms
- Addons detected (non‑exhaustive): accounting/finance (base_accounting_kit, base_account_budget, om_account_asset, sv_account_revenue, ntp_payment_support, ntp_payment_remittance, onnet_payment, tas_payment, tas_auto_transfer, tas_auto_net_off, tas_contra_account_separation), Vietnam localization (l10n_vn_tasys, ntp_vn_tax, ntp_vas_tax_report), invoicing/e‑invoice (onnet_einvoice, vn_einvoice, ntp_einvoice, ntp_invoice_slicing, ntp_invoice_connect_so_and_po), HR/Payroll (ntp_payroll, hr_organizational_chart), logistics/stock (bi_all_in_one_stock_backdate, bi_inventory_adjustment_with_cost, td_reset_stock_moves, ntp_stock_landed_cost, app_stock_picking_post), sales/purchase/subscription (purchase_subscription, so_po_advance_payment_app), UX/Widgets/Reporting (dashboard_widgets, report_xlsx, web_widget_bokeh_chart, app_odoo_customize, app_sequence_customize), integrations (facebook_messenger_chat, onnet_customer_groups), and internal utilities (ntp_asset, ntp_document, ntp_currency_rate_live, ntp_cne, ntp_communications, ks_warehouse_report).

Key architectural observations
1) Modular structure follows standard Odoo addon conventions: each module includes __manifest__.py, models/, controllers/ (where applicable), security/, data/, views/.
2) Multiple controllers present (e.g., dashboard_widgets, hr_organizational_chart, ntp_cne, ntp_payment_support) implying external endpoints and binary/file responses.
3) Security rules exist (security.xml, ir.model.access.csv) but need consistency checks across modules for least‑privilege and record rules.
4) Reporting/export modules (report_xlsx, dashboard_widgets) can impact performance due to heavy compute and large dataset exports.
5) Finance‑heavy modules suggest frequent ORM writes and scheduled jobs, requiring attention to compute/store strategies and batching.

Common risk areas to verify (Odoo 15 best practices)
- Access control and record rules: Ensure every model has explicit ir.model.access with correct read/write/create/unlink; apply domain‑based record rules where multi‑company or confidentiality is required.
- Controllers security: Use auth="user" where applicable; avoid exposing auth="public" unless strictly necessary; validate parameters, enforce csrf for unsafe methods, and avoid direct SQL in controllers.
- ORM performance: Prefer search_read with fields, compute fields with store=True where values are frequently shown/filtered; avoid N+1 by prefetching related fields; use sudo sparingly.
- Cron and long‑running jobs: Offload heavy tasks to queue/job (if queue_job is available) or chunk processing; guard crons with singleton locks to prevent overlaps.
- Data integrity: Use SQL constraints and Python constraints (_sql_constraints, @api.constrains); validate state transitions in workflows (sales/invoice/payments).
- Multi‑company: Ensure company_id propagation on created/related records; domains and rules consider company context; avoid mixing companies in UoM/taxes/accounts.
- Internationalization: Wrap user‑facing strings with _() for translations; include i18n templates if required.
- Upgradability: Avoid overriding core methods unnecessarily; prefer extension patterns (inheritance + super()); avoid writing directly to private fields; add proper uninstall hooks if data must be cleaned.

Quick wins (low effort, high value)
1) Lint and static checks
   - Add/enable flake8/black/isort or match existing style; run pre‑commit hooks. At minimum, standardize import orders and remove dead code.
   - Scan for dangerous sudo(), eval(), direct SQL; replace with safe ORM patterns and parameterized queries.

2) Security hardening for controllers
   - Review all http.Controller routes for auth, csrf, type, methods; add input validation and explicit content‑types for binary routes.
   - Ensure attachments/binary downloads use access checks (read on ir.attachment or underlying model) and avoid exposing file paths.

3) Access control consistency
   - For each custom model, verify ir.model.access.csv exists with minimal needed rights; add record rules for company/ownership separation.

4) Performance and UX in reporting/export
   - In report_xlsx and dashboard widgets, implement pagination/limits; compute aggregates in SQL with safe parameters or use read_group; stream large exports if feasible.

5) Compute fields and batch writes
   - Set store=True for frequently displayed computed fields; ensure depends() is accurate; batch write() operations for large datasets.

6) Logging and observability
   - Use _logger with adequate levels; avoid logging secrets; add contextual info (record ids, company) for background jobs.

Targeted deeper reviews suggested
- ntp_cne (controllers/main.py): e‑invoice notifications from external sources. Verify authentication, payload validation, idempotency, and error handling.
- ntp_payment_support (controllers/main.py): Binary/file operations — confirm access checks and safe streaming.
- finance modules (tas_* and sv_account_revenue): Validate journal entries integrity, lock dates, reconciliation flows, and tax/localization compatibility.
- dashboard_widgets: Ensure queries aggregate efficiently; cache or memoize where safe; avoid loading large datasets into the browser.

Coding guidelines to adopt (Odoo‑aligned)
- Follow PEP8; keep methods small and cohesive; prefer explicit field names in search/search_read; avoid broad sudo(); always call super() properly in overridden methods.
- Use @api.model_create_multi for create() where bulk creations occur; prefer _prepare_* helper methods.
- Use named constraints and raise ValidationError with translated messages.

Performance checklist
- Indexes: Add indexes on frequently filtered fields (via index=True on fields). For write‑heavy models, evaluate trade‑offs.
- Read_group and SQL: Prefer read_group for aggregations; when SQL is needed, use self.env.cr.execute with parameters; never string‑format SQL.
- Prefetch: Use with_context(prefetch_fields=False) cautiously; leverage Odoo’s prefetch by reading needed fields in one go.

Security checklist
- Ensure all controllers default to auth="user"; use auth="public" only with explicit constraints and rate limiting if exposed publicly.
- Validate mimetype and size of uploaded files; scan/strip dangerous content when converting to attachments.
- Verify portal access models only expose required fields.

Testing and CI recommendations
- Add minimal unit tests for core business logic (compute, constraints); for controllers, add http tests using odoo.tests.HttpCase.
- Introduce a lightweight CI workflow to run flake8 and Odoo lint checks on changed modules.

Migration/maintenance notes
- Keep manifests accurate (depends, data, demo); bump versions on changes; add post_init_hook/uninstall_hook when needed.
- Document crons and external dependencies (API keys, endpoints) per module in README files.

Next steps (proposed)
1) Choose 3 priority modules for deep dive: ntp_cne (integration), report_xlsx (performance), tas_payment (finance core). Prepare module‑specific findings and patches.
2) Implement controller security hardening patterns and sample tests in one pilot module; replicate pattern across others.
3) Add repository linting configuration and pre‑commit hooks; run once to catch basic issues.

Appendix: Review inputs
- Repository enumeration via manifest search and controller discovery from the current tree. Detailed code‑level audit pending module‑by‑module walkthrough.
