# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from crm.fcrm.doctype.erpnext_crm_settings import erpnext_crm_settings as settings_api


class TestERPNextCRMSettings(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if "erpnext" not in frappe.get_installed_apps():
			return

		from frappe.tests.utils.generators import make_test_records

		make_test_records("Quotation")
		from crm.tests import load_crm_user_test_records
		from crm.tests.test_search_sqlite import SALES_USER

		load_crm_user_test_records()
		cls.sales_user = SALES_USER
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

		from crm.tests.test_search_sqlite import make_deal, make_lead

		self.lead = make_lead(self.sales_user)
		self.deal = make_deal(self.sales_user, self.lead)
		frappe.db.set_value("Customer", "_Test Customer", "crm_deal", self.deal)
		frappe.set_user(self.sales_user)
		self.addCleanup(frappe.set_user, "Administrator")

	def test_create_and_update_draft_quotation(self):
		quotation = settings_api.create_quotation(
			self.deal,
			[{"item_code": self.item_code, "qty": 2, "rate": 100}],
		)
		self.assertEqual(frappe.db.get_value("Quotation", quotation["name"], "docstatus"), 0)
		self.assertEqual(frappe.db.get_value("Quotation", quotation["name"], "crm_deal"), self.deal)

		settings_api.update_quotation_items(
			quotation["name"], [{"item_code": self.item_code, "qty": 5, "rate": 100}]
		)
		rows = frappe.get_all(
			"Quotation Item", filters={"parent": quotation["name"]}, fields=["qty", "rate"]
		)
		self.assertEqual(rows, [{"qty": 5.0, "rate": 100.0}])
		listed = settings_api.get_deal_quotations(self.deal)
		self.assertEqual(listed[0]["docstatus"], 0)

	def test_empty_items_are_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			settings_api.create_quotation(self.deal, [])

	def test_zero_quantity_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			settings_api.create_quotation(
				self.deal,
				[{"item_code": self.item_code, "qty": 0, "rate": 100}],
			)

	def test_create_requires_quotation_permission(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			settings_api.create_quotation(
				self.deal,
				[{"item_code": self.item_code, "qty": 1, "rate": 100}],
			)

	def test_remote_erpnext_quotation_is_rejected(self):
		frappe.db.set_single_value("ERPNext CRM Settings", "is_erpnext_in_different_site", 1)
		with self.assertRaises(frappe.ValidationError):
			settings_api.create_quotation(
				self.deal,
				[{"item_code": self.item_code, "qty": 1, "rate": 100}],
			)

	def test_submitted_quotation_cannot_be_edited(self):
		quotation = settings_api.create_quotation(
			self.deal,
			[{"item_code": self.item_code, "qty": 2, "rate": 100}],
		)
		frappe.get_doc("Quotation", quotation["name"]).submit()
		with self.assertRaises(frappe.ValidationError):
			settings_api.update_quotation_items(
				quotation["name"], [{"item_code": self.item_code, "qty": 5, "rate": 100}]
			)
		self.assertEqual(
			frappe.db.get_value("Quotation Item", {"parent": quotation["name"]}, "qty"), 2
		)

	def test_missing_rate_uses_standard_selling_price(self):
		from erpnext.stock.doctype.item.test_item import make_item

		item = make_item("CRM Inline Quotation Priced Item", {"is_stock_item": 0})
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": item.name,
				"price_list": "Standard Selling",
				"price_list_rate": 321,
			}
		).insert(ignore_permissions=True)
		quotation = settings_api.create_quotation(
			self.deal, [{"item_code": item.name, "qty": 1}]
		)
		self.assertEqual(
			frappe.db.get_value("Quotation Item", {"parent": quotation["name"]}, "rate"), 321
		)

	def test_missing_standard_price_defaults_to_zero(self):
		from erpnext.stock.doctype.item.test_item import make_item

		item = make_item("CRM Inline Quotation Unpriced Item", {"is_stock_item": 0})
		quotation = settings_api.create_quotation(self.deal, [{"item_code": item.name, "qty": 1}])
		self.assertEqual(
			frappe.db.get_value("Quotation Item", {"parent": quotation["name"]}, "rate"), 0
		)

	def test_deal_without_customer_creates_prospect_quotation(self):
		frappe.db.set_value("Customer", "_Test Customer", "crm_deal", None)
		quotation = settings_api.create_quotation(
			self.deal, [{"item_code": self.item_code, "qty": 1, "rate": 50}]
		)
		doc = frappe.get_doc("Quotation", quotation["name"])
		self.assertEqual(doc.quotation_to, "CRM Deal")
		self.assertEqual(doc.party_name, self.deal)
