<!-- ops-sync:begin — synced from portolan-sdi/portolan-ops. Edit there, not here. -->
# Portolan agent norms

All agents MUST read this document before starting work, with no exceptions, ever. (Claude Code does not read `AGENTS.md` but imports this file via a one-line `CLAUDE.md`.) Most of this content is synced downstream from `portolan-ops`. Put repo-specific instructions in `AGENTS.md`, never in `CLAUDE.md`, which the sync overwrites.

## Ground rules

Agents MUST read the complete contents of [norms](https://github.com/portolan-sdi/portolan-ops/blob/main/norms) and [policies](https://github.com/portolan-sdi/portolan-ops/blob/main/policies/) before starting work, with no exceptions, ever.

The [portolan-spec](https://github.com/portolan-sdi/portolan-spec) repo is the absolute ground truth for the Portolan spec. All other tools are downstream of it.

Before documenting any command, flag, or API, verify that it exists.

Use conventional commits always.

All tickets and PRs MUST follow the [templates](https://github.com/portolan-sdi/portolan-ops/blob/main/templates/).

GitHub applies issue forms only in the web UI. With `gh issue create`, write each form field as a `### <field label>` heading, in the form's order. Include `### Priority` with one of `P0` to `P3` from the [priority rubric](https://github.com/portolan-sdi/portolan-ops/blob/main/norms/repos.md#priority). Pass the form's type label with `--label`, and pass the body with `--body-file`. The writing hook denies a body that skips its form, and issue governance flags one.

## Org-wide facts

The canonical homepage is <https://www.portolan-sdi.org/>. Canonical URLs live in [copy/urls.md](https://github.com/portolan-sdi/portolan-ops/blob/main/copy/urls.md). Do not hardcode variants.

Community discussion happens in the [Portolan Google Group](https://groups.google.com/g/portolan) and the [Portolan channel](https://cloudnativegeo.slack.com/archives/C0A1JBH9529) in Cloud-Native Geo Slack. Planning happens in [org-level GitHub projects](https://github.com/orgs/portolan-sdi/projects/1).

Files between `ops-sync` markers are synced from [portolan-ops](https://github.com/portolan-sdi/portolan-ops). They are overwritten on every sync run. To change one, edit it in portolan-ops.

One canonical home per fact. If a value like a color, URL, or policy line exists in portolan-ops, link to it rather than copying it.
<!-- ops-sync:end -->

## This Repository

The git-backed metadata and tools for the Portolan mirror of GLC_FCS30D, published at
<https://data.source.coop/portolan-mirrors/glc-fcs30d/catalog.json>.

### The publish boundary

`catalog/` is the published catalog. Everything in it is published, and
nothing outside it ever is. Do not move a file into `catalog/` to make it
publish, and do not add a path outside `publish_dir` to `tools/publish.py`.

### What is generated, and from what

- `tools/pipeline.py` converted and uploaded the 24,986 COGs. It wrote one JSON line
  per COG; those lines are committed as `data/cogs.jsonl`.
- `tools/build_stac.py` writes `catalog/glc_fcs30d/collection.json`, the `updated`
  field of `catalog/catalog.json`, and the gitignored item tree
  (`catalog/glc_fcs30d/<year>/`) from `data/cogs.jsonl`, `data/zenodo-record.json`
  and `data/derived-assets.json`. Never hand-edit a generated file; change the
  generator or its inputs. CI regenerates the tree and fails on any diff.
- `tools/items_parquet.py` and `tools/overview.py` write the item mirror, the
  overview COG and the thumbnail, and record their file fields in
  `data/derived-assets.json`. Rerun `tools/build_stac.py` after either.
- The class table lives once, in `tools/classes.py`.

### Data never enters git

Never commit a GeoParquet or COG file. The thumbnail PNG is the one binary in
`catalog/`, because the link gate needs it on disk.

### The conformance allow-list

`ACCEPTED` in `tests/test_conformance.py` ships empty. Never add an entry
without a matching row in `docs/conformance.md` giving the rule, where it
fires, why it is accepted, and the issue tracking its removal.

### Published agent guides

Every claim in a `catalog/**/AGENTS.md` is either quoted from a source or
measured from the data. An invented join key or column name produces a
confident wrong answer that nothing downstream catches.
