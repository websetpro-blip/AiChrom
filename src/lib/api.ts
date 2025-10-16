const BASE = "http://127.0.0.1:8765";

export async function getProfiles() {
  const r = await fetch(`${BASE}/profiles`);
  return r.json();
}

export async function createProfile() {
  const r = await fetch(`${BASE}/profiles`, { method: "POST" });
  return r.json();
}

export async function startProfile(id?: string) {
  const r = await fetch(`${BASE}/profiles/${id}/start`, { method: "POST" });
  return r.json();
}

export async function selfTest(id?: string) {
  const r = await fetch(`${BASE}/profiles/${id}/selftest`, { method: "POST" });
  return r.json();
}

export async function startSelected() { 
  // заготовка под выделенные строки 
  return { ok: true }; 
}

export async function selfTestSelected() { 
  return { ok: true }; 
}
