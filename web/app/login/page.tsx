"use client";

import { LogIn } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const BOT_USERNAME = "PostboxBot";
const apiBaseUrl = process.env.NEXT_PUBLIC_POSTBOX_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

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
  const [statusCode, setStatusCode] = useState<number | null>(null);
  const scriptLoaded = useRef(false);

  useEffect(() => {
    if (scriptLoaded.current) return;
    scriptLoaded.current = true;

    // Load Telegram Login Widget script
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-web-app.js";
    script.async = true;
    document.body.appendChild(script);
  }, []);

  const handleTelegramAuth = (user: TelegramUser) => {
    setIsLoading(true);
    setError(null);

    const authData = {
      id: user.id,
      first_name: user.first_name,
      username: user.username || null,
      last_name: user.last_name || null,
      language_code: user.language_code || null,
      photo_url: user.photo_url || null,
      auth_date: user.auth_date,
      hash: user.hash,
    };

    fetch(`${apiBaseUrl}/api/auth/telegram`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(authData),
    })
      .then(async (response) => {
        const data = await response.json();
        setStatusCode(response.status);

        if (response.ok && data.token && data.is_approved) {
          // Save token to localStorage
          localStorage.setItem("postbox-auth-token", data.token);
          localStorage.setItem("postbox-user-id", data.user_id);
          // Redirect to main app
          router.push("/");
        } else if (response.status === 200 && !data.is_approved) {
          setError(data.message || "Ожидается одобрение администратора");
        } else {
          setError(data.message || "Ошибка авторизации. Пожалуйста, попробуйте еще раз.");
        }
      })
      .catch((err) => {
        console.error("Auth error:", err);
        setError("Ошибка подключения. Пожалуйста, проверьте соединение и попробуйте еще раз.");
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    // Initialize Telegram Login Widget
    setTimeout(() => {
      if ((window as any).Telegram?.Login) {
        (window as any).Telegram.Login.auth(
          {
            bot_id: 8801253207,
            request_access: "write",
          },
          handleTelegramAuth
        );
      } else {
        // Fallback: create a button that opens Telegram login
        const button = document.getElementById("telegram-login-btn");
        if (button) {
          button.style.display = "block";
        }
      }
    }, 100);
  }, []);

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

        <div
          id="telegram-login-btn"
          style={{
            display: "none",
            marginBottom: "1rem",
          }}
        >
          <a
            href={`https://t.me/${BOT_USERNAME}?start=login`}
            style={{
              display: "inline-block",
              padding: "0.75rem 1.5rem",
              backgroundColor: "#0088cc",
              color: "white",
              borderRadius: "0.5rem",
              textDecoration: "none",
              fontWeight: "500",
            }}
          >
            Войти через Telegram
          </a>
        </div>

        {error && (
          <div
            style={{
              padding: "1rem",
              marginBottom: "1rem",
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

        {isLoading && (
          <div style={{ padding: "1rem", color: "var(--color-text-secondary)" }}>
            Загрузка...
          </div>
        )}

        <p
          style={{
            marginTop: "2rem",
            fontSize: "0.875rem",
            color: "var(--color-text-secondary)",
          }}
        >
          Первые 5 пользователей будут зарегистрированы автоматически.
          <br />
          Остальные будут ждать одобрения администратора.
        </p>
      </div>
    </div>
  );
}
