# Demo script

A walkthrough for showing changectl to a prospective client. About 20 minutes.

## Before the demo

1. Invite the second account. As Tesa (a document manager), open **Users**, fill in **Email**, **Name** and **Role** (Operations), leave **Doc manager** unticked, and click **Invite**.
2. Sign in once with each account (Tesa's and the second one) so the allowlist row is bound to the Google identity.
3. Run the seed against the deployed database (start the Cloud SQL Auth Proxy first, see the README):

   ```bash
   SEED_TESA_EMAIL=<tesa's email> SEED_BEN_EMAIL=<ben's email> \
   SEED_SECOND_EMAIL=<second account's email> .venv/bin/python scripts/seed_demo.py
   ```

   It prints the change numbers it created and is safe to run twice.
4. Open **Documents** (`/documents`) and check that three documents are listed: Prototype BOM, Cable Assembly Spec and Supplier Spec - Connector, each at Rev 1.

The seed's other users (Priya, Marcus, Dana) are history only. They never sign in.

## Walkthrough

Files for steps 2 to 5 can be built from `scripts/demo_files.py` (`bom_xlsx(1)` and `bom_xlsx(2)`), or use your own spreadsheet with the columns Item, Material No, Description, Supplier and Qty.

1. **The BOM.** On **Documents**, open Prototype BOM and click **Download** under *Current revision*. Open the sheet `BOM`: material number, description and supplier columns, one connector (J4) supplied by Northgate Connectors.

2. **Initial release, as an engineer.** Sign in as the second account. Click **Changes**, then go to `/changes/new`. Enter **Title** "Initial release of prototype BOM 2" (any new name), **Description**, **Reason**, and **Justification** (the **Same as reason** button copies it), then click **Create change**. On the change page, under *Documents*, choose a **File**, leave **Attach to existing document** on *New document*, give a **New document title**, and click **Attach file**. Under *Approvers* tick Engineering and Quality users and click **Save approvers**. Click **Submit**. The record is now locked.

3. **Approvals and release.** Sign in as an approver; open **Changes**, filter **Approval** and open the change. Click **Approve**; the **Sign approval** dialog shows what you are signing; click **Approve** again. When the last approver has signed, the status moves to Implementation. Sign in as Tesa (document manager), open the change and click **Release**. The **Cut-in date** defaults to today; confirm with **Release**. The change closes and the document is at Rev 1.

4. **A revision.** The connector's supplier part goes end-of-life. Download Rev 1 of the Prototype BOM, change the J4 supplier in Excel and add a `Changes` tab describing it. As the engineer, create a new change (**Create change**) with a **Reason** (supplier end-of-life) and **Justification**. Under *Documents* pick the file, set **Attach to existing document** to Prototype BOM and click **Attach file**. It is stored as a redline. Choose approvers, **Save approvers**, **Submit**, and run the same approval flow as step 3.

5. **Clean file and supersede.** When the change reaches Implementation, Tesa clicks **Release**. In the dialog, optionally use **Replace with clean file** to upload the clean spreadsheet in place of the redline (the redline stays downloadable as **Download redline**), set the **Cut-in date**, and release. Rev 2 becomes current and Rev 1 is superseded.

6. **Search and history.** Go to **Documents** and search "connector" in the *Search released documents* box. The BOM returns at Rev 2. Open it: *Revisions* lists Rev 1 and Rev 2 with their changes, cut-in dates, who approved and when. Open a change and read *History* for the audit trail.

7. **A change mid-approval.** Open **Changes**, filter **Approval**, and open "Replace EOL connector J4" (seeded). Marcus has approved; Dana has not. As the second account or Tesa, show the approver list, the redline of the BOM under *Documents*, and *Comments*. This is what the Approve button would sign.

8. **Users.** Open **Users**. Show the roles, the **Doc manager** flag and the **Invite** form: access is by invitation only, and a person who is not on the list lands on the not-invited page.

## After the demo

Re-seeding is safe. To start from empty, recreate the database with `scripts/migrate_db.py` and run the seed again.
