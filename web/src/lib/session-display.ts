import type { ConnectionState } from "@/lib/gatewayClient";

export function sessionSourceLabel(source: string | null | undefined): string {
  const value = source?.trim();
  return value || "source not recorded";
}

export function sessionModelLabel(model: string | null | undefined): string {
  const value = model?.trim();
  if (!value) return "model not recorded";
  return value.split("/").filter(Boolean).pop() ?? value;
}

export function configuredModelLabel(
  model: string | null | undefined,
): string {
  const value = model?.trim();
  if (!value) return "model not observed";
  return value.split("/").filter(Boolean).pop() ?? value;
}

const CHAT_CONTROL_STATE: Record<ConnectionState, string> = {
  idle: "chat controls: idle",
  connecting: "chat controls: connecting",
  open: "chat controls: live",
  closed: "chat controls: closed",
  error: "chat controls: error",
};

export function chatControlStateLabel(state: ConnectionState): string {
  return CHAT_CONTROL_STATE[state];
}
