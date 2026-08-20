#!/usr/bin/env python3
"""Sunshine module packages: what a user installs, and what installing does.

`docs/decisions/0013-module-installation.md` settled that a Sunshine module
comes in two kinds. A *compiled capability* is what `first_party/` has always
described: a Chromium-integrating surface, command or profile service, built
with the browser, and worth a build because it changes the browser itself. An
*installed package* is a folder or a zip the user picks, validated and unpacked
into the profile, and served as ordinary web content from
`chrome-untrusted://sunshine-module/<id>/`. Installing one costs no build.

This file is the whole of what installing means, written where it can be run
and tested before the browser can run anything: the package format, the checks
that decide whether a package may be installed, and the record store that
remembers what is installed. `scripts/install_module.py` is its command line,
and the browser-side installer mirrors it rather than re-deriving it. Keeping
the rules here instead of only in a contract document is deliberate -- an
install pipeline stated in prose cannot be run against a real zip until the
surface exists, and by then the rules get re-invented rather than reread.

Three things this file deliberately does not do.

**It grants nothing.** A package declares `capabilities: []` and a `security`
block that is the schema 2 block, checked by the same function that checks a
first-party manifest. `docs/SECURITY_ARCHITECTURE_CONTRACT.md` section 4 names a
second permission vocabulary as the failure this contract set is most exposed
to, so there is one vocabulary and packages are held to the strict end of it.

**It registers no scheme.** SEC-13 and ADR 0003 stand: the origin is Chromium's
own `chrome-untrusted://`, and `sunshine-module` is a host name inside it, which
is a thing Chromium registers and Sunshine does not.

**It executes nothing.** Validation reads bytes. No package code runs here, and
none runs during installation in the browser either -- a package's first
execution is when the user opens it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]

PACKAGE_SCHEMA_VERSION = 3
RECORD_SCHEMA_VERSION = 1

MANIFEST_NAME = "module.json"
RECORD_NAME = "modules.json"
# Under the Chromium profile directory. Chromium owns the profile; Sunshine owns
# one directory inside it and nothing else.
INSTALL_SUBDIRECTORY = "Sunshine/Modules"
MODULE_ORIGIN = "chrome-untrusted://sunshine-module"

# What a record store does with a file it was not written to understand. Both
# policies are the ones `scripts/workspace_model.py` already settled on for
# Sunshine-owned profile state, for the same reasons: a newer browser's file is
# preserved rather than truncated to what this version understands, and an
# unreadable one is rebuilt from the installs still on disk rather than being
# taken as "nothing is installed" and silently discarding the user's modules.
UNKNOWN_SCHEMA_POLICY = "preserve_without_rewrite"
CORRUPTION_POLICY = "recover_by_rescan"

# A module id is `<vendor>.<name>`. The vendor half exists so two authors can
# both publish "notes" without colliding, and so an installed package can never
# be mistaken for a compiled capability: those are `sunshine.*`, and that vendor
# is refused here.
MODULE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:[-.][a-z0-9]+)*$")
RESERVED_VENDORS = frozenset({"sunshine", "chrome", "chromium"})
SEMVER = re.compile(r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$")

# A path inside a package. No drive letters, no backslashes, no leading slash,
# no `..`, no dot-files, and nothing that needs normalising before it is safe --
# the check is that the name is already the safe spelling, not that it can be
# made into one.
PACKAGE_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*$")

ALLOWED_SUFFIXES = frozenset({
    ".html", ".css", ".js", ".json", ".svg", ".png", ".jpg", ".jpeg",
    ".webp", ".gif", ".woff2", ".txt", ".md",
})
WEB_TEXT_SUFFIXES = frozenset({".html", ".css", ".js"})

# A package ships the files the browser runs. These are the files of a tree that
# has to be built first, and a package containing one is either half a source
# checkout or a build step the user is expected to run -- which is the thing
# ADR 0013 exists to remove. Refusing them by name says so at install time
# rather than serving a directory of TypeScript the browser cannot execute.
BUILD_INPUT_NAMES = frozenset({
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "tsconfig.json", "vite.config.js", "vite.config.ts", "webpack.config.js",
    "rollup.config.js", "gulpfile.js", "Gruntfile.js", "BUILD.gn", "Makefile",
    "CMakeLists.txt",
})
BUILD_INPUT_DIRECTORIES = frozenset({"node_modules", ".git", ".svn", "src"})

MAX_FILES = 2000
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_PATH_DEPTH = 8
# One entry expanding more than this from its stored size is a decompression
# bomb rather than a well-compressed asset. Measured against real assets, plain
# text reaches roughly 5:1 and an already-compressed image never approaches it.
MAX_EXPANSION_RATIO = 200

# Every way an install can be refused. The set is closed on purpose: the surface
# shows a message per code and the command line exits naming one, so a new
# failure mode is a deliberate addition to the contract rather than a new string
# appearing in a dialog.
REFUSAL_CODES = frozenset({
    "NOT_A_PACKAGE",
    "MANIFEST_MISSING",
    "MANIFEST_INVALID",
    "ID_RESERVED",
    "ENTRY_MISSING",
    "ICON_MISSING",
    "PATH_UNSAFE",
    "TYPE_NOT_ALLOWED",
    "BUILD_INPUT",
    "TOO_MANY_FILES",
    "TOO_LARGE",
    "DYNAMIC_CODE",
    "REMOTE_RESOURCE",
    "ALREADY_INSTALLED",
    "NOT_INSTALLED",
    "VERSION_NOT_NEWER",
    "INTEGRITY_MISMATCH",
    "RECORD_UNREADABLE",
    "RECORD_FROM_A_LATER_VERSION",
})


class PackageError(ValueError):
    """A package that may not be installed, and the reason in one token."""

    def __init__(self, code: str, message: str) -> None:
        if code not in REFUSAL_CODES:
            raise AssertionError(f"undeclared refusal code: {code}")
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


_SECURITY_VALIDATOR = None
_WEB_ASSET_RULES = None


def _security_validator():
    """Schema 2's security check, reused rather than restated.

    The two manifests are different documents with different required keys, but
    the six-key security block means exactly the same thing in both, and its
    refusals -- `allowlist` until a host-allowlist contract exists,
    `user_selected` until a file broker exists, a credential never -- are the
    ones a package needs most. Importing it keeps a package from ever being
    held to a weaker version of a rule the compiled modules pass.
    """

    global _SECURITY_VALIDATOR
    if _SECURITY_VALIDATOR is not None:
        return _SECURITY_VALIDATOR
    path = ROOT / "scripts/validate_first_party_modules.py"
    spec = importlib.util.spec_from_file_location("validate_first_party_modules", path)
    if spec is None or spec.loader is None:  # pragma: no cover - packaging error
        raise RuntimeError("unable to load the first-party module validator")
    module = importlib.util.module_from_spec(spec)
    # Registered before it is executed: a dataclass defined in a module that is
    # not in sys.modules cannot resolve its own annotations, and fails at import
    # rather than at use.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _SECURITY_VALIDATOR = module
    return module


def _web_asset_rules():
    """SEC-14's patterns, from the guard that owns them.

    `scripts/verify_web_asset_security.py` decides what "no dynamically
    constructed code and no remote resource" means for a Sunshine-authored
    asset. A package's assets are not Sunshine-authored, but they are served
    from a Sunshine-owned origin to a user who installed them on Sunshine's
    word, so they are held to the same rule -- and to the same patterns, so the
    two cannot drift into disagreeing about what `eval` is.
    """

    global _WEB_ASSET_RULES
    if _WEB_ASSET_RULES is not None:
        return _WEB_ASSET_RULES
    path = ROOT / "scripts/verify_web_asset_security.py"
    spec = importlib.util.spec_from_file_location("verify_web_asset_security", path)
    if spec is None or spec.loader is None:  # pragma: no cover - packaging error
        raise RuntimeError("unable to load the web asset guard")
    module = importlib.util.module_from_spec(spec)
    # Registered before it is executed: a dataclass defined in a module that is
    # not in sys.modules cannot resolve its own annotations, and fails at import
    # rather than at use.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _WEB_ASSET_RULES = module
    return module


@dataclass(frozen=True)
class PackageFile:
    path: str
    size: int
    stored_size: int


@dataclass(frozen=True)
class Package:
    """A validated package that has not been installed yet."""

    manifest: dict
    files: tuple[PackageFile, ...]
    integrity: str
    source_path: Path
    packed: bool

    @property
    def id(self) -> str:
        return self.manifest["id"]

    @property
    def version(self) -> str:
        return self.manifest["version"]

    @property
    def display_name(self) -> str:
        return self.manifest["display_name"]

    @property
    def total_bytes(self) -> int:
        return sum(entry.size for entry in self.files)

    def url(self) -> str:
        """Where the browser serves this package's entry document from."""

        return f"{MODULE_ORIGIN}/{self.id}/{self.manifest['entry']}"


# --- Reading a package -------------------------------------------------------


def _check_path(name: str) -> None:
    if not PACKAGE_PATH.fullmatch(name):
        raise PackageError("PATH_UNSAFE", f"unsafe path in package: {name!r}")
    parts = PurePosixPath(name).parts
    if len(parts) > MAX_PATH_DEPTH:
        raise PackageError("PATH_UNSAFE", f"path nested deeper than {MAX_PATH_DEPTH}: {name}")
    if any(part in BUILD_INPUT_DIRECTORIES for part in parts[:-1]):
        raise PackageError("BUILD_INPUT", f"a package ships built files, not a source tree: {name}")
    leaf = parts[-1]
    if leaf in BUILD_INPUT_NAMES:
        raise PackageError("BUILD_INPUT", f"a package ships built files, not a build input: {name}")
    if PurePosixPath(leaf).suffix.lower() not in ALLOWED_SUFFIXES:
        raise PackageError("TYPE_NOT_ALLOWED", f"a package may not contain {leaf!r}")


def _check_size(name: str, size: int, stored_size: int, total: int) -> None:
    if size > MAX_FILE_BYTES:
        raise PackageError("TOO_LARGE", f"{name} is larger than {MAX_FILE_BYTES} bytes")
    if total > MAX_TOTAL_BYTES:
        raise PackageError("TOO_LARGE", f"the package unpacks to more than {MAX_TOTAL_BYTES} bytes")
    if stored_size > 0 and size // stored_size > MAX_EXPANSION_RATIO:
        raise PackageError("TOO_LARGE", f"{name} expands more than {MAX_EXPANSION_RATIO}:1")


def _zip_contents(path: Path) -> dict[str, tuple[bytes, int]]:
    contents: dict[str, tuple[bytes, int]] = {}
    total = 0
    with zipfile.ZipFile(path) as archive:
        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
        if len(entries) > MAX_FILES:
            raise PackageError("TOO_MANY_FILES", f"more than {MAX_FILES} files in the package")
        for entry in entries:
            name = entry.filename
            # A symlink survives a zip as a mode in the external attributes, and
            # a package that can link out of its own directory is a package that
            # can serve any file the browser can read.
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise PackageError("PATH_UNSAFE", f"symbolic link in package: {name}")
            _check_path(name)
            if name in contents:
                raise PackageError("PATH_UNSAFE", f"the package holds {name} twice")
            total += entry.file_size
            _check_size(name, entry.file_size, entry.compress_size, total)
            data = archive.read(entry)
            if len(data) != entry.file_size:
                raise PackageError("NOT_A_PACKAGE", f"{name} does not match its declared size")
            contents[name] = (data, entry.compress_size)
    return contents


def _directory_contents(path: Path) -> dict[str, tuple[bytes, int]]:
    contents: dict[str, tuple[bytes, int]] = {}
    total = 0
    found = sorted(item for item in path.rglob("*") if not item.is_dir())
    if len(found) > MAX_FILES:
        raise PackageError("TOO_MANY_FILES", f"more than {MAX_FILES} files in the package")
    for item in found:
        name = item.relative_to(path).as_posix()
        if item.is_symlink():
            raise PackageError("PATH_UNSAFE", f"symbolic link in package: {name}")
        _check_path(name)
        size = item.stat().st_size
        total += size
        _check_size(name, size, size, total)
        contents[name] = (item.read_bytes(), size)
    return contents


def _integrity(contents: dict[str, tuple[bytes, int]]) -> str:
    """A digest over the whole package, not over one file at a time.

    The name is hashed with the bytes so that renaming a file changes the
    digest, and the length of each name is hashed before it so that two
    different splits of the same concatenation cannot collide.
    """

    digest = hashlib.sha256()
    for name in sorted(contents):
        data = contents[name][0]
        digest.update(f"{len(name)}:{name}:{len(data)}:".encode("utf-8"))
        digest.update(data)
    return f"sha256:{digest.hexdigest()}"


def validate_manifest(payload: object) -> dict:
    """Schema 3, the manifest a package carries.

    Schema 2 is the compiled module's manifest and stays as it is. A package
    answers different questions -- it has a version, an entry document and an
    author who is not Sunshine -- and shares the two answers that matter for
    trust: it declares no capability, and it makes the same six security
    statements every Sunshine module makes.
    """

    required = {"schema_version", "id", "display_name", "version", "description",
                "owner", "kind", "entry", "capabilities", "security"}
    optional = {"icon"}
    if not isinstance(payload, dict):
        raise PackageError("MANIFEST_INVALID", f"{MANIFEST_NAME} must hold an object")
    missing = sorted(required - payload.keys())
    unknown = sorted(payload.keys() - required - optional)
    if missing or unknown:
        raise PackageError("MANIFEST_INVALID", f"missing={missing}, unknown={unknown}")
    if payload["schema_version"] != PACKAGE_SCHEMA_VERSION:
        raise PackageError("MANIFEST_INVALID", f"schema_version must be {PACKAGE_SCHEMA_VERSION}")

    module_id = payload["id"]
    if not isinstance(module_id, str) or not MODULE_ID.fullmatch(module_id):
        raise PackageError("MANIFEST_INVALID", "id must be <vendor>.<name>, lowercase")
    if module_id.split(".", 1)[0] in RESERVED_VENDORS:
        raise PackageError(
            "ID_RESERVED",
            f"{module_id.split('.', 1)[0]}.* names a compiled capability and cannot be installed",
        )

    for field in ("display_name", "description"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise PackageError("MANIFEST_INVALID", f"{field} must be a non-empty string")
    if len(payload["display_name"]) > 64 or len(payload["description"]) > 240:
        raise PackageError("MANIFEST_INVALID", "display_name or description is too long to show")
    if not isinstance(payload["version"], str) or not SEMVER.fullmatch(payload["version"]):
        raise PackageError("MANIFEST_INVALID", "version must be MAJOR.MINOR.PATCH")
    if payload["owner"] != "third_party":
        raise PackageError("MANIFEST_INVALID", "an installed package declares owner third_party")
    if payload["kind"] != "package":
        raise PackageError("MANIFEST_INVALID", "kind must be package")

    entry = payload["entry"]
    if not isinstance(entry, str) or not entry.endswith(".html"):
        raise PackageError("MANIFEST_INVALID", "entry must name an .html document in the package")
    _check_path(entry)
    if "icon" in payload:
        icon = payload["icon"]
        if not isinstance(icon, str) or PurePosixPath(icon).suffix.lower() not in {".png", ".svg"}:
            raise PackageError("MANIFEST_INVALID", "icon must be a .png or .svg in the package")
        _check_path(icon)

    # SEC-4: a `chromium.*` capability is a Chromium privilege, and nothing a
    # user installs at runtime is given one. The field is still required, and
    # still has to be written, because a manifest that omits it reads exactly
    # like one that was never asked -- the rule schema 2 states about silence.
    if payload["capabilities"] != []:
        raise PackageError(
            "MANIFEST_INVALID",
            "an installed package declares no capability; capabilities must be []",
        )

    validator = _security_validator()
    try:
        validator.validate_security(payload["security"], MANIFEST_NAME)
    except validator.ModuleValidationError as error:
        raise PackageError("MANIFEST_INVALID", str(error)) from error
    if payload["security"]["remote_content"] is not False:
        raise PackageError("MANIFEST_INVALID", "an installed package hosts no remote content")
    return payload


def _check_web_assets(contents: dict[str, tuple[bytes, int]]) -> None:
    rules = _web_asset_rules()
    for name in sorted(contents):
        if PurePosixPath(name).suffix.lower() not in WEB_TEXT_SUFFIXES:
            continue
        try:
            text = contents[name][0].decode("utf-8")
        except UnicodeDecodeError as error:
            raise PackageError("NOT_A_PACKAGE", f"{name} is not UTF-8 text") from error
        for number, line in enumerate(text.splitlines(), start=1):
            for pattern, why in rules.DYNAMIC_CODE:
                if pattern.search(line):
                    raise PackageError("DYNAMIC_CODE", f"{name}:{number}: {why} (SEC-14)")
            if rules.ALLOWED_REMOTE_CONTEXT.match(line):
                continue
            for url in rules.REMOTE_URL.findall(line):
                raise PackageError(
                    "REMOTE_RESOURCE", f"{name}:{number}: loads {url} from the network (SEC-14)"
                )


def read_package(path: Path) -> Package:
    """Everything that decides whether this package may be installed.

    Order matters. Structure is checked before the manifest is read, because a
    package whose paths cannot be trusted cannot be trusted to hold a manifest
    either; the manifest is checked before the assets, so that a package that
    was never a package fails saying so rather than failing on line 40 of a file
    it should not have been read for.
    """

    path = Path(path)
    if path.is_dir():
        contents = _directory_contents(path)
        packed = False
    elif path.is_file() and zipfile.is_zipfile(path):
        contents = _zip_contents(path)
        packed = True
    else:
        raise PackageError("NOT_A_PACKAGE", f"{path} is neither a package folder nor a zip")

    if MANIFEST_NAME not in contents:
        raise PackageError("MANIFEST_MISSING", f"no {MANIFEST_NAME} at the root of the package")
    try:
        payload = json.loads(contents[MANIFEST_NAME][0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackageError("MANIFEST_INVALID", f"{MANIFEST_NAME} is not readable JSON: {error}") from error
    manifest = validate_manifest(payload)

    if manifest["entry"] not in contents:
        raise PackageError("ENTRY_MISSING", f"the package has no {manifest['entry']}")
    if "icon" in manifest and manifest["icon"] not in contents:
        raise PackageError("ICON_MISSING", f"the package has no {manifest['icon']}")
    _check_web_assets(contents)

    files = tuple(
        PackageFile(path=name, size=len(contents[name][0]), stored_size=contents[name][1])
        for name in sorted(contents)
    )
    return Package(
        manifest=manifest,
        files=files,
        integrity=_integrity(contents),
        source_path=path.resolve(),
        packed=packed,
    )


# --- What the user is asked to agree to --------------------------------------


def consent_summary(package: Package) -> dict:
    """What the install prompt states, decided here rather than in the dialog.

    A permission prompt whose text is written in the surface is a prompt that
    can disagree with what the code does. This returns the claims, and every one
    of them is a fact already established by validation: the capability list is
    empty because it was refused otherwise, and the three access lines are read
    from the security block the manifest had to state.
    """

    security = package.manifest["security"]
    return {
        "id": package.id,
        "display_name": package.display_name,
        "version": package.version,
        "description": package.manifest["description"],
        "source_path": str(package.source_path),
        "file_count": len(package.files),
        "total_bytes": package.total_bytes,
        "integrity": package.integrity,
        "origin": f"{MODULE_ORIGIN}/{package.id}/",
        "grants": {
            "browser_capabilities": package.manifest["capabilities"],
            "network": security["network"]["access"],
            "filesystem": security["filesystem"]["access"],
            "credentials": security["credentials"]["direct_access"],
        },
    }


# --- The installed record ----------------------------------------------------


@dataclass(frozen=True)
class InstalledModule:
    id: str
    version: str
    display_name: str
    source: str
    location: str
    installed_at: str
    enabled: bool
    integrity: str

    def as_record(self) -> dict:
        return {
            "id": self.id,
            "version": self.version,
            "display_name": self.display_name,
            "source": self.source,
            "location": self.location,
            "installed_at": self.installed_at,
            "enabled": self.enabled,
            "integrity": self.integrity,
        }


class UnknownRecordSchemaError(PackageError):
    """A record file written by a later version of the browser."""

    def __init__(self, found: object) -> None:
        super().__init__(
            "RECORD_FROM_A_LATER_VERSION",
            f"{RECORD_NAME} declares schema {found}; it is preserved, not rewritten",
        )


class InstallStore:
    """The installed-module record, and the directory the packages live in.

    One store per profile. `root` is the Sunshine directory inside a Chromium
    profile, and every path this class touches is inside it -- an installed
    module is profile state, so a second profile has its own modules and an
    off-the-record session inherits none.
    """

    def __init__(self, profile: Path) -> None:
        self.profile = Path(profile)
        self.root = self.profile / INSTALL_SUBDIRECTORY
        self.record_path = self.root / RECORD_NAME

    # -- reading

    def read(self) -> tuple[InstalledModule, ...]:
        if not self.record_path.is_file():
            return ()
        try:
            payload = json.loads(self.record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self.recover()
        if not isinstance(payload, dict):
            return self.recover()
        found = payload.get("schema_version")
        if found != RECORD_SCHEMA_VERSION:
            if isinstance(found, int) and found > RECORD_SCHEMA_VERSION:
                raise UnknownRecordSchemaError(found)
            return self.recover()
        entries = payload.get("modules")
        if not isinstance(entries, list):
            return self.recover()
        modules: list[InstalledModule] = []
        for entry in entries:
            try:
                modules.append(InstalledModule(**entry))
            except TypeError:
                return self.recover()
        return tuple(sorted(modules, key=lambda module: module.id))

    def recover(self) -> tuple[InstalledModule, ...]:
        """Rebuild the record from the packages still on disk.

        `CORRUPTION_POLICY`. The alternative -- treating an unreadable record as
        an empty one -- silently uninstalls everything the user installed, and
        does it at the moment they are least able to tell why. A copied package
        carries its own manifest, so the record is derivable; what is lost is
        the enable flag and the install date, and losing those is recoverable in
        a way that losing the modules is not. An unpacked install is not on disk
        here and cannot be recovered, which is one more reason it is the
        developer's mode rather than the user's.
        """

        modules: list[InstalledModule] = []
        if not self.root.is_dir():
            return ()
        for directory in sorted(self.root.iterdir()):
            if not directory.is_dir() or not (directory / MANIFEST_NAME).is_file():
                continue
            try:
                package = read_package(directory)
            except PackageError:
                continue
            if package.id != directory.name:
                continue
            modules.append(InstalledModule(
                id=package.id,
                version=package.version,
                display_name=package.display_name,
                source="packed",
                location=directory.name,
                installed_at="",
                enabled=True,
                integrity=package.integrity,
            ))
        self.write(tuple(modules))
        return tuple(modules)

    def find(self, module_id: str) -> InstalledModule | None:
        for module in self.read():
            if module.id == module_id:
                return module
        return None

    def directory(self, module: InstalledModule) -> Path:
        """Where this module's files are, whichever way it was installed."""

        if module.source == "unpacked":
            return Path(module.location)
        return self.root / module.location

    # -- writing

    def write(self, modules: tuple[InstalledModule, ...]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": RECORD_SCHEMA_VERSION,
            "modules": [module.as_record() for module in sorted(modules, key=lambda m: m.id)],
        }
        text = json.dumps(payload, indent=2, sort_keys=False) + "\n"
        temporary = self.record_path.with_suffix(".json.new")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(self.record_path)

    def _replace(self, modules: tuple[InstalledModule, ...], module: InstalledModule) -> None:
        kept = tuple(item for item in modules if item.id != module.id)
        self.write(kept + (module,))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def install(source: Path, profile: Path, *, unpacked: bool = False,
            reinstall: bool = False, enabled: bool = True,
            installed_at: str | None = None) -> InstalledModule:
    """Validate a package and put it where the browser will serve it from.

    Nothing is written until validation has passed, and the files land by a
    rename rather than by being written into their final place: an install that
    is interrupted leaves either the previous version or nothing, never half a
    module. An upgrade moves the old directory aside first and removes it only
    once the new one is in place, for the same reason.
    """

    store = InstallStore(profile)
    package = read_package(Path(source))
    if unpacked and package.packed:
        raise PackageError("NOT_A_PACKAGE", "an unpacked install needs a folder, not a zip")

    existing = store.find(package.id)
    if existing is not None and not reinstall:
        if _version_key(package.version) <= _version_key(existing.version):
            code = "ALREADY_INSTALLED" if package.version == existing.version else "VERSION_NOT_NEWER"
            raise PackageError(
                code,
                f"{package.id} {existing.version} is installed; {package.version} is not newer",
            )

    store.root.mkdir(parents=True, exist_ok=True)
    if unpacked:
        location = str(package.source_path)
    else:
        location = package.id
        destination = store.root / location
        staging = Path(tempfile.mkdtemp(prefix=f".staging-{package.id}-", dir=store.root))
        try:
            _materialise(package, staging)
            previous = destination.with_name(f".previous-{package.id}")
            if destination.exists():
                shutil.rmtree(previous, ignore_errors=True)
                destination.replace(previous)
            staging.replace(destination)
            shutil.rmtree(previous, ignore_errors=True)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    module = InstalledModule(
        id=package.id,
        version=package.version,
        display_name=package.display_name,
        source="unpacked" if unpacked else "packed",
        location=location,
        installed_at=installed_at or _now(),
        enabled=enabled,
        integrity=package.integrity,
    )
    store._replace(store.read(), module)
    return module


def _materialise(package: Package, destination: Path) -> None:
    source = package.source_path
    if package.packed:
        with zipfile.ZipFile(source) as archive:
            for entry in package.files:
                target = destination / entry.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(entry.path))
        return
    for entry in package.files:
        target = destination / entry.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / entry.path, target)


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def uninstall(module_id: str, profile: Path) -> InstalledModule:
    """Remove a module, and remove its files if this profile owns them.

    An unpacked install is served from a folder the user maintains, and deleting
    that folder is not this program's business; the record goes and the files
    stay where they were.
    """

    store = InstallStore(profile)
    module = store.find(module_id)
    if module is None:
        raise PackageError("NOT_INSTALLED", f"{module_id} is not installed")
    if module.source == "packed":
        shutil.rmtree(store.root / module.location, ignore_errors=True)
    store.write(tuple(item for item in store.read() if item.id != module_id))
    return module


def set_enabled(module_id: str, profile: Path, enabled: bool) -> InstalledModule:
    """Disabling keeps the files and stops the browser serving them.

    It is a separate act from uninstalling because the two answer different
    questions -- "stop this" and "get rid of this" -- and a user who cannot say
    the first says the second and loses their data.
    """

    store = InstallStore(profile)
    module = store.find(module_id)
    if module is None:
        raise PackageError("NOT_INSTALLED", f"{module_id} is not installed")
    updated = InstalledModule(**{**module.as_record(), "enabled": enabled})
    store._replace(store.read(), updated)
    return updated


def verify_installed(profile: Path) -> list[str]:
    """Re-read what is installed, and report what no longer holds.

    Run before serving, not only after installing. A copied package that no
    longer hashes to what was recorded has been modified since the user agreed
    to it, and that is a refusal rather than a warning: `INTEGRITY_MISMATCH` is
    the one failure here that the browser must not serve through. An unpacked
    install is expected to change -- that is what it is for -- so it is
    revalidated rather than compared, and a change that breaks the rules is
    reported the same way a bad package would be.
    """

    store = InstallStore(profile)
    problems: list[str] = []
    for module in store.read():
        directory = store.directory(module)
        if not directory.is_dir():
            problems.append(f"{module.id}: MISSING: {directory} is gone")
            continue
        try:
            package = read_package(directory)
        except PackageError as error:
            problems.append(f"{module.id}: {error}")
            continue
        if package.id != module.id:
            problems.append(f"{module.id}: MANIFEST_INVALID: the folder now holds {package.id}")
        elif module.source == "packed" and package.integrity != module.integrity:
            problems.append(f"{module.id}: INTEGRITY_MISMATCH: modified since it was installed")
    return problems


def serve_map(profile: Path) -> dict[str, Path]:
    """The one thing the browser's data source needs: id to directory.

    Only enabled modules appear. A disabled module's origin resolves to nothing
    at all rather than to an error page, because a disabled module should not be
    distinguishable from one that was never installed by anything a page can
    observe.
    """

    store = InstallStore(profile)
    return {
        module.id: store.directory(module)
        for module in store.read()
        if module.enabled
    }


if __name__ == "__main__":  # pragma: no cover - the command line lives next door
    print(__doc__.strip().splitlines()[0], file=sys.stderr)
    print("Run scripts/install_module.py to install, list, or remove a package.", file=sys.stderr)
    raise SystemExit(2)
