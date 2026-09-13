// Copyright 2026 The Sunshine Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// Sunshine's uninstall launcher.
//
// **It does not uninstall anything, and it deliberately asks nothing.** Windows
// already knows how to remove Sunshine: `setup.exe` writes `UninstallString`
// into `Software\Microsoft\Windows\CurrentVersion\Uninstall\Sunshine` at
// install time, and Settings -> Apps runs it. What did not exist was a file a
// person could double-click, and that is all this is: it finds that string and
// runs it.
//
// The reason it asks nothing is the same reason `docs/INSTALLER_UI_CONTRACT.md`
// section 1 gives for the setup front-end not reimplementing installation.
// `setup.exe --uninstall` launches `chrome.exe --uninstall` to draw the
// confirmation dialog -- which is also where the "delete my profile data"
// choice lives, and where a running browser is detected. A dialog of our own
// would be a second confirmation in front of that one, asking the same question
// worse.
//
// **The security-shaped part is which hive the command came from.**
// `HKEY_CURRENT_USER` is writable by the unprivileged user. A program that read
// a command line from there and ran it *elevated* would be a local privilege
// escalation with a shortcut on the desktop. So the hive decides: a per-user
// installation's command runs with the token this process already has, and only
// a command read from `HKEY_LOCAL_MACHINE` -- a key an unprivileged user cannot
// write -- is ever elevated. UN-3 states it and
// `scripts/verify_installer_frontend.py` refuses a source that breaks it.

#include <windows.h>

#include <shellapi.h>

#include <string>

#include "uninstall_resource.h"

namespace {

// Section 5 of the installer contract: the engine's exit code passes through
// untouched, so these sit well above the range `installer::InstallStatus` uses.
constexpr int kExitNothingInstalled = 0xB1;
constexpr int kExitBadRegistration = 0xB2;
constexpr int kExitCouldNotRun = 0xB3;
constexpr int kExitRefusedElevation = 0xB4;

constexpr wchar_t kUninstallKey[] =
    L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Sunshine";

// What one hive's registration says. `machine` is the whole security story:
// see the file comment.
struct Registration {
  bool found = false;
  bool machine = false;
  std::wstring command;
  std::wstring display_version;
};

std::wstring ReadString(HKEY key, const wchar_t* name) {
  DWORD bytes = 0;
  // RegGetValueW rather than RegQueryValueExW: HKCU is writable by an
  // unprivileged user and RegQueryValueExW documents that a REG_SZ "may not
  // have been stored with the proper terminating null characters", so the
  // string this program is about to parse could have run off the end of its
  // buffer. RRF_RT_REG_SZ also rejects every other type without a second check.
  if (::RegGetValueW(key, nullptr, name, RRF_RT_REG_SZ, nullptr, nullptr,
                     &bytes) != ERROR_SUCCESS ||
      bytes < sizeof(wchar_t)) {
    return std::wstring();
  }
  std::wstring value(bytes / sizeof(wchar_t), L'\0');
  if (::RegGetValueW(key, nullptr, name, RRF_RT_REG_SZ, nullptr, value.data(),
                     &bytes) != ERROR_SUCCESS) {
    return std::wstring();
  }
  value.resize(::wcsnlen(value.c_str(), value.size()));
  return value;
}

// HKCU first, then HKLM, which is the order a person means. Somebody with both
// a per-user and a per-machine Sunshine is removing the one that is theirs;
// the per-machine one is still in Settings -> Apps, and removing it needs an
// administrator anyway.
Registration FindInstallation() {
  for (const auto& hive : {std::pair{HKEY_CURRENT_USER, false},
                           std::pair{HKEY_LOCAL_MACHINE, true}}) {
    HKEY key = nullptr;
    if (::RegOpenKeyExW(hive.first, kUninstallKey, 0,
                        KEY_QUERY_VALUE | KEY_WOW64_32KEY, &key) != ERROR_SUCCESS) {
      continue;
    }
    Registration found;
    found.command = ReadString(key, L"UninstallString");
    found.display_version = ReadString(key, L"DisplayVersion");
    ::RegCloseKey(key);
    if (!found.command.empty()) {
      found.found = true;
      found.machine = hive.second;
      return found;
    }
  }
  return Registration();
}

// Splits `"C:\...\setup.exe" --uninstall --system-level` into the program and
// the rest.
//
// Hand-written rather than CommandLineToArgvW because that function returns an
// *argument vector*, and rebuilding a command line from one re-quotes it --
// a lossy round trip through the exact syntax this program must not alter. The
// string was written by upstream's own installer and is passed on as it was
// found.
bool SplitCommand(const std::wstring& line, std::wstring* program,
                  std::wstring* arguments) {
  size_t begin = line.find_first_not_of(L' ');
  if (begin == std::wstring::npos) {
    return false;
  }
  size_t end = 0;
  if (line[begin] == L'"') {
    end = line.find(L'"', begin + 1);
    if (end == std::wstring::npos) {
      return false;
    }
    *program = line.substr(begin + 1, end - begin - 1);
    ++end;
  } else {
    end = line.find(L' ', begin);
    if (end == std::wstring::npos) {
      end = line.size();
    }
    *program = line.substr(begin, end - begin);
  }
  if (program->empty()) {
    return false;
  }
  size_t rest = line.find_first_not_of(L' ', end);
  *arguments = rest == std::wstring::npos ? std::wstring() : line.substr(rest);
  return true;
}

void Say(const wchar_t* text, UINT icon) {
  ::MessageBoxW(nullptr, text, L"Sunshine", MB_OK | icon);
}

}  // namespace

int WINAPI wWinMain(HINSTANCE, HINSTANCE, LPWSTR, int) {
  const Registration installation = FindInstallation();
  if (!installation.found) {
    // Not an error the way a failure is. Somebody double-clicked this on a
    // machine with no Sunshine on it, and the useful thing to say is that
    // there is nothing to remove.
    Say(L"Sunshine does not appear to be installed on this computer, so there "
        L"is nothing to remove.",
        MB_ICONINFORMATION);
    return kExitNothingInstalled;
  }

  std::wstring program;
  std::wstring arguments;
  if (!SplitCommand(installation.command, &program, &arguments)) {
    Say(L"Sunshine's uninstall registration could not be read. It can still be "
        L"removed from Settings \u2192 Apps.",
        MB_ICONERROR);
    return kExitBadRegistration;
  }

  // UN-3. `runas` only for the per-machine installation, whose command came
  // from a key an unprivileged user cannot write. The per-user command runs
  // with the token this process already has -- elevating it would let anyone
  // who can write their own HKCU choose what an administrator runs.
  SHELLEXECUTEINFOW execute = {};
  execute.cbSize = sizeof(execute);
  execute.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC;
  execute.lpVerb = installation.machine ? L"runas" : L"open";
  execute.lpFile = program.c_str();
  execute.lpParameters = arguments.empty() ? nullptr : arguments.c_str();
  execute.nShow = SW_SHOWNORMAL;

  if (!::ShellExecuteExW(&execute)) {
    if (::GetLastError() == ERROR_CANCELLED) {
      // The elevation prompt was refused. Nothing was removed and that is not
      // a failure -- the same reading IU-12 takes of a declined prompt.
      return kExitRefusedElevation;
    }
    Say(L"Sunshine's uninstaller could not be started. It can still be removed "
        L"from Settings \u2192 Apps.",
        MB_ICONERROR);
    return kExitCouldNotRun;
  }

  // Wait, and report what upstream reported. This program adds no opinion about
  // what a given status means: `setup.exe` decides whether an uninstall
  // happened, and section 5 of the contract says its code is passed through.
  DWORD status = 0;
  if (execute.hProcess) {
    ::WaitForSingleObject(execute.hProcess, INFINITE);
    ::GetExitCodeProcess(execute.hProcess, &status);
    ::CloseHandle(execute.hProcess);
  }
  return static_cast<int>(status);
}
