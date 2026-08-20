# Example module package

The smallest complete Sunshine module package: a note that stays in the profile.

```text
module-package/
├─ module.json    the manifest (schema 3)
├─ index.html     the entry document
├─ app.css
├─ app.js
└─ icon.svg
```

Nothing here is compiled, bundled, transpiled or minified. These five files are
what the browser parses and runs.

## Try it

```sh
scripts/install_module.py validate first_party/templates/module-package
scripts/install_module.py install first_party/templates/module-package --profile <profile>
```

## Publish it

Zip the *contents* of the folder, not the folder itself — `module.json` has to
be at the root of the archive.

```sh
cd first_party/templates/module-package && zip -r ../scratchpad.zip .
```

## Write your own

Copy this folder, change `id` to `<your-vendor>.<name>` — `sunshine.*` is
reserved for the compiled capabilities in `first_party/modules/` — and keep
`capabilities` empty: an installed package is served as ordinary web content and
receives no browser privilege. `docs/MODULE_PACKAGE_CONTRACT.md` states the
format in full, and the validator refuses anything it does not allow, naming the
rule.
