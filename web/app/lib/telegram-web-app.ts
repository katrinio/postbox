/**
 * Telegram Web App utilities
 * https://core.telegram.org/bots/webapps
 */

export interface TelegramUser {
  id: number;
  is_bot: boolean;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  is_premium?: boolean;
  photo_url?: string;
}

export interface TelegramWebAppData {
  user: TelegramUser;
  auth_date: number;
  hash: string;
  start_param?: string;
}

export function getTelegramWebAppData(): TelegramWebAppData | null {
  if (typeof window === "undefined") return null;

  const webApp = (window as any).Telegram?.WebApp;
  if (!webApp) return null;

  // Web App provides initData as a string that needs to be parsed
  const initData = webApp.initData;
  if (!initData) return null;

  // Parse initData
  const params = new URLSearchParams(initData);
  const user = params.get("user");
  const authDate = params.get("auth_date");
  const hash = params.get("hash");
  const startParam = params.get("start_param");

  if (!user || !authDate || !hash) return null;

  try {
    return {
      user: JSON.parse(user),
      auth_date: parseInt(authDate, 10),
      hash,
      start_param: startParam || undefined,
    };
  } catch {
    return null;
  }
}

export function isWebApp(): boolean {
  if (typeof window === "undefined") return false;
  return !!(window as any).Telegram?.WebApp;
}

export function closeWebApp(): void {
  if (typeof window === "undefined") return;
  (window as any).Telegram?.WebApp?.close?.();
}
