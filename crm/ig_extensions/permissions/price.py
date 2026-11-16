import frappe
from frappe import _
from crm.ig_extensions.permissions.customer_scope import scope_required, _customer


def query_condition(user=None):
	user = user or frappe.session.user
	if not scope_required(user):
		return ""
	return ("(`tabItem Price`.selling = 1 AND COALESCE(`tabItem Price`.supplier, '') = '' AND "
		"(COALESCE(`tabItem Price`.customer, '') = '' OR EXISTS (SELECT 1 FROM `tabCustomer` customer "
		f"WHERE customer.name = `tabItem Price`.customer AND {_customer('customer', user)})))")


def has_permission(doc, ptype, user=None, **kwargs):
	user = user or frappe.session.user
	if not scope_required(user) or doc.is_new() or ptype == "create":
		return True
	if not doc.selling or doc.supplier:
		frappe.throw(_("This price is not available for your sales role."), frappe.PermissionError)
	if doc.customer:
		frappe.has_permission("Customer", "read", doc=doc.customer, user=user, throw=True)
	return True


def can_access(name, user=None):
	user = user or frappe.session.user
	if not scope_required(user):
		return True
	row = frappe.db.get_value("Item Price", name, ["selling", "supplier", "customer"], as_dict=True)
	if not row or not row.selling or row.supplier:
		return False
	if row.customer:
		from crm.ig_extensions.permissions.customer_scope import can_access as can_read_customer
		return can_read_customer("Customer", row.customer, user)
	return True
