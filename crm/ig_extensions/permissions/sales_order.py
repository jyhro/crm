"""Creator ownership applies across CRM, REST, document methods and link searches."""

import frappe
from frappe import _
from crm.ig_extensions.permissions.sales_scope import visible_users, user_condition


def is_order_manager(user=None):
	return visible_users(user) is None


def get_permission_query_conditions(user=None):
	user = user or frappe.session.user
	if is_order_manager(user):
		return ""
	return user_condition("`tabSales Order`.`owner`", user)


def has_permission(doc, ptype, user=None, **kwargs):
	user = user or frappe.session.user
	if is_order_manager(user) or ptype == "create" or doc.is_new():
		return True  # Does not grant rights: Frappe still checks the role's permissions.
	# Trust the stored creator, never a caller-supplied owner in a save payload.
	owner = frappe.db.get_value("Sales Order", doc.name, "owner")
	if owner not in visible_users(user):
		# Returning False alone lets Frappe's subsequent DocShare fallback grant access.
		frappe.throw(_("You can only access sales orders you created."), frappe.PermissionError)
	return True


def validate_creator(doc, method=None):
	if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
		return
	if doc.is_new():
		doc.owner = frappe.session.user
	else:
		owner = frappe.db.get_value("Sales Order", doc.name, "owner")
		if owner and doc.owner != owner:
			frappe.throw(_("The creator of a sales order cannot be changed."), frappe.PermissionError)
