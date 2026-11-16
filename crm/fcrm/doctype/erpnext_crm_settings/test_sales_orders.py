# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from crm.fcrm.doctype.erpnext_crm_settings import erpnext_crm_settings as settings_api

SALES_USER = "crm.user1@example.com"
OTHER_SALES_USER = "crm.user2@example.com"
SALES_MANAGER = "crm.manager@example.com"


class TestSalesOrders(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if "erpnext" not in frappe.get_installed_apps():
			return

		from frappe.tests.utils.generators import make_test_records

		from crm.tests import load_crm_user_test_records

		make_test_records("Sales Order")
		load_crm_user_test_records()
		cls.item_code = "_Test Item Home Desktop 100"

	def setUp(self):
		super().setUp()
		if "erpnext" not in frappe.get_installed_apps():
			self.skipTest("ERPNext is not installed")

		frappe.set_user("Administrator")
		settings = frappe.get_single("ERPNext CRM Settings")
		settings.enabled = 1
		settings.is_erpnext_in_different_site = 0
		settings.erpnext_company = "_Test Company"
		settings.save(ignore_permissions=True)
		self.addCleanup(frappe.set_user, "Administrator")

	def make_order(self, user, qty=2, rate=100):
		"""Create a draft order as `user`, for an organization of their own."""
		frappe.set_user(user)
		organization = (
			frappe.get_doc(
				{"doctype": "CRM Organization", "organization_name": "Pedidos " + frappe.generate_hash(length=6)}
			)
			.insert()
			.name
		)
		return settings_api.create_organization_sales_order(
			organization, [{"item_code": self.item_code, "qty": qty, "rate": rate}]
		)["name"]

	def test_sales_user_lists_only_own_orders(self):
		mine = self.make_order(SALES_USER)
		theirs = self.make_order(OTHER_SALES_USER)
		frappe.set_user(SALES_USER)
		names = [row["name"] for row in settings_api.get_my_sales_orders()]
		self.assertIn(mine, names)
		self.assertNotIn(theirs, names)

	def test_sales_manager_lists_orders_of_every_user(self):
		first = self.make_order(SALES_USER)
		second = self.make_order(OTHER_SALES_USER)
		frappe.set_user(SALES_MANAGER)
		names = [row["name"] for row in settings_api.get_my_sales_orders()]
		self.assertIn(first, names)
		self.assertIn(second, names)

	def test_detail_returns_customer_items_and_total(self):
		name = self.make_order(SALES_USER, qty=3, rate=50)
		detail = settings_api.get_sales_order_detail(name)
		self.assertEqual(detail["name"], name)
		self.assertEqual(detail["docstatus"], 0)
		self.assertEqual(detail["total"], 150)
		self.assertEqual(
			[(row["item_code"], row["qty"], row["rate"], row["amount"]) for row in detail["items"]],
			[(self.item_code, 3, 50, 150)],
		)

	def test_delete_removes_a_draft_order(self):
		name = self.make_order(SALES_USER)
		settings_api.delete_sales_order(name)
		self.assertFalse(frappe.db.exists("Sales Order", name))

	def test_mark_ready_submits_the_draft(self):
		name = self.make_order(SALES_USER)
		result = settings_api.mark_sales_order_ready(name)
		self.assertEqual(result["docstatus"], 1)
		self.assertEqual(frappe.db.get_value("Sales Order", name, "docstatus"), 1)

	def test_ready_order_cannot_be_deleted(self):
		name = self.make_order(SALES_USER)
		settings_api.mark_sales_order_ready(name)
		with self.assertRaises(frappe.ValidationError):
			settings_api.delete_sales_order(name)
		self.assertTrue(frappe.db.exists("Sales Order", name))

	def test_ready_order_cannot_be_marked_ready_again(self):
		name = self.make_order(SALES_USER)
		settings_api.mark_sales_order_ready(name)
		with self.assertRaises(frappe.ValidationError):
			settings_api.mark_sales_order_ready(name)

	def test_guest_cannot_delete_an_order(self):
		name = self.make_order(SALES_USER)
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			settings_api.delete_sales_order(name)

	def test_guest_cannot_mark_an_order_ready(self):
		name = self.make_order(SALES_USER)
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			settings_api.mark_sales_order_ready(name)
