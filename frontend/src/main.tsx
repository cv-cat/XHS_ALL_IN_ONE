import React from "react";
import ReactDOM from "react-dom/client";

import { AppProviders } from "./app/providers";
import { AppRouter } from "./app/router";
import "./global.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AppProviders>
      <AppRouter />
    </AppProviders>
  </React.StrictMode>
);
