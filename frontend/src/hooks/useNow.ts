import { useSyncExternalStore } from "react";
import { serverNow } from "../api/client";

// One shared one-second ticker for every countdown on the page.
const subscribers = new Set<() => void>();
let timer: number | undefined;

function subscribe(callback: () => void): () => void {
  subscribers.add(callback);
  if (timer === undefined) {
    timer = window.setInterval(() => {
      for (const cb of subscribers) cb();
    }, 1000);
  }
  return () => {
    subscribers.delete(callback);
    if (subscribers.size === 0 && timer !== undefined) {
      window.clearInterval(timer);
      timer = undefined;
    }
  };
}

function snapshot(): number {
  return Math.floor(serverNow() / 1000) * 1000;
}

/** Server time in ms, refreshed every second. */
export function useNow(): number {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}
