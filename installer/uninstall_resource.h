// Copyright 2026 The Sunshine Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef SUNSHINE_INSTALLER_UNINSTALL_RESOURCE_H_
#define SUNSHINE_INSTALLER_UNINSTALL_RESOURCE_H_

// The launcher's only resource. It carries no dialog and no engine: UN-1 is
// that it asks nothing and installs nothing, so there is nothing else to
// embed. Separate from resource.h so that the setup front-end's ids and this
// one's cannot drift into each other.
#define IDI_UNINSTALL 103

#endif  // SUNSHINE_INSTALLER_UNINSTALL_RESOURCE_H_
