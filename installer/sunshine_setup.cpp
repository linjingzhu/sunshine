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
#include <shellapi.h>
#include <shlobj.h>

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
    DWORD type = 0;
    const LSTATUS status =
        ::RegQueryValueExW(key, L"DisplayVersion", nullptr, &type,
                           reinterpret_cast<LPBYTE>(buffer), &size);
    ::RegCloseKey(key);
    if (status == ERROR_SUCCESS && type == REG_SZ) {
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

std::wstring CreateStagingDirectory(bool elevated) {
  wchar_t temp[MAX_PATH] = {};
  if (!::GetTempPathW(MAX_PATH, temp)) {
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

// IU-10. `kEngineSha256` is generated by the build that embedded the engine, so
// this compares the resource against the thing the build intended to carry. It
// is cheap, and it is what makes a failure of IU-9 non-fatal rather than fatal.
bool HashMatches(const BYTE* data, DWORD size) {
  BYTE digest[32] = {};
  const NTSTATUS status = ::BCryptHash(BCRYPT_SHA256_ALG_HANDLE, nullptr, 0,
                                       const_cast<PUCHAR>(data), size, digest,
                                       sizeof(digest));
  if (status != 0) {
    return false;
  }
  static const wchar_t kHex[] = L"0123456789abcdef";
  std::wstring hex;
  for (BYTE value : digest) {
    hex.push_back(kHex[value >> 4]);
    hex.push_back(kHex[value & 0x0f]);
  }
  return hex == kEngineSha256;
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
                       0, nullptr, nullptr, &startup, &process)) {
    ::WaitForSingleObject(process.hProcess, INFINITE);
    ::GetExitCodeProcess(process.hProcess, &outcome.exit_code);
    ::CloseHandle(process.hThread);
    ::CloseHandle(process.hProcess);
    outcome.ran = true;
  }
  // IU-11: nothing is left extracted, whether or not the install succeeded.
  RemoveDirectoryTree(staging);
  return outcome;
}

// Elevation, by relaunching this same binary with the closed switch set. The
// choices cross as arguments, never as a file: a file in a user-writable
// directory that an elevated process then reads is the classic shape of this
// bug.
bool RelaunchElevated(const Choices& choices, DWORD* exit_code) {
  wchar_t self[MAX_PATH] = {};
  if (!::GetModuleFileNameW(nullptr, self, MAX_PATH)) {
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
  if (!::ShellExecuteExW(&info)) {
    return false;  // IU-12: a declined prompt is not an error and not a
                   // fallback to a per-user install.
  }
  ::WaitForSingleObject(info.hProcess, INFINITE);
  ::GetExitCodeProcess(info.hProcess, exit_code);
  ::CloseHandle(info.hProcess);
  return true;
}

// ---------------------------------------------------------------------------
// The dialog. Real Win32 controls so that keyboard traversal and screen-reader
// names come from the system (IU-14), owner-drawn so that the palette is
// Sunshine's (D6). The token mapping lives in one table and nowhere else.
// ---------------------------------------------------------------------------

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
      ::CheckDlgButton(dialog, IDC_SCOPE_USER, BST_CHECKED);
      ::CheckDlgButton(dialog, IDC_DESKTOP_SHORTCUT, BST_CHECKED);
      ::CheckDlgButton(dialog, IDC_TASKBAR_SHORTCUT, BST_CHECKED);
      ::CheckDlgButton(dialog, IDC_LAUNCH_WHEN_DONE, BST_CHECKED);
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
      break;
    default:
      break;
  }
  return FALSE;
}

}  // namespace

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, LPWSTR, int) {
  Choices choices;
  bool elevated_continuation = false;
  if (!ParseCommandLine(&choices, &elevated_continuation)) {
    ::MessageBoxW(nullptr,
                  L"This installer was given an option it does not recognise, "
                  L"and will not run.",
                  L"Sunshine", MB_OK | MB_ICONERROR);
    return 2;
  }

  ::CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

  // The elevated relaunch does not draw. It was already agreed to, once, in the
  // window the user was looking at.
  if (elevated_continuation) {
    const Outcome outcome = RunEngine(choices, /*elevated=*/true);
    ::CoUninitialize();
    return outcome.ran ? static_cast<int>(outcome.exit_code) : 3;
  }

  DialogState state;
  state.installed_version = InstalledVersion();
  const INT_PTR result = ::DialogBoxParamW(instance, MAKEINTRESOURCEW(IDD_SETUP),
                                           nullptr, DialogProc,
                                           reinterpret_cast<LPARAM>(&state));
  if (result != IDOK || !state.accepted) {
    ::CoUninitialize();
    return 1;
  }

  int status = 0;
  if (state.choices.system_level) {
    DWORD exit_code = 0;
    if (RelaunchElevated(state.choices, &exit_code)) {
      status = static_cast<int>(exit_code);
    } else {
      status = 1;  // Declined, or could not elevate. Nothing was installed.
    }
  } else {
    const Outcome outcome = RunEngine(state.choices, /*elevated=*/false);
    status = outcome.ran ? static_cast<int>(outcome.exit_code) : 3;
  }
  ::CoUninitialize();
  return status;
}
