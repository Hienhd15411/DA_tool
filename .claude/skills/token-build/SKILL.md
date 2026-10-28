---
name: token-build
description: Set up or run the token build pipeline. Transform the DTCG tokens/*.json (source of truth) into platform artifacts (CSS variables, Tailwind @theme, JS/TS, iOS Asset Catalog, Android, Compose) with Style Dictionary / Tokens Studio / W3C DTCG export. Use when the user wants to generate platform theme files from tokens, wire token CI, or multi-platform token output.
---

# Skill: Token Build

> **Step 0: is the kit here?** This skill reads files from the kit. Check once:
> `ls design/uxui-kit/tokens >/dev/null 2>&1 && echo KIT_OK || echo KIT_MISSING`
> On `KIT_MISSING` only the skill folders were installed, which is what
> `npx skills add` does. Say so plainly, point the user at
> `npx ux-ui-agent-skills init` or the plugin install, and stop. Do not guess the
> contents of a file you could not open.

Turn the DTCG token source of truth into platform-ready outputs. Tokens are authored once; every platform output is generated.

## Steps
1. Read `design/uxui-kit/workflows/token-build.md` (architecture, tool options, resolution rules, output targets, CI).
2. Pick the tool: **Style Dictionary** (multi-platform, the default), **Tokens Studio** (Figma-owned tokens; pairs with `figma-integration`), W3C DTCG export, or a small custom script (model on `design/uxui-kit/scripts/validate_tokens.py`).
3. Honor the resolution rules: resolve aliases to final values per platform; expose semantic + component tokens (primitives stay internal); emit base + dark/brand/density overrides (`design/uxui-kit/tokens/theming.json`) as deltas only; format by `$type`.
4. Generate the requested target(s): CSS `:root` vars, Tailwind v4 `@theme`, typed JS/TS, iOS Asset Catalog + `Color.DS`/`Spacing`, Android `colors.xml`/Compose theme.
5. Wire CI: on `design/uxui-kit/tokens/*.json` change, run `design/uxui-kit/scripts/validate_tokens.py`, regenerate, fail if committed artifacts are stale; gate colors with `design/uxui-kit/scripts/contrast.py`.

## Verification (definition of done)
- `python3 design/uxui-kit/scripts/validate_tokens.py` passes (no unresolved aliases).
- Regenerating produces no diff vs. committed artifacts.
- Dark/brand/density outputs contain only deltas, not full duplicates.
