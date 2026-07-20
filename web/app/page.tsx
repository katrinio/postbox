"use client";

import {
  ArrowDownLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronRight,
  CloudOff,
  Home,
  Inbox,
  LogOut,
  MailPlus,
  Monitor,
  Moon,
  PenLine,
  Settings2,
  Send,
  Sun,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "./hooks/useAuth";
import { JournalScreen } from "./JournalScreen";

type Tab = "home" | "journal" | "new";
type PreviewMode = "default" | "empty" | "offline";
type ThemeMode = "system" | "light" | "dark";

type MailCardProps = {
  name: string;
  sent: string;
  travel: string;
  tone: "blush" | "sage" | "blue";
};

const tabs: Array<{ id: Tab; label: string; icon: typeof Home }> = [
  { id: "home", label: "Дом", icon: Home },
  { id: "journal", label: "Журнал", icon: BookOpen },
  { id: "new", label: "Новое", icon: PenLine },
];

const previewModes: Array<{ id: PreviewMode; label: string }> = [
  { id: "default", label: "Обычный" },
  { id: "empty", label: "Пустой" },
  { id: "offline", label: "Без сети" },
];

const themeModes: Array<{ id: ThemeMode; label: string; icon: typeof Sun }> = [
  { id: "system", label: "Система", icon: Monitor },
  { id: "light", label: "Светлая", icon: Sun },
  { id: "dark", label: "Ночная", icon: Moon },
];

function MailCard({ name, sent, travel, tone }: MailCardProps) {
  return (
    <article className={`mail-card mail-card--${tone}`}>
      <div>
        <span className="mail-card__direction">
          <ArrowUpRight aria-hidden="true" size={15} strokeWidth={2} />
          исходящее
        </span>
        <h3>{name}</h3>
        <p>{sent}</p>
        <strong>{travel}</strong>
      </div>
      <ChevronRight className="mail-card__chevron" aria-hidden="true" size={24} strokeWidth={1.8} />
    </article>
  );
}

function SectionHeading({ title, count }: { title: string; count?: number }) {
  return (
    <div className="section-heading">
      <h2>{title}</h2>
      {count !== undefined && (
        <span className="section-heading__count">
          {count}
          <ChevronRight aria-hidden="true" size={19} strokeWidth={1.8} />
        </span>
      )}
    </div>
  );
}

function EmptyHome({ onCreate }: { onCreate: () => void }) {
  return (
    <section className="empty-state" aria-labelledby="empty-title">
      <div className="empty-state__mark" aria-hidden="true">
        <Inbox size={28} strokeWidth={1.7} />
      </div>
      <p className="eyebrow">Пока тихо</p>
      <h2 id="empty-title">Первое письмо начнёт историю</h2>
      <p>Запиши открытку, которую отправила или неожиданно получила.</p>
      <button className="primary-button" type="button" onClick={onCreate}>
        <MailPlus aria-hidden="true" size={19} />
        Добавить письмо
      </button>
    </section>
  );
}

function HomeScreen({ mode, onCreate }: { mode: PreviewMode; onCreate: () => void }) {
  if (mode === "empty") {
    return <EmptyHome onCreate={onCreate} />;
  }

  return (
    <>
      {mode === "offline" && (
        <div className="offline-banner" role="status">
          <CloudOff aria-hidden="true" size={18} />
          <span>
            <strong>Сейчас нет сети</strong>
            Показываем последние сохранённые записи
          </span>
        </div>
      )}

      <section className="mail-section" aria-labelledby="travelling-title">
        <div id="travelling-title">
          <SectionHeading title="В пути" count={2} />
        </div>
        <div className="mail-stack">
          <MailCard name="Маша" sent="Отправлено 12 июля" travel="4 дня в пути" tone="blush" />
          <MailCard name="Анна" sent="Отправлено 8 июля" travel="8 дней в пути" tone="sage" />
        </div>
      </section>

      <section className="recent-section" aria-labelledby="recent-title">
        <div id="recent-title">
          <SectionHeading title="Недавно получено" />
        </div>
        <article className="recent-card">
          <span className="recent-card__icon" aria-hidden="true">
            <ArrowDownLeft size={22} strokeWidth={1.8} />
          </span>
          <div>
            <h3>От мамы</h3>
            <p>Сегодня</p>
          </div>
          <ChevronRight aria-hidden="true" size={23} strokeWidth={1.8} />
        </article>
      </section>
    </>
  );
}

function NewMailScreen() {
  return (
    <section className="new-screen" aria-labelledby="new-title">
      <div className="screen-intro">
        <p className="eyebrow">Новое событие</p>
        <h2 id="new-title">Что произошло?</h2>
        <p>Выбери направление — детали спросим на следующем шаге.</p>
      </div>
      <div className="choice-stack">
        <button className="choice-card choice-card--send" type="button">
          <span className="choice-card__icon" aria-hidden="true"><Send size={24} /></span>
          <span>
            <strong>Я отправила</strong>
            <small>Письмо или открытка начали путь</small>
          </span>
          <ArrowRight aria-hidden="true" size={22} />
        </button>
        <button className="choice-card choice-card--receive" type="button">
          <span className="choice-card__icon" aria-hidden="true"><Inbox size={24} /></span>
          <span>
            <strong>Я получила</strong>
            <small>Почта неожиданно оказалась в ящике</small>
          </span>
          <ArrowRight aria-hidden="true" size={22} />
        </button>
      </div>
      <p className="quiet-note">Фотографии не нужны — сохраняем только саму историю письма.</p>
    </section>
  );
}

export default function PostboxPrototype() {
  const { isAuthenticated, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>("home");
  const [previewMode, setPreviewMode] = useState<PreviewMode>("default");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => {
    if (typeof window === "undefined") return "system";

    const storedTheme = window.localStorage.getItem("postbox-theme");
    return storedTheme === "light" || storedTheme === "dark" ? storedTheme : "system";
  });

  // Show nothing while checking auth
  if (isAuthenticated === null) {
    return null;
  }

  useEffect(() => {
    const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = () => {
      const resolvedTheme = themeMode === "system" ? (systemTheme.matches ? "dark" : "light") : themeMode;
      document.documentElement.dataset.theme = resolvedTheme;
      document.querySelector('meta[name="theme-color"]')?.setAttribute(
        "content",
        resolvedTheme === "dark" ? "#252B2E" : "#CFCEC6",
      );
    };

    applyTheme();
    systemTheme.addEventListener("change", applyTheme);
    return () => systemTheme.removeEventListener("change", applyTheme);
  }, [themeMode]);

  const chooseTheme = (mode: ThemeMode) => {
    setThemeMode(mode);
    window.localStorage.setItem("postbox-theme", mode);
  };

  return (
    <main className="prototype-stage">
      <div className="app-shell">
        <header className="app-header">
          <div>
            <p className="wordmark">Postbox</p>
            <p className="greeting">Доброе утро</p>
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              className="icon-button"
              type="button"
              aria-label="Открыть состояния прототипа"
              aria-expanded={previewOpen}
              onClick={() => setPreviewOpen(true)}
            >
              <Settings2 aria-hidden="true" size={21} />
            </button>
            <button
              className="icon-button"
              type="button"
              aria-label="Выход"
              onClick={logout}
            >
              <LogOut aria-hidden="true" size={21} />
            </button>
          </div>
        </header>

        <div className="screen-content">
          {activeTab === "home" && <HomeScreen mode={previewMode} onCreate={() => setActiveTab("new")} />}
          {activeTab === "journal" && <JournalScreen />}
          {activeTab === "new" && <NewMailScreen />}
        </div>

        <nav className="bottom-nav" aria-label="Основная навигация">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                className={isActive ? "bottom-nav__item bottom-nav__item--active" : "bottom-nav__item"}
                type="button"
                key={tab.id}
                aria-current={isActive ? "page" : undefined}
                onClick={() => setActiveTab(tab.id)}
              >
                <Icon aria-hidden="true" size={21} strokeWidth={isActive ? 2.2 : 1.8} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {previewOpen && (
          <div className="sheet-backdrop" role="presentation" onMouseDown={() => setPreviewOpen(false)}>
            <section
              className="preview-sheet"
              role="dialog"
              aria-modal="true"
              aria-labelledby="preview-title"
              onMouseDown={(event) => event.stopPropagation()}
            >
              <div className="preview-sheet__header">
                <div>
                  <p className="eyebrow">Прототип</p>
                  <h2 id="preview-title">Настройки</h2>
                </div>
                <button className="icon-button" type="button" aria-label="Закрыть" onClick={() => setPreviewOpen(false)}>
                  <X aria-hidden="true" size={20} />
                </button>
              </div>
              <div className="sheet-section">
                <h3>Тема</h3>
                <div className="theme-options" aria-label="Тема оформления">
                  {themeModes.map((mode) => {
                    const Icon = mode.icon;
                    return (
                      <button
                        type="button"
                        key={mode.id}
                        aria-pressed={themeMode === mode.id}
                        onClick={() => chooseTheme(mode.id)}
                      >
                        <Icon aria-hidden="true" size={19} />
                        <span>{mode.label}</span>
                        {themeMode === mode.id && <Check className="theme-options__check" aria-hidden="true" size={16} />}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="sheet-section">
                <h3>Состояние экрана</h3>
                <div className="preview-options">
                  {previewModes.map((mode) => (
                    <button
                      type="button"
                      key={mode.id}
                      aria-pressed={previewMode === mode.id}
                      onClick={() => {
                        setPreviewMode(mode.id);
                        setActiveTab("home");
                        setPreviewOpen(false);
                      }}
                    >
                      <span>{mode.label}</span>
                      {previewMode === mode.id && <Check aria-hidden="true" size={19} />}
                    </button>
                  ))}
                </div>
              </div>
            </section>
          </div>
        )}
      </div>
    </main>
  );
}
