import React from "react";
import { createRoot } from "react-dom/client";
import { BaseStyles, ThemeProvider } from "@primer/react";
import { App } from "./app/App";
import "./styles.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("GitWarp console root element was not found.");
}

createRoot(root).render(
  <React.StrictMode>
    <ThemeProvider colorMode="day">
      <BaseStyles>
        <App token={document.documentElement.dataset.gitwarpToken ?? ""} />
      </BaseStyles>
    </ThemeProvider>
  </React.StrictMode>,
);
