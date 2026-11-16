import frappe
from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect

CRM_ROLES = {"Sales User", "Sales Manager"}

# first path segment of the desk and of the other apps' own UIs
BLOCKED_ROOTS = {"desk", "app", "apps", "helpdesk", "hrms", "hr"}


def is_crm_only_user(user: str | None = None) -> bool:
	"""CRM users work in the CRM and nowhere else, unless they are System Managers."""
	user = user or frappe.session.user
	if user in ("Guest", "Administrator"):
		return False
	roles = set(frappe.get_roles(user))
	return bool(roles & CRM_ROLES) and "System Manager" not in roles


def is_blocked_path(path: str) -> bool:
	return path.strip("/").split("/", 1)[0] in BLOCKED_ROOTS


def confine_to_crm():
	"""before_request: send CRM-only users back to the CRM from the desk and other apps."""
	request = getattr(frappe.local, "request", None)
	# path first: API and asset requests must not pay for a role lookup
	if not request or not is_blocked_path(request.path):
		return
	if is_crm_only_user():
		raise HTTPException(response=redirect("/crm"))


def make_crm_the_default_app():
	"""after_migrate: land everyone on the CRM unless an admin picked another default app."""
	if not frappe.db.get_single_value("System Settings", "default_app"):
		frappe.db.set_single_value("System Settings", "default_app", "crm")
