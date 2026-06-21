#!/usr/bin/env python3
"""
VoltIQ Africa — Automated Auth Patch Script
=============================================
Applies the 3 security fixes to your real index.html:
  1. Removes the plaintext USERS object
  2. Replaces doLogin() / doLogout() with real Worker-based auth
  3. Adds Authorization headers to all Worker fetch() calls
  4. Updates model string from claude-sonnet-4-5 to claude-sonnet-4-6

SAFETY: Creates a timestamped backup before touching anything.
Verifies every patch applied successfully before declaring success.
If ANY patch fails to match, the script stops and tells you exactly
which one — it will NOT partially patch your file.

USAGE:
    python3 patch_voltiq_auth.py /path/to/your/index.html

Run this from the same terminal where you have your index.html.
"""

import sys
import re
import shutil
import datetime

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 patch_voltiq_auth.py /path/to/index.html")
        sys.exit(1)

    filepath = sys.argv[1]

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"File not found: {filepath}")
        sys.exit(1)

    original_content = content
    backup_path = f"{filepath}.backup-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy(filepath, backup_path)
    print(f"Backup created: {backup_path}")

    patches_applied = []
    patches_failed = []

    users_pattern = re.compile(
        r"const USERS = \{[^}]*'admin':[^}]*\}[^}]*'operator':[^}]*\}[^}]*'demo':[^}]*\}[^}]*\};",
        re.DOTALL
    )
    if users_pattern.search(content):
        content = users_pattern.sub(
            "// USERS object removed - auth is now handled server-side by the Worker.\n"
            "// See WORKER_BASE_URL and doLogin()/doLogout() below.",
            content
        )
        patches_applied.append("Patch 1: Removed plaintext USERS object")
    else:
        patches_failed.append("Patch 1: Could not find USERS object pattern")

    old_dologin_pattern = re.compile(
        r"function doLogin\(\) \{.*?^\}",
        re.DOTALL | re.MULTILINE
    )

    new_dologin = '''const WORKER_BASE_URL = 'https://voltiq-api.momolistic2008.workers.dev';

let currentSessionToken = null;
let currentUserRole = null;

async function doLogin() {
  const user = document.getElementById('loginUser').value.trim();
  const pass = document.getElementById('loginPass').value;
  const err  = document.getElementById('loginError');
  const btn  = document.querySelector('.login-btn');

  if (!user || !pass) {
    err.textContent = 'Please enter both username and password.';
    err.style.display = 'block';
    return;
  }

  btn.disabled = true;
  btn.textContent = 'AUTHENTICATING...';
  err.style.display = 'none';

  try {
    const res = await fetch(`${WORKER_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password: pass }),
    });

    const data = await res.json();

    if (!res.ok) {
      err.textContent = (data.error || 'Invalid credentials. Please try again.');
      err.style.display = 'block';
      document.getElementById('loginPass').value = '';
      document.getElementById('loginPass').focus();
      return;
    }

    currentSessionToken = data.token;
    currentUserRole = data.role;

    document.getElementById('loginOverlay').style.display = 'none';
    document.getElementById('statusText').textContent = data.role.toUpperCase();
    document.getElementById('initTime').textContent =
      new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    sessionStart = Date.now();
    startSessionTimer();

    const adminBtn = document.getElementById('adminPanelBtn');
    if (adminBtn) {
      adminBtn.style.display = data.role === 'Administrator' ? 'inline-block' : 'none';
    }

  } catch (e) {
    err.textContent = 'Network error - could not reach authentication server.';
    err.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = 'ACCESS SYSTEM';
  }
}'''

    if old_dologin_pattern.search(content):
        content = old_dologin_pattern.sub(new_dologin, content, count=1)
        patches_applied.append("Patch 2a: Replaced doLogin()")
    else:
        patches_failed.append("Patch 2a: Could not find doLogin() function")

    old_dologout_pattern = re.compile(
        r"function doLogout\(\) \{.*?^\}",
        re.DOTALL | re.MULTILINE
    )

    new_dologout = '''async function doLogout() {
  if (currentSessionToken) {
    try {
      await fetch(`${WORKER_BASE_URL}/auth/logout`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${currentSessionToken}` },
      });
    } catch (e) {
    }
  }

  currentSessionToken = null;
  currentUserRole = null;
  sessionStart = null;

  document.getElementById('loginUser').value = '';
  document.getElementById('loginPass').value = '';
  document.getElementById('loginError').style.display = 'none';
  document.getElementById('loginOverlay').style.display = 'flex';
}'''

    if old_dologout_pattern.search(content):
        content = old_dologout_pattern.sub(new_dologout, content, count=1)
        patches_applied.append("Patch 2b: Replaced doLogout()")
    else:
        patches_failed.append("Patch 2b: Could not find doLogout() function")

    fetch_pattern = re.compile(
        r"(fetch\('https://voltiq-api\.momolistic2008\.workers\.dev',\s*\{\s*method:\s*'POST',\s*headers:\s*\{\s*)'Content-Type':\s*'application/json'(\s*\})",
    )

    count_before = len(fetch_pattern.findall(content))
    if count_before > 0:
        content = fetch_pattern.sub(
            r"\1'Content-Type': 'application/json', 'Authorization': `Bearer ${currentSessionToken}`\2",
            content
        )
        patches_applied.append(f"Patch 3: Added auth header to {count_before} fetch() call(s)")
    else:
        patches_failed.append("Patch 3: Could not find fetch() calls to patch (0 matches)")

    model_count = content.count("claude-sonnet-4-5")
    if model_count > 0:
        content = content.replace("claude-sonnet-4-5", "claude-sonnet-4-6")
        patches_applied.append(f"Patch 4: Updated {model_count} model string reference(s) to claude-sonnet-4-6")
    else:
        patches_failed.append("Patch 4: No 'claude-sonnet-4-5' references found (may already be updated)")

    print("\n" + "="*70)
    print("PATCH RESULTS")
    print("="*70)
    for p in patches_applied:
        print(f"OK: {p}")
    for p in patches_failed:
        print(f"WARN: {p}")

    critical_patches = ["Patch 1", "Patch 2a", "Patch 2b", "Patch 3"]
    critical_failed = [p for p in patches_failed if any(p.startswith(cp) for cp in critical_patches)]

    if critical_failed:
        print("\nCRITICAL PATCHES FAILED. File NOT modified.")
        print(f"Your original file is untouched. Backup also at: {backup_path}")
        print("\nShare the relevant section of your file and we'll fix the pattern.")
        sys.exit(1)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\nALL CRITICAL PATCHES APPLIED SUCCESSFULLY")
    print(f"File updated: {filepath}")
    print(f"Backup available at: {backup_path}")
    print("\nNext steps:")
    print("1. Open index.html in a browser and confirm the login screen still loads")
    print("2. Confirm 'View Source' no longer shows any password")
    print("3. Deploy your Worker (see DEPLOY.md) BEFORE testing login")
    print("4. git add . && git commit -m 'fix: server-side auth, remove plaintext passwords'")
    print("5. git push")


if __name__ == "__main__":
    main()
