import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import "./styles.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("GitWarp console root element was not found.");
}

createRoot(root).render(
  <React.StrictMode>
    <App token={document.documentElement.dataset.gitwarpToken ?? ""} />
  </React.StrictMode>,
);
