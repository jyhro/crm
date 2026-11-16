"""Customer ownership follows the existing CRM organization, without inferring a Profit mapping."""

import frappe
from frappe import _

from crm.ig_extensions.permissions.sales_order import is_order_manager
from crm.ig_extensions.permissions.sales_scope import user_condition

CUSTOMER_DOCTYPES = {"CRM Organization", "Customer", "Contact", "Address"}


def scope_required(user):
	# Other back-office roles retain their native permissions internally; the HTTP
	# boundary separately denies application/API access to accounts without a CRM role.
	return bool({"Sales User", "Sales Manager"} & set(frappe.get_roles(user))) and not is_order_manager(user)


def _responsible(alias, owner_field, doctype, user):
	u = frappe.db.escape(user)
	return (
		f"({user_condition(f'{alias}.{owner_field}', user)} OR EXISTS (SELECT 1 FROM `tabToDo` assigned"
		f" WHERE assigned.reference_type = '{doctype}' AND assigned.reference_name = {alias}.name"
		f" AND {user_condition('assigned.allocated_to', user)} AND assigned.status != 'Cancelled'))"
	)


def _organization(alias, user):
	u = frappe.db.escape(user)
	deal = _responsible("owned_deal", "deal_owner", "CRM Deal", user)
	lead = _responsible("owned_lead", "lead_owner", "CRM Lead", user)
	return (
		f"({user_condition(f'{alias}.owner', user)} OR EXISTS (SELECT 1 FROM `tabCRM Deal` owned_deal"
		f" WHERE owned_deal.organization = {alias}.name AND {deal})"
		f" OR EXISTS (SELECT 1 FROM `tabCRM Lead` owned_lead WHERE owned_lead.organization = {alias}.name AND {lead}))"
	)


def _customer(alias, user):
	u = frappe.db.escape(user)
	return (
		f"(EXISTS (SELECT 1 FROM `tabCRM Organization` org WHERE org.name = {alias}.customer_name AND {_organization('org', user)})"
		f" OR (NOT EXISTS (SELECT 1 FROM `tabCRM Organization` org WHERE org.name = {alias}.customer_name) AND {user_condition(f'{alias}.owner', user)})"
		f" OR EXISTS (SELECT 1 FROM `tabCRM Deal` owned_deal WHERE owned_deal.name = {alias}.crm_deal"
		f" AND {_responsible('owned_deal', 'deal_owner', 'CRM Deal', user)}))"
	)


def scope_condition(doctype, user):
	u = frappe.db.escape(user)
	if doctype == "CRM Organization":
		return _organization("`tabCRM Organization`", user)
	if doctype == "Customer":
		return _customer("`tabCustomer`", user)
	if doctype == "Contact":
		return (
			f"(EXISTS (SELECT 1 FROM `tabCRM Organization` org WHERE org.name = `tabContact`.company_name AND {_organization('org', user)})"
			f" OR (NOT EXISTS (SELECT 1 FROM `tabCRM Organization` org WHERE org.name = `tabContact`.company_name) AND {user_condition('`tabContact`.owner', user)})"
			" OR EXISTS (SELECT 1 FROM `tabCRM Contacts` linked_contact JOIN `tabCRM Deal` owned_deal"
			" ON owned_deal.name = linked_contact.parent WHERE linked_contact.contact = `tabContact`.name"
			f" AND linked_contact.parenttype = 'CRM Deal' AND {_responsible('owned_deal', 'deal_owner', 'CRM Deal', user)}))"
		)
	links = "dl.parent = `tabAddress`.name AND dl.parenttype = 'Address' AND dl.link_doctype IN ('Customer', 'CRM Organization')"
	own_link = (
		"((dl.link_doctype = 'CRM Organization' AND EXISTS (SELECT 1 FROM `tabCRM Organization` org"
		f" WHERE org.name = dl.link_name AND {_organization('org', user)}))"
		" OR (dl.link_doctype = 'Customer' AND EXISTS (SELECT 1 FROM `tabCustomer` customer"
		f" WHERE customer.name = dl.link_name AND {_customer('customer', user)})))"
	)
	return (
		f"(({user_condition('`tabAddress`.owner', user)} AND NOT EXISTS (SELECT 1 FROM `tabDynamic Link` dl WHERE {links}))"
		f" OR (EXISTS (SELECT 1 FROM `tabDynamic Link` dl WHERE {links})"
		f" AND NOT EXISTS (SELECT 1 FROM `tabDynamic Link` dl WHERE {links} AND NOT {own_link})))"
	)


def query_condition(doctype, user=None):
	user = user or frappe.session.user
	return scope_condition(doctype, user) if scope_required(user) else ""


def organization_query(user=None):
	return query_condition("CRM Organization", user)


def customer_query(user=None):
	return query_condition("Customer", user)


def contact_query(user=None):
	return query_condition("Contact", user)


def address_query(user=None):
	return query_condition("Address", user)


def can_access(doctype, name, user=None):
	user = user or frappe.session.user
	if not scope_required(user):
		return True
	return bool(frappe.db.sql(
		f"SELECT name FROM `tab{doctype}` WHERE name = %s AND ({scope_condition(doctype, user)}) LIMIT 1",
		(name,),
	))


def has_permission(doc, ptype, user=None, **kwargs):
	if ptype == "create" or doc.is_new():
		return True
	if not can_access(doc.doctype, doc.name, user):
		frappe.throw(_("You can only access customers in your own portfolio."), frappe.PermissionError)
	return True


def validate_customer_links(doc, method=None):
	if not scope_required(frappe.session.user):
		return
	if doc.doctype == "ToDo" and doc.reference_type in {"CRM Lead", "CRM Deal", *CUSTOMER_DOCTYPES, "Sales Order"} and doc.reference_name:
		# A self-created assignment must not grant access to a previously hidden client.
		frappe.has_permission(doc.reference_type, "read", doc=doc.reference_name, throw=True)
	if doc.doctype == "CRM Organization" and doc.is_new():
		# Creating an organization named after a different seller's existing ERP
		# customer must not make that customer appear to belong to the new creator.
		for customer in frappe.get_all("Customer", filters={"customer_name": doc.organization_name}, pluck="name"):
			frappe.has_permission("Customer", "read", doc=customer, throw=True)
	# Existing assigned CRM leads/deals retain their native rules. A new link cannot
	# be used to pull a different seller's organization, contact or customer into scope.
	protected = {*CUSTOMER_DOCTYPES, "CRM Lead", "CRM Deal", "Sales Order", "CRM Call Log", "FCRM Note"}
	for record in [doc, *doc.get_all_children()]:
		for field in record.meta.get_link_fields():
			if field.options in protected and (name := record.get(field.fieldname)):
				frappe.has_permission(field.options, "read", doc=name, throw=True)
		for field in record.meta.get_dynamic_link_fields():
			if record.get(field.options) in protected and record.get(field.fieldname):
				frappe.has_permission(record.get(field.options), "read", doc=record.get(field.fieldname), throw=True)

	if doc.doctype == "Contact" and doc.company_name and frappe.db.exists("CRM Organization", doc.company_name):
		frappe.has_permission("CRM Organization", "read", doc=doc.company_name, throw=True)
	for row in doc.get("links") or []:
		if row.get("link_doctype") in CUSTOMER_DOCTYPES and row.get("link_name"):
			frappe.has_permission(row.link_doctype, "read", doc=row.link_name, throw=True)


def before_rename(doc, method=None, *args, **kwargs):
	if scope_required(frappe.session.user):
		frappe.throw(_("Only an administrator can rename customer organizations."), frappe.PermissionError)
