# Phase 7: Plex catalogue and safe local-source integration

Status: detailed gated plan, 2026-10-20. Documentation only; no Plex connection, credentials, implementation or test results are claimed. Implementation begins after reviewed Phase 5 and Phase 6 acceptance. The fixed-source mode remains a fallback.

## 1. Goal and v1 boundary

Browse allowed Plex libraries in the existing handset, select a supported item/version, resolve it to an approved read-only local file and use the accepted Wapflix converter/cache/session pipeline. Plex supplies metadata, not a second video transcoder.

V1: one configured server and credential, selected movie/show libraries, local single-part media, explicit variant handling and supported external local SRT. Defer discovery, multiple servers/accounts, Plex login UI, cloud/remote original-video retrieval, Plex transcoding, multi-part playback, embedded/image subtitles, OCR, artwork proxying, automatic subtitle downloads, watch-state writes and whole-library conversion.

## 2. Configuration, credential and server contract

Required local configuration: Plex base origin, read-only credential-file mount, expected server machineIdentifier after operator-approved diagnostic, library allowlist and explicit path mappings. Stable Wapflix client identifier is stored privately under state. Host values are supplied, not guessed.

Use an operator-provisioned credential with a validated lifecycle. The documented XML-inspection token is temporary; do not promise permanent deployment authentication from that method. Wapflix invokes read-only API operations, but that does not make the underlying account token a specially scoped read-only token. Never edit Plex files/databases to extract credentials.

Send X-Plex-Token in the backend header, not browser/query URLs, and request JSON explicitly with Accept: application/json. Include the documented client/product identifiers. Record the tested server/API compatibility profile in 7.1; pin its API-header semantics rather than assuming the latest/default version. Unsupported profiles fail clearly.

Base URL must be fixed HTTP(S), with no userinfo/query/fragment. HTTPS verifies certificates; a private CA can be configured, not silent verification disablement. HTTP requires the documented trusted-network boundary. Redirects are refused by default. Returned Plex keys may be absolute URLs: follow only validated documented same-origin local-library paths/features; never forward credentials to another origin, cloud provider or custom URI scheme.

Credential/server/library-policy changes require service restart in v1 and a new authorisation epoch. Invalidate/hide old catalogue metadata. New preparation/admission requires fresh successful item authorisation; stale metadata is not authority. A 401/403 blocks new Plex selections and reports reconfiguration, without leaking the credential.

## 3. Bounded browsing and search

Default and maximum requested page size: 50 items. Send both X-Plex-Container-Start and X-Plex-Container-Size. Validate returned offset/count/total where supplied: servers may force pagination, return fewer items or ignore a request. A short page alone is not proof of EOF. Detect nonadvancing/repeated pages and stop, rather than loop or load the whole library. Accept unpaginated output only when a verified bounded complete result is demonstrated; otherwise return an unsupported-pagination error.

Plex request connect budget: two seconds; total request budget: five seconds. Raw response ceiling: four MiB. Read bounded data before parsing; oversized/unsupported responses fail clearly instead of truncating into a fake valid page. Search query limit: 128 characters. Use supported server-side search restricted to allowed libraries; never implement search by fetching every page.

Metadata LRU: 60-second freshness, at most 200 page/detail entries and eight MiB of normalised stored data, with whichever limit is reached first enforced. Cache is private, partitioned by server identity/authorisation epoch/query context. Do not store raw responses indefinitely. Library mutation during pagination can invalidate a cursor; report refresh rather than promise snapshot consistency.

Normalise only display fields and application handles: type, title/year, summary, hierarchy, season/episode indexes, duration in seconds, availability/selection status and supported choices. Plex media durations expressed in milliseconds are converted once. Do not expose file paths, secret-bearing keys or raw Plex responses. Containers such as shows/seasons are browsable, not playable leaves. Do not scan/probe media while listing.

## 4. IDs and source identity

Assign opaque Wapflix item/variant handles backed by a bounded private registry. Internal references bind server machineIdentifier, allowed library and ratingKey; variants additionally bind media/part/stream identity. Never identify by title alone or treat an item ID as a filesystem path/Plex URL. Each lookup rechecks allowed scope.

Registry handles are stable while retained. Evicted unreferenced handles return a refresh-required response; do not promise permanent private deep links in v1. Registry allocation is subject to the Phase 6 state budget and an explicit 7.0 cap. Phase 8 persistent viewing records must pin their required identity references before promising durable resume.

Frame-cache identity uses stable internal source/version/profile/window identity, not temporary registry handles or navigation IDs. A server identity change creates a distinct namespace and requires approval.

## 5. Deterministic local path mapping

Initial profile supports POSIX Plex paths. Map configured source prefixes to container roots with component-boundary matching and deterministic longest-prefix selection. Reject conflicting equal-prefix mappings. Do not use substring replacement, title matching or opportunistic disk search. Windows/UNC paths require a later explicit profile.

Resolve the mapped file and require a readable regular file inside an approved read-only media root, including symlink checks and mount identity from Phase 6. Missing/unmapped/outside-root files produce distinct errors. Plex's exists/accessible flags are hints, not proof of container access.

Build an immutable backend descriptor with server/item/media/part/stream reference, confined path, Phase 6 source fingerprint, validated geometry/duration/profile, caption identity and source-window bounds. No private path is returned to the browser. Recheck identity before decoder admission; changes require preparation again, not silent substitution. Preserve Phase 6 handling of source changes during decoding.

Do not change a global app.video when selecting an item. Each playback/job owns its resolved descriptor, and replacement releases its old ownership under the existing lifecycle.

## 6. Version and part policy

Auto-select only an unambiguous supported single-part version with an unambiguous supported video stream. Multiple versions return needs_version_selection with bounded safe display choices and opaque variant handles; the selected handle must still belong to the freshly authorised item. Never silently choose first/highest resolution. An explicit server-side pin may select a known supported variant.

Multi-part, unresolved mixed streams, nonlocal/unmapped parts or unsupported decoder/duration cases are clearly classified. Choosing a version never changes Plex's selected stream/version attributes. Finer compatibility follows Phase 9 rather than weakening the v1 contract.

## 7. Cancellable preparation before playback

Cold item selection must not put a five-second Plex lookup plus a twenty-second probe inside a six-second control acknowledgement. Add an acknowledged preparation stage using the Stage 5 operation-identity/fencing contract, with its exact field names bound at 7.0.

Proposed additive route family: POST /api/sources/prepare, authenticated preparation-status and cancellation operations, then an optional source-ticket argument to existing playback start. Final wire names are frozen with conformance fixtures before implementation; no fallback to browser file paths.

Preparation acknowledges promptly, then performs fresh item authorisation/details, mapping, confined file validation, selected-source probe and SRT resolution in bounded background work. One active source probe and at most one latest pending preparation initially; superseded work is cancelled/coalesced. Preparation total budget: 30 seconds, including cancellation/cleanup of probe work within the accepted subprocess rules. No video conversion starts during preparation.

Preparing B does not stop active playback A. Cancelling B cannot cancel A. Commit replacement only when the user starts the prepared selection through the existing fenced session admission. Revalidate descriptor/source identity and preparation ownership then; do not create a new global-source race.

A ready source ticket is opaque, owner/authorisation-epoch/version-bound and valid for 60 seconds. Retry of the same accepted Start operation follows existing idempotency/fencing, not duplicate conversion. Expired/changed tickets require preparation again. Seek keeps the admitted descriptor; it does not re-resolve another item implicitly.

Extend the source adapter with the required preparation/start-selection contract in a separate tested slice. Preserve start() with no selection for the configured fixed-source fallback. The handset shows PREPARING separately from BUFFERING; Back/Home, newer selection and timeout invalidate both preparation and playback generations correctly.

## 8. Local subtitle policy

V1 uses supported local external SRT only. Metadata may identify language/format but does not guarantee a usable filesystem path. Resolve only confined deterministic sidecars for the selected part or explicit approved mappings; do not fetch arbitrary stream keys or download tracks.

Preferred language is configured, initially English. For a unique suitable matching full SRT, select it; a unique language-unknown plain sidecar is labelled unknown, not falsely English. Forced-only or ambiguous candidates are not silently substituted for full captions. If no unambiguous supported track is available, video remains usable with a clear caption status; track-picker/embedded support follows later. Do not mutate Plex's selected subtitle setting.

Use the existing defensive SRT parser/size limits and absolute source-time contract. Version caption data separately from image frames. No full SRT or private path reaches the browser, only normalised selected cues/status.

## 9. Handset integration

Add library navigation incrementally using existing linked-page/focus/back behaviour: allowed library -> titles -> details; show -> season -> episode -> details; variant selection when required -> preparation -> playback. Do not preload every episode or replace the interface with a desktop grid.

Preserve selected page/query/cursor/focus when returning. IDs distinguish identical titles. Unsupported/unavailable items remain understandable without exposing paths. Requests from an old page/search cannot replace a newer page or source. Raw titles/summaries are text, never executable markup. Existing static/fixed-source modes and public Pages remain independent.

Persistent Continue Watching, watched-state writes, recommendations and autoplay-next for Plex belong to Phase 8. Do not call management, stream-selection setters, timeline/scrobble or deletion APIs as a side effect of browsing/preparation.

## 10. Outage, security and privacy behaviour

Plex offline/timeouts: show an actionable catalogue error; a bounded cached page may be visibly stale but cannot authorise new playback. Fresh preparation/admission fails closed. Existing already-validated local playback can continue without ongoing Plex polling; revocation does not imply instant cancellation of an already-admitted local session in this single-owner v1. Document that boundary.

401/403 clears authorisation-dependent metadata and blocks new Plex selections; missing item/library/variant, unmapped path, changed source and unsupported part have distinct additive error codes. Do not relabel all failures as expired playback. Keep Stop/diagnostics responsive and retain Phase 6 recovery semantics.

Every endpoint enforces the allowed library and server binding, not just the browse UI. No arbitrary proxy, redirect following, original file download route or browser token URL. Apply existing request-size/deadline/rate/admission bounds; source probes are separately limited from converters.

No credentials, source media, personal catalogue export, private frame cache, full SRT or local path enters Pages, images/build context, public shares, CI artifacts or default logs. Use generated/sanitised fixtures; never commit live tokens. Artwork is excluded from v1, avoiding a new image/token proxy surface.

## 11. Small delivery checkpoints

| Step | Only deliver | Gate |
| --- | --- | --- |
| 7.0 | Configuration, API compatibility, ID/registry cap and source/preparation contract freeze | Required host facts and bounded schemas agreed |
| 7.1 | Read-only connection diagnostic | Validated identity/auth/library types; redacted failures |
| 7.2 | Paginated catalogue/search adapter | Correct bounded pages, response validation, no whole-library import |
| 7.3 | Version/part selection and local resolver | Deterministic descriptor or precise unsupported result |
| 7.4 | Preparation and selected-source admission | Prompt acknowledgement; cancellation/ownership safe; fixed fallback works |
| 7.5 | Handset browse/variant/preparation views | Correct hierarchy, focus and latest-page/source behaviour |
| 7.6 | Subtitle and cache/source integration | Correct cues and no cross-item/stale-frame reuse |
| 7.7 | Real server/browser/host failure acceptance | Supported content plays end to end without credential/path exposure |

Split each again into one or two implementation files plus focused tests as needed. Do not build the whole Plex client in one pass or reconstruct Phases 5-6. Backend paths/modules are chosen against the accepted Phase 6 service, not a new server generation per feature.

## 12. Acceptance and test matrix

Unit/fixture coverage: JSON normalisation and duration units; authentication redaction; same-origin key resolution/redirect refusal; pagination ignored/forced/repeated/empty/mutated; equal-title IDs; registry expiry; prefix boundary/longest match/symlink escape; version/part ambiguity; sidecar ambiguity/language; immutable descriptor/source change; expired ticket and credential epoch.

Integration coverage: selected-item authorisation, async probe limits/deadlines, prepare B while A plays, cancel-before-ack, slow A then newer B, Start ticket retry, selection/seek/Stop races, source replacement, USB/cache failure, Plex offline/revoked token, exact-window cache identity and fixed-source regression.

Host/browser gate: browse an allowed library, open a supported leaf/version, prepare without blocking control requests, start before full conversion, use captions/pause/seek, Stop and select another item without stale frames, return to correct focus, handle unsupported/offline items clearly, and confirm public Pages has no Plex/API dependency.

Distinguish mocked tests, real Plex compatibility, browser results and N5105 throughput. No live compatibility or performance claim follows from documentation. Later daily-use/persistence plans are detailed only after source identity and this gate are accepted.

## References

- https://developer.plex.tv/pms/
- https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/
- https://python-plexapi.readthedocs.io/en/latest/modules/media.html
