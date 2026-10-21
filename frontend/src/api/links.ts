import { useMutation } from "@tanstack/react-query";

import { ApiError, postJson } from "./client.ts";

export interface Link {
  code: string;
  short_url: string;
  original_url: string;
  created_at: string;
}

export function useCreateLink() {
  return useMutation<Link, ApiError, string>({
    mutationFn: (url) => postJson<Link>("/api/links", { url }),
  });
}
