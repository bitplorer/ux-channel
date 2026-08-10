/**
 * ux-channel browser client surface (0.1).
 * Status: DX stub — mirrors ``ux-channel.js`` / ``window.uxChannel``.
 */

export type ProtocolV = "1";

export interface Intent {
  v: ProtocolV;
  action: string;
  args?: Record<string, unknown>;
  cap?: string;
  target?: string;
  request_id?: string;
  form?: Record<string, unknown>;
  accept_stream?: boolean;
  idempotency_key?: string;
  meta?: Record<string, unknown>;
}

export interface Result {
  v: ProtocolV;
  ok: boolean;
  ops: Op[];
  error?: { code: string; message: string; fields?: Record<string, string[]>; retryable?: boolean };
  meta?: Record<string, unknown>;
}

export type Op = {
  op: string;
  target?: string;
  html?: string;
  [key: string]: unknown;
};

export interface UxChannel {
  runAction(action: string, args?: Record<string, unknown>, cap?: string, target?: string, opts?: object): Promise<Result>;
  applyResult(result: Result, opts?: object): Promise<void>;
  postIntent(intent: Intent): Promise<Result>;
  on(eventName: string, fn: (detail: unknown, ev: Event) => void): () => void;
  version: string;
  reportError(kind: string, payload?: object): unknown;
  configure(opts?: object): object;
}

declare global {
  interface Window {
    uxChannel: UxChannel;
    uxBridge?: { scan(root?: ParentNode): void; [k: string]: unknown };
    uxInspector?: { frames(): unknown[]; conversations(): unknown[] };
  }
}

export {};
