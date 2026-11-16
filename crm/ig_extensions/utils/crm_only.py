import frappe
from frappe import _
import re
from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect

CRM_ROLES = {"Sales User", "Sales Manager"}

# first path segment of the desk and of the other apps' own UIs
ALLOWED_ROOTS = {"crm", "api", "assets", "files", "login", "logout", "update-password", "reset-password", "twofactor", "socket.io"}

# Deliberately narrow: these are framework services used by the CRM, not Desk APIs.
FRAMEWORK_METHODS = {
	"login", "logout", "ping", "frappe.auth.get_logged_user", "frappe.apps.get_apps",
	"frappe.client.get", "frappe.client.get_list", "frappe.client.get_value",
	"frappe.client.get_count", "frappe.client.get_single_value", "frappe.client.get_doc_permissions",
	"frappe.client.insert", "frappe.client.save", "frappe.client.set_value", "frappe.client.delete",
	"frappe.client.rename_doc", "frappe.desk.search.search_link",
	"frappe.desk.form.load.getdoctype", "frappe.desk.form.assign_to.add",
	"frappe.desk.form.assign_to.add_multiple", "frappe.desk.form.assign_to.remove_multiple",
	"frappe.desk.form.utils.update_comment", "frappe.desk.like.toggle_like",
	"frappe.core.doctype.communication.email.make", "frappe.core.doctype.user.user.get_timezones",
	"frappe.email.doctype.email_template.email_template.get_email_template",
	"frappe.model.utils.user_settings.get", "frappe.model.utils.user_settings.save",
	"frappe.onboarding.update_user_onboarding_status", "upload_file", "frappe.handler.upload_file",
	# asked by the socket.io server with the user's cookie, to authenticate and to join doc rooms
	"frappe.realtime.get_user_info", "frappe.realtime.has_permission",
}
AUTH_METHODS = {"login", "logout", "ping", "frappe.auth.get_logged_user"}
CRM_USER_METHODS = {"crm.api.user.change_password", "crm.api.user.needs_password_setup"}
SUPPORT_DOCTYPES = {
	"Sales Order", "Quotation", "Customer", "Item",
	"Item Price", "Item Group", "UOM", "Price List", "Currency", "Country", "Territory",
	"Industry Type", "Customer Group", "Contact", "Address", "ToDo",
	"Communication", "Comment", "File", "Email Template", "Notification Log", "Call Outcome",
	"Company", "Language", "FCRM Settings", "FCRM Note",
}
READ_ONLY_DOCTYPES = {"FCRM Settings", "Company", "ERPNext CRM Settings"}
WRITE_METHODS = {"frappe.client.insert", "frappe.client.save", "frappe.client.set_value", "frappe.client.delete", "frappe.client.rename_doc"}


def is_crm_only_user(user: str | None = None) -> bool:
	"""Only System Managers may enter the other installed applications."""
	user = user or frappe.session.user
	if user in ("Guest", "Administrator"):
		return False
	roles = set(frappe.get_roles(user))
	return "System Manager" not in roles


def is_blocked_path(path: str) -> bool:
	if path.startswith("/private/files/"):
		return False
	return path.strip("/").split("/", 1)[0] not in ALLOWED_ROOTS


def confine_to_crm():
	"""before_request: send CRM-only users back to the CRM from the desk and other apps."""
	request = getattr(frappe.local, "request", None)
	# path first: API and asset requests must not pay for a role lookup
	if not request or not is_blocked_path(request.path):
		return
	if is_crm_only_user():
		raise HTTPException(response=redirect("/crm"))


def _deny():
	frappe.throw(_("This account can only access authorized CRM resources."), frappe.PermissionError)


def _restrict_doctype(doctype, method):
	if not isinstance(doctype, str):
		_deny()
	# Metadata for a User link is needed for assignment, never expose account records.
	if doctype == "User" and method in {"frappe.desk.search.search_link", "frappe.desk.form.load.getdoctype"}:
		return
	if doctype == "User" and method in {"frappe.client.get", "frappe.client.get_doc_permissions", "frappe.client.save", "frappe.client.set_value"}:
		payload = frappe.parse_json(frappe.form_dict.get("doc")) if frappe.form_dict.get("doc") else {}
		target = frappe.form_dict.get("name") or frappe.form_dict.get("docname") or payload.get("name")
		if target == frappe.session.user:
			return
	if method == "frappe.desk.form.load.getdoctype" and doctype in {"Dynamic Link", "Contact Phone", "Contact Email", "Sales Order Item", "Quotation Item", "Payment Schedule", "Sales Taxes and Charges"}:
		return
	if doctype == "ERPNext CRM Settings":
		if method != "frappe.client.get_single_value" or frappe.form_dict.get("field") != "enabled":
			_deny()
	elif not (doctype.startswith("CRM ") or doctype in SUPPORT_DOCTYPES):
		_deny()
	if doctype in READ_ONLY_DOCTYPES and method in WRITE_METHODS:
		_deny()


def _restrict_order_filters(params):
	from crm.ig_extensions.permissions.sales_scope import visible_users

	users = visible_users()
	if users is None:
		return
	# A top-level filter also covers Frappe's OR-based DocShare fallback in lists.
	try:
		filters = frappe.parse_json(params.get("filters")) or []
	except ValueError:
		filters = params.get("filters")
	if isinstance(filters, str):
		filters = [["name", "=", filters]]
	elif isinstance(filters, dict):
		filters = [
			[key, *(value if isinstance(value, list) else ["=", value])]
			for key, value in filters.items()
		]
	if not isinstance(filters, list):
		_deny()
	params["filters"] = [*filters, ["Sales Order", "owner", "in", users]]
	if params.get("query"):
		_deny()  # A custom link query must not bypass creator visibility.


def _restrict_customer_shares(params, doctype):
	from crm.ig_extensions.permissions.customer_scope import can_access
	from crm.ig_extensions.permissions.sales_order import is_order_manager
	if is_order_manager():
		return
	if params.get("query"):
		_deny()
	shared = frappe.get_all("DocShare", filters={"share_doctype": doctype},
		or_filters={"user": frappe.session.user, "everyone": 1}, pluck="share_name")
	if doctype == "Item Price":
		from crm.ig_extensions.permissions.price import can_access as can_read_price
		foreign = [name for name in shared if not can_read_price(name)]
	elif doctype == "FCRM Note":
		from crm.ig_extensions.permissions.note import can_access as can_read_note
		foreign = [name for name in shared if not can_read_note(name)]
	elif doctype == "CRM Call Log":
		from crm.ig_extensions.permissions.call_log import can_access as can_read_call
		foreign = [name for name in shared if not can_read_call(name)]
	else:
		foreign = [name for name in shared if not can_access(doctype, name)]
	if foreign:
		try:
			filters = frappe.parse_json(params.get("filters")) or []
		except ValueError:
			filters = params.get("filters")
		if isinstance(filters, str):
			filters = [["name", "=", filters]]
		elif isinstance(filters, dict):
			filters = [[key, *(value if isinstance(value, list) else ["=", value])] for key, value in filters.items()]
		if not isinstance(filters, list):
			_deny()
		params["filters"] = [*filters, [doctype, "name", "not in", foreign]]


def _check_record(doctype, name):
	if doctype in {"Sales Order", "CRM Organization", "Customer", "Contact", "Address", "CRM Call Log", "FCRM Note", "Item Price"} and name:
		frappe.has_permission(doctype, "read", doc=name, throw=True)


def enforce_crm_access():
	"""auth_hook: runs AFTER cookie, API-key and OAuth authentication has resolved."""
	request = getattr(frappe.local, "request", None)
	if not request or request.method == "OPTIONS" or not is_crm_only_user():
		return
	params = frappe.form_dict
	method = params.get("cmd")
	if not method:
		match = re.match(r"^/api/(?:v[12]/)?method/([^/]+)/*$", request.path)
		method = match.group(1) if match else None
	if method:
		if not isinstance(method, str):
			_deny()
		if method in AUTH_METHODS:
			return
		if not CRM_ROLES.intersection(frappe.get_roles()):
			_deny()
		if method.startswith("crm.api.user.") and method not in CRM_USER_METHODS:
			_deny()
		if method in {"crm.api.invite_by_email", "crm.api.settings.create_email_account"}:
			_deny()
		if not (method.startswith(("crm.", "crm.ig_extensions.")) or method in FRAMEWORK_METHODS):
			_deny()
		for key in ("doctype", "dt", "reference_doctype", "reference_type"):
			if params.get(key):
				_restrict_doctype(params[key], method)
				_check_record(params[key], params.get("name") or params.get("docname") or params.get("reference_name"))
		payload = frappe.parse_json(params.get("doc")) if params.get("doc") else None
		if payload:
			if not isinstance(payload, dict):
				_deny()
			_restrict_doctype(payload.get("doctype"), method)
			if payload.get("name") and frappe.db.exists(payload.get("doctype"), payload["name"]):
				_check_record(payload.get("doctype"), payload["name"])
		if params.get("doctype") == "Sales Order":
			_restrict_order_filters(params)
		elif params.get("doctype") in {"CRM Organization", "Customer", "Contact", "Address", "CRM Call Log", "FCRM Note", "Item Price"}:
			_restrict_customer_shares(params, params.doctype)
		return
	if request.path.startswith("/api/"):
		if params.get("run_method"):
			_deny()
		# CRM uses REST v1 resources; deny unneeded v2 bulk/document/admin surfaces.
		match = re.match(r"^/api/(?:v1/)?resource/([^/]+)(?:/.*)?$", request.path)
		if not match or not CRM_ROLES.intersection(frappe.get_roles()):
			_deny()
		doctype = match.group(1)
		_restrict_doctype(doctype, "frappe.client.get" if request.method == "GET" else "frappe.client.save")
		if doctype == "Sales Order":
			_restrict_order_filters(params)
		elif doctype in {"CRM Organization", "Customer", "Contact", "Address", "CRM Call Log", "FCRM Note", "Item Price"}:
			_restrict_customer_shares(params, doctype)
		return
	confine_to_crm()


def make_crm_the_default_app():
	"""after_migrate: land everyone on the CRM unless an admin picked another default app."""
	if not frappe.db.get_single_value("System Settings", "default_app"):
		frappe.db.set_single_value("System Settings", "default_app", "crm")
