async function apiFetch(url, options = {}) {
  const opts = Object.assign({ credentials: "include" }, options);
  opts.headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
  return fetch(url, opts);
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function requireLogin() {
  const res = await apiFetch("/api/auth/me");
  if (!res.ok) {
    window.location.href = "/login";
    return null;
  }
  const user = await res.json();
  const navUser = document.getElementById("nav-user");
  const navLogout = document.getElementById("nav-logout");
  if (navUser) navUser.textContent = `${user.display_name} (${user.email})`;
  if (navLogout) {
    navLogout.style.display = "inline-block";
    navLogout.onclick = async () => {
      await apiFetch("/api/auth/logout", { method: "POST" });
      window.location.href = "/login";
    };
  }
  return user;
}

function formatDateTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
