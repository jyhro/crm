"""Permission-aware order exploration. Filters never replace creator isolation."""

import frappe
from frappe import _
from frappe.utils import getdate

SALES_ORDER_LIST_FIELDS = ["name", "status", "docstatus", "grand_total", "currency", "transaction_date", "delivery_date", "customer", "customer_name", "modified"]
def _is_erpnext_installed():
	return "erpnext" in frappe.get_installed_apps()

from crm.ig_extensions.permissions.sales_order import is_order_manager
from crm.ig_extensions.permissions.sales_scope import visible_users


def _available():
	settings = frappe.get_single("ERPNext CRM Settings")
	return bool(settings.enabled and not settings.is_erpnext_in_different_site and _is_erpnext_installed()
		and frappe.has_permission("Sales Order", "read"))


def _query(fields, from_date=None, to_date=None, order_id=None, customer=None, item_code=None, status=None, **kwargs):
	filters = []
	if not is_order_manager():
		filters.append(["owner", "in", visible_users()])
	if from_date and to_date and getdate(from_date) > getdate(to_date):
		frappe.throw(_("The start date must be before the end date."), frappe.ValidationError)
	if from_date:
		filters.append(["transaction_date", ">=", getdate(from_date)])
	if to_date:
		filters.append(["transaction_date", "<=", getdate(to_date)])
	if order_id:
		filters.append(["name", "like", "%" + order_id.strip() + "%"])
	if customer:
		filters.append(["customer", "=", customer])
	if status:
		states = {"draft": 0, "ready": 1, "cancelled": 2}
		if status not in states:
			frappe.throw(_("Invalid order status."), frappe.ValidationError)
		filters.append(["docstatus", "=", states[status]])
	query = frappe.qb.get_query("Sales Order", fields=fields, filters=filters, ignore_permissions=False, **kwargs)
	if item_code:
		items = frappe.qb.DocType("Sales Order Item")
		orders = frappe.qb.DocType("Sales Order")
		parents = frappe.qb.from_(items).select(items.parent).where(
			(items.item_code == item_code) & (items.parenttype == "Sales Order") & (items.parentfield == "items")
		)
		query = query.where(orders.name.isin(parents))
	return query


@frappe.whitelist()
def get_page(limit: int = 50, start: int = 0, from_date: str | None = None, to_date: str | None = None,
	order_id: str | None = None, customer: str | None = None, item_code: str | None = None, status: str | None = None):
	if not _available():
		return {"rows": [], "total": 0, "states": {}, "enabled": False}
	filters = dict(from_date=from_date, to_date=to_date, order_id=order_id, customer=customer, item_code=item_code, status=status)
	rows = _query([*SALES_ORDER_LIST_FIELDS, "owner"], **filters,
		order_by="creation desc, name desc", limit=min(max(int(limit), 1), 100), offset=max(int(start), 0)).run(as_dict=True)
	counts = _query(["docstatus", {"COUNT": "name", "as": "count"}], **filters, group_by="docstatus").run(as_dict=True)
	states = {str(row.docstatus): int(row.count) for row in counts}
	return {"rows": rows, "total": sum(states.values()), "states": states, "enabled": True}


@frappe.whitelist()
def get_filter_options(field: str, txt: str = ""):
	if field not in {"customer", "item_code"}:
		frappe.throw(_("Invalid filter."), frappe.ValidationError)
	if not _available():
		return []
	if field == "customer":
		query = _query(["customer", "customer_name"], distinct=True, limit=25, order_by="customer_name asc")
		if txt:
			orders = frappe.qb.DocType("Sales Order")
			query = query.where(orders.customer_name.like("%" + txt + "%") | orders.customer.like("%" + txt + "%"))
		return [{"value": row.customer, "label": row.customer_name or row.customer} for row in query.run(as_dict=True)]
	items = frappe.qb.DocType("Sales Order Item")
	query = frappe.qb.from_(items).select(items.item_code, items.item_name).distinct().where(
		items.parent.isin(_query(["name"])) & (items.parenttype == "Sales Order") & (items.parentfield == "items")
	)
	if txt:
		query = query.where(items.item_code.like("%" + txt + "%") | items.item_name.like("%" + txt + "%"))
	return [{"value": row.item_code, "label": row.item_name or row.item_code, "description": row.item_code}
		for row in query.orderby(items.item_code).limit(25).run(as_dict=True)]
