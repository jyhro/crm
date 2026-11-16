# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from werkzeug.exceptions import HTTPException
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from crm.tests import load_crm_user_test_records
from crm.utils.crm_only import confine_to_crm, is_blocked_path, is_crm_only_user

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

	def request(self, path, user):
		frappe.set_user(user)
		frappe.local.request = Request(EnvironBuilder(path=path, method="GET").get_environ())

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
		):
			self.assertTrue(is_blocked_path(path), path)

	def test_crm_api_and_asset_paths_are_not_blocked(self):
		for path in (
			"/",
			"/crm",
			"/crm/leads",
			"/api/method/ping",
			"/assets/crm/frontend/index.js",
			"/login",
			"/application",
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
