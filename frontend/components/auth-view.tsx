"use client";

import { useState, type FormEvent } from "react";
import { Loader2, LockKeyhole } from "lucide-react";
import { login, register, type AuthResponse } from "@/lib/api/backend";

export function AuthView({ onAuthenticated }: { onAuthenticated: (auth: AuthResponse) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      onAuthenticated(await (mode === "login" ? login(email, password) : register(email, password)));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authentication failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-midnight-lowest p-4">
      <section className="glass-panel w-full max-w-sm p-6" aria-labelledby="auth-heading">
        <div className="mb-6 flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-rag bg-rag-primaryStrong/20 text-rag-primary">
            <LockKeyhole className="h-5 w-5" />
          </div>
          <div>
            <h1 id="auth-heading" className="text-xl font-semibold text-rag-primary">Agent-RAG</h1>
            <p className="text-sm text-rag-muted">{mode === "login" ? "Sign in to your workspace" : "Create your workspace account"}</p>
          </div>
        </div>
        <div className="mb-5 grid grid-cols-2 rounded-rag bg-midnight-lowest p-1">
          {(["login", "register"] as const).map((item) => (
            <button
              key={item}
              className={`min-h-9 rounded-rag text-sm capitalize ${mode === item ? "bg-rag-primaryStrong text-rag-primary" : "text-rag-muted"}`}
              type="button"
              onClick={() => { setMode(item); setError(""); }}
            >
              {item}
            </button>
          ))}
        </div>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="block text-sm text-rag-muted">
            Email
            <input
              required
              autoComplete="email"
              className="mt-1 h-10 w-full rounded-rag border border-rag-outline/50 bg-midnight-lowest px-3 text-rag-text outline-none focus:border-rag-secondary"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label className="block text-sm text-rag-muted">
            Password
            <input
              required
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className="mt-1 h-10 w-full rounded-rag border border-rag-outline/50 bg-midnight-lowest px-3 text-rag-text outline-none focus:border-rag-secondary"
              minLength={10}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error ? <p className="text-sm text-rag-error" role="alert">{error}</p> : null}
          <button
            className="flex h-10 w-full items-center justify-center gap-2 rounded-rag bg-rag-primaryStrong text-rag-primary disabled:opacity-60"
            disabled={loading}
            type="submit"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
      </section>
    </main>
  );
}
