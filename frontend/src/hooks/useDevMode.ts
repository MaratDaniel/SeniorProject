import { useEffect, useState } from "react";

// The dev mailbox exists only when the backend runs with ADAL_ENV=dev. Checked once per page load.
let known: boolean | null = null;
let pending: Promise<boolean> | null = null;

function check(): Promise<boolean> {
  if (known !== null) return Promise.resolve(known);
  if (!pending) {
    pending = fetch("/api/dev/outbox", { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then((res) => res.ok)
      .catch(() => false)
      .then((ok) => {
        known = ok;
        return ok;
      });
  }
  return pending;
}

export function useDevMode(): boolean {
  const [dev, setDev] = useState<boolean>(known ?? false);
  useEffect(() => {
    let alive = true;
    check().then((ok) => {
      if (alive) setDev(ok);
    });
    return () => {
      alive = false;
    };
  }, []);
  return dev;
}
