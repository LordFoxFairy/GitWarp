import { Button } from "@primer/react";
import { CodeIcon, GitBranchIcon, PulseIcon } from "@primer/octicons-react";
import type { RepositoryTab } from "../types";

const TABS: Array<{ id: RepositoryTab; label: string; icon: typeof GitBranchIcon }> = [
  { id: "branches", label: "Branches", icon: GitBranchIcon },
  { id: "metadata", label: "Sandboxes", icon: GitBranchIcon },
  { id: "code", label: "Repository", icon: CodeIcon },
  { id: "health", label: "Diagnostics", icon: PulseIcon },
];

interface RepositoryTabsProps {
  activeTab: RepositoryTab;
  onTabChange: (tab: RepositoryTab) => void;
}

export function RepositoryTabs({ activeTab, onTabChange }: RepositoryTabsProps) {
  return (
    <nav className="repo-tabs" aria-label="Repository sections">
      {TABS.map((tab) => (
        <Button
          key={tab.id}
          variant="invisible"
          className={`repo-tab ${tab.id === activeTab ? "active" : ""}`}
          type="button"
          leadingVisual={tab.icon}
          aria-current={tab.id === activeTab ? "page" : undefined}
          onClick={() => onTabChange(tab.id)}
        >
          {tab.label}
        </Button>
      ))}
    </nav>
  );
}
