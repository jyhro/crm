"""Native ERPNext documents, permissions and transactions; no forked controllers."""
import math
import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, add_days, today, flt


def _order(name, permission, lock=False):
	doc = frappe.get_doc("Sales Order", name, for_update=lock)
	doc.check_permission(permission)
	return doc


def _version(doc, modified):
	if not modified or get_datetime(modified) != get_datetime(doc.modified):
		frappe.throw(_("This order changed. Reload it before saving."), frappe.TimestampMismatchError)


def _items(items, delivery_date):
	if not isinstance(items, list) or not items:
		frappe.throw(_("Add at least one product."))
	rows = []
	for item in items:
		if not isinstance(item, dict) or not item.get("item_code"):
			frappe.throw(_("Select a product for every line."))
		frappe.has_permission("Item", "read", doc=item["item_code"], throw=True)
		qty = flt(item.get("qty"))
		if not math.isfinite(qty) or qty <= 0:
			frappe.throw(_("Quantity must be greater than zero."))
		row = {"item_code": item["item_code"], "qty": qty, "delivery_date": delivery_date}
		if item.get("rate") not in (None, ""):
			rate = flt(item["rate"])
			if not math.isfinite(rate) or rate < 0:
				frappe.throw(_("Rate cannot be negative."))
			row["rate"] = rate
		rows.append(row)
	return rows


@frappe.whitelist()
def get_sales_order_detail(name: str):
	doc = _order(name, "read")
	organizations = frappe.get_list("CRM Organization", filters={"name": doc.customer_name}, pluck="name", limit=1)
	return {**{key: doc.get(key) for key in ["name", "status", "docstatus", "customer", "customer_name", "transaction_date", "delivery_date", "currency", "total", "total_taxes_and_charges", "grand_total", "owner", "modified"]},
		"organization": organizations[0] if organizations else None,
		"items": [{key: row.get(key) for key in ["item_code", "item_name", "qty", "uom", "rate", "amount"]} for row in doc.items],
		"can_edit": doc.docstatus == 0 and doc.has_permission("write"),
		"can_delete": doc.docstatus == 0 and doc.has_permission("delete"),
		"can_mark_ready": doc.docstatus == 0 and doc.has_permission("submit")}


@frappe.whitelist(methods=["POST"])
def update_sales_order_items(name: str, items: list[dict], delivery_date: str | None = None, modified: str | None = None):
	doc = _order(name, "write", lock=True)
	if doc.docstatus != 0:
		frappe.throw(_("Only draft orders can be edited."))
	_version(doc, modified)
	doc.delivery_date = getdate(delivery_date or doc.delivery_date)
	doc.set("items", _items(items, doc.delivery_date))
	doc.save()
	return {"name": doc.name, "modified": doc.modified}


@frappe.whitelist(methods=["POST"])
def delete_sales_order(name: str):
	doc = _order(name, "delete", lock=True)
	if doc.docstatus != 0:
		frappe.throw(_("Only draft orders can be deleted."))
	doc.delete()
	return {"name": name}


@frappe.whitelist(methods=["POST"])
def mark_sales_order_ready(name: str):
	doc = _order(name, "submit", lock=True)
	if doc.docstatus == 1:
		return {"name": doc.name, "docstatus": 1, "status": doc.status}
	if doc.docstatus != 0:
		frappe.throw(_("Only draft orders can be marked as ready."))
	doc.submit()
	return {"name": doc.name, "docstatus": doc.docstatus, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def create_organization_sales_order(organization: str, items: list[dict], delivery_date: str | None = None):
	frappe.has_permission("CRM Organization", "read", doc=organization, throw=True)
	frappe.has_permission("Sales Order", "create", throw=True)
	settings = frappe.get_single("ERPNext CRM Settings")
	if not settings.enabled or settings.is_erpnext_in_different_site or not settings.erpnext_company:
		frappe.throw(_("Configure the local ERPNext integration before creating orders."))
	customer = frappe.db.get_value("Customer", {"customer_name": organization}, "name")
	if not customer:
		customer_group = frappe.db.get_single_value("Selling Settings", "customer_group")
		if not customer_group or frappe.db.get_value("Customer Group", customer_group, "is_group"):
			customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		territory = frappe.db.get_single_value("Selling Settings", "territory")
		if not territory or frappe.db.get_value("Territory", territory, "is_group"):
			territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
		if not customer_group or not territory:
			frappe.throw(_("Configure a customer group and territory before creating orders."))
		customer = frappe.get_doc({"doctype": "Customer", "customer_name": organization, "customer_type": "Company",
			"customer_group": customer_group, "territory": territory}).insert().name
	frappe.has_permission("Customer", "read", doc=customer, throw=True)
	delivery = getdate(delivery_date or add_days(today(), 7))
	doc = frappe.get_doc({"doctype": "Sales Order", "customer": customer, "company": settings.erpnext_company,
		"transaction_date": today(), "delivery_date": delivery, "order_type": "Sales",
		"selling_price_list": "Standard Selling", "items": _items(items, delivery)}).insert()
	return {"name": doc.name, "modified": doc.modified}
