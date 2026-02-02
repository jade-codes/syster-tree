# Systree

Python wrapper for the Syster CLI - SysML v2 and KerML analysis.

## Installation

```bash
pip install systree
```

Or from source:

```bash
cd systree
pip install -e ".[dev]"
```

### Installing the CLI

```bash
cargo install syster-cli
```

Or via make:

```bash
make install-cli
```

## Python Usage

### Basic Analysis

```python
from systree import analyze

# Analyze a single file
result = analyze("model.sysml")
print(f"Files: {result.file_count}, Symbols: {result.symbol_count}")
print(f"Errors: {result.error_count}, Warnings: {result.warning_count}")
print(f"Diagnostics: {result.diagnostics}")

# Analyze without standard library (faster)
result = analyze("model.sysml", stdlib=False)

# With custom stdlib path
result = analyze("model.sysml", stdlib_path="/path/to/sysml.library")
```

### Extract Symbols

```python
from systree import get_symbols

# Get typed symbol objects
file_symbols = get_symbols("model.sysml", stdlib=False)
for fs in file_symbols:
    print(f"File: {fs.path}")
    for sym in fs.symbols:
        print(f"  {sym.kind}: {sym.qualified_name} @ L{sym.start_line}:{sym.start_col}")
        if sym.supertypes:
            print(f"    extends: {sym.supertypes}")
```

### Export Formats

```python
from systree import export_xmi, export_jsonld, export_kpar

# Export to XMI (returns XML string)
xmi = export_xmi("model.sysml")

# Export to JSON-LD (returns list of elements)
jsonld = export_jsonld("model.sysml")

# Export to KPAR (returns bytes - ZIP archive)
kpar_bytes = export_kpar("model.sysml")
with open("model.kpar", "wb") as f:
    f.write(kpar_bytes)
```

### Import Interchange Files

```python
from systree import import_file, import_symbols, decompile

# Import and validate XMI/KPAR/JSON-LD
result = import_file("model.xmi")
print(f"Imported {result.symbol_count} elements")

# Import and extract symbols
file_symbols = import_symbols("model.xmi")
for fs in file_symbols:
    for sym in fs.symbols:
        print(f"  {sym.kind}: {sym.qualified_name}")

# Decompile back to SysML v2 text
sysml_source = decompile("model.xmi")
print(sysml_source)
```

### Error Handling

```python
from systree import analyze, CliNotFoundError, AnalysisError

try:
    result = analyze("model.sysml")
except CliNotFoundError:
    print("Run: make install-cli")
except AnalysisError as e:
    print(f"Analysis failed: {e}")
```

## API Reference

### `analyze(path, *, verbose=False, stdlib=True, stdlib_path=None) -> AnalysisResult`

Analyze SysML/KerML files.

**Returns:** `AnalysisResult` with `file_count`, `symbol_count`, `error_count`, `warning_count`, `diagnostics`

### `get_symbols(path, *, stdlib=True, stdlib_path=None) -> list[FileSymbols]`

Extract typed symbol objects from files.

**Returns:** List of `FileSymbols`, each containing `path` and `symbols: list[Symbol]`

### `export_xmi(path, *, stdlib=True, stdlib_path=None) -> str`

Export model to XMI XML format.

### `export_jsonld(path, *, stdlib=True, stdlib_path=None) -> list | dict`

Export model to JSON-LD format.

### `export_kpar(path, *, stdlib=True, stdlib_path=None) -> bytes`

Export model to KPAR (Kernel Package Archive) format. Returns ZIP bytes.

### `import_file(path, *, stdlib=True, stdlib_path=None) -> AnalysisResult`

Import and validate an interchange file (XMI, KPAR, or JSON-LD).

### `import_symbols(path, *, stdlib=True, stdlib_path=None) -> list[FileSymbols]`

Import interchange file and extract typed symbol objects.

### `decompile(path, *, stdlib=True, stdlib_path=None) -> str`

Decompile interchange file back to SysML v2 source text.

### Models

#### `AnalysisResult`
- `file_count: int`
- `symbol_count: int`
- `error_count: int`
- `warning_count: int`
- `diagnostics: list[dict]`

#### `Symbol`
- `name: str` - Simple name
- `qualified_name: str` - Full path (e.g., `"Package::Class"`)
- `kind: str` - Symbol kind (`"Package"`, `"PartDef"`, etc.)
- `file: str | None` - Source file
- `start_line: int | None` - Start line (1-based)
- `start_col: int | None` - Start column (1-based)
- `end_line: int | None` - End line
- `end_col: int | None` - End column
- `supertypes: list[str]` - Supertype names

#### `FileSymbols`
- `path: str` - File path
- `symbols: list[Symbol]` - Symbols in file

### Exceptions

- `SystreeError` - Base exception
- `CliNotFoundError` - syster CLI not installed
- `AnalysisError` - Analysis failed

## Development

```bash
make install-cli  # Install syster CLI
make dev          # Install with dev deps
make test         # Run tests
```

## License

MIT
