import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Order matters: tokens define the variables, global uses them.
import "./styles/tokens.css";
import "./styles/global.css";

import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
