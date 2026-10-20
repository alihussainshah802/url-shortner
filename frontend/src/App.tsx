import { useEffect, useState } from "react";
import { fetchHealth } from "./api/health.ts";

type ApiState = "checking" | "ok" | "down";

export default function App() {
  const [api, setApi] = useState<ApiState>("checking");

  useEffect(() => {
    fetchHealth()
      .then((h) => setApi(h.status === "ok" ? "ok" : "down"))
      .catch(() => setApi("down"));
  }, []);

  return (
    <main>
      <h1>url-shortner</h1>
      <p>API status: {api}</p>
    </main>
  );
}
