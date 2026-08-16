# Windows native Chromium build pipeline

Status: pipeline implementation prepared; physical build worker execution pending.

## Delivered

- dedicated self-hosted Windows x64 workflow;
- strict disk, toolchain, and Visual Studio preflight;
- pinned Chromium bootstrap and downstream patch application;
- optimized native chrome and mini_installer targets;
- unsigned test installer upload with size report;
- static contract tests preventing hosted-runner and Electron regression.

## Verification

- repository Python tests: required before publication;
- workflow contract: statically verified on ordinary CI;
- native Windows compile: pending dedicated runner;
- runtime/visual verification: pending produced installer.

No native build success is claimed until the dedicated workflow completes.
