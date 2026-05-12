# FirstAgenda Publication — API capture

The SPA at <https://dagsordener-referater.hvidovre.dk/> is "Powered by
FirstAgenda Publication" and loads its data via XHR/fetch calls to a JSON
backend. We target that backend directly. This file is where the captured
requests live so the scraper can be wired up.

## How to capture

1. Open <https://dagsordener-referater.hvidovre.dk/> in Chrome/Firefox.
2. Open DevTools → **Network** tab → filter **Fetch/XHR** → check
   **Preserve log**.
3. Reload the page, then click through:
   - the committee list / sidebar
   - a recent meeting (open the agenda)
   - one of the PDF links inside an agenda
4. For each interesting request (skip fonts, analytics, etc.), right-click →
   **Copy → Copy as cURL** *and* **Copy response**.
5. Paste below under the matching section. Redact any auth tokens or session
   cookies you don't want committed (the API is public, so there shouldn't
   be any, but check).
6. Save a representative response body for each endpoint to
   `tests/fixtures/json/<name>.json` (e.g. `committees.json`,
   `meetings_88.json`, `agenda_2877.json`).

## Endpoints

### 1. List of committees / publication root

- **Request URL:** `TODO`
- **Method:** `GET`
- **Required headers (if any):** `TODO`
- **Sample response file:** `tests/fixtures/json/committees.json`

```
# paste curl here
```

### 2. Meetings for a committee

- **Request URL:** `TODO` (parameterised by committee id)
- **Method:** `GET`
- **Sample response file:** `tests/fixtures/json/meetings_<committee_id>.json`

```
# paste curl here
```

### 3. Single meeting / agenda (with item list and attachments)

- **Request URL:** `TODO` (parameterised by meeting/agenda id)
- **Method:** `GET`
- **Sample response file:** `tests/fixtures/json/agenda_<agenda_id>.json`

```
# paste curl here
```

### 4. PDF attachment download

- **URL pattern:** `TODO` (note: may be a FirstAgenda CDN host, e.g.
  `*.firstagenda.com` or similar — record it as seen)
- **Auth required:** yes / no
- **Example URL:** `TODO`

```
# paste curl here
```

## Notes

- FirstAgenda's documented API exposes only public/released material —
  closed committees and closed meetings are filtered server-side, which is
  what we want.
- If the API uses an `Authorization` or `X-Api-Key` header that you'd rather
  not commit, set it via the `HKR_API_KEY` env var; the scraper will read
  that and pass it through `HttpClient(extra_headers=...)`.
- Once these four sections are filled in, the next steps are:
  1. Set `BASE_URL` in `src/hkr/sources.py` and adjust the path builders.
  2. Drop sample bodies into `tests/fixtures/json/`.
  3. Implement `parse_committees`, `parse_meeting_list`, `parse_agenda` in
     `src/hkr/parser.py`, test-first against the fixtures.
