# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.4a0] - 2026-02-24

### Changed

- `find_cli()` now uses `importlib.metadata` to locate pip-installed binary directly
- No longer depends on `~/.local/bin` being on PATH
- PATH lookup kept as fallback for development/cargo-installed binaries

## [0.4.3a0] - 2026-02-24

Version aligned with syster-cli 0.4.3-alpha.

### Changed

- `pip install systree` now automatically installs the CLI binary via `syster-cli` PyPI wheel
- Removed cargo/crates.io fallback — binary comes from PyPI platform wheel
- Simplified `find_cli()` to just check PATH

## [0.4.0a2] - 2026-02-24

Version aligned with syster-cli 0.4.0-alpha.

### Changed

- `find_cli()` now verifies CLI version matches before use
- Mismatched or missing CLI auto-installs correct version from crates.io
- Auto-install CLI from crates.io via `cargo install`

### Fixed

- Fixed UUID normalization in double-export stability test

## [0.3.2a0] - 2026-02-10

Version aligned with syster-cli 0.3.2-alpha.

### Added

- `export_yaml()` function for YAML format export
- `export_ast()` function to get raw AST JSON output
- `get_stdlib_path()` to see which stdlib is being used
- `get_cache_dir()` to get the cache directory path
- `self_contained` parameter for all export functions
  - When `True`, includes standard library in export for standalone output
- GitHub Actions CI/CD workflows using syster-pipelines
- Comprehensive tests for self-contained exports

### Changed

- Stdlib now defaults to cache directory (`~/.cache/systree/sysml.library`)
- Auto-downloads stdlib from GitHub if not found in cache
- Updated test expectations to match CLI 0.3.2-alpha output format
  - Accept both `PartDef` and `PartDefinition` as valid kinds
  - Use `declaredName=` instead of `name=` in XMI assertions

### Fixed

- Fixed integration tests for CLI 0.3.2-alpha compatibility

## [0.1.1] - 2026-02-09

### Added

- Initial release
- `analyze()` - Analyze SysML/KerML files
- `get_symbols()` - Extract typed symbol objects
- `export_xmi()` - Export to XMI format
- `export_jsonld()` - Export to JSON-LD format
- `export_kpar()` - Export to KPAR format
- `import_file()` - Import and validate interchange files
- `import_symbols()` - Import and extract symbols
- `import_export()` - Direct roundtrip with ID preservation
- `decompile()` - Decompile interchange to SysML text
- `download_stdlib()` - Download SysML v2 standard library
- Auto-detection of stdlib from environment, cache, or monorepo
