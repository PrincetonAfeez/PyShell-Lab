# PyShell Lab JSON Schemas

These files describe the structured command objects that sit between parsing and execution in PyShell Lab. They use **JSON Schema draft 2020-12** and are dependency-free: no runtime package is required to read them.

## Files

| File | Purpose |
|------|---------|
| [`command.schema.json`](command.schema.json) | Top-level command node (`SimpleCommand`, `Pipeline`, `BackgroundCommand`, or `CommandSequence`); self-contained for validation |
| [`common.schema.json`](common.schema.json) | Same `$defs` as fragments for editing; [`command.schema.json`](command.schema.json) inlines them for portable validation |

Each schema file declares `"$schema": "https://json-schema.org/draft/2020-12/schema"`.

Serialized objects use a `"kind"` discriminator (`simple`, `pipeline`, `background`, `sequence`) so validators can tell node types apart.

## Example

The schemas describe **parser AST nodes**, not a flat `{command, args}` object. A minimal valid document for `echo hello > out.txt` is [`examples/command.example.json`](../examples/command.example.json):

```json
{
  "kind": "simple",
  "words": [
    {
      "parts": [
        { "text": "echo", "quote": "none" },
        { "text": "hello", "quote": "none" }
      ]
    }
  ],
  "redirections": [
    {
      "operator": ">",
      "target": {
        "parts": [{ "text": "out.txt", "quote": "none" }]
      }
    }
  ]
}
```

From the repository root, install the optional validator and run:

```bash
python -m pip install -r Schema/requirements-validation.txt
check-jsonschema --schemafile Schema/command.schema.json examples/command.example.json
```

Expected result: the command exits with status 0 and prints `ok -- validation done` (or similar success output from your validator).

Equivalent using the module form (useful when `check-jsonschema` is not on `PATH`):

```bash
python -m check_jsonschema --schemafile Schema/command.schema.json examples/command.example.json
```

## Dependencies

The schema files themselves have no runtime dependencies.

Optional validation examples may use `check-jsonschema` or another JSON Schema draft 2020-12 compatible validator. For a pinned toolchain, install from [`requirements-validation.txt`](requirements-validation.txt):

```bash
python -m pip install -r Schema/requirements-validation.txt
```

## Quick start

Install the optional validator, then validate the example above or any other command JSON:

```bash
python -m pip install -r Schema/requirements-validation.txt
python -m check_jsonschema --schemafile Schema/command.schema.json examples/command.example.json
```

If `check-jsonschema` is on your `PATH`:

```bash
check-jsonschema --schemafile Schema/command.schema.json examples/command.example.json
```

Validate other documents the same way:

```bash
check-jsonschema --schemafile Schema/command.schema.json path/to/your-command.json
```

## Validation workflow

1. **Choose the schema matching the object type**
   - [`command.schema.json`](command.schema.json) — parsed command AST nodes (`SimpleCommand`, `Pipeline`, `BackgroundCommand`, `CommandSequence`). Example: [`examples/command.example.json`](../examples/command.example.json).
   - [`common.schema.json`](common.schema.json) — shared `$defs` only; not a top-level document schema. Use [`command.schema.json`](command.schema.json) when validating files.
   - **Not defined in this repository:** `result.schema.json` (command exit/output records), `session.schema.json` (interactive `ShellState`), and `config.schema.json` (`~/.pyshellrc` / startup). PyShell Lab builds commands from shell source text and keeps session/config in Python dataclasses, not JSON interchange. Add matching schemas under `Schema/` if you introduce JSON for those objects.

2. **Validate the JSON** with any JSON Schema draft **2020-12** validator. From the repo root:

   ```bash
   python -m pip install -r Schema/requirements-validation.txt
   check-jsonschema --schemafile Schema/command.schema.json path/to/object.json
   ```

3. **Interpret the result**
   - Success (exit code 0) — the document matches the schema; safe for tooling that expects that shape.
   - Failure — treat as an input/schema mismatch: read the validator’s error path, fix the JSON (or the schema if the contract changed), and re-run until validation passes.

PyShell does not validate JSON at shell startup; validation is for reviewers, CI, or external tools that exchange command AST documents.

## Relation to the Python AST

The in-memory AST lives in `src/pyshell_lab/ast.py` as dataclasses. These JSON schemas document the same shapes for tooling, reviews, and interchange. The shell does not load command JSON at runtime today; the lexer and parser build the AST from shell source text.

## License

These schema files are part of PyShell Lab and are licensed under the MIT License. See [`../LICENSE`](../LICENSE) for details.
