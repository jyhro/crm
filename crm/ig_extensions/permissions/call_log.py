import frappe
from frappe import _
from crm.ig_extensions.permissions.sales_scope import visible_users, user_condition


def agent_condition(user=None):
	return (
		f"((`tabCRM Call Log`.type = 'Outgoing' AND {user_condition('`tabCRM Call Log`.caller', user)})"
		f" OR (`tabCRM Call Log`.type = 'Incoming' AND {user_condition('`tabCRM Call Log`.receiver', user)})"
		" OR (COALESCE(`tabCRM Call Log`.caller, '') = '' AND COALESCE(`tabCRM Call Log`.receiver, '') = ''"
		f" AND {user_condition('`tabCRM Call Log`.owner', user)}))"
	)


def query_condition(user=None):
	return "" if visible_users(user) is None else agent_condition(user)


def has_permission(doc, ptype, user=None, **kwargs):
	if visible_users(user) is None or ptype == "create" or doc.is_new():
		return True
	if not can_access(doc.name, user):
		frappe.throw(_("You can only access calls in your authorized team."), frappe.PermissionError)
	return True


def can_access(name, user=None):
	return visible_users(user) is None or bool(frappe.db.sql(
		f"SELECT name FROM `tabCRM Call Log` WHERE name = %s AND ({agent_condition(user)})", (name,)))


def validate_agent(doc, method=None):
	users = visible_users()
	if users is None or frappe.session.user == "Guest":
		return
	field = "caller" if doc.type == "Outgoing" else "receiver"
	if doc.is_new():
		if doc.get(field) and doc.get(field) not in users:
			frappe.throw(_("You cannot register calls for another sales team."), frappe.PermissionError)
		doc.set(field, doc.get(field) or frappe.session.user)
	else:
		has_permission(doc, "write")
		old = frappe.db.get_value("CRM Call Log", doc.name, ["caller", "receiver", "type"], as_dict=True)
		if any(doc.get(key) != old.get(key) for key in ("caller", "receiver", "type")):
			frappe.throw(_("The call agent cannot be changed."), frappe.PermissionError)
