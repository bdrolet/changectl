# Demo script

A walkthrough for showing changectl to a prospective client. About 20 minutes.

## Before the demo

1. Run the seed against the deployed database (start the Cloud SQL Auth Proxy first, see the README). It creates Tesa's and Ben's accounts, so it must run before anyone signs in:

   ```bash
   SEED_TESA_EMAIL=<tesa's email> SEED_BEN_EMAIL=<ben's email> \
   SEED_SECOND_EMAIL=<second account's email> .venv/bin/python scripts/seed_demo.py
   ```

   It prints the change numbers it created and is safe to run twice. If you do not set `SEED_SECOND_EMAIL`, invite the second account in step 3.
2. Sign in once as Tesa (a document manager), so her row is bound to her Google identity.
3. As Tesa, open **Users**. If the second account is not listed yet, fill in **Email**, **Name** and **Role** (Operations), leave **Doc manager** unticked, and click **Invite**.
4. Sign in once with the second account.
5. Open **Documents** (`/documents`) and check that three documents are listed: Prototype BOM, Cable Assembly Spec and Supplier Spec - Connector, each at Rev 1.

6. Write the demo files to a folder you can reach from the browser's file picker:

   ```bash
   .venv/bin/python scripts/demo_files.py --out ~/changectl-demo
   ```

   It writes `Prototype BOM.xlsx` (Rev 1), `Prototype BOM rev2.xlsx` (the clean Rev 2, J4 moved to Ridgeview Connectors, with a `Changes` sheet), `Cable Assembly Spec.docx`, `Supplier Spec - Connector.pdf` and `Test Fixture Spec.docx`, a document the seed never creates.

The seed's other users (Priya, Marcus, Dana) are history only. They never sign in. The seeded change "Replace EOL connector J4" has two approvers: Marcus, who has signed, and a live account that has not. That live approver is the second account when the seed ran with `SEED_SECOND_EMAIL`, otherwise Tesa. Below, "the live approver" means whichever of the two it is.

Never attach a file to Prototype BOM during the demo: the seeded change already holds its pending Rev 2, so a second attach is refused as *document busy*.

## Walkthrough

Steps 2 and 3 use `Test Fixture Spec.docx`; step 5 uses `Prototype BOM rev2.xlsx`. Both come from the folder written in *Before the demo*.

1. **The BOM.** On **Documents**, open Prototype BOM and click **Download** under *Current revision*. Open the sheet `BOM`: material number, description and supplier columns, one connector (J4) supplied by Northgate Connectors.

2. **Initial release, as an engineer.** Sign in as Ben. Click **Changes**, then **New change**. Enter **Title** "Initial release of test fixture spec", a **Description**, a **Reason** and a **Justification** (the **Same as reason** button copies it), then click **Create change**. The app opens the read-only change page; click **Edit**. Under *Documents*, choose `Test Fixture Spec.docx` as the **File**, leave **Attach to existing document** on *New document*, enter **New document title** "Test Fixture Spec", and click **Attach file**. Under *Approvers*, tick the second account (each person is listed with their role) and click **Save approvers**. Open the change again from **Changes** and click **Submit**. The record is now locked.

3. **Approval and release.** Sign in as the second account; open **Changes**, filter **Approval** and open the change. Click **Approve**; the **Sign approval** dialog shows who is signing and what; click **Approve** again. With its only approver signed, the change moves to Implementation. Sign in as Tesa (document manager), open the change and click **Release**. The **Cut-in date** in the dialog defaults to today; confirm with **Release Rev 1**. The change closes and Test Fixture Spec is at Rev 1.

4. **A revision, signed live.** The J4 connector's supplier part goes end-of-life, and engineering has already raised the change. Open **Changes**, filter **Approval**, and open "Replace EOL connector J4" (seeded, created by Priya). Under *Documents* the Prototype BOM redline is attached as its pending Rev 2; under *Approvers* Marcus has signed and the live approver is pending. Sign in as the live approver, open the change and click **Approve**, then **Approve** again in the **Sign approval** dialog. The change moves to Implementation. (Do not use **Request changes** here: the change would return to Priya, who never signs in, and could not be resubmitted.)

5. **Clean file and supersede.** Sign in as Tesa, open "Replace EOL connector J4" and click **Release**. In the dialog, use **Replace with clean file** to upload `Prototype BOM rev2.xlsx` in place of the redline (the redline stays downloadable as **Download redline**), set the **Cut-in date**, and click **Release Rev 2**. Rev 2 becomes current and Rev 1 is superseded.

6. **Search and history.** Go to **Documents** and search "connector" in the *Search released documents* box. The BOM returns at Rev 2. Open it: *Revisions* lists Rev 1 and Rev 2 with their changes, cut-in dates, who approved and when. Open a change and read *History* for the audit trail.

7. **The signed record.** Open **Changes** and open "Replace EOL connector J4" again, now closed. Under *Approvers* each person shows their decision and when they signed: Marcus from the seed, the live approver from step 4. Under *Documents* the released Rev 2 and its **Download redline** sit side by side, and *Comments* and *History* hold the rest of the record. Each approval is bound to the hashes of the files as they were when it was signed.

8. **Users.** Open **Users**. Show the roles, the **Doc manager** flag and the **Invite** form: access is by invitation only, and a person who is not on the list lands on the not-invited page.

## After the demo

Re-seeding is safe. To start from empty, recreate the database with `scripts/migrate_db.py` and run the seed again.
