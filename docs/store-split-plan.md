# Splitting the store: plan and trigger (12 October 2026)

Status: PLAN, nothing implemented except the read-only `tools/store_sizes.py`.
Decision wanted from Chris: approve Stage 1 now, and the trigger for Stage 3.

## The answer in five lines

1. The store is 1.85 GB raw and 454 MB as the published `parl-monitor.db.gz`: 22% of GitHub's 2 GiB per-asset limit. The 1.6 GB raw warning that fires on every push is about the old uncompressed asset; compressed, the limit is about 8 GB of raw store.
2. Steady growth (new sittings and votes in the parliaments we already cover) is about **0.63 GB raw a year, about 155 MB compressed**. 84% of it is roll-call vote rows. The jump from 0.19 GB to 1.85 GB between 25 September and 12 October was one-off backfill of new countries, not a rate.
3. **Do now (Stage 1, about a day):** compact the store. On a scratch copy, VACUUM plus `WITHOUT ROWID` on the 37 vote tables took it from 1,825 MB to 1,480 MB raw (-19%) and from 447 MB to 308 MB compressed (-31%), with no change to any query.
4. **Split at the trigger (Stage 3):** when the compressed asset passes **1.0 GiB (1.07 GB)**, split by country group into five store files, each its own release asset, ATTACHed by `src/db.connect` so existing SQL is unchanged, then let each Mini job pull and push only the files it uses (Stage 4).
5. **When:** at the central estimate (the regional parliaments and Africa added as planned) the trigger is reached around **Q4 2027 to Q1 2028 without compaction, 2029 or later with it**. A high-growth case (big regional backfills plus speech text for four more large parliaments) reaches it around **February to March 2027 without compaction, Q3 2027 with it**. Start building the split code (Stage 2) when the asset passes 0.75 GB.

## 1. What was measured

All figures from the laptop's copy of the published store (`data/parl-monitor.db`, 1,825,136,640 bytes, the publish of 12 October 00:21 London), opened read-only; the compaction tests ran on a scratch copy outside the repo, since deleted. Reproduce with `python3 tools/store_sizes.py` (new, read-only) and `--groups`.

### 1.1 Where the bytes are

| | MB | share |
|---|---:|---:|
| Whole file | 1,825 | 100% |
| Table data | 1,251 | 69% |
| Indexes | 574 | 31% |
| of which primary-key autoindexes | 376 | 21% |
| Unused space inside pages (VACUUM recovers most) | 218 | 12% |
| The 38 `<cc>_votes` tables, with their indexes | 989 | 54% |
| of which their indexes | 518 | 28% |
| Text-heavy tables (speeches, gazette, items, rulings, testimony, petitions) | 575 | 31% |

The 15 biggest tables (bytes include their indexes):

| table | MB | of which index | rows | rows dated in the last year |
|---|---:|---:|---:|---:|
| fr_votes | 154.1 | 83.0 | 1,540,884 | 63% |
| sp_items (Scottish Parliament questions and motions) | 125.4 | 5.2 | 172,505 | 6% |
| es_votes | 119.0 | 71.4 | 729,368 | 33% |
| it_votes | 109.5 | 62.8 | 1,059,282 | 94% |
| ca_gazette_items | 101.2 | 3.3 | 26,782 | 5% |
| pl_votes (already WITHOUT ROWID) | 92.7 | 40.3 | 1,006,432 | 100% |
| prov_votes | 86.1 | 38.3 | 632,929 | 7% |
| prov_speeches | 74.4 | 0.7 | 13,051 | 7% |
| de_speeches | 73.6 | 0.5 | 11,213 | 9% |
| ca_speeches | 71.9 | 1.7 | 24,704 | 13% |
| br_votes | 58.8 | 34.1 | 480,014 | 25% |
| mp_events (UK) | 58.4 | 7.5 | 186,119 | 9% |
| ch_votes | 58.3 | 32.3 | 936,086 | 34% |
| eu_votes | 51.6 | 26.0 | 505,330 | 100% |
| us_votes | 36.2 | 20.6 | 383,736 | 53% |

By table prefix (MB, indexes included): ca 226, prov 188, fr 161, sp 161, es 121, it 119, de 112, UK and shared tables without a prefix about 107, pl 97, us 80, ch 66, br 61, eu 53, then nl 30, sd 29, cv 20, hr 20, be 20, ec 19, ie 17, pe 16, au 15, and 20 smaller prefixes. 369 tables in all.

### 1.2 How fast it grows

**History** (the committed sidecar, 559 publishes since 24 August):

| date | raw | compressed | tables |
|---|---:|---:|---:|
| 24 Aug | 93 MB | | |
| 25 Sep | 195 MB | | 109 |
| 29 Sep | 627 MB | | 123 |
| 8 Oct | 895 MB | | 137 |
| 9 Oct | 1,018 MB | | 312 |
| 10 Oct | 1,648 MB | | 349 |
| 11 Oct | 1,825 MB | 447 MB | 369 |
| 12 Oct 09:27 | 1,852 MB | 454 MB | 369 |

Almost all of the growth since late September was first collection of new countries with years of backfill (+630 MB on 10 October alone). That is a series of events, not a rate, so the steady rate is estimated from the data's own dates instead.

**Steady state.** For every table over 1 MB with a usable date (its own `date`/`dated`/`voted_at`/..., or its division's date for a vote table), the rows dated in the last 365 days times the table's bytes per row: what the same parliaments will add in the next year if they sit as much as in the last. Covered: 1,688 MB of the 1,825.

- **About 633 MB raw a year (12 MB a week)**, about 155 MB compressed at today's ratio.
- Vote rows are **530 MB a year (84%)**: it_votes 103, fr_votes 98, pl_votes 93, eu_votes 52, es_votes 40, ch_votes 20, us_votes 19, br_votes 14. Text tables add only 55 MB a year: their size is old backfill.
- By proposed shard (section 3, option a): Europe south and east 254 MB a year, Europe west 209, North America and Oceania 87, UK core 43, Latin America 40.

**Known additions still to come** (estimates, the main uncertainty):

| addition | raw estimate | basis |
|---|---:|---|
| Regional parliaments (`regions-at`, `-es`, `-it`, `-mx`, `-pe`, and Nova Scotia; about 100 bodies) | 0.5 to 2 GB, central 1 GB | the 9 Canadian provinces are 188 MB for 16 years with speeches (about 21 MB a body); most regional bodies publish no member-level roll calls, so about 10 MB a body |
| Completing current backfills (Poland's 10th term is 1.0 of about 2.3 million positions per `src/pl_store.py`; Dutch member votes, none dated in the last year) | about 0.1 GB | pl_store docstring: 60 bytes a position |
| Africa (Q1 2027) | 0.3 to 0.8 GB | thin records, like the smaller Latin American countries (1 to 20 MB each) |
| Speech text for BR, PL, IT, ES (not stored yet) | 0.3 to 0.6 GB | de_speeches 74 MB, ca_speeches 72 MB |

**Compression ratio.** 4.08x for the whole store today. On scratch copies, vote tables compress 4.4x and text tables 3.6x; the worst case measured in `tools/db_state.py` (generated high-entropy text) is 2.85x. So 2 GiB compressed is about 7.7 to 8.7 GB of raw store at today's mix, about 6 GB at worst.

### 1.3 What the store costs each job

Every store-writing job pulls and pushes the whole store, one at a time on the Mini (FIFO lock, `tools/mini_run.sh`). On the Mini the raw upload took 13 to 16 minutes for 1.64 to 1.76 GB (about 1.9 MB/s, `docs/mac-mini.md`); the compressed upload takes 4 to 5 minutes, plus about 16 s to compress and 4 s to prove the gzip. `tools/collector_budget.sh` reserves `PUBLISH_S=1200` (20 minutes) for the publish. At 1.9 MB/s that reserve is used up at about 2.2 GB compressed, so job time and the asset limit run out at about the same size: neither bites before about 1.5 GB compressed.

### 1.4 Who writes what

- **Country tables** (`fr_*`, `ca_*`, ...) are written by that country's jobs only: `jobs/<cc>-weekly.sh` and its backfills (`ca-backfill`, `prov-backfill`, `sk-docs-backfill`, `hu-karzat-backfill`, `latam-courts-backfill` for BO/CO/EC/PE/UY).
- **UK tables** (no prefix, plus `sp_`, `sd_`, `ni_`, `cv_`, `dv_`): `sunday-pull`, `monday-publish`, `member-profiles`, `sp-weekly`, `sd-weekly`, `ni-weekly`, `retag-backfill`, `day-sweep`, `upr-monthly`.
- **Shared tables written by almost every job**: `gaps` (61 writer files), `source_runs` (the heartbeat `db_state.py --push` stamps on every publish), `stance`, `judge_verdicts`, `vote_meanings`, `country_agenda` and `country_petitions` (one row set per country), `member_service`/`member_party`/`member_post` and the `mi_*` and `att_*` tables (per-country rows from `src/member_profiles.py`, `src/member_intel.py`, `src/attendance.py`), `api_spend`. Together about 25 MB.
- **Readers of everything**: `editions-session-judge`, `judge-queue-in`, `coverage`, `health`, `latam-monthly` (all Latin America).
- No store: `division-watch`, `devolved-watch`, `au-`, `ie-`, `us-division-watch`, `vote-briefs-daily`, `edition-publish` (until an edition is due), `mx-weekly`, `us-senate-catchup`.
- GitHub: 48 workflows pull the store and 28 push it (the backups of the Mini jobs).
- Code: 218 files open the store through `src/db.connect`, 22 call `sqlite3.connect` directly; each of the 34 `src/<cc>_store.py` modules creates its tables in `ensure_schema(conn)` (67 call sites). One existing ATTACH: `src/country_live.py`.

## 2. When to act: the trigger

| level (compressed asset) | meaning | action |
|---|---|---|
| 0.75 GB | about 18 months of steady growth, or one big expansion wave, from the trigger | build Stage 2 (the split code, single-file mode) |
| **1.0 GiB (1.07 GB)** | **the trigger** | **Stage 3 cutover within two weeks** |
| 1.5 GB (today's "split now" warning) | too late: on 10 October the store grew about 155 MB compressed in one day; at that rate 1.5 GB to 2 GiB is four days | emergency fallback (option f) |
| 2 GiB | GitHub refuses the upload; `db_state.py` already refuses first | |

Also trigger Stage 3 early if either: (a) a planned addition is expected to add more than 0.3 GB compressed within a month while the asset is over 0.75 GB; or (b) the Mini's pull plus push takes over 15 minutes on median across a week (its network has slowed).

The raw-size warning (`STORE_WARN_BYTES`, 1.6 GB) fires on every push and so warns about nothing. Proposed, for Chris to approve (not changed here): replace it with a compressed "plan" warning at 0.75 GB and move the "split now" warning from 1.5 GB to 1.0 GiB; keep the 2 GiB refusal. `tools/health_summary.py`'s Store line would follow.

**Projected date of the 1.0 GiB trigger:**

| scenario | assumptions | without Stage 1 | with Stage 1 compaction |
|---|---|---|---|
| Low | steady growth only (0.63 GB raw a year) | 2030 | after 2031 |
| Central | regions +1 GB by end of November 2026, current backfills +0.1 GB, Africa +0.4 GB in Q1 2027, steady rate rising to 0.8 GB a year | Q4 2027 to Q1 2028 (raw about 4.1 to 4.4 GB) | 2029 |
| High | regions +2 GB, Africa +0.8 GB, speech text for four large parliaments +0.5 GB, all within about five months | February to March 2027 | Q3 2027 |

The central path: raw about 3.1 GB at the end of 2026 and 3.7 GB at the end of Q1 2027 (0.75 GB and 0.9 GB compressed), so Stage 2 would start around Q1 2027.

## 3. The options

### (a) Split by country group into several store files (RECOMMENDED, at the trigger)

Five files, each published as its own release asset (`parl-monitor-<shard>.db.gz`), sized from today's data:

| shard | prefixes | raw now | compressed (est.) | growth a year |
|---|---|---:|---:|---:|
| core | UK (no prefix, `sp_ sd_ ni_ cv_ dv_ edm_ pq_ ...`) and every shared table, UN/UPR | 328 MB | 80 MB | 43 MB |
| europe-west | fr de be nl ch at ie eu | 468 MB | 115 MB | 209 MB |
| europe-south-east | es it pt pl hr hu sk | 374 MB | 92 MB | 254 MB |
| north-america-oceania | ca prov us uss au | 508 MB | 125 MB | 87 MB |
| latam | ar bo br cl co do ec gt hn mx nic pa pe sv uy ve latam | 147 MB | 36 MB | 40 MB |

Regional parliaments go in their country's shard (Spanish regions in europe-south-east, Mexican and Peruvian in latam); Africa gets a sixth. Every shard is years from 2 GiB, and a shard can itself be split again the same way. SQLite allows 10 attached databases by default, so core plus up to nine shards.

**How queries keep working.** `db.connect(path)` opens `core` as `main` and ATTACHes each shard file present. SQLite resolves an unqualified table name by searching `main`, then the attached databases in order, so every existing `SELECT ... FROM fr_votes JOIN members ...` and every INSERT/UPDATE keeps working untouched, across shards. Transactions spanning files stay atomic in the default rollback-journal mode (the store does not use WAL).

**The trap, and its guard.** `CREATE TABLE IF NOT EXISTS fr_votes` without a schema name looks only in `main`: run against the attached connection it would create an empty `fr_votes` in core, which `main`-first lookup would then read instead of the real one. So DDL must be routed: a `SHARDS` map in `src/db.py` (prefix to shard) and a helper that schema-qualifies the `CREATE TABLE`/`CREATE INDEX` statements of each `ensure_schema` (SQLite accepts `CREATE INDEX shard.name ON table (...)`). A test opens a sharded fixture and fails if any table exists in two schemas or a prefixed table sits in core.

**Code changes:**
- `src/db.py`: `SHARDS`, `shard_paths()`, ATTACH in `connect()`, DDL routing used by `init_db` and the 34 `ensure_schema` functions (one shared helper; the 67 call sites stay).
- The 22 direct `sqlite3.connect` callers: move to `db.connect`, or confirm they only touch core. `src/country_live.py` (attaches the store itself): attach each shard.
- `tools/db_state.py`: per-shard assets and `.prev` names; `pull(shards)`/`push(shards)`; the sidecar becomes a manifest (`{"shards": {name: {sha256, bytes, gz_sha256, gz_bytes, tables}}}`); `check_lineage`, `live_asset_is_ours`, `_failed_upload_state`, `swap_in_asset` and the fresh-`.prev` rule applied per shard, unchanged in logic; `check_counts` per shard; `stamp_heartbeat` writes core; `size_warnings` per shard and in total; `.store-pulled` per shard.
- `tools/merge_sidecar.py`: merge the manifest shard by shard (the newest publish of each shard wins, as now for the whole).
- `tools/mini_run.sh`: "store changed but not published" per shard; `# mini_run: no-store` stays.
- `tools/health_summary.py`, `tools/coverage.py`: sizes per shard.
- New `tools/store_split.py`: `--split` (one file into shards, verifying every table's row count), `--merge` (the rollback), `--check`.
- Tests: `tests/test_db_state.py` extended per shard; a sharded-fixture run of the store tests.

**Risks:**
- Cross-shard queries: handled by ATTACH; the only cost is the DDL trap above.
- Partial publish: a job that writes core and its shard can publish one and lose the other to a race. Each file stays internally consistent; cross-file links are loose (gap rows, heartbeats, per-country rows in shared tables). Mitigation: publish the country shard first and core last, keep both aside until both verify (the existing keep-aside swap applied to a list), and report a half-publish as the run's failure, as a lost store is reported now.
- Collision and `.prev` recovery: the same rules per asset; the risk is a bug in the generalisation, so the existing tests run per shard.
- GitHub backups: they keep pulling and pushing ALL shards (GitHub's transfers are about 40 s), so the 48 workflows change only in the command line, if at all.
- An old-code reader after the cutover: the manifest carries no top-level `sha256`, and no asset is named `parl-monitor.db.gz`, so old code fails loudly ("no store asset") instead of reading half a store. The rollback copy is named `parl-monitor.db.gz.pre-split`, a name `plan_pull` never takes.

**Job time:** unchanged until Stage 4 (a full pull downloads five files totalling the same bytes).

### (b) Move bulky text into an archive store

Text tables are 575 MB (31%) but grow 55 MB a year; the votes grow ten times faster. Moving columns (speech bodies, gazette text, item bodies) means schema changes in many tables and rewriting every query that reads the text (debate reports, since-the-last-vote, clips, 5CA, briefs). It buys about 140 MB compressed once and almost nothing after. **Not recommended**; the shard layout above already lets a text-heavy country sit in its own file.

### (c) Per-job partial pull and push (RECOMMENDED as Stage 4, needs a)

Each job declares the shards it writes and reads, like the existing `# mini_run: no-store` line: `# mini_run: shards core europe-west`. The wrapper pulls only those (and deletes any other shard file in the runner clone, so a forgotten dependency fails as "no such table" rather than reading a stale copy); `db_state.py --push` publishes only shards whose sha changed. Readers of everything (`editions-session-judge`, `coverage`, `health`, `judge-queue-in`) declare `all`.

**Code changes:** `tools/mini_run.sh` (parse the line, pass shards to `db_state.py --pull`), every `jobs/*.sh` that needs the store (about 60, one comment line each), `tools/db_state.py --push` (skip unchanged shards, already free since the sha is computed anyway).

**Effect on job time (Mini):** a typical country weekly would move core plus one shard, about 200 MB compressed instead of 454 MB (today) or 1.07 GB (at the trigger): about 2 minutes of upload instead of 4 to 5 (today) or 9 to 10 (at the trigger). With about 45 store-writing Mini jobs a week, that is 2 to 5 hours a week of lock time returned, and the 20-minute `PUBLISH_S` reserve stops being a concern. Collisions get rarer too: two jobs collide only if they share a shard (core is the common one).

**Risk:** a job reads a shard it did not declare (fails loudly, fixed by one line); core is still written by nearly every job, so core remains the serialisation point, as the whole store is today.

### (d) Compaction: VACUUM and WITHOUT ROWID (RECOMMENDED now, Stage 1)

Measured on a scratch copy of the store:

| step | raw | compressed (gzip 4) |
|---|---:|---:|
| as published | 1,825 MB | 447 MB |
| `VACUUM` | 1,693 MB (-7%) | 395 MB (-12%) |
| plus the 37 rowid vote tables rebuilt `WITHOUT ROWID` | 1,480 MB (-19%) | 308 MB (-31%) |

VACUUM took about 10 s; the rebuild about 20 s. `WITHOUT ROWID` stores a vote table inside its primary key instead of beside it, removing the duplicate key index (336 MB of autoindex on the vote tables). `pl_votes` already does this (`src/pl_store.py`: about 60 bytes a position against 100). New vote rows are smaller too, so the steady rate falls by about a fifth.

**Code changes:**
- `tools/db_state.py push()`: `VACUUM` before `stamp_heartbeat()` and the sha (or only when `store_sizes` reports over 5% unused), so the published bytes are the compacted ones. At 10 to 20 s it costs less than the upload time it saves (12% of a 4-minute upload is about 30 s).
- Each `src/<cc>_store.py` vote-table `CREATE TABLE` gains `WITHOUT ROWID`, plus a one-off migration in its `ensure_schema` (create new, copy, drop, rename, recreate indexes, guarded by a check of `sqlite_master.sql`), run once by the next job of each country.
- `src/prov_store.py` (`v.rowid` at lines 583 and 598) addresses `prov_votes` rows by rowid: switch to its primary key. No other code uses rowid on a vote table (`prov_member_terms` and `src/ingest/prov_bc.py` keep theirs; that table is not converted).

**Risks:** a missed rowid user (grep found the one; tests on every store module would catch the rest); the first push after the migration changes most bytes of the store, so the lineage guard behaves as after any publish; tables without a primary key cannot be converted (all 37 vote tables have one). Each migration is per table and idempotent, so it can go country by country.

**Effect on job time:** about a third less to upload and download from the first publish.

Pruning was also checked: the store has no free pages, no table holds obviously redundant copies that the raw archive does not also hold, and the raw payloads already live in the separate `raw-archive` release (`tools/raw_state.py`). Dropping old text (for example `ca_gazette_items` before the current parliament) is possible but loses history the monitors cite; not proposed.

### (e) Move off GitHub releases to a bucket

Cloudflare R2 or Backblaze B2 have free tiers of 10 GB with no size limit per object that matters here. It removes the 2 GiB ceiling but not the transfer time, adds a credential on the Mini and on GitHub, and loses what the collision logic leans on: GitHub's per-asset sha256 digest and the instant rename used for the keep-aside copy (a bucket would need versioned objects or copy-then-delete instead). The repo's rule is no paid services, and growth past a free tier would become one. **Not recommended** unless the shards together pass about 5 GB compressed.

### (f) Split the asset, not the store (emergency fallback)

Publish the one `.gz` in parts (`parl-monitor.db.gz.part1..N`, each under 1.9 GB) with the parts listed in the sidecar, and reassemble on pull. Changes only `tools/db_state.py` (upload, verify and keep-aside per part; pull concatenates before decompressing) and its tests: about a day. It lifts the ceiling with no SQL change, but job time keeps growing with the store, and a multi-part swap is less atomic than one asset. **Keep it as the fallback** if the asset passes 1.5 GB before Stage 3 has landed.

## 4. Recommendation and staged plan

Recommended: **(d) now, then (a) at the trigger, then (c)**; (f) only as an emergency; (b) and (e) not at all for now.

**Stage 1: compact (now, about a day of work).**
1. `WITHOUT ROWID` for the 37 vote tables with migrations, `prov_store` off rowid, tests.
2. VACUUM in `db_state.py --push`.
3. Retune the size warnings (section 2) and add per-table sizes to the health DM's Store line from `tools/store_sizes.py --json` (top five tables and the unused share).
4. Expected: about 1.5 GB raw and 310 MB compressed after the first publish; the trigger date moves out by about a year at the central estimate.

**Stage 2: build the split, inactive (when the compressed asset passes 0.75 GB; about 3 to 4 days).**
1. `SHARDS` map, ATTACH in `db.connect`, DDL routing, the two-schemas guard test.
2. `db_state.py` manifest and per-shard pull/push, running with ONE shard (`core` = everything): the code path is live in production, the bytes unchanged.
3. `tools/store_split.py --split/--merge/--check`, run on a laptop copy: every table's row count equal, the full test suite green against the sharded fixture, and a dry run of three weeklies (one per shard family) against split files in a scratch directory.

**Stage 3: cutover (at the trigger, about two hours in a quiet slot).**
1. Pick a slot clear of every Mini plist and workflow cron (not Saturday). Hold the Mini's lock (or unload the plists) and set a repo variable that makes the GitHub store workflows skip (the `MINI_RUN_*` mechanism already does this per job).
2. Pull the store, `store_split.py --split`, `--check`.
3. Rename `parl-monitor.db.gz` to `parl-monitor.db.gz.pre-split` (kept two weeks as the rollback), upload the five shard assets, verify each against GitHub's digest, commit the manifest sidecar in one commit.
4. Release the lock and the workflows; watch the first run of every job for a week (all still pull every shard).
5. Rollback: `store_split.py --merge` over the current shards, publish the single file under the old name with the previous code, revert the merge commit.

**Stage 4: partial pull and push (the week after the cutover).**
Add `# mini_run: shards ...` to the jobs one family at a time, readers-of-everything last, checking each job's next run.

## 5. Monitoring

`python3 tools/store_sizes.py` (top tables, index and unused share), `--groups` (by prefix, the shard arithmetic above), `--json`. It opens the store read-only (`mode=ro`) and never changes it (test: `tests/test_store_sizes.py`). The compressed size is already in the sidecar (`gz_bytes`) and the health DM.
