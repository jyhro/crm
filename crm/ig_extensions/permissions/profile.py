from contextlib import contextmanager

import frappe
from frappe import _

PROFILE_FIELDS = {"first_name", "middle_name", "last_name", "full_name", "user_image", "email_signature", "language", "time_zone", "bio", "crm_availability", "crm_availability_changed_on"}


def require_crm_role():
	frappe.only_for(["System Manager", "Sales Manager", "Sales User"], True)


def _profile_value(value):
	if isinstance(value, list):
		return [_profile_value(row) for row in value]
	if hasattr(value, "as_dict"):
		value = value.as_dict()
	if isinstance(value, dict):
		return {key: _profile_value(item) for key, item in value.items() if key not in {"modified", "modified_by", "creation", "owner", "__unsaved", "__islocal"}}
	return value


@contextmanager
def accepting_validated_invitation(email):
	"""Internal scope, used only after the invitation token has been validated."""
	previous = frappe.flags.get("crm_invitation_account")
	frappe.flags.crm_invitation_account = email.lower()
	try:
		yield
	finally:
		frappe.flags.crm_invitation_account = previous


def validate_profile(doc, method=None):
	if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
		return
	# This request-local capability cannot be supplied through a User payload.
	if frappe.flags.get("crm_invitation_account") == (doc.email or doc.name or "").lower():
		return
	if doc.is_new() or doc.name != frappe.session.user:
		frappe.throw(_("Only administrators can manage user accounts."), frappe.PermissionError)
	before = doc.get_doc_before_save()
	if not before:
		return
	for field in doc.meta.fields:
		if field.fieldname not in PROFILE_FIELDS and field.fieldtype not in {"Section Break", "Column Break", "Tab Break", "HTML", "Button"}:
			if frappe.as_json(_profile_value(doc.get(field.fieldname))) != frappe.as_json(_profile_value(before.get(field.fieldname))):
				frappe.throw(_("Only personal profile fields may be changed."), frappe.PermissionError)
