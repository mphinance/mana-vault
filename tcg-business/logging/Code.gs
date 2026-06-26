/**
 * TCG Toolkit — response logger (Google Apps Script Web App)
 *
 * Receives interview answers POSTed from idea-generator.html and appends them
 * as a row to a Google Sheet in your Drive. The sheet is created automatically
 * on first use ("TCG Toolkit Submissions"), so there is nothing to pre-build.
 *
 * Deploy: see SETUP.md in this folder. In short:
 *   1. script.google.com → New project → paste this file.
 *   2. Run `setup` once and authorize (creates the sheet, grants permissions).
 *   3. Deploy → New deployment → Web app → Execute as: Me, Access: Anyone.
 *   4. Copy the /exec URL and hand it back to wire into the page.
 */

const SPREADSHEET_NAME = 'TCG Toolkit Submissions';
const SHEET_TAB = 'Submissions';
const PROP_KEY = 'TCG_SPREADSHEET_ID';

const HEADERS = [
  'Timestamp', 'Name', 'Capital', 'Skill', 'Time', 'Risk', 'Interests',
  'Game', 'Top idea 1', 'Top idea 2', 'Top idea 3', 'Prompt', 'User agent', 'Page',
];

function getSheet_() {
  const props = PropertiesService.getScriptProperties();
  let ss = null;
  const existingId = props.getProperty(PROP_KEY);
  if (existingId) {
    try { ss = SpreadsheetApp.openById(existingId); } catch (e) { ss = null; }
  }
  if (!ss) {
    ss = SpreadsheetApp.create(SPREADSHEET_NAME);
    props.setProperty(PROP_KEY, ss.getId());
  }
  let sheet = ss.getSheetByName(SHEET_TAB) || ss.insertSheet(SHEET_TAB);
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const sheet = getSheet_();
    sheet.appendRow([
      new Date(),
      data.name || '',
      data.capital || '',
      data.skill || '',
      data.time || '',
      data.risk || '',
      Array.isArray(data.interests) ? data.interests.join(', ') : (data.interests || ''),
      data.game || '',
      data.top1 || '',
      data.top2 || '',
      data.top3 || '',
      data.prompt || '',
      data.userAgent || '',
      data.page || '',
    ]);
    return json_({ ok: true });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function doGet() {
  return ContentService.createTextOutput('TCG Toolkit logging endpoint is live.');
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/** Run this once from the editor to create the sheet and grant permissions. */
function setup() {
  const sheet = getSheet_();
  Logger.log('Spreadsheet ready: ' + sheet.getParent().getUrl());
}
