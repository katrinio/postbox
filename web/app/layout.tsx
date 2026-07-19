import type { Metadata, Viewport } from "next";
import "@fontsource-variable/onest";
import "./globals.css";

export const metadata: Metadata = {
  title: "Postbox — тихая переписка",
  description: "Личный журнал бумажных писем и открыток.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#CFCEC6",
};

const themeScript = `
  try {
    const saved = localStorage.getItem("postbox-theme") || "system";
    const dark = saved === "dark" || (saved === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  } catch (_) {
    document.documentElement.dataset.theme = "light";
  }
`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        {children}
      </body>
    </html>
  );
}
