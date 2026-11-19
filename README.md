# aHPS – Odoo 20 custom modules

Custom modules for Advanced Helios Process Solutions Ltd (aHPS), implemented by Globx.

| Module | What it does |
|---|---|
| `ahps_kyc` | Customer KYC: KYC tab on customers, KYC documents, workflow (Send KYC Form → Submit → Approve / Reject), customer ID `YYYY.NNN`, duplicate-company warning, blocks sending/confirming quotations and posting invoices until the KYC is approved |
| `ahps_reports` | aHPS document layouts: Quotation (instruments / spare parts / service), Pro Forma Invoice, Customer Invoice / Credit Note, Request for Quotation, Purchase Order |

`ahps_reports` depends on `ahps_kyc` (the customer ID is printed on quotations and PFIs).

## Install on staging

Install **aHPS Document Templates** from Apps; it pulls in **aHPS Customer KYC**.

## Configuration after install

1. **Settings › Companies › aHPS Documents**: certificate of registration (e.g. `PVT-XYUE2P9`), signatory (`J. Mbugua`), handling charges text, sales / finance / operations contacts, PO special note, the PO invoice-address contact (Emmanuel Rurema), and which bank accounts to print.
2. **Company**: logo, address (`PO Box 1325 – 00621 Village Market`, Nairobi, Kenya), phone, email, and the KRA PIN in the *Tax ID* field.
3. **Bank accounts** of the company (Contacts › the company › Bank Accounts): set the bank name, the SWIFT code (BARCKENX) and the new **Account Currency** (KES / EUR / USD) on each account.
4. **Sales › Settings › Customer KYC (aHPS)**: upload the blank KYC form (it is attached to the KYC request email). Use *Require approved KYC* to switch the blocking on or off.
5. **Customer number**: Settings › Technical › Sequences › *aHPS Customer Number*. Set *Next Number* to continue from the aHPS register (currently 231 → 232).
6. **Users**: Settings › Users › *Customer KYC* = *KYC Officer* (Joyce) or *KYC Manager* (Emmanuel / Janet). Managers approve and reject KYCs and can edit customer IDs.
7. **Products**: *HS Code*, *Country of Origin* and *Document Charge Type* (Shipping / Other) on the product form. Freight products should be set to *Shipping*, so they are totalled as Shipping / Total CPT on PFIs.

### Document numbers (configuration, no code needed)

- Quotations / orders (`Q2026.153`): Sequences › *Sales Order* → prefix `Q%(year)s.`, padding 3.
- Purchase orders (`2026-053`): Sequences › *Purchase Order* → prefix `%(year)s-`, padding 3.
- Invoices (`INV2026087`): rename the first posted invoice of the journal to the wanted format. Odoo continues the sequence from it.
- PFI numbers (`PFI2026178`): sequence *aHPS Pro Forma Invoice*, assigned when the PFI is first printed.

## Not included yet

- Packing List: on hold until aHPS sends the details (article number and weights/volumes per product).
- Delivery Note: template received, not requested yet.
