"""Match the CRM's existing sales hierarchy when determining supervision scope."""

import frappe


def visible_users(user=None):
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	if user == "Administrator" or "System Manager" in roles:
		return None
	if "Sales Manager" in roles:
		if frappe.db.get_single_value("FCRM Settings", "enable_sales_hierarchy"):
			root = frappe.db.get_value("CRM Sales Hierarchy", {"user": user}, ["lft", "rgt"], as_dict=True)
			if root:
				return sorted({user, *frappe.get_all("CRM Sales Hierarchy", filters={"lft": [">=", root.lft], "rgt": ["<=", root.rgt]}, pluck="user")})
		return None
	return [user]


def user_condition(field, user=None):
	users = visible_users(user)
	return "1=1" if users is None else f"{field} IN ({', '.join(frappe.db.escape(value) for value in users)})"
