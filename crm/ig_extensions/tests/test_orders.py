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
		frappe.db.set_single_value("FCRM Settings", "enable_sales_hierarchy", 0)
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

	def test_list_is_served_in_pages_newest_first(self):
		older = self.make_order(SALES_USER)
		newer = self.make_order(SALES_USER)
		first_page = settings_api.get_my_sales_orders(limit=1)
		second_page = settings_api.get_my_sales_orders(limit=1, start=1)
		self.assertEqual([row["name"] for row in first_page], [newer])
		self.assertEqual([row["name"] for row in second_page], [older])

	def test_draft_detail_allows_edit_delete_and_mark_ready(self):
		detail = settings_api.get_sales_order_detail(self.make_order(SALES_USER))
		self.assertEqual(
			(detail["can_edit"], detail["can_delete"], detail["can_mark_ready"]), (True, True, True)
		)

	def test_ready_detail_allows_no_changes(self):
		name = self.make_order(SALES_USER)
		settings_api.mark_sales_order_ready(name)
		detail = settings_api.get_sales_order_detail(name)
		self.assertEqual(
			(detail["can_edit"], detail["can_delete"], detail["can_mark_ready"]), (False, False, False)
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

	def test_other_creator_cannot_open_or_change_order(self):
		name = self.make_order(OTHER_SALES_USER)
		frappe.set_user(SALES_USER)
		for action in (
			settings_api.get_sales_order_detail,
			settings_api.delete_sales_order,
			settings_api.mark_sales_order_ready,
		):
			with self.subTest(action=action.__name__), self.assertRaises(frappe.PermissionError):
				action(name)
		with self.assertRaises(frappe.PermissionError):
			settings_api.update_sales_order_items(name, [{"item_code": self.item_code, "qty": 3}])

	def test_generic_list_value_and_link_search_hide_foreign_orders(self):
		from frappe.client import get_list, get_value
		from frappe.desk.search import search_link

		mine = self.make_order(SALES_USER)
		theirs = self.make_order(OTHER_SALES_USER)
		frappe.set_user(SALES_USER)
		names = [row.name for row in get_list("Sales Order", fields=["name"], filters={"name": ["in", [mine, theirs]]})]
		self.assertEqual(names, [mine])
		self.assertFalse(get_value("Sales Order", "grand_total", theirs))
		self.assertFalse(search_link("Sales Order", txt=theirs))

	def test_generic_document_read_and_forged_owner_cannot_bypass_ownership(self):
		from frappe.client import get, save

		name = self.make_order(OTHER_SALES_USER)
		frappe.set_user("Administrator")
		payload = frappe.get_doc("Sales Order", name).as_dict()
		payload.owner = SALES_USER
		frappe.set_user(SALES_USER)
		with self.assertRaises(frappe.PermissionError):
			get("Sales Order", name)
		with self.assertRaises(frappe.PermissionError):
			save(payload)

	def test_assignment_or_share_does_not_change_the_creator(self):
		from frappe.client import get

		name = self.make_order(OTHER_SALES_USER)
		frappe.set_user("Administrator")
		frappe.share.add("Sales Order", name, SALES_USER, read=1, write=1, notify=0)
		frappe.set_user(SALES_USER)
		with self.assertRaises(frappe.PermissionError):
			get("Sales Order", name)

	def test_manager_and_admin_keep_cross_creator_access(self):
		name = self.make_order(SALES_USER)
		for user in (SALES_MANAGER, "crm.admin@example.com", "Administrator"):
			frappe.set_user(user)
			self.assertEqual(settings_api.get_sales_order_detail(name)["name"], name)

	def test_creator_cannot_be_reassigned_by_a_sales_user(self):
		name = self.make_order(SALES_USER)
		doc = frappe.get_doc("Sales Order", name)
		doc.owner = OTHER_SALES_USER
		with self.assertRaises((frappe.PermissionError, frappe.CannotChangeConstantError)):
			doc.save()
		self.assertEqual(frappe.db.get_value("Sales Order", name, "owner"), SALES_USER)

	def test_customer_organization_and_contact_are_isolated_in_lists_search_and_documents(self):
		from frappe.client import get, get_list
		from frappe.desk.search import search_link

		name = self.make_order(SALES_USER)
		customer, organization = frappe.db.get_value("Sales Order", name, ["customer", "customer_name"])
		frappe.set_user("Administrator")
		contact = frappe.get_doc({"doctype": "Contact", "first_name": "Portfolio", "company_name": organization}).insert()
		address = frappe.get_doc({"doctype": "Address", "address_title": "Portfolio", "address_line1": "Test street", "city": "Test city", "country": "United States", "links": [{"link_doctype": "Customer", "link_name": customer}]}).insert()
		for doctype, docname in (("CRM Organization", organization), ("Customer", customer), ("Contact", contact.name), ("Address", address.name)):
			frappe.set_user(OTHER_SALES_USER)
			with self.subTest(doctype=doctype):
				self.assertFalse(get_list(doctype, filters={"name": docname}))
				self.assertFalse(search_link(doctype, txt=docname))
				with self.assertRaises(frappe.PermissionError):
					get(doctype, docname)
			frappe.set_user(SALES_USER)
			self.assertEqual(get(doctype, docname)["name"], docname)
			frappe.set_user(SALES_MANAGER)
			self.assertEqual(get(doctype, docname)["name"], docname)

	def test_order_cannot_be_created_for_another_sellers_customer(self):
		name = self.make_order(OTHER_SALES_USER)
		organization = frappe.db.get_value("Sales Order", name, "customer_name")
		frappe.set_user(SALES_USER)
		with self.assertRaises(frappe.PermissionError):
			settings_api.create_organization_sales_order(organization, [{"item_code": self.item_code, "qty": 1}])

	def test_contact_cannot_be_moved_to_another_sellers_organization(self):
		mine = self.make_order(SALES_USER)
		theirs = self.make_order(OTHER_SALES_USER)
		my_org = frappe.db.get_value("Sales Order", mine, "customer_name")
		their_org = frappe.db.get_value("Sales Order", theirs, "customer_name")
		frappe.set_user(SALES_USER)
		contact = frappe.get_doc({"doctype": "Contact", "first_name": "Own contact", "company_name": my_org}).insert()
		contact.company_name = their_org
		with self.assertRaises(frappe.PermissionError):
			contact.save()

	def test_combined_order_filters_counts_and_pagination(self):
		from crm.ig_extensions.api.sales_orders import get_page, get_filter_options
		from frappe.utils import today, add_days
		mine = self.make_order(SALES_USER)
		customer = frappe.db.get_value("Sales Order", mine, "customer")
		self.make_order(OTHER_SALES_USER)
		frappe.set_user(SALES_USER)
		page = get_page(from_date=today(), to_date=today(), order_id=mine, customer=customer, item_code=self.item_code, status="draft", limit=1)
		self.assertEqual([row.name for row in page["rows"]], [mine])
		self.assertEqual(page["total"], 1)
		self.assertEqual(page["states"], {"0": 1})
		self.assertEqual(get_page(order_id=mine, start=1)["rows"], [])
		self.assertEqual(get_page(from_date=add_days(today(), 1))["total"], 0)
		self.assertEqual(get_page(status="ready")["total"], 0)
		self.assertEqual(get_filter_options("customer"), [{"value": customer, "label": frappe.db.get_value("Customer", customer, "customer_name")}])
		self.assertIn(self.item_code, [row["value"] for row in get_filter_options("item_code")])
		with self.assertRaises(frappe.ValidationError):
			get_page(from_date=today(), to_date=add_days(today(), -1))

	def test_repeated_products_do_not_duplicate_orders_or_counts(self):
		from crm.ig_extensions.api.sales_orders import get_page
		frappe.db.set_single_value("Selling Settings", "allow_multiple_items", 1)
		name = self.make_order(SALES_USER)
		doc = frappe.get_doc("Sales Order", name)
		doc.append("items", {"item_code": self.item_code, "qty": 1, "rate": 50, "delivery_date": doc.delivery_date})
		doc.save()
		page = get_page(item_code=self.item_code, order_id=name)
		self.assertEqual(page["total"], 1)
		self.assertEqual([row.name for row in page["rows"]], [name])

	def test_product_catalog_and_supervision_use_real_records(self):
		from crm.ig_extensions.api.workspace import get_products, get_product, get_overview
		frappe.set_user(SALES_USER)
		before = get_overview()["orders"]
		name = self.make_order(SALES_USER)
		self.assertTrue(get_products(txt=self.item_code)["rows"])
		self.assertEqual(get_product(self.item_code)["item_code"], self.item_code)
		overview = get_overview()
		self.assertEqual(overview["orders"], before + 1)
		self.assertIn(self.item_code, [row.item_code for row in overview["products"]])
		with self.assertRaises(frappe.PermissionError):
			get_overview(user=OTHER_SALES_USER)

	def test_call_logs_are_isolated_by_agent_not_webhook_creator(self):
		from crm.ig_extensions.api.workspace import get_overview
		from frappe.client import get, get_list
		from frappe.utils import now_datetime
		frappe.set_user("Administrator")
		call = frappe.get_doc({"doctype": "CRM Call Log", "id": "isolation-" + frappe.generate_hash(length=12), "from": "+10000000000", "to": "+10000000001", "status": "Completed", "type": "Outgoing", "caller": OTHER_SALES_USER, "start_time": now_datetime(), "duration": 10}).insert()
		frappe.set_user(SALES_USER)
		self.assertFalse(get_list("CRM Call Log", filters={"name": call.name}))
		with self.assertRaises(frappe.PermissionError):
			get("CRM Call Log", call.name)
		frappe.set_user(SALES_MANAGER)
		self.assertEqual(get("CRM Call Log", call.name)["caller"], OTHER_SALES_USER)
		self.assertGreaterEqual(get_overview(user=OTHER_SALES_USER)["calls"], 1)

	def test_self_assignment_cannot_pull_a_hidden_customer_into_scope(self):
		name = self.make_order(OTHER_SALES_USER)
		organization = frappe.db.get_value("Sales Order", name, "customer_name")
		deal = frappe.db.get_value("CRM Deal", {"organization": organization}, "name")
		frappe.set_user(SALES_USER)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype": "ToDo", "allocated_to": SALES_USER, "reference_type": "CRM Deal", "reference_name": deal, "description": "Forbidden self assignment"}).insert()

	def test_renaming_organization_cannot_take_over_another_customer(self):
		mine = self.make_order(SALES_USER)
		theirs = self.make_order(OTHER_SALES_USER)
		my_org = frappe.db.get_value("Sales Order", mine, "customer_name")
		their_customer = frappe.db.get_value("Sales Order", theirs, "customer_name")
		frappe.set_user(SALES_USER)
		with self.assertRaises(frappe.PermissionError):
			frappe.rename_doc("CRM Organization", my_org, their_customer + " renamed")

	def test_manager_in_hierarchy_sees_only_own_subtree(self):
		from crm.ig_extensions.permissions.sales_scope import visible_users
		from crm.ig_extensions.api.sales_orders import get_page
		first = self.make_order(SALES_USER)
		second = self.make_order(OTHER_SALES_USER)
		frappe.set_user("Administrator")
		frappe.db.set_single_value("FCRM Settings", "enable_sales_hierarchy", 1)
		# Keep the fixture independent of any persisted hierarchy from earlier runs.
		for user in (SALES_MANAGER, SALES_USER, OTHER_SALES_USER):
			for row in frappe.get_all("CRM Sales Hierarchy", filters={"user": user}, pluck="name"):
				frappe.delete_doc("CRM Sales Hierarchy", row, ignore_permissions=True, force=True)
		manager = frappe.get_doc({"doctype": "CRM Sales Hierarchy", "user": SALES_MANAGER, "is_group": 1}).insert()
		frappe.get_doc({"doctype": "CRM Sales Hierarchy", "user": SALES_USER, "reports_to": manager.name}).insert()
		frappe.get_doc({"doctype": "CRM Sales Hierarchy", "user": OTHER_SALES_USER}).insert()
		frappe.set_user(SALES_MANAGER)
		self.assertEqual(set(visible_users()), {SALES_MANAGER, SALES_USER})
		page = get_page()
		names = [row.name for row in page["rows"]]
		self.assertIn(first, names)
		self.assertNotIn(second, names)
		with self.assertRaises(frappe.PermissionError):
			settings_api.get_sales_order_detail(second)

	def test_own_app_rejects_stale_edits_and_submit_is_idempotent(self):
		from crm.ig_extensions.api import orders
		name = self.make_order(SALES_USER)
		original = orders.get_sales_order_detail(name)
		items = [{"item_code": self.item_code, "qty": 3, "rate": 100}]
		orders.update_sales_order_items(name, items, modified=str(original["modified"]))
		with self.assertRaises(frappe.TimestampMismatchError):
			orders.update_sales_order_items(name, items, modified=str(original["modified"]))
		first = orders.mark_sales_order_ready(name)
		second = orders.mark_sales_order_ready(name)
		self.assertEqual(first, second)
		self.assertEqual(frappe.db.get_value("Sales Order", name, "docstatus"), 1)

	def test_note_call_associations_do_not_reveal_foreign_calls(self):
		from crm.ig_extensions.api.notes import get_note_calls, get_notes
		from frappe.client import get
		calls, notes = [], []
		for user in (SALES_USER, OTHER_SALES_USER):
			frappe.set_user(user)
			call = frappe.get_doc({"doctype": "CRM Call Log", "id": "ig-note-" + frappe.generate_hash(length=12), "type": "Outgoing", "status": "Completed", "caller": user, "from": "+15550001001", "to": "+15550001002"}).insert()
			note = frappe.get_doc({"doctype": "FCRM Note", "title": "Call test", "content": "Authorized test note", "reference_doctype": "CRM Call Log", "reference_docname": call.name}).insert()
			calls.append(call.name)
			notes.append(note.name)
		frappe.set_user(SALES_USER)
		linked = get_note_calls(notes)
		self.assertEqual([row.name for row in linked[notes[0]]], [calls[0]])
		self.assertNotIn(notes[1], linked)
		self.assertNotIn(notes[1], [row.name for row in get_notes()["rows"]])
		with self.assertRaises(frappe.PermissionError):
			get("FCRM Note", notes[1])

	def test_private_price_cannot_be_read_or_shared_into_seller_scope(self):
		from crm.ig_extensions.permissions.price import can_access
		from crm.ig_extensions.utils.crm_only import _restrict_customer_shares
		from frappe.client import get
		name = self.make_order(OTHER_SALES_USER)
		frappe.set_user("Administrator")
		price = frappe.get_doc({"doctype": "Item Price", "item_code": self.item_code, "price_list": "Standard Selling", "price_list_rate": 177,
			"customer": frappe.db.get_value("Sales Order", name, "customer")}).insert()
		frappe.share.add("Item Price", price.name, SALES_USER, read=1, flags={"ignore_share_permission": True})
		frappe.set_user(SALES_USER)
		self.assertFalse(can_access(price.name))
		with self.assertRaises(frappe.PermissionError):
			get("Item Price", price.name)
		params = frappe._dict(filters=[])
		_restrict_customer_shares(params, "Item Price")
		self.assertIn(["Item Price", "name", "not in", [price.name]], params.filters)

	def test_personal_profile_update_preserves_roles_and_prevents_escalation(self):
		frappe.set_user(SALES_USER)
		doc = frappe.get_doc("User", SALES_USER)
		roles = sorted(row.role for row in doc.roles)
		doc.first_name = "Personal profile test"
		doc.save()
		self.assertEqual(sorted(row.role for row in doc.roles), roles)
		doc.append("roles", {"role": "System Manager"})
		with self.assertRaises(frappe.PermissionError):
			doc.save()

	def test_catalog_stock_reports_real_zero_separately_from_unknown(self):
		from crm.ig_extensions.api.workspace import get_stock
		frappe.set_user("Administrator")
		warehouse = frappe.db.get_value("Warehouse", {"is_group": 0, "company": "_Test Company", "disabled": 0}, "name")
		bin_doc = frappe.get_doc({"doctype": "Bin", "item_code": self.item_code, "warehouse": warehouse}) if not frappe.db.exists("Bin", {"item_code": self.item_code, "warehouse": warehouse}) else frappe.get_doc("Bin", {"item_code": self.item_code, "warehouse": warehouse})
		bin_doc.actual_qty = 0
		bin_doc.save()
		frappe.set_user(SALES_USER)
		stock = get_stock([self.item_code])[self.item_code]
		self.assertEqual(stock["status"], "known")
		self.assertTrue(any(row["warehouse"] == warehouse and row["actual_qty"] == 0 for row in stock["warehouses"]))

	def test_integrated_creation_uses_native_order_and_creator(self):
		from crm.ig_extensions.api.orders import create_organization_sales_order, get_sales_order_detail
		frappe.set_user(SALES_USER)
		organization = frappe.get_doc({"doctype": "CRM Organization", "organization_name": "Integrated " + frappe.generate_hash(length=10)}).insert()
		created = create_organization_sales_order(organization.name, [{"item_code": self.item_code, "qty": 2, "rate": 31}])
		detail = get_sales_order_detail(created["name"])
		self.assertEqual(detail["owner"], SALES_USER)
		self.assertEqual(detail["total"], 62)
		self.assertTrue(detail["can_edit"])

	def test_nested_contact_cannot_grant_access_to_foreign_contact(self):
		self.make_order(SALES_USER)
		frappe.set_user(OTHER_SALES_USER)
		contact = frappe.get_doc({"doctype": "Contact", "first_name": "Foreign integration test"}).insert()
		frappe.set_user(SALES_USER)
		deal = frappe.get_doc({"doctype": "CRM Deal", "organization": frappe.get_all("CRM Organization", filters={"owner": SALES_USER}, pluck="name", limit=1)[0], "deal_owner": SALES_USER, "status": "Qualification"})
		deal.append("contacts", {"contact": contact.name})
		with self.assertRaises(frappe.PermissionError):
			deal.insert()
