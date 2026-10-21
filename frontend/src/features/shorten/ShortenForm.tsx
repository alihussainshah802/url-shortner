import { Loader2, Printer } from "lucide-react";
import { useState, type FormEvent } from "react";

import { useCreateLink } from "@/api/links.ts";
import { Alert, AlertDescription } from "@/components/ui/alert.tsx";
import { Button } from "@/components/ui/button.tsx";
import { Input } from "@/components/ui/input.tsx";
import { Label } from "@/components/ui/label.tsx";

import { LabelResult } from "./LabelResult.tsx";
import { normalizeUrl } from "./utils.ts";

export function ShortenForm() {
  const [url, setUrl] = useState("");
  const { mutate, data, error, isPending, reset } = useCreateLink();

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = normalizeUrl(url);
    if (target === "") return;
    mutate(target);
  }

  return (
    <div>
      {/* The printer: ink-coloured body that holds the form. */}
      <form
        onSubmit={onSubmit}
        className="rounded-t-lg bg-primary px-5 pt-5 pb-6 text-primary-foreground sm:px-6"
      >
        <Label htmlFor="url" className="font-mono text-xs tracking-widest uppercase">
          Long link
        </Label>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row">
          <Input
            id="url"
            name="url"
            type="text"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            placeholder="https://example.com/a/very/long/path"
            value={url}
            onChange={(event) => {
              setUrl(event.target.value);
              if (error) reset();
            }}
            aria-invalid={error ? true : undefined}
            className="h-11 border-transparent bg-card font-mono text-sm text-card-foreground"
          />
          <Button
            type="submit"
            disabled={isPending}
            className="h-11 bg-accent px-5 text-accent-foreground hover:bg-accent/85"
          >
            {isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Printer aria-hidden />}
            {isPending ? "Printing…" : "Print short link"}
          </Button>
        </div>
        {error && (
          <Alert variant="destructive" className="mt-4 border-0 bg-card">
            <AlertDescription>{error.message}</AlertDescription>
          </Alert>
        )}
      </form>

      {/* The slot the label feeds out of. */}
      <div aria-hidden className="h-2 bg-black/90 shadow-[inset_0_-3px_0_0_rgb(255_255_255/0.12)]" />

      <div aria-live="polite">{data && <LabelResult key={data.code} link={data} />}</div>
    </div>
  );
}
