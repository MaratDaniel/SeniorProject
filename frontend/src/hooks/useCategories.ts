import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Category } from "../api/types";

let cache: Category[] | null = null;
let pending: Promise<Category[]> | null = null;

function load(): Promise<Category[]> {
  if (cache) return Promise.resolve(cache);
  if (!pending) {
    pending = api<Category[]>("/api/categories")
      .then((list) => {
        cache = list;
        return list;
      })
      .catch(() => {
        pending = null;
        return [];
      });
  }
  return pending;
}

export function useCategories(): Category[] {
  const [list, setList] = useState<Category[]>(cache ?? []);
  useEffect(() => {
    let alive = true;
    load().then((l) => {
      if (alive) setList(l);
    });
    return () => {
      alive = false;
    };
  }, []);
  return list;
}

export function categoryName(list: Category[], slug: string): string {
  return list.find((c) => c.slug === slug)?.name ?? slug.charAt(0).toUpperCase() + slug.slice(1).replace(/[-_]/g, " ");
}
