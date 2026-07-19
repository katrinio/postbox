"use client";

import { LogIn } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

const apiBaseUrl = process.env.NEXT_PUBLIC_POSTBOX_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

// Mock Telegram user for development
interface DevTelegramUser {
  id: number;
  first_name: string;
  username?: string;
}

interface TelegramUser {
  id: number;
  is_bot: boolean;
  first_name: string;
  username?: string;
  last_name?: string;
  language_code?: string;
  is_premium?: boolean;
  added_to_attachment_menu?: boolean;
  allows_user_initiated_help_requests?: boolean;
  allows_write_to_pm?: boolean;
  profile_accent_color_id?: number;
  profile_background_custom_emoji_id?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}

export default function LoginPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [telegramId, setTelegramId] = useState("");
  const [firstName, setFirstName] = useState("");
  const [username, setUsername] = useState("");

  const handleDevAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    if (!telegramId || !firstName) {
      setError("Пожалуйста, заполните обязательные поля");
      setIsLoading(false);
      return;
    }

    const authData = {
      id: parseInt(telegramId, 10),
      first_name: firstName,
      username: username || null,
      last_name: null,
      language_code: "ru",
      photo_url: null,
      auth_date: Math.floor(Date.now() / 1000),
      hash: "dev_hash_" + Date.now(), // Mock hash for development
    };

    try {
      const response = await fetch(`${apiBaseUrl}/api/auth/telegram`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(authData),
      });

      const data = await response.json();

      if (response.ok && data.token && data.is_approved) {
        localStorage.setItem("postbox-auth-token", data.token);
        localStorage.setItem("postbox-user-id", data.user_id);
        router.push("/");
      } else if (response.status === 200 && !data.is_approved) {
        setError(data.message || "Ожидается одобрение администратора");
      } else {
        setError(data.message || "Ошибка авторизации");
      }
    } catch (err) {
      console.error("Auth error:", err);
      setError("Ошибка подключения. Проверьте что API запущен на http://localhost:8000");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div
        style={{
          width: "100%",
          maxWidth: "400px",
          padding: "2rem",
          textAlign: "center",
        }}
      >
        <div
          style={{
            marginBottom: "2rem",
            display: "flex",
            justifyContent: "center",
          }}
        >
          <LogIn size={48} strokeWidth={1.5} />
        </div>

        <h1 style={{ fontSize: "1.5rem", fontWeight: "600", marginBottom: "0.5rem" }}>
          Postbox
        </h1>
        <p style={{ color: "var(--color-text-secondary)", marginBottom: "2rem" }}>
          Личный журнал бумажных писем
        </p>

        <form onSubmit={handleDevAuth} style={{ width: "100%" }}>
          <div style={{ marginBottom: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
              <label style={{ fontSize: "0.875rem", fontWeight: "500" }}>
                Telegram ID *
              </label>
              <a
                href="https://t.me/userinfobot"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  fontSize: "0.75rem",
                  color: "#0088cc",
                  textDecoration: "none",
                }}
              >
                Узнать ID →
              </a>
            </div>
            <input
              type="number"
              value={telegramId}
              onChange={(e) => setTelegramId(e.target.value)}
              placeholder="Откройте @userinfobot чтобы узнать"
              disabled={isLoading}
              style={{
                width: "100%",
                padding: "0.75rem",
                borderRadius: "0.5rem",
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-bg-secondary)",
                color: "var(--color-text)",
                fontSize: "1rem",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "1rem" }}>
            <label style={{ fontSize: "0.875rem", fontWeight: "500", display: "block", marginBottom: "0.5rem" }}>
              Имя *
            </label>
            <input
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              placeholder="John"
              disabled={isLoading}
              style={{
                width: "100%",
                padding: "0.75rem",
                borderRadius: "0.5rem",
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-bg-secondary)",
                color: "var(--color-text)",
                fontSize: "1rem",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "1.5rem" }}>
            <label style={{ fontSize: "0.875rem", fontWeight: "500", display: "block", marginBottom: "0.5rem" }}>
              Username (опционально)
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="john_doe"
              disabled={isLoading}
              style={{
                width: "100%",
                padding: "0.75rem",
                borderRadius: "0.5rem",
                border: "1px solid var(--color-border)",
                backgroundColor: "var(--color-bg-secondary)",
                color: "var(--color-text)",
                fontSize: "1rem",
                boxSizing: "border-box",
              }}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            style={{
              width: "100%",
              padding: "0.75rem",
              backgroundColor: isLoading ? "var(--color-text-disabled)" : "#0088cc",
              color: "white",
              border: "none",
              borderRadius: "0.5rem",
              fontSize: "1rem",
              fontWeight: "500",
              cursor: isLoading ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "0.5rem",
            }}
          >
            <LogIn size={18} />
            {isLoading ? "Вход..." : "Войти"}
          </button>
        </form>

        {error && (
          <div
            style={{
              marginTop: "1rem",
              padding: "1rem",
              backgroundColor: "rgba(220, 38, 38, 0.1)",
              borderLeft: "4px solid rgb(220, 38, 38)",
              borderRadius: "0.25rem",
              color: "rgb(127, 29, 29)",
              fontSize: "0.875rem",
            }}
          >
            {error}
          </div>
        )}

        <div
          style={{
            marginTop: "2rem",
            padding: "1rem",
            backgroundColor: "rgba(0, 136, 204, 0.05)",
            borderLeft: "4px solid #0088cc",
            borderRadius: "0.25rem",
            fontSize: "0.75rem",
            color: "var(--color-text-secondary)",
          }}
        >
          <strong>📱 Как найти свой Telegram ID:</strong>
          <ol style={{ marginTop: "0.5rem", marginBottom: "0.5rem", paddingLeft: "1.25rem" }}>
            <li>Откройте <a href="https://t.me/userinfobot" target="_blank" rel="noopener noreferrer" style={{ color: "#0088cc" }}>@userinfobot</a></li>
            <li>Скопируйте ваш ID из ответа</li>
            <li>Вставьте выше и нажмите "Войти"</li>
          </ol>
          <p style={{ margin: "0.5rem 0 0 0" }}>
            ✨ Первые 5 пользователей будут зарегистрированы автоматически.
          </p>
        </div>
      </div>
    </div>
  );
}
