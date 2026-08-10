import { Suspense } from "react";
import { Dashboard } from "@/components/Dashboard";

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="flex h-dvh items-center justify-center bg-zinc-950">
          <p className="animate-pulse font-mono text-xs tracking-widest text-zinc-500">
            LOADING BLACKBOX…
          </p>
        </div>
      }
    >
      <Dashboard />
    </Suspense>
  );
}
