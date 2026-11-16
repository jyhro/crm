# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.exceptions import HTTPException
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from crm.tests import load_crm_user_test_records
from crm.ig_extensions.utils.crm_only import (
	confine_to_crm,
	is_blocked_path,
	is_crm_only_user,
	make_crm_the_default_app,
	enforce_crm_access,
)

SALES_USER = "crm.user1@example.com"
OTHER_SALES_USER = "crm.user2@example.com"
SALES_MANAGER = "crm.manager@example.com"
CRM_ADMIN = "crm.admin@example.com"


class TestCRMOnlyUsers(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		load_crm_user_test_records()

	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		self.addCleanup(setattr, frappe.local, "form_dict", frappe.local.form_dict)

	def request(self, path, user, params=None):
		frappe.set_user(user)
		frappe.local.request = Request(EnvironBuilder(path=path, method="GET").get_environ())
		frappe.local.form_dict = frappe._dict(params or {})

	def test_user_with_only_sales_roles_is_crm_only(self):
		self.assertTrue(is_crm_only_user(SALES_USER))
		self.assertTrue(is_crm_only_user(SALES_MANAGER))

	def test_system_manager_is_not_crm_only(self):
		self.assertFalse(is_crm_only_user(CRM_ADMIN))
		self.assertFalse(is_crm_only_user("Administrator"))

	def test_guest_is_not_crm_only(self):
		self.assertFalse(is_crm_only_user("Guest"))

	def test_sales_user_with_another_non_admin_role_is_still_crm_only(self):
		# other apps add roles on their own (Employee, ...); only System Manager lifts the limit
		user = frappe.get_doc("User", OTHER_SALES_USER)
		user.add_roles("Report Manager")
		self.addCleanup(user.remove_roles, "Report Manager")
		self.assertTrue(is_crm_only_user(OTHER_SALES_USER))

	def test_non_admin_without_sales_role_cannot_enter_other_apps(self):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "desk.only@example.com",
				"first_name": "Desk Only",
				"send_welcome_email": 0,
				"roles": [{"role": "Report Manager"}],
			}
		).insert(ignore_permissions=True)
		self.assertTrue(is_crm_only_user(user.name))

	def test_confinement_runs_before_every_request(self):
		self.assertIn("crm.ig_extensions.utils.crm_only.confine_to_crm", frappe.get_hooks("before_request"))

	def test_crm_becomes_the_default_app_when_none_is_set(self):
		frappe.db.set_single_value("System Settings", "default_app", "")
		make_crm_the_default_app()
		self.assertEqual(frappe.db.get_single_value("System Settings", "default_app"), "crm")

	def test_a_default_app_chosen_by_an_admin_is_kept(self):
		frappe.db.set_single_value("System Settings", "default_app", "erpnext")
		make_crm_the_default_app()
		self.assertEqual(frappe.db.get_single_value("System Settings", "default_app"), "erpnext")

	def test_default_app_is_set_after_every_migrate(self):
		self.assertIn("crm.ig_extensions.install.apply_configuration", frappe.get_hooks("after_migrate"))

	def test_desk_and_other_app_paths_are_blocked(self):
		for path in (
			"/desk",
			"/desk/sales-order",
			"/app",
			"/app/item/X",
			"/apps",
			"/helpdesk",
			"/helpdesk/tickets",
			"/hrms",
			"/me",
			"/update-profile",
			"/printview",
			"/insights",
			"/drive",
			"/application",
		):
			self.assertTrue(is_blocked_path(path), path)

	def test_crm_api_and_asset_paths_are_not_blocked(self):
		for path in (
			"/crm",
			"/crm/leads",
			"/api/method/ping",
			"/assets/crm/frontend/index.js",
			"/login",
			"/logout",
			"/update-password",
			"/private/files/document.pdf",
			"/files/logo.png",
		):
			self.assertFalse(is_blocked_path(path), path)

	def test_sales_user_opening_desk_is_redirected_to_crm(self):
		self.request("/desk/sales-order", SALES_USER)
		with self.assertRaises(HTTPException) as ctx:
			confine_to_crm()
		response = ctx.exception.get_response()
		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.headers["Location"], "/crm")

	def test_sales_user_opening_crm_is_not_redirected(self):
		self.request("/crm/leads", SALES_USER)
		confine_to_crm()

	def test_admin_opening_desk_is_not_redirected(self):
		self.request("/desk", CRM_ADMIN)
		confine_to_crm()

	def test_api_guard_runs_after_api_key_authentication(self):
		from unittest.mock import patch
		from frappe.auth import validate_auth

		self.assertIn("crm.ig_extensions.utils.crm_only.enforce_crm_access", frappe.get_hooks("auth_hooks"))
		self.request("/api/method/frappe.desk.form.load.getdoc", "Guest")
		with patch("frappe.auth.validate_auth_via_api_keys", side_effect=lambda header: frappe.set_user(SALES_USER)), patch("frappe.auth.validate_oauth"), patch("frappe.get_request_header", return_value="token dummy:dummy"):
			with self.assertRaises(frappe.PermissionError):
				validate_auth()

	def test_unneeded_framework_and_other_app_methods_are_blocked(self):
		for method in ("frappe.desk.form.load.getdoc", "frappe.desk.form.load.getdoc", "frappe.desk.query_report.run", "erpnext.accounts.report.general_ledger.general_ledger.execute", "frappe.core.doctype.user.user.generate_keys", "crm.api.user.update_user_role"):
			for prefix in ("/api/method/", "/api/v1/method/", "/api/v2/method/"):
				self.request(prefix + method, SALES_USER)
				with self.subTest(method=method, prefix=prefix), self.assertRaises(frappe.PermissionError):
					enforce_crm_access()

	def test_legacy_cmd_cannot_bypass_api_guard(self):
		self.request("/", SALES_MANAGER, {"cmd": "frappe.desk.form.load.getdoc"})
		with self.assertRaises(frappe.PermissionError):
			enforce_crm_access()

	def test_account_and_admin_resources_are_blocked(self):
		for doctype in ("User", "Role", "System Settings", "User Permission", "Server Script", "Sales Invoice"):
			for user in (SALES_USER, SALES_MANAGER):
				for prefix in ("/api/resource/", "/api/v1/resource/", "/api/v2/document/"):
					self.request(prefix + doctype, user)
					with self.subTest(doctype=doctype, user=user, prefix=prefix), self.assertRaises(frappe.PermissionError):
						enforce_crm_access()

	def test_nested_doc_payload_cannot_write_administration_records(self):
		self.request("/api/method/frappe.client.save", SALES_USER, {"doc": {"doctype": "User", "name": OTHER_SALES_USER}})
		with self.assertRaises(frappe.PermissionError):
			enforce_crm_access()

	def test_order_lists_and_searches_always_include_creator_filter(self):
		for method in ("frappe.client.get_list", "frappe.client.get_value", "frappe.desk.search.search_link", "crm.api.doc.get_data"):
			self.request("/api/method/" + method, SALES_USER, {"doctype": "Sales Order", "filters": {"owner": OTHER_SALES_USER}})
			enforce_crm_access()
			self.assertIn(["Sales Order", "owner", "in", [SALES_USER]], frappe.form_dict.filters)

	def test_authentication_and_crm_api_are_preserved(self):
		for method in ("logout", "frappe.auth.get_logged_user", "crm.api.session.get_users", "crm.api.user.change_password"):
			self.request("/api/method/" + method, SALES_USER)
			enforce_crm_access()

	def test_realtime_socket_can_authenticate(self):
		# the socket.io server asks this with the user's cookie; refused, nothing updates live
		self.request("/api/method/frappe.realtime.get_user_info", SALES_USER)
		enforce_crm_access()

	def test_realtime_socket_can_join_crm_document_rooms(self):
		self.request("/api/method/frappe.realtime.has_permission", SALES_USER, {"doctype": "CRM Lead"})
		enforce_crm_access()

	def test_admin_apis_are_preserved(self):
		self.request("/api/resource/User", CRM_ADMIN)
		enforce_crm_access()

	def test_rest_document_methods_cannot_mutate_read_only_settings(self):
		self.request("/api/resource/FCRM Settings/FCRM Settings", SALES_USER, {"run_method": "restore_defaults", "force": 1})
		with self.assertRaises(frappe.PermissionError):
			enforce_crm_access()
		settings = frappe.get_doc("FCRM Settings")
		with self.assertRaises(frappe.PermissionError):
			settings.restore_defaults(force=True)
