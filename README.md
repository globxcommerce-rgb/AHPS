# aHPS – Odoo 20 custom modules

Custom modules for Advanced Helios Process Solutions Ltd (aHPS), implemented by Globx.

| Module | What it does |
|---|---|
| `ahps_kyc` | KYC for customers **and** suppliers: separate, locked online forms for customers and suppliers (the form follows *Registers As* on the contact), KYC tab and documents, workflow (Send KYC Link → Submitted → Approve / Reject), customer ID `CYYYY.NNN` / supplier ID `SYYYY.NNN`, customer categories as contact tags, duplicate-company warning, blocks sending/confirming quotations and posting invoices until the KYC is approved |
| `ahps_reports` | aHPS document layouts: Quotation (instruments / spare parts / service), Pro Forma Invoice, Customer Invoice / Credit Note, Request for Quotation, Purchase Order. Partner logos as uploadable records, quotation currency switch (EUR base price list → USD / KES) |

`ahps_reports` depends on `ahps_kyc` (the customer ID is printed on quotations and PFIs).

## Install on staging

Install **aHPS Document Templates** from Apps; it pulls in **aHPS KYC (Customers & Suppliers)**.
Upgrading from 1.0: the upgrade migrates the KYC document types and reloads the KYC request email.

## Configuration after install

1. **Settings › Companies › aHPS Documents**: certificate of registration (e.g. `PVT-XYUE2P9`), signatory (`J. Mbugua`), handling charges text, sales / finance / operations contacts, PO special note, the PO invoice-address contact (Emmanuel Rurema), and which bank accounts to print.
2. **Company**: logo, address (`PO Box 1325 – 00621 Village Market`, Nairobi, Kenya), phone, email, and the KRA PIN in the *Tax ID* field.
3. **Bank accounts** of the company (Contacts › the company › Bank Accounts): set the bank name, the SWIFT code (BARCKENX) and the new **Account Currency** (KES / EUR / USD) on each account.
4. **Sales › Settings › KYC (aHPS)**: *Require approved KYC* switches the blocking on or off. *Public registration page* opens `/kyc/register/customer` and `/kyc/register/supplier`, where a new customer or supplier can register without being invited (both links can be copied from the setting).
5. **Customer number**: nothing to set. On approval the number continues after the highest number already used (customers `C2026.238`, suppliers `S2026.066`). Version 20.0.1.2.0 adds the C/S prefix to the imported IDs.
6. **Users**: Settings › Users › *KYC* = *KYC Officer* (Joyce) or *KYC Manager* (Emmanuel / Janet). Managers approve and reject KYCs and can edit customer IDs.
7. **Base price list (currency switch)**: Settings › Companies › aHPS Documents › *Base Price List* = the EUR price list. Keep the USD and KES exchange rates up to date (Accounting › Configuration › Currencies). On a quotation, changing *Quote Currency* converts all prices at the rate of the quotation date and switches to a price list in that currency (created automatically, based on the EUR list). The rate used is the day's rate × (1 + *FX Risk Factor*), default set on the company (aHPS Documents tab), changeable per quotation; a typed *Exchange Rate* still overrides it.
8. **Document design**: Settings › Companies › aHPS Documents › *Use aHPS Document Design*. Untick to print Odoo's standard layout (Settings › Document Layout) instead.
9. **Incoterm**: any Incoterm except EXW adds a *Shipping Charges* line (price to fill in) to the quotation; EXW removes it. *Delivery Terms* on the PDF come from the Incoterm and its location.
10. **Manual POs**: set *Sales Order* on a purchase order to link it; the sales order shows a *Supplier POs* button.
8. **Document logos**: Sales › Configuration › Document Logos. *Partner logo* entries are printed in the footer (in sequence order); the *Accreditation badge* is printed on invoices. Archive a logo to hide it.
9. **Products**: *HS Code*, *Country of Origin* and *Document Charge Type* (Shipping / Other) on the product form. Freight products should be set to *Shipping*, so they are totalled as Shipping / Total CPT on PFIs.

## KYC process

1. Create the company contact, then **Send KYC Link** (or copy the *Online KYC Form* link from the KYC tab and send it yourself). Set *Registers As* first: the link opens a customer-only or supplier-only form that the company cannot switch.
2. The company opens the link and picks **Customer** or **Supplier**:
   - both: company details, TIN, registration number, addresses (physical, postal, invoice, delivery), contact person, documents (certificate of incorporation, TIN certificate) and the declaration;
   - customers: type of company (End User + sector, or Reseller), procurement and finance contacts;
   - suppliers: authorized person, bank details (bank, account, currency, SWIFT, IBAN) and the extra documents (tax compliance, business license, bank letter).
3. On submit, the answers fill the contact: KYC fields, customer category tags, child contacts (linked to their roles), invoice / delivery addresses, bank account and KYC documents. The KYC becomes *Submitted* and KYC Managers get a *Review KYC* activity.
4. A KYC Manager approves (customer → customer ID; supplier → vendor) or rejects with a reason. On approval the company is emailed its customer or supplier ID. On rejection the company is emailed the reason and the form link (can be unticked in the reject popup); the form opens pre-filled with the reason on top, so they correct and resubmit.
5. Document types and which registration type needs them: Contacts › Configuration › KYC Document Types (*Applies To*, *Required*, *On Online Form*).

### Customer categories

Contact tags: **End User** (with Breweries, Soft Drinks, Water, Institutes, Wine & Spirits, Dairy, Others) and **Reseller**. Add sectors as child tags of End User; they appear on the online form automatically.

### Document numbers (configuration, no code needed)

- Quotations / orders (`Q2026.153`): Sequences › *Sales Order* → prefix `Q%(year)s.`, padding 3.
- Purchase orders (`2026-053`): Sequences › *Purchase Order* → prefix `%(year)s-`, padding 3.
- Invoices (`INV2026087`): rename the first posted invoice of the journal to the wanted format. Odoo continues the sequence from it.
- PFI numbers (`PFI2026178`): sequence *aHPS Pro Forma Invoice*, assigned when the PFI is first printed.

## Not included yet

- Packing List: on hold until aHPS sends the details (article number and weights/volumes per product).
- Delivery Note: template received, not requested yet.
