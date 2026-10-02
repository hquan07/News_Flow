"use client";

import type { KeyboardEvent, ReactNode } from "react";

export type DashboardNavigationItem = {
  id: string;
  label: string;
  icon: ReactNode;
  featured?: boolean;
};

type Props = {
  activeId: string;
  ariaLabel: string;
  items: DashboardNavigationItem[];
  onChange: (id: string) => void;
};

export default function DashboardSidebar({
  activeId,
  ariaLabel,
  items,
  onChange,
}: Props) {
  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;

    const tabs = Array.from(
      event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'),
    );
    if (!tabs.length) return;

    const currentIndex = Math.max(0, tabs.indexOf(document.activeElement as HTMLButtonElement));
    let nextIndex = currentIndex;

    if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = tabs.length - 1;
    else {
      const offset = event.key === "ArrowDown" || event.key === "ArrowRight" ? 1 : -1;
      nextIndex = (currentIndex + offset + tabs.length) % tabs.length;
    }

    event.preventDefault();
    tabs[nextIndex].focus();
    tabs[nextIndex].click();
  };

  return (
    <aside
      className="dashboard-sidebar"
      role="tablist"
      aria-label={ariaLabel}
      onKeyDown={handleKeyDown}
    >
      {items.map((item) => {
        const active = item.id === activeId;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            tabIndex={active ? 0 : -1}
            aria-selected={active}
            className={`dashboard-sidebar-button ${active ? "active" : ""} ${item.featured ? "featured" : ""}`}
            onClick={() => onChange(item.id)}
          >
            <span className="dashboard-sidebar-icon" aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        );
      })}
    </aside>
  );
}
