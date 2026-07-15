export type ExpiringSession = {
  access_token: string;
  expires_in: number;
};

export class AuthenticationExpiredError extends Error {
  constructor(message = "Your session has expired. Please sign in again.") {
    super(message);
    this.name = "AuthenticationExpiredError";
  }
}

type SessionListener<T> = (session: T | null) => void;

const REFRESH_LEAD_MS = 60_000;
const REFRESH_RETRY_MS = 30_000;

export class AuthSessionManager<T extends ExpiringSession> {
  private session: T | null = null;
  private expiresAt = 0;
  private refreshPromise: Promise<T> | null = null;
  private refreshTimer: number | null = null;
  private listeners = new Set<SessionListener<T>>();
  private generation = 0;

  constructor(private readonly requestRefresh: () => Promise<T>) {}

  accept(session: T): T {
    this.generation += 1;
    return this.store(session);
  }

  private store(session: T): T {
    this.session = session;
    this.expiresAt = Date.now() + Math.max(0, session.expires_in) * 1000;
    this.scheduleRefresh();
    this.emit(session);
    return session;
  }

  clear(): void {
    const hadSession = this.session !== null;
    this.generation += 1;
    this.session = null;
    this.expiresAt = 0;
    this.clearRefreshTimer();
    if (hadSession) this.emit(null);
  }

  subscribe(listener: SessionListener<T>): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  async accessToken(minValidityMs = REFRESH_LEAD_MS): Promise<string> {
    if (!this.session) {
      await this.refresh();
    } else if (this.expiresAt - Date.now() <= minValidityMs) {
      try {
        await this.refresh();
      } catch (error) {
        if (!this.session || this.expiresAt <= Date.now()) throw error;
      }
    }
    if (!this.session) throw new AuthenticationExpiredError();
    return this.session.access_token;
  }

  async refresh(): Promise<T> {
    if (!this.refreshPromise) {
      const generation = this.generation;
      this.refreshPromise = this.requestRefresh()
        .then((session) => {
          if (generation === this.generation) return this.store(session);
          if (this.session) return this.session;
          throw new AuthenticationExpiredError();
        })
        .catch((error: unknown) => {
          if (error instanceof AuthenticationExpiredError) this.clear();
          else this.scheduleRetry();
          throw error;
        })
        .finally(() => {
          this.refreshPromise = null;
        });
    }
    return this.refreshPromise;
  }

  private scheduleRefresh(): void {
    this.clearRefreshTimer();
    if (typeof window === "undefined" || !this.session) return;
    const lifetimeMs = Math.max(0, this.session.expires_in) * 1000;
    const leadMs = Math.min(REFRESH_LEAD_MS, lifetimeMs / 2);
    const delayMs = Math.max(1_000, this.expiresAt - Date.now() - leadMs);
    this.refreshTimer = window.setTimeout(() => {
      void this.refresh().catch(() => undefined);
    }, delayMs);
  }

  private scheduleRetry(): void {
    this.clearRefreshTimer();
    if (typeof window === "undefined" || !this.session) return;
    this.refreshTimer = window.setTimeout(() => {
      void this.refresh().catch(() => undefined);
    }, REFRESH_RETRY_MS);
  }

  private clearRefreshTimer(): void {
    if (this.refreshTimer !== null) clearTimeout(this.refreshTimer);
    this.refreshTimer = null;
  }

  private emit(session: T | null): void {
    this.listeners.forEach((listener) => listener(session));
  }
}

export function isAuthenticationExpiredError(error: unknown): error is AuthenticationExpiredError {
  return error instanceof AuthenticationExpiredError;
}
