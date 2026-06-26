# Logging setup — Google Sheet

This wires the **Idea Generator** so that when someone clicks **💾 Save my responses**,
their answers get appended as a row to a Google Sheet in your Drive. No server, no cost.

The page → a Google Apps Script Web App → a row in your Sheet.

You do this once. It takes ~3 minutes. The only part Claude can't do for you is the
**Deploy** click inside Google (that's an account-authorization step).

---

## Steps

### 1. Create the script
1. Go to **https://script.google.com** → **New project**.
2. Delete the default `Code.gs` contents and paste in everything from
   [`Code.gs`](./Code.gs) in this folder.
3. Rename the project (top-left) to something like `TCG Toolkit Logger`. Save (⌘/Ctrl+S).

### 2. Authorize it
1. In the function dropdown (top toolbar) pick **`setup`**, then click **Run**.
2. Google will prompt for permissions — approve them (it needs to create/edit a
   spreadsheet in your Drive). You may see an "unverified app" screen → **Advanced →
   Go to TCG Toolkit Logger (unsafe)** → **Allow**. This is your own script, so it's fine.
3. This creates a sheet named **"TCG Toolkit Submissions"** in your Drive with the header row.

### 3. Deploy as a Web App
1. Click **Deploy** (top-right) → **New deployment**.
2. Click the gear ⚙️ next to "Select type" → **Web app**.
3. Set:
   - **Description**: anything (e.g. `v1`)
   - **Execute as**: **Me**
   - **Who has access**: **Anyone**  ← required so the browser can POST anonymously
4. Click **Deploy**, approve any further prompt, and **copy the Web app URL**.
   It ends in **`/exec`**, like:
   `https://script.google.com/macros/s/AKfy…long…/exec`

### 4. Hand the URL back
Paste that `/exec` URL into the chat and Claude will drop it into
`idea-generator.html` (the `LOG_ENDPOINT` constant), commit, and push — the live
site picks it up automatically. Until then, the form stays fully local and sends nothing.

---

## Notes

- **Privacy:** while `LOG_ENDPOINT` is empty the page sends nothing and says so in its
  footer. Once wired, the footer changes to tell users their answers are shared if they
  click save, and saving is always an explicit, optional click.
- **Where's the data:** open the **TCG Toolkit Submissions** sheet in your Drive anytime.
  One row per saved response: timestamp, optional name, all six answers, the top-3 ideas,
  the generated prompt, and the browser's user-agent.
- **Updating the script later:** if you edit `Code.gs`, you must **Deploy → Manage
  deployments → Edit → New version** for the change to take effect. The `/exec` URL stays
  the same, so no re-wiring needed.
- **Want me to analyze responses?** Since the data's in your Drive, paste a row or share
  the sheet and I can summarize patterns and suggest follow-ups for each person.
