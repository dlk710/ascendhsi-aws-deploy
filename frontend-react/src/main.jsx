import React from "react";
import ReactDOM from "react-dom/client";
import "./tokens.css";
import "./styles.css";

class RootErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <main style={{ minHeight: "100vh", padding: "32px", background: "#f6f1e7", color: "#17251f" }}>
          <div style={{ maxWidth: "720px", margin: "80px auto", padding: "24px", border: "1px solid #dfd6c7", borderRadius: "8px", background: "#fffdfa" }}>
            <h1 style={{ marginTop: 0 }}>Ascend portal failed to load.</h1>
            <p style={{ lineHeight: 1.5 }}>The React app hit a runtime error before it could render the page.</p>
            <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{String(this.state.error?.stack || this.state.error?.message || this.state.error)}</pre>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}

const root = document.getElementById("root");

function renderImportError(error) {
  if (!root) return;
  root.innerHTML = `
    <main style="min-height:100vh;padding:32px;background:#f6f1e7;color:#17251f;">
      <div style="max-width:720px;margin:80px auto;padding:24px;border:1px solid #dfd6c7;border-radius:8px;background:#fffdfa;">
        <h1 style="margin-top:0;">Ascend portal failed to load.</h1>
        <p style="line-height:1.5;">The app hit an import-time error before React could render the page.</p>
        <pre style="white-space:pre-wrap;overflow-wrap:anywhere;">${String(error?.stack || error?.message || error)}</pre>
      </div>
    </main>
  `;
}

async function start() {
  try {
    const module = await import("./App");
    const App = module.default;
    ReactDOM.createRoot(root).render(
      <React.StrictMode>
        <RootErrorBoundary>
          <App />
        </RootErrorBoundary>
      </React.StrictMode>,
    );
  } catch (error) {
    renderImportError(error);
  }
}

start();
