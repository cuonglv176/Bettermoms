# -*- coding: utf-8 -*-
{
	'name': 'Warehouse Report',

	'summary': """
Prepares all type of warehouse/inventory reports in XLSX.
""",

	'description': """
Best Warehouse Reports Apps ,
    Warehouse Management System ,
    Warehouse Reports Apps ,
    Reports for Warehouse ,
    Stock Management System  ,
    Stock Measures Reports ,
    Warehouse Measure Reports ,
    Inventory Measures Reports ,
    Valuation Report Apps ,
    Stock Valuation Report Apps ,
    Inventory Valuation Report  ,
    Warehouse Valuation Apps ,
    Stock Movement Report Apps ,
    Warehouse Movement Report Apps ,
    Warehouse Stock Report Apps ,
    Stock Location Report Apps ,
    Stock Transfer Report Apps ,
    Inventory Transfer Report ,
    Stock IN and OUT Report ,
    Stock IN/OUT Report ,
    Inventory IN/OUT Report ,
    Status Wise Report ,
    Stock Transfer Dates Report  ,
    Stock Locations Report ,
    Inventory Location Reports ,
    Inventory Report Apps ,
    Product Movement Reports ,
    Stock Inventory Ageing Report ,
    Stock Inventory Ageing Report ,
    Stock Status Report ,
    Stock Ageing No Movement Report ,
    Stock Inventory Ageing Report with all movements ,
    Print warehouse report ,
    Professional Reports Excel ,
    Sales Analysis Report ,
    Purchase Product Quality Report  ,
    Quality Control Reports ,
    Quality Inspection Reports ,
    Excel Printout Reports  ,
    Excel Report for Warehouse ,
    Per Order Reports ,
    Per Product Reports ,
    Per Sale Reports ,
    Internal Reports ,
    Sale Report Apps ,
    Product Report Apps ,
    Purchase Report Apps ,
    Division Report Apps ,
    Restrict Picking Report
""",

	'author': 'Ksolves India Ltd.',

	'license': 'OPL-1',

	'currency': 'EUR',

	'price': '33',

	'website': 'https://www.ksolves.com',

	'maintainer': 'Ksolves India Ltd.',

	'live_test_url': 'https://warehousereport14.kappso.com/',

	'category': 'Warehouse',

	'version': '15.0.1.0.2',

	'support': 'sales@ksolves.com',

	'images': ['static/description/warehouse_report_banner.gif'],

	'depends': ['base', 'stock', 'sale_stock', 'purchase_stock', 'report_xlsx'],

	'data': ['security/ir.model.access.csv', 'security/ks_warehouse_security.xml', 'views/ks_warehouse_view.xml', 'wizard/ks_warehouse_report_valuation_view.xml', 'wizard/ks_warehouse_report_measures_view.xml', 'wizard/ks_warehouse_report_movement_view.xml', 'wizard/ks_warehouse_report_in_out_status_view.xml', 'wizard/ks_warehouse_report_location_transfer_view.xml', 'wizard/ks_warehouse_report_ageing_no_movement_view.xml', 'wizard/ks_warehouse_report_ageing_with_movement_view.xml'],

	'external_dependencies': {'python': ['openpyxl']},
}
