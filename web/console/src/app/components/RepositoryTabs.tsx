import type { RepositoryTab } from "../types";

const TABS: Array<{ id: RepositoryTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "worktrees", label: "Worktrees" },
  { id: "agents", label: "Agents" },
  { id: "health", label: "Health" },
];

interface RepositoryTabsProps {
  activeTab: RepositoryTab;
  onTabChange: (tab: RepositoryTab) => void;
}

export function RepositoryTabs({ activeTab, onTabChange }: RepositoryTabsProps) {
  return (
    <nav className="repo-tabs" aria-label="Repository sections">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          className={`repo-tab ${tab.id === activeTab ? "active" : ""}`}
          type="button"
          onClick={() => onTabChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
