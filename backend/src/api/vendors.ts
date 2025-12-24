const API_BASE = "http://127.0.0.1:8000";
const USER_ID = "demo_user";

// Load vendors for current user
export async function loadPreferredVendors() {
  const res = await fetch(`${API_BASE}/vendors/?user_id=${USER_ID}`);
  return await res.json();
}

// Add vendor
export async function addPreferredVendor(name: string, phone: string, trade: string) {
  const res = await fetch(`${API_BASE}/vendors/add`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: USER_ID, name, phone, trade }),
  });
  return await res.json();
}

// Remove vendor
export async function removePreferredVendor(name: string) {
  const res = await fetch(`${API_BASE}/vendors/remove`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: USER_ID, name }),
  });
  return await res.json();
}
