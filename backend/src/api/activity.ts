export async function logActivity(action: string, payload: any) {
  try {
    await fetch("http://localhost:8000/activity/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: "u1",
        project_id: "p1",
        action,
        payload
      })
    });
  } catch (e) {
    // silent fail by design
  }
}
