"""Checks around inherited CRM endpoints using Frappe's supported RPC overrides."""
import frappe
from urllib.parse import quote


@frappe.whitelist()
def get_customer_link(crm_deal: str):
	frappe.has_permission("CRM Deal", "read", doc=crm_deal, throw=True)
	from crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings import get_customer_link as original
	from crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings import get_local_customer
	if not frappe.db.get_single_value("ERPNext CRM Settings", "is_erpnext_in_different_site"):
		customer = get_local_customer(crm_deal)
		if customer:
			frappe.has_permission("Customer", "read", doc=customer, throw=True)
	return original(crm_deal)


@frappe.whitelist()
def get_apps():
	from frappe.apps import get_apps as original
	apps = original()
	if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
		return apps
	return [app for app in apps if app.get("name") in {"crm"}]


@frappe.whitelist()
def get_sales_order_url_for_organization(organization: str):
	frappe.has_permission("CRM Organization", "read", doc=organization, throw=True)
	return "/crm/sales-orders?organization=" + quote(organization, safe="")


@frappe.whitelist()
def get_my_sales_orders(limit: int = 50, start: int = 0):
	from crm.ig_extensions.api.sales_orders import get_page
	return get_page(limit=limit, start=start)["rows"]


@frappe.whitelist()
def get_organization_sales_orders(organization: str):
	frappe.has_permission("CRM Organization", "read", doc=organization, throw=True)
	from crm.ig_extensions.api.sales_orders import _query, _available
	if not _available():
		return []
	customer = frappe.db.get_value("Customer", {"customer_name": organization}, "name")
	if not customer:
		return []
	rows = _query(["name", "status", "docstatus", "grand_total", "currency", "transaction_date", "delivery_date", "customer", "customer_name", "owner"], customer=customer, order_by="modified desc", limit=200).run(as_dict=True)
	for row in rows:
		row["url"] = "/crm/sales-orders/" + quote(row.name, safe="")
	return rows
