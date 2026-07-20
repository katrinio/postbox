"use client";

import { ArrowDownLeft, ArrowUpRight, CloudOff, Inbox } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type JournalFilter = "all" | "in_transit" | "received";
type MailDirection = "outgoing" | "incoming";
type MailStatus = "in_transit" | "received";

type JournalItem = {
  id: number;
  correspondent: string;
  direction: MailDirection;
  status: MailStatus;
  sent_at: string | null;
  received_at: string | null;
  journal_date: string;
  travel_days: number | null;
  note: string | null;
};

type JournalResponse = {
  items: JournalItem[];
  stats: {
    total: number;
    in_transit: number;
    outgoing: number;
    incoming: number;
  };
  page: number;
  pages: number;
  total: number;
};

const journalFilters: Array<{ id: JournalFilter; label: string }> = [
  { id: "all", label: "Все" },
  { id: "in_transit", label: "В пути" },
  { id: "received", label: "Получено" },
];

// Use relative /api path for same-origin requests in production
// For local development without proxy, set NEXT_PUBLIC_POSTBOX_API_URL to http://localhost:8000
const apiBaseUrl = process.env.NEXT_PUBLIC_POSTBOX_API_URL
  ? process.env.NEXT_PUBLIC_POSTBOX_API_URL.replace(/\/$/, "")
  : "";
const journalDateFormatter = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" });

function formatJournalDate(value: string) {
  return journalDateFormatter.format(new Date(`${value}T00:00:00`));
}

function formatJournalStatus(item: JournalItem) {
  if (item.direction === "incoming") return "Получено";
  if (item.status === "in_transit") {
    return item.travel_days === null ? "В пути" : `В пути · ${item.travel_days} дн.`;
  }
  return item.travel_days === null ? "Дошло" : `Дошло за ${item.travel_days} дн.`;
}

export function JournalScreen() {
  const [filter, setFilter] = useState<JournalFilter>("all");
  const [journal, setJournal] = useState<JournalResponse | null>(null);
  const [error, setError] = useState(false);

  const loadJournal = useCallback(async (signal?: AbortSignal) => {
    try {
      const token = localStorage.getItem("postbox-auth-token");
      const url = apiBaseUrl ? `${apiBaseUrl}/api/journal` : `/api/journal`;
      const response = await fetch(url, {
        signal,
        headers: {
          "Authorization": `Bearer ${token}`,
        },
      });
      if (!response.ok) throw new Error(`Journal request failed: ${response.status}`);
      setJournal((await response.json()) as JournalResponse);
      setError(false);
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError(true);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const request = window.setTimeout(() => void loadJournal(controller.signal), 0);
    return () => {
      window.clearTimeout(request);
      controller.abort();
    };
  }, [loadJournal]);

  const visibleItems = (journal?.items ?? []).filter((item) => {
    if (filter === "in_transit") return item.status === "in_transit";
    if (filter === "received") return item.status === "received";
    return true;
  });

  return (
    <section className="journal-screen" aria-labelledby="journal-title">
      <div className="screen-intro">
        <p className="eyebrow">Все письма</p>
        <h2 id="journal-title">Журнал</h2>
        <p>Хронология отправленных и полученных открыток.</p>
      </div>
      <div className="filter-row" aria-label="Фильтры журнала">
        {journalFilters.map((item) => (
          <button
            className={filter === item.id ? "filter-pill filter-pill--active" : "filter-pill"}
            type="button"
            aria-pressed={filter === item.id}
            key={item.id}
            onClick={() => setFilter(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {!journal && !error && (
        <div className="journal-feedback" role="status">
          <span className="journal-feedback__pulse" aria-hidden="true" />
          Открываем журнал…
        </div>
      )}
      {error && (
        <div className="journal-feedback journal-feedback--error" role="alert">
          <CloudOff aria-hidden="true" size={22} />
          <div>
            <h3>Журнал пока не открылся</h3>
            <p>Проверь, что локальный API запущен, и попробуй ещё раз.</p>
          </div>
          <button type="button" onClick={() => void loadJournal()}>Повторить</button>
        </div>
      )}
      {journal && visibleItems.length === 0 && (
        <div className="journal-feedback">
          <Inbox aria-hidden="true" size={23} />
          {filter === "all" ? "В журнале пока нет писем." : "Здесь пока нет писем."}
        </div>
      )}
      {journal && visibleItems.length > 0 && (
        <div className="journal-list">
          {visibleItems.map((item) => (
            <article className="journal-row" key={item.id}>
              <span className={`journal-row__icon journal-row__icon--${item.direction}`} aria-hidden="true">
                {item.direction === "incoming" ? <ArrowDownLeft size={19} /> : <ArrowUpRight size={19} />}
              </span>
              <div>
                <h3>{item.direction === "incoming" ? `От ${item.correspondent}` : `Для ${item.correspondent}`}</h3>
                <p>{formatJournalStatus(item)}</p>
              </div>
              <time dateTime={item.journal_date}>{formatJournalDate(item.journal_date)}</time>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
