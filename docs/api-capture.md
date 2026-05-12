# FirstAgenda Publication — API reference (Hvidovre)

The SPA at <https://dagsordener-referater.hvidovre.dk/> is "Powered by
FirstAgenda Publication" and loads data via XHR to a JSON backend on the same
host. The endpoints were captured to `docs/har-capture.json`; representative
response bodies are committed under `tests/fixtures/json/`.

Three endpoints are enough to crawl the whole dataset:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/agenda/udvalgsliste` | Every committee, grouped by election period, with all meetings inlined |
| `GET /api/agenda/dagsorden/{meeting_id}` | One meeting's agenda items, fields, and PDF attachments |
| `GET /Vis/Pdf/bilag/{document_id}` | PDF stream for any document GUID |

No authentication is required for public material. A `.AspNet.Cookies` session
cookie is observed in the browser but the API responds to anonymous requests as
well — the cookie is set on first visit and is not enforced.

## 1. `GET /api/agenda/udvalgsliste`

Response shape:

```json
{
  "Udvalg": {
    "Udvalg 2026-2029": [
      {
        "Id": "ac4bbfca-65b5-4a1a-9ff3-0e9717ed6adf",
        "Navn": "By- og Planudvalget",
        "OrganisationId": "00000000-0000-0000-0000-000000000000",
        "Historisk": false,
        "Moeder": [
          {
            "Id": "fd2d6261-1220-429e-9ed0-46db433c496c",
            "Dato": "2026-05-04T14:00:00+02:00",
            "MeetingBeginUtc": "2026-05-04T14:00:00+02:00",
            "ReleasedDate": "2026-05-06T10:53:07+02:00",
            "Sted": "Sollentuna II",
            "Afsluttet": true,
            "Navn": "Referat",
            "IsSupplementaryAgenda": false
          }
        ]
      }
    ],
    "Udvalg 2022-2025": [ ... ],
    "Udvalg 2018-2021": [ ... ],
    "Udvalg 2014-2017": [ ... ],
    "Folkeoplysningsudvalget 2014 og frem": [ ... ]
  }
}
```

Observed scale: ~5 periods, ~8 committees each, ~50 meetings each → ~1400 meetings total.

Meeting `Navn` values observed: `Referat`, `Dagsorden`, `Tillægsdagsorden`,
`Lukket referat`, `Referat 1. behandling budget`. Lukkede møder are filtered
server-side; what reaches the API is public.

## 2. `GET /api/agenda/dagsorden/{meeting_id}`

`meeting_id` is the GUID from `Moeder[].Id` above. Top-level response keys:

```
Id                       - mirrors meeting_id
Udvalg{Id, Navn, ...}    - parent committee
Moede{Dato, Sted, Navn, Moededeltagere, ...}   (Moede.Id is the zero GUID — ignore it)
TillaegsDagsorden        - bool
Dagsordenpunkter[]       - the agenda items
LiveIntegrationEnabled
Lydfiler                 - audio files (rare; not handled yet)
```

Each `Dagsordenpunkter` entry:

```
Id                 - item GUID
Number/Punktnummer - "1", "2", ...
Navn/Caption       - item title
SagsNummer         - "25/26257"
IsOpen             - bool
Felter[]           - case-presentation pieces, each with Link + DocumentId (a PDF)
Bilag[]            - attachments, each {Id, Navn, Order, HarPdfVersion}
Presentations, ItemDecision, Lydfiler, Ressourcer  (often null)
```

Both `Felter[].DocumentId` and `Bilag[].Id` are document GUIDs that resolve via
`/Vis/Pdf/bilag/{guid}`. `Felter[].Link` already contains that URL; for `Bilag`
we build it. We skip the zero GUID (placeholder for empty fields).

## 3. `GET /Vis/Pdf/bilag/{document_id}`

Streams `application/pdf`. We content-address downloads by sha256, so identical
PDFs referenced from multiple items dedupe to one file on disk.

## Search endpoint (not used)

`GET /api/agenda/soeg/?request.kriterie.udvalgId=...&request.kriterie.moedeDato=YYYY&request.paging...`
exists but is unnecessary: `udvalgsliste` already returns every meeting we need
for discovery, and `dagsorden/{id}` gives the full per-meeting detail.

## Optional auth header

If a future capture turns up an `Authorization` header that should not be
committed, set it in `HKR_API_KEY` and the CLI will pass it through
`HttpClient(extra_headers={"Authorization": ...})`.
