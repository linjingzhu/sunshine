// Copyright 2026 The Sunshine Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// Sunshine's installer front-end.
//
// It asks questions and phrases a request. It installs nothing. `mini_installer.exe`
// -- carried inside this binary as an opaque resource, exactly as upstream built
// it -- does the installing, and keeps handling every failure it already
// handles: a partial archive, a running browser, an in-progress update, a
// downgrade. `docs/INSTALLER_UI_CONTRACT.md` is the contract; the invariant
// identifiers cited below are its.
//
// The security-shaped part of this file is the elevation boundary, and it is
// shaped that way on purpose. This program extracts a payload to disk and
// executes it, and does so as an administrator for a per-machine install, which
// is the documented shape of a local privilege escalation. So: asInvoker in the
// manifest (IU-7), elevate only on the per-machine choice and only by
// relaunching, carry the choices as a closed set of switches rather than a file
// an unprivileged user could rewrite (IU-8), extract only after elevating into
// a directory they cannot write (IU-9), and check the engine's hash against the
// value baked in at build time before running it (IU-10).

#include <windows.h>

#include <bcrypt.h>
#include <sddl.h>
#include <commctrl.h>
#include <shellapi.h>
#include <shlobj.h>
#include <uxtheme.h>
#include <wincodec.h>

#include <string>
#include <vector>

#include "engine_hash.h"
#include "resource.h"

namespace {

// ---------------------------------------------------------------------------
// The choices, and the closed switch set that carries them across elevation.
// ---------------------------------------------------------------------------

struct Choices {
  bool system_level = false;
  bool desktop_shortcut = true;
  bool taskbar_shortcut = true;
  bool quick_launch_shortcut = false;
  bool make_default = false;
  bool launch_when_done = true;
};

// IU-8. Every switch this program accepts is in this table and nothing else is.
// An argument outside it is not ignored, it is a refusal to run: an installer
// that silently drops what it was told is one whose behaviour cannot be
// predicted from its command line.
struct Switch {
  const wchar_t* name;
  bool Choices::* field;
  bool value;
};

constexpr wchar_t kElevatedSwitch[] = L"--sunshine-elevated";

// Section 5: the engine's exit code is reported as the engine's, not as this
// program's. So the engine's value passes through untouched and these sit well
// above the range `installer::InstallStatus` uses, rather than colliding with
// it at 1, 2 and 3 as they did.
constexpr int kExitCancelled = 0xA1;
constexpr int kExitBadArguments = 0xA2;
constexpr int kExitEngineNeverRan = 0xA3;
constexpr int kExitNoWindow = 0xA4;
constexpr int kExitCouldNotElevate = 0xA5;
constexpr int kExitRefusedElevation = 0xA6;

constexpr Switch kSwitches[] = {
    {L"--system-level", &Choices::system_level, true},
    {L"--no-desktop-shortcut", &Choices::desktop_shortcut, false},
    {L"--no-taskbar-shortcut", &Choices::taskbar_shortcut, false},
    {L"--quick-launch-shortcut", &Choices::quick_launch_shortcut, true},
    {L"--make-default", &Choices::make_default, true},
    {L"--no-launch", &Choices::launch_when_done, false},
};

// Returns false when the command line contains anything this program does not
// define. There is deliberately no switch that skips the dialog: section 9 of
// the contract refuses a silent mode, and IU-15 is that refusal.
bool ParseCommandLine(Choices* choices, bool* elevated_continuation) {
  int count = 0;
  LPWSTR* argv = ::CommandLineToArgvW(::GetCommandLineW(), &count);
  if (!argv) {
    return false;
  }
  bool ok = true;
  for (int index = 1; index < count; ++index) {
    const std::wstring argument(argv[index]);
    if (argument == kElevatedSwitch) {
      *elevated_continuation = true;
      continue;
    }
    bool matched = false;
    for (const Switch& option : kSwitches) {
      if (argument == option.name) {
        choices->*(option.field) = option.value;
        matched = true;
        break;
      }
    }
    if (!matched) {
      ok = false;
      break;
    }
  }
  ::LocalFree(argv);
  return ok;
}

std::wstring BuildElevatedCommandLine(const Choices& choices) {
  std::wstring line(kElevatedSwitch);
  for (const Switch& option : kSwitches) {
    if (choices.*(option.field) == option.value) {
      line.append(L" ").append(option.name);
    }
  }
  return line;
}

// ---------------------------------------------------------------------------
// What the machine already has. IU-16: this is the only state read before the
// user has agreed to anything, and it is read from Windows' own uninstall
// registration -- `Software\Microsoft\Windows\CurrentVersion\Uninstall\Sunshine`,
// value `DisplayVersion`, in the 32-bit view, which is where setup.exe writes
// it. Nothing else is read and nothing is written.
// ---------------------------------------------------------------------------

std::wstring InstalledVersion() {
  static constexpr wchar_t kUninstallKey[] =
      L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Sunshine";
  for (HKEY root : {HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE}) {
    HKEY key = nullptr;
    if (::RegOpenKeyExW(root, kUninstallKey, 0, KEY_QUERY_VALUE | KEY_WOW64_32KEY,
                        &key) != ERROR_SUCCESS) {
      continue;
    }
    wchar_t buffer[64] = {};
    DWORD size = sizeof(buffer);
    // RegGetValueW, not RegQueryValueExW. The first hive read here is
    // HKEY_CURRENT_USER, which any unprivileged user can write, and
    // RegQueryValueExW documents that a REG_SZ "may not have been stored with
    // the proper terminating null characters" -- so a 64-character
    // DisplayVersion would have been read past the end of this buffer.
    // RegGetValueW adds the terminator, and RRF_RT_REG_SZ rejects every other
    // type without a second check.
    const LSTATUS status = ::RegGetValueW(key, nullptr, L"DisplayVersion",
                                          RRF_RT_REG_SZ, nullptr, buffer, &size);
    ::RegCloseKey(key);
    if (status == ERROR_SUCCESS) {
      return std::wstring(buffer);
    }
  }
  return std::wstring();
}

// ---------------------------------------------------------------------------
// Where Sunshine will land. Shown, never typed -- D2 of the review, and IU-4.
// ---------------------------------------------------------------------------

std::wstring InstallLocation(bool system_level) {
  PWSTR folder = nullptr;
  const KNOWNFOLDERID& id =
      system_level ? FOLDERID_ProgramFiles : FOLDERID_LocalAppData;
  if (FAILED(::SHGetKnownFolderPath(id, 0, nullptr, &folder))) {
    return std::wstring();
  }
  std::wstring path(folder);
  ::CoTaskMemFree(folder);
  return path.append(L"\\Sunshine\\Application");
}

// ---------------------------------------------------------------------------
// Staging. IU-9: when elevated, the directory the engine is written into must
// not be writable by an unprivileged user, or the engine can be replaced
// between the write and the execute.
// ---------------------------------------------------------------------------

// Where staging goes, and it is not one directory for both cases.
//
// An elevated install must not stage under the user's own %TEMP%. UAC gives
// the elevated process the same user profile, so that directory's *parent*
// grants the unelevated user FILE_DELETE_CHILD: they cannot write into a
// protected child, but they can delete it and put a directory of the same name
// with their own engine in its place, between the write and the execute. A
// protected DACL on the child does not close that, and IU-9 was not achieved
// until this did. %SystemRoot%\Temp denies Users delete-child by default,
// which is what makes the DACL below load-bearing rather than decorative.
std::wstring StagingRoot(bool elevated) {
  wchar_t buffer[MAX_PATH + 1] = {};
  if (elevated) {
    const UINT length = ::GetSystemWindowsDirectoryW(buffer, ARRAYSIZE(buffer));
    if (length == 0 || length > MAX_PATH) {
      return std::wstring();
    }
    std::wstring root(buffer, length);
    if (!root.empty() && root.back() != L'\\') {
      root.push_back(L'\\');
    }
    return root + L"Temp\\";
  }
  // GetTempPathW returns the *required* length when the buffer is too small,
  // and that value is non-zero -- so `if (!GetTempPathW(...))` passed while
  // leaving the buffer empty, and the staging path became a bare relative name
  // created in whatever current directory this process inherited.
  const DWORD length = ::GetTempPathW(ARRAYSIZE(buffer), buffer);
  if (length == 0 || length > MAX_PATH) {
    return std::wstring();
  }
  return std::wstring(buffer, length);
}

std::wstring CreateStagingDirectory(bool elevated) {
  const std::wstring temp = StagingRoot(elevated);
  if (temp.empty()) {
    return std::wstring();
  }
  GUID guid = {};
  if (FAILED(::CoCreateGuid(&guid))) {
    return std::wstring();
  }
  wchar_t name[64] = {};
  ::StringFromGUID2(guid, name, ARRAYSIZE(name));

  std::wstring path(temp);
  path.append(L"sunshine-setup-").append(name);

  SECURITY_ATTRIBUTES attributes = {};
  PSECURITY_DESCRIPTOR descriptor = nullptr;
  if (elevated) {
    // Protected from inheritance, full control to Administrators and SYSTEM,
    // and to nobody else.
    if (!::ConvertStringSecurityDescriptorToSecurityDescriptorW(
            L"D:P(A;OICI;GA;;;BA)(A;OICI;GA;;;SY)", SDDL_REVISION_1,
            &descriptor, nullptr)) {
      return std::wstring();
    }
    attributes.nLength = sizeof(attributes);
    attributes.lpSecurityDescriptor = descriptor;
  }
  const BOOL created =
      ::CreateDirectoryW(path.c_str(), elevated ? &attributes : nullptr);
  if (descriptor) {
    ::LocalFree(descriptor);
  }
  return created ? path : std::wstring();
}

void RemoveDirectoryTree(const std::wstring& directory) {
  if (directory.empty()) {
    return;
  }
  WIN32_FIND_DATAW found = {};
  const std::wstring pattern = directory + L"\\*";
  HANDLE handle = ::FindFirstFileW(pattern.c_str(), &found);
  if (handle != INVALID_HANDLE_VALUE) {
    do {
      const std::wstring name(found.cFileName);
      if (name == L"." || name == L"..") {
        continue;
      }
      ::DeleteFileW((directory + L"\\" + name).c_str());
    } while (::FindNextFileW(handle, &found));
    ::FindClose(handle);
  }
  ::RemoveDirectoryW(directory.c_str());
}

// ---------------------------------------------------------------------------
// The engine: extracted, hashed, and only then run.
// ---------------------------------------------------------------------------

bool WriteFileBytes(const std::wstring& path, const BYTE* data, DWORD size) {
  HANDLE file = ::CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr,
                              CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
  if (file == INVALID_HANDLE_VALUE) {
    return false;
  }
  DWORD written = 0;
  const BOOL ok = ::WriteFile(file, data, size, &written, nullptr);
  ::CloseHandle(file);
  return ok && written == size;
}

std::wstring HexDigest(const BYTE (&digest)[32]) {
  static const wchar_t kHex[] = L"0123456789abcdef";
  std::wstring hex;
  for (BYTE value : digest) {
    hex.push_back(kHex[value >> 4]);
    hex.push_back(kHex[value & 0x0f]);
  }
  return hex;
}

// IU-10, and this is the check that matters: it hashes the file that will be
// executed, through a handle it then holds open across CreateProcessW.
//
// Hashing the in-memory resource instead -- which is what this did first --
// proves only that the binary carries what the build put in it. It says
// nothing about the bytes on disk at the moment of execution, which is the
// entire window IU-9 and IU-10 exist to close. The handle denies write and
// delete sharing, so between this returning and the process starting there is
// no longer anything to race.
HANDLE OpenVerifiedEngine(const std::wstring& path) {
  HANDLE file = ::CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ,
                              nullptr, OPEN_EXISTING,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
  if (file == INVALID_HANDLE_VALUE) {
    return nullptr;
  }
  BCRYPT_HASH_HANDLE hash = nullptr;
  if (!BCRYPT_SUCCESS(::BCryptCreateHash(BCRYPT_SHA256_ALG_HANDLE, &hash,
                                         nullptr, 0, nullptr, 0, 0))) {
    ::CloseHandle(file);
    return nullptr;
  }
  bool ok = true;
  std::vector<BYTE> chunk(64 * 1024);
  for (;;) {
    DWORD read = 0;
    if (!::ReadFile(file, chunk.data(), static_cast<DWORD>(chunk.size()), &read,
                    nullptr)) {
      ok = false;
      break;
    }
    if (read == 0) {
      break;
    }
    if (!BCRYPT_SUCCESS(::BCryptHashData(hash, chunk.data(), read, 0))) {
      ok = false;
      break;
    }
  }
  BYTE digest[32] = {};
  if (ok) {
    ok = BCRYPT_SUCCESS(::BCryptFinishHash(hash, digest, sizeof(digest), 0));
  }
  ::BCryptDestroyHash(hash);
  if (!ok || HexDigest(digest) != kEngineSha256) {
    ::CloseHandle(file);
    return nullptr;
  }
  return file;
}

// The cheap sanity check on the resource. Kept because it costs nothing and
// catches a mis-built binary before anything is written, but it is explicitly
// NOT the IU-10 check -- `OpenVerifiedEngine` is.
bool HashMatches(const BYTE* data, DWORD size) {
  BYTE digest[32] = {};
  const NTSTATUS status = ::BCryptHash(BCRYPT_SHA256_ALG_HANDLE, nullptr, 0,
                                       const_cast<PUCHAR>(data), size, digest,
                                       sizeof(digest));
  if (status != 0) {
    return false;
  }
  return HexDigest(digest) == kEngineSha256;
}

// ---------------------------------------------------------------------------
// The request. Every key here is one `chrome/installer/util/initial_preferences_constants.h`
// already defines -- IU-3. A control whose effect is not one of these names is
// a control doing something upstream did not agree to.
// ---------------------------------------------------------------------------

std::string InitialPreferences(const Choices& choices) {
  auto flag = [](bool value) { return value ? "true" : "false"; };
  std::string json = "{\n  \"distribution\": {\n";
  json += std::string("    \"do_not_create_desktop_shortcut\": ") +
          flag(!choices.desktop_shortcut) + ",\n";
  json += std::string("    \"do_not_create_taskbar_shortcut\": ") +
          flag(!choices.taskbar_shortcut) + ",\n";
  json += std::string("    \"do_not_create_quick_launch_shortcut\": ") +
          flag(!choices.quick_launch_shortcut) + ",\n";
  json += std::string("    \"make_chrome_default_for_user\": ") +
          flag(choices.make_default) + ",\n";
  json += std::string("    \"do_not_launch_chrome\": ") +
          flag(!choices.launch_when_done) + "\n";
  // Deliberately not `system_level`. The scope reaches setup.exe as the
  // --system-level switch, which mini_installer forwards, and one fact stated
  // in two places is one fact that can disagree with itself.
  json += "  }\n}\n";
  return json;
}

// ---------------------------------------------------------------------------

struct Outcome {
  bool ran = false;
  DWORD exit_code = 0;
};

Outcome RunEngine(const Choices& choices, bool elevated) {
  Outcome outcome;
  HRSRC resource = ::FindResourceW(nullptr, MAKEINTRESOURCEW(IDR_ENGINE), RT_RCDATA);
  HGLOBAL loaded = resource ? ::LoadResource(nullptr, resource) : nullptr;
  const BYTE* data = loaded ? static_cast<const BYTE*>(::LockResource(loaded)) : nullptr;
  const DWORD size = resource ? ::SizeofResource(nullptr, resource) : 0;
  if (!data || !size || !HashMatches(data, size)) {
    return outcome;  // IU-10: refuse, and fall back to no other copy.
  }

  const std::wstring staging = CreateStagingDirectory(elevated);
  if (staging.empty()) {
    return outcome;
  }
  const std::wstring engine = staging + L"\\mini_installer.exe";
  const std::wstring preferences = staging + L"\\initial_preferences.json";
  const std::string json = InitialPreferences(choices);
  if (!WriteFileBytes(engine, data, size) ||
      !WriteFileBytes(preferences,
                      reinterpret_cast<const BYTE*>(json.data()),
                      static_cast<DWORD>(json.size()))) {
    RemoveDirectoryTree(staging);
    return outcome;
  }

  // IU-10, at the only moment it means anything.
  HANDLE verified = OpenVerifiedEngine(engine);
  if (!verified) {
    RemoveDirectoryTree(staging);
    return outcome;
  }

  std::wstring command = L"\"" + engine + L"\" --installerdata=\"" +
                         preferences + L"\"";
  if (choices.system_level) {
    command.append(L" --system-level");
  }

  STARTUPINFOW startup = {};
  startup.cb = sizeof(startup);
  PROCESS_INFORMATION process = {};
  std::vector<wchar_t> mutable_command(command.begin(), command.end());
  mutable_command.push_back(L'\0');
  if (::CreateProcessW(nullptr, mutable_command.data(), nullptr, nullptr, FALSE,
                       0, nullptr, staging.c_str(), &startup, &process)) {
    ::WaitForSingleObject(process.hProcess, INFINITE);
    outcome.ran = ::GetExitCodeProcess(process.hProcess, &outcome.exit_code) != FALSE;
    ::CloseHandle(process.hThread);
    ::CloseHandle(process.hProcess);
  }
  // Held until the engine has been started, so that nothing could replace the
  // file between the hash and the launch.
  ::CloseHandle(verified);
  // IU-11: nothing is left extracted, whether or not the install succeeded.
  RemoveDirectoryTree(staging);
  return outcome;
}

// Elevation, by relaunching this same binary with the closed switch set. The
// choices cross as arguments, never as a file: a file in a user-writable
// directory that an elevated process then reads is the classic shape of this
// bug.
// Returns false and sets `declined` when the user said no to the prompt, which
// is not a failure and must not be reported as one (IU-12).
bool RelaunchElevated(const Choices& choices, DWORD* exit_code, bool* declined) {
  *declined = false;
  wchar_t self[MAX_PATH + 1] = {};
  const DWORD length = ::GetModuleFileNameW(nullptr, self, ARRAYSIZE(self));
  // On truncation this returns the buffer size with ERROR_INSUFFICIENT_BUFFER,
  // which is non-zero -- so the old `if (!GetModuleFileNameW(...))` would have
  // handed a truncated path to ShellExecuteExW as the thing to elevate.
  if (length == 0 || length > MAX_PATH) {
    return false;
  }
  const std::wstring arguments = BuildElevatedCommandLine(choices);
  SHELLEXECUTEINFOW info = {};
  info.cbSize = sizeof(info);
  info.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC;
  info.lpVerb = L"runas";
  info.lpFile = self;
  info.lpParameters = arguments.c_str();
  info.nShow = SW_SHOWNORMAL;
  // The elevated child should not inherit a working directory the unelevated
  // parent chose.
  wchar_t system_directory[MAX_PATH + 1] = {};
  if (::GetSystemDirectoryW(system_directory, ARRAYSIZE(system_directory))) {
    info.lpDirectory = system_directory;
  }
  if (!::ShellExecuteExW(&info)) {
    // IU-12: a declined prompt is not an error and not a fallback to a
    // per-user install. It is also the only outcome here that is not a
    // failure, and it has to be distinguished by asking, because
    // ShellExecuteExW reports both the same way.
    *declined = ::GetLastError() == ERROR_CANCELLED;
    return false;
  }
  // "ShellExecuteEx does not always return an hProcess, even if a process is
  // launched as the result of the call." Without this the waits fail silently,
  // the exit code stays zero, and the front-end reports a successful install
  // that it never observed.
  if (info.hProcess == nullptr) {
    return false;
  }
  ::WaitForSingleObject(info.hProcess, INFINITE);
  const BOOL read = ::GetExitCodeProcess(info.hProcess, exit_code);
  ::CloseHandle(info.hProcess);
  return read != FALSE;
}

// ---------------------------------------------------------------------------
// The dialog. Real Win32 controls so that keyboard traversal and screen-reader
// names come from the system (IU-14), owner-drawn so that the palette is
// Sunshine's (D6). The token mapping lives in one table and nowhere else.
// ---------------------------------------------------------------------------

// The banner. Decoded once, from the resource compiled into this binary, and
// never from a file (IU-6). WIC reads it out of memory, so there is no path
// anywhere in this program that an image could arrive by.
HBITMAP DecodeBanner() {
  HRSRC resource = ::FindResourceW(nullptr, MAKEINTRESOURCEW(IDR_BANNER), RT_RCDATA);
  HGLOBAL loaded = resource ? ::LoadResource(nullptr, resource) : nullptr;
  auto* data = loaded ? static_cast<BYTE*>(::LockResource(loaded)) : nullptr;
  const DWORD size = resource ? ::SizeofResource(nullptr, resource) : 0;
  if (!data || !size) {
    return nullptr;
  }

  IWICImagingFactory* factory = nullptr;
  if (FAILED(::CoCreateInstance(CLSID_WICImagingFactory, nullptr,
                                CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&factory)))) {
    return nullptr;
  }
  IWICStream* stream = nullptr;
  IWICBitmapDecoder* decoder = nullptr;
  IWICBitmapFrameDecode* frame = nullptr;
  IWICFormatConverter* converter = nullptr;
  HBITMAP bitmap = nullptr;

  if (SUCCEEDED(factory->CreateStream(&stream)) &&
      SUCCEEDED(stream->InitializeFromMemory(data, size)) &&
      SUCCEEDED(factory->CreateDecoderFromStream(
          stream, nullptr, WICDecodeMetadataCacheOnLoad, &decoder)) &&
      SUCCEEDED(decoder->GetFrame(0, &frame)) &&
      SUCCEEDED(factory->CreateFormatConverter(&converter)) &&
      SUCCEEDED(converter->Initialize(frame, GUID_WICPixelFormat32bppBGR,
                                      WICBitmapDitherTypeNone, nullptr, 0.0,
                                      WICBitmapPaletteTypeCustom))) {
    UINT width = 0;
    UINT height = 0;
    if (SUCCEEDED(converter->GetSize(&width, &height)) && width && height) {
      BITMAPINFO info = {};
      info.bmiHeader.biSize = sizeof(info.bmiHeader);
      info.bmiHeader.biWidth = static_cast<LONG>(width);
      info.bmiHeader.biHeight = -static_cast<LONG>(height);  // top-down
      info.bmiHeader.biPlanes = 1;
      info.bmiHeader.biBitCount = 32;
      info.bmiHeader.biCompression = BI_RGB;
      void* bits = nullptr;
      bitmap = ::CreateDIBSection(nullptr, &info, DIB_RGB_COLORS, &bits, nullptr, 0);
      if (bitmap && FAILED(converter->CopyPixels(nullptr, width * 4,
                                                 width * height * 4,
                                                 static_cast<BYTE*>(bits)))) {
        ::DeleteObject(bitmap);
        bitmap = nullptr;
      }
    }
  }

  if (converter) { converter->Release(); }
  if (frame) { frame->Release(); }
  if (decoder) { decoder->Release(); }
  if (stream) { stream->Release(); }
  factory->Release();
  return bitmap;
}

struct Palette {
  COLORREF surface;
  COLORREF text;
  COLORREF muted;
  COLORREF accent;
  COLORREF accent_text;
};

bool SystemPrefersDark() {
  HKEY key = nullptr;
  if (::RegOpenKeyExW(HKEY_CURRENT_USER,
                      L"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\"
                      L"Personalize",
                      0, KEY_QUERY_VALUE, &key) != ERROR_SUCCESS) {
    return false;
  }
  DWORD light = 1;
  DWORD size = sizeof(light);
  DWORD type = 0;
  const LSTATUS status =
      ::RegQueryValueExW(key, L"AppsUseLightTheme", nullptr, &type,
                         reinterpret_cast<LPBYTE>(&light), &size);
  ::RegCloseKey(key);
  return status == ERROR_SUCCESS && type == REG_DWORD && light == 0;
}

Palette CurrentPalette() {
  // `docs/DESIGN_SYSTEM_CONTRACT.md`'s tokens, translated once. A Win32 dialog
  // cannot resolve a CSS custom property, so the mapping is the artefact that
  // gets reviewed when the design system changes.
  if (SystemPrefersDark()) {
    return Palette{RGB(0x1b, 0x1b, 0x1f), RGB(0xf2, 0xf2, 0xf5),
                   RGB(0x9a, 0x9a, 0xa5), RGB(0xff, 0xc4, 0x3d),
                   RGB(0x1b, 0x1b, 0x1f)};
  }
  return Palette{RGB(0xff, 0xff, 0xff), RGB(0x1b, 0x1b, 0x1f),
                 RGB(0x5f, 0x5f, 0x6a), RGB(0xff, 0xc4, 0x3d),
                 RGB(0x1b, 0x1b, 0x1f)};
}

struct DialogState {
  Choices choices;
  std::wstring installed_version;
  bool accepted = false;
  Palette palette;
  HBRUSH surface_brush = nullptr;
  HBITMAP banner = nullptr;
};

void RefreshLocation(HWND dialog, DialogState* state) {
  const bool machine = ::IsDlgButtonChecked(dialog, IDC_SCOPE_MACHINE) == BST_CHECKED;
  state->choices.system_level = machine;
  ::SetDlgItemTextW(dialog, IDC_LOCATION, InstallLocation(machine).c_str());
}

void ReadChoices(HWND dialog, DialogState* state) {
  auto checked = [dialog](int control) {
    return ::IsDlgButtonChecked(dialog, control) == BST_CHECKED;
  };
  state->choices.desktop_shortcut = checked(IDC_DESKTOP_SHORTCUT);
  state->choices.taskbar_shortcut = checked(IDC_TASKBAR_SHORTCUT);
  state->choices.quick_launch_shortcut = checked(IDC_QUICK_LAUNCH_SHORTCUT);
  state->choices.make_default = checked(IDC_MAKE_DEFAULT);
  state->choices.launch_when_done = checked(IDC_LAUNCH_WHEN_DONE);
  state->choices.system_level = checked(IDC_SCOPE_MACHINE);
}

// The banner and the buttons are owner-drawn because D6 chose Sunshine's own
// look, and they are still real Win32 controls because IU-14 wants keyboard
// traversal and accessible names, which the system gives to a real control and
// not to a rectangle somebody painted.
void DrawBanner(const DRAWITEMSTRUCT& item, DialogState* state) {
  if (!state->banner) {
    ::SetDCBrushColor(item.hDC, state->palette.accent);
    ::FillRect(item.hDC, &item.rcItem,
               static_cast<HBRUSH>(::GetStockObject(DC_BRUSH)));
    return;
  }
  BITMAP measured = {};
  ::GetObjectW(state->banner, sizeof(measured), &measured);
  HDC memory = ::CreateCompatibleDC(item.hDC);
  HGDIOBJ previous = ::SelectObject(memory, state->banner);
  ::SetStretchBltMode(item.hDC, HALFTONE);
  ::SetBrushOrgEx(item.hDC, 0, 0, nullptr);
  ::StretchBlt(item.hDC, item.rcItem.left, item.rcItem.top,
               item.rcItem.right - item.rcItem.left,
               item.rcItem.bottom - item.rcItem.top, memory, 0, 0,
               measured.bmWidth, measured.bmHeight, SRCCOPY);
  ::SelectObject(memory, previous);
  ::DeleteDC(memory);
}

void DrawButton(const DRAWITEMSTRUCT& item, DialogState* state) {
  const bool primary = item.CtlID == IDC_INSTALL;
  const bool pressed = (item.itemState & ODS_SELECTED) != 0;
  const bool disabled = (item.itemState & ODS_DISABLED) != 0;

  COLORREF face = primary ? state->palette.accent : state->palette.surface;
  if (pressed) {
    // A press is a shade, not a different colour: the token set has one accent
    // and inventing a second here would put a colour outside the design system
    // into the one surface nobody can inspect with devtools.
    face = RGB(GetRValue(face) * 4 / 5, GetGValue(face) * 4 / 5,
               GetBValue(face) * 4 / 5);
  }
  ::SetDCBrushColor(item.hDC, face);
  ::FillRect(item.hDC, &item.rcItem,
             static_cast<HBRUSH>(::GetStockObject(DC_BRUSH)));
  if (!primary) {
    ::SetDCBrushColor(item.hDC, state->palette.muted);
    ::FrameRect(item.hDC, &item.rcItem,
                static_cast<HBRUSH>(::GetStockObject(DC_BRUSH)));
  }

  wchar_t caption[64] = {};
  ::GetWindowTextW(item.hwndItem, caption, ARRAYSIZE(caption));
  ::SetBkMode(item.hDC, TRANSPARENT);
  ::SetTextColor(item.hDC, disabled ? state->palette.muted
                                    : (primary ? state->palette.accent_text
                                               : state->palette.text));
  RECT text = item.rcItem;
  ::DrawTextW(item.hDC, caption, -1, &text,
              DT_CENTER | DT_VCENTER | DT_SINGLELINE);

  // IU-14: focus is visible at every stop.
  if (item.itemState & ODS_FOCUS) {
    RECT focus = item.rcItem;
    ::InflateRect(&focus, -3, -3);
    ::DrawFocusRect(item.hDC, &focus);
  }
}

INT_PTR CALLBACK DialogProc(HWND dialog, UINT message, WPARAM wparam,
                            LPARAM lparam) {
  auto* state = reinterpret_cast<DialogState*>(
      ::GetWindowLongPtrW(dialog, GWLP_USERDATA));
  switch (message) {
    case WM_INITDIALOG: {
      state = reinterpret_cast<DialogState*>(lparam);
      ::SetWindowLongPtrW(dialog, GWLP_USERDATA, lparam);
      state->palette = CurrentPalette();
      state->surface_brush = ::CreateSolidBrush(state->palette.surface);
      state->banner = DecodeBanner();
      // Seeded from the struct rather than from literals, so that when a
      // declined elevation prompt re-enters this dialog the user finds the
      // choices they made rather than the defaults (IU-12).
      const Choices& seed = state->choices;
      ::CheckDlgButton(dialog, seed.system_level ? IDC_SCOPE_MACHINE : IDC_SCOPE_USER,
                       BST_CHECKED);
      ::CheckDlgButton(dialog, IDC_DESKTOP_SHORTCUT,
                       seed.desktop_shortcut ? BST_CHECKED : BST_UNCHECKED);
      ::CheckDlgButton(dialog, IDC_TASKBAR_SHORTCUT,
                       seed.taskbar_shortcut ? BST_CHECKED : BST_UNCHECKED);
      ::CheckDlgButton(dialog, IDC_QUICK_LAUNCH_SHORTCUT,
                       seed.quick_launch_shortcut ? BST_CHECKED : BST_UNCHECKED);
      ::CheckDlgButton(dialog, IDC_MAKE_DEFAULT,
                       seed.make_default ? BST_CHECKED : BST_UNCHECKED);
      ::CheckDlgButton(dialog, IDC_LAUNCH_WHEN_DONE,
                       seed.launch_when_done ? BST_CHECKED : BST_UNCHECKED);
      // The themed BUTTON class draws its own label with the *theme's* text
      // colour and ignores what WM_CTLCOLORBTN returns, so in dark mode these
      // six labels rendered near-black on near-black. Stripping the theme is
      // what makes the palette apply (IU-13).
      for (int control : {IDC_SCOPE_USER, IDC_SCOPE_MACHINE, IDC_DESKTOP_SHORTCUT,
                          IDC_TASKBAR_SHORTCUT, IDC_QUICK_LAUNCH_SHORTCUT,
                          IDC_MAKE_DEFAULT, IDC_LAUNCH_WHEN_DONE}) {
        ::SetWindowTheme(::GetDlgItem(dialog, control), L"", L"");
      }
      // Section 9: the dialog says when it is updating rather than showing a
      // button labelled Install that silently does something else. A failed
      // read is not a reason to block, so an empty version simply installs.
      if (state->installed_version.empty()) {
        ::SetDlgItemTextW(dialog, IDC_HEADLINE, L"Install Sunshine");
        ::SetDlgItemTextW(dialog, IDC_INSTALL, L"Install");
      } else {
        const std::wstring headline =
            L"Sunshine " + state->installed_version +
            L" is installed. This will update it.";
        ::SetDlgItemTextW(dialog, IDC_HEADLINE, headline.c_str());
        ::SetDlgItemTextW(dialog, IDC_INSTALL, L"Update");
      }
      RefreshLocation(dialog, state);
      return TRUE;
    }
    case WM_SETTINGCHANGE:
    case WM_THEMECHANGED: {
      // Section 4: the dialog follows the system setting, and follows a change
      // to it while it is open. It read the theme once and never again.
      if (!state) {
        break;
      }
      state->palette = CurrentPalette();
      if (state->surface_brush) {
        ::DeleteObject(state->surface_brush);
      }
      state->surface_brush = ::CreateSolidBrush(state->palette.surface);
      ::InvalidateRect(dialog, nullptr, TRUE);
      return TRUE;
    }
    case WM_DRAWITEM: {
      if (!state) {
        break;
      }
      const auto& item = *reinterpret_cast<DRAWITEMSTRUCT*>(lparam);
      // On an ODT_MENU item CtlID is 0 and hwndItem is an HMENU, which
      // DrawButton would hand to GetWindowTextW. Dispatch on the type.
      if (item.CtlType == ODT_STATIC && item.CtlID == IDC_BANNER) {
        DrawBanner(item, state);
      } else if (item.CtlType == ODT_BUTTON) {
        DrawButton(item, state);
      } else {
        break;
      }
      return TRUE;
    }
    case WM_CTLCOLORDLG:
    case WM_CTLCOLORSTATIC:
    case WM_CTLCOLORBTN: {
      if (!state) {
        break;
      }
      auto context = reinterpret_cast<HDC>(wparam);
      ::SetBkColor(context, state->palette.surface);
      ::SetTextColor(context, state->palette.text);
      return reinterpret_cast<INT_PTR>(state->surface_brush);
    }
    case WM_COMMAND: {
      if (!state) {
        break;
      }
      switch (LOWORD(wparam)) {
        case IDC_SCOPE_USER:
        case IDC_SCOPE_MACHINE:
          RefreshLocation(dialog, state);
          return TRUE;
        case IDOK:      // Enter, via the dialog manager's default-button path.
        case IDC_INSTALL:
          ReadChoices(dialog, state);
          state->accepted = true;
          ::EndDialog(dialog, IDOK);
          return TRUE;
        case IDCANCEL:
          ::EndDialog(dialog, IDCANCEL);
          return TRUE;
        default:
          break;
      }
      break;
    }
    case WM_DESTROY:
      if (state && state->surface_brush) {
        ::DeleteObject(state->surface_brush);
        state->surface_brush = nullptr;
      }
      if (state && state->banner) {
        ::DeleteObject(state->banner);
        state->banner = nullptr;
      }
      break;
    default:
      break;
  }
  return FALSE;
}

}  // namespace

// Whether this process actually holds an elevated token, as opposed to having
// been told on the command line that it does.
bool RunningElevated() {
  HANDLE token = nullptr;
  if (!::OpenProcessToken(::GetCurrentProcess(), TOKEN_QUERY, &token)) {
    return false;
  }
  TOKEN_ELEVATION elevation = {};
  DWORD size = 0;
  const BOOL ok = ::GetTokenInformation(token, TokenElevation, &elevation,
                                        sizeof(elevation), &size);
  ::CloseHandle(token);
  return ok && elevation.TokenIsElevated;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, LPWSTR, int) {
  Choices choices;
  bool elevated_continuation = false;
  if (!ParseCommandLine(&choices, &elevated_continuation)) {
    ::MessageBoxW(nullptr,
                  L"This installer was given an option it does not recognise, "
                  L"and will not run.",
                  L"Sunshine", MB_OK | MB_ICONERROR);
    return kExitBadArguments;
  }

  const HRESULT com = ::CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
  const bool owns_com = SUCCEEDED(com);

  // The elevated relaunch does not draw. It was already agreed to, once, in the
  // window the user was looking at.
  //
  // It took its own elevation on trust before, which meant `--sunshine-elevated`
  // was a complete unattended install path for anything that could already run
  // a process -- exactly what IU-15 forbids, and the guard was looking for the
  // word "silent" while the switch sat in the table beside it. Both facts are
  // now checked rather than assumed. What this cannot defend against is a
  // caller that is *already* administrator, and IU-15 says so rather than
  // pretending otherwise: such a caller does not need this program.
  if (elevated_continuation) {
    if (!RunningElevated() || !choices.system_level) {
      return kExitRefusedElevation;
    }
    const Outcome outcome = RunEngine(choices, /*elevated=*/true);
    if (owns_com) {
      ::CoUninitialize();
    }
    return outcome.ran ? static_cast<int>(outcome.exit_code) : kExitEngineNeverRan;
  }

  // Common Controls v6 is declared in the manifest and linked, but the classes
  // still have to be registered in this activation context. Without this
  // DialogBoxParamW can return -1, which the old code mapped to "the user
  // cancelled" -- a silent, misattributed failure.
  INITCOMMONCONTROLSEX controls = {sizeof(controls), ICC_STANDARD_CLASSES};
  ::InitCommonControlsEx(&controls);

  DialogState state;
  state.installed_version = InstalledVersion();

  int status = 0;
  for (;;) {
    state.accepted = false;
    const INT_PTR result = ::DialogBoxParamW(
        instance, MAKEINTRESOURCEW(IDD_SETUP), nullptr, DialogProc,
        reinterpret_cast<LPARAM>(&state));
    if (result == -1) {
      ::MessageBoxW(nullptr, L"Sunshine could not open its installer window.",
                    L"Sunshine", MB_OK | MB_ICONERROR);
      status = kExitNoWindow;
      break;
    }
    if (result != IDOK || !state.accepted) {
      status = kExitCancelled;  // Nothing was installed.
      break;
    }

    if (!state.choices.system_level) {
      const Outcome outcome = RunEngine(state.choices, /*elevated=*/false);
      status = outcome.ran ? static_cast<int>(outcome.exit_code) : kExitEngineNeverRan;
      break;
    }

    DWORD exit_code = 0;
    bool declined = false;
    if (RelaunchElevated(state.choices, &exit_code, &declined)) {
      status = static_cast<int>(exit_code);
      break;
    }
    if (declined) {
      // IU-12: the prompt was refused, which is not an error and not a reason
      // to install something smaller instead. Back to the dialog, with the
      // choices intact.
      continue;
    }
    status = kExitCouldNotElevate;  // Nothing was installed.
    break;
  }

  if (owns_com) {
    ::CoUninitialize();
  }
  return status;
}
